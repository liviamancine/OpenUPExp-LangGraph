"""Grafo LangGraph da Fase 1, construído a partir do manifesto.

Ver docs/architecture/02-mapeamento-fase-1-visao.md §2.5 e 07-human-in-the-loop.md.
O estado do grafo guarda apenas referências; o conteúdo vive nas tabelas de domínio.
"""

import uuid
from datetime import datetime, timezone
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from sqlalchemy import select, text

from openupexp.agents.gateway import AgentGateway
from openupexp.agents.phase1 import HANDLERS
from openupexp.agents.registry import ARTIFACT_TYPES, VISION_EDITABLE
from openupexp.agents.runtime import TaskContext, WriteResult, execute_task
from openupexp.baml_client import types as T
from openupexp.db.models import HitlRequest, Run, TaskExecution
from openupexp.db.session import session_scope
from openupexp.domain import artifacts as store
from openupexp.domain.events import audit, emit
from openupexp.exports.vision import _meta, export_markdown, render_vision_markdown
from openupexp.process.manifest import Manifest, PhaseSpec, TaskSpec
from openupexp.retrieval.embeddings import Embedder


class RunState(TypedDict, total=False):
    run_id: str
    iteration: dict[str, int]
    decision: dict | None


def node_name(task_id: str) -> str:
    return "t_" + task_id.replace(".", "_")


def initial_state(run_id: uuid.UUID, phase: PhaseSpec) -> RunState:
    return {"run_id": str(run_id), "iteration": {sp.id: 1 for sp in phase.subprocesses}, "decision": None}


# ---------------------------------------------------------------------------
# 1.3.2 Consolidação (handler executado via execute_task)
# ---------------------------------------------------------------------------


async def consolidate_vision(ctx: TaskContext) -> list[WriteResult]:
    cur = await store.current_versions(ctx.session, ctx.run.id)
    phase_types = set(ctx.phase.writers())
    await store.set_status(ctx.session, [v.id for t, v in cur.items() if t in phase_types], "approved")

    contents = {t: v.content for t, v in cur.items()}
    meta = await _meta(ctx.session, ctx.run, "aprovado", f"1.{ctx.iteration - 1}")
    markdown = render_vision_markdown(contents, meta)

    required_ids = []
    for atype in VISION_EDITABLE:
        at = ARTIFACT_TYPES[atype]
        if at.list_field:
            required_ids += [i["id"] for i in (contents.get(atype) or {}).get(at.list_field, []) if i.get("id")]
    digest = await ctx.call("BuildPhaseDigest", T.DigestInput(documento=markdown, ids_obrigatorios=required_ids))
    mentioned = set(digest.ids_cobertos) | {i for i in required_ids if i in digest.resumo}
    digest_content = digest.model_dump(mode="json")
    digest_content["ids_faltantes"] = sorted(set(required_ids) - mentioned)

    return [
        WriteResult("vision.draft", {"markdown": markdown,
                                     "versoes": {t: str(v.id) for t, v in cur.items() if t in phase_types}},
                    origin="consolidation", status="approved"),
        WriteResult("digest.vision", digest_content, status="approved"),
    ]


# ---------------------------------------------------------------------------
# Construção do grafo
# ---------------------------------------------------------------------------


def build_phase_graph(manifest: Manifest, phase_id: str, gateway: AgentGateway, embedder: Embedder) -> StateGraph:
    phase = manifest.phase(phase_id)
    if not phase.implemented:
        raise NotImplementedError(f"Fase {phase_id} ainda não é executável (ver docs/architecture/03).")
    tasks = phase.tasks()
    builder = StateGraph(RunState)

    def make_task_node(task: TaskSpec):
        sp = phase.subprocess_of(task.id)
        handler = consolidate_vision if task.handler == "consolidate_vision" else HANDLERS[task.id]

        async def node(state: RunState) -> RunState:
            run_id = uuid.UUID(state["run_id"])
            await execute_task(
                run_id=run_id, phase=phase, task=task, handler=handler,
                gateway=gateway, embedder=embedder, iteration=state["iteration"].get(sp.id, 1),
            )
            if task.handler == "consolidate_vision":
                async with session_scope() as s:
                    run = await s.get(Run, run_id)
                    draft = await store.current_version(s, run_id, "vision.draft")
                    exp = await export_markdown(s, run, draft.id, draft.content["markdown"])
                    await emit(s, run_id, "export_created", export_id=exp.id, formato="md")
            return {}

        return node

    def make_gate_node(task: TaskSpec):
        sp = phase.subprocess_of(task.id)

        async def gate(state: RunState) -> RunState:
            run_id = uuid.UUID(state["run_id"])
            iteration = state["iteration"].get(sp.id, 1)
            key = f"{run_id}:{task.id}:{iteration}"
            async with session_scope() as s:
                # UPSERT idempotente: a retomada reexecuta este nó desde o início
                inserted = await s.execute(
                    text(
                        """
                        INSERT INTO hitl_request (id, run_id, task_id, bpmn_element_id, kind, idempotency_key,
                                                  payload, policy, status, round, iteracao, created_at)
                        VALUES (:id, :run, :task, :el, 'approval', :key, CAST(:payload AS jsonb),
                                CAST(:policy AS jsonb), 'open', 1, :it, now())
                        ON CONFLICT (idempotency_key) DO NOTHING
                        RETURNING id
                        """
                    ),
                    {
                        "id": uuid.uuid4(), "run": run_id, "task": task.id, "el": task.bpmn_element,
                        "key": key, "it": iteration,
                        "payload": _json({"reviews": task.reviews, "outcomes": {
                            k: o.model_dump() for k, o in task.outcomes.items()}, "name": task.name}),
                        "policy": _json({"decided_by_role": task.decided_by_role}),
                    },
                )
                created = inserted.first() is not None
                req = await s.scalar(select(HitlRequest).where(HitlRequest.idempotency_key == key))
                if created:
                    cur = await store.current_versions(s, run_id)
                    phase_types = set(phase.writers())
                    await store.set_status(s, [v.id for t, v in cur.items()
                                               if t in phase_types and v.status == "draft"], "in_review")
                    s.add(TaskExecution(run_id=run_id, task_id=task.id, bpmn_element_id=task.bpmn_element,
                                        iteracao=iteration, status="waiting_human",
                                        meta={"hitl_request_id": str(req.id)}))
                    run = await s.get(Run, run_id)
                    run.status = "waiting_human"
                    run.current_task = task.id
                    await emit(s, run_id, "hitl_requested", task_id=task.id, hitl_request_id=req.id,
                               iteracao=iteration)
                req_id = str(req.id)
            decision = interrupt({"hitl_request_id": req_id, "task_id": task.id})
            return {"decision": decision}

        return gate

    def make_apply_node(task: TaskSpec):
        order = [sp.id for sp in phase.subprocesses]

        async def apply_decision(state: RunState) -> RunState:
            run_id = uuid.UUID(state["run_id"])
            decision = state["decision"] or {}
            outcome = task.outcomes[decision["decision"]]
            iteration = dict(state["iteration"])
            async with session_scope() as s:
                te = await s.scalar(
                    select(TaskExecution)
                    .where(TaskExecution.run_id == run_id, TaskExecution.task_id == task.id,
                           TaskExecution.status == "waiting_human")
                    .order_by(TaskExecution.inicio.desc()).limit(1)
                )
                if te is not None:
                    te.status = "completed"
                    te.fim = datetime.now(timezone.utc)
                    te.meta = dict(te.meta or {}, decision=decision.get("decision"))
                run = await s.get(Run, run_id)
                run.status = "running"
                if outcome.next in order:  # revisit: volta a um subprocesso
                    redo = order[order.index(outcome.next):]
                    redo_types = {w.artifact for sp_id in redo
                                  for t in phase.subprocess(sp_id).tasks for w in t.writes}
                    cur = await store.current_versions(s, run_id)
                    phase_types = set(phase.writers())
                    await store.set_status(s, [v.id for t, v in cur.items() if t in redo_types], "stale")
                    await store.set_status(s, [v.id for t, v in cur.items()
                                               if t in phase_types - redo_types and v.status == "in_review"],
                                           "draft")
                    for sp_id in redo:
                        iteration[sp_id] = iteration.get(sp_id, 1) + 1
                await emit(s, run_id, "decision_applied", task_id=task.id, decision=decision.get("decision"),
                           next=outcome.next)
                await audit(s, "system", None, "apply_decision", "run", str(run_id),
                            decision=decision, gate=task.id, iteration=iteration)
            return {"iteration": iteration, "decision": decision}

        return apply_decision

    # nós
    gate_tasks = [t for t in tasks if t.mechanism == "hitl_approval"]
    for t in tasks:
        if t.mechanism == "hitl_approval":
            builder.add_node(node_name(t.id), make_gate_node(t))
            builder.add_node(node_name(t.id) + "_apply", make_apply_node(t))
        elif t.mechanism == "hitl_consensus":
            raise NotImplementedError("consenso previsto para o marco M5")
        else:
            builder.add_node(node_name(t.id), make_task_node(t))

    # arestas sequenciais segundo a ordem do manifesto
    builder.add_edge(START, node_name(tasks[0].id))
    for prev, nxt in zip(tasks, tasks[1:]):
        src = node_name(prev.id) + ("_apply" if prev.mechanism == "hitl_approval" else "")
        if prev.mechanism == "hitl_approval":
            builder.add_edge(node_name(prev.id), src)
            continue  # a saída do gateway é condicional (abaixo)
        builder.add_edge(src, node_name(nxt.id))
    last = tasks[-1]
    builder.add_edge(node_name(last.id), END)

    for g in gate_tasks:
        targets = {}
        for decision, outcome in g.outcomes.items():
            if outcome.next in {sp.id for sp in phase.subprocesses}:
                targets[decision] = node_name(phase.subprocess(outcome.next).tasks[0].id)
            else:
                targets[decision] = node_name(outcome.next)

        def route(state: RunState, _targets=targets) -> str:
            return _targets[(state.get("decision") or {})["decision"]]

        builder.add_conditional_edges(node_name(g.id) + "_apply", route, list(set(targets.values())))
    return builder


def _json(value) -> str:
    import json

    return json.dumps(value, ensure_ascii=False)
