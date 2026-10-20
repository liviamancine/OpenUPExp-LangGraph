"""Grafo LangGraph de uma fase, construído a partir do manifesto.

Ver docs/architecture/02-mapeamento-fase-1-visao.md §2.5 e 07-human-in-the-loop.md.
O estado do grafo guarda apenas referências; o conteúdo vive nas tabelas de domínio.

Interações humanas (todas via interrupt(), retomadas com Command(resume=decisão)):
  approval  — gateway de aprovação (hitl_approval)
  consensus — Reach Consensus (hitl_consensus): participantes registram posição; o Engenheiro encerra
  input     — entrada humana antes de uma tarefa (ex.: material de elicitação em 2.2.1)
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from sqlalchemy import select, text

from openupexp.agents import phase1, phase2
from openupexp.agents.gateway import AgentGateway
from openupexp.agents.registry import ARTIFACT_TYPES, PHASE_DOCUMENT, VISION_EDITABLE
from openupexp.agents.runtime import TaskContext, WriteResult, execute_task
from openupexp.baml_client import types as T
from openupexp.db.models import HitlRequest, Run, TaskExecution
from openupexp.db.session import session_scope
from openupexp.domain import artifacts as store
from openupexp.domain.events import audit, emit
from openupexp.exports.documents import export_markdown
from openupexp.exports.vision import _meta, render_vision_markdown
from openupexp.process.manifest import Manifest, Outcome, PhaseSpec, TaskSpec
from openupexp.retrieval.embeddings import Embedder

HANDLERS = {**phase1.HANDLERS, **phase2.HANDLERS}


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


def _human_kind(task: TaskSpec) -> str | None:
    return {"hitl_approval": "approval", "hitl_consensus": "consensus"}.get(task.mechanism)


def build_phase_graph(manifest: Manifest, phase_id: str, gateway: AgentGateway, embedder: Embedder) -> StateGraph:
    phase = manifest.phase(phase_id)
    if not phase.implemented:
        raise NotImplementedError(f"Fase {phase_id} ainda não é executável (ver docs/architecture/03).")
    tasks = phase.tasks()
    order = [sp.id for sp in phase.subprocesses]
    builder = StateGraph(RunState)

    def entry(task: TaskSpec) -> str:
        """Primeiro nó de uma tarefa: a entrada humana, quando a tarefa exige uma."""
        return node_name(task.id) + ("_input" if task.human_input else "")

    def make_task_node(task: TaskSpec):
        sp = phase.subprocess_of(task.id)
        handler = consolidate_vision if task.handler == "consolidate_vision" else HANDLERS[task.id]

        async def node(state: RunState) -> RunState:
            run_id = uuid.UUID(state["run_id"])
            await execute_task(
                run_id=run_id, phase=phase, task=task, handler=handler,
                gateway=gateway, embedder=embedder, iteration=state["iteration"].get(sp.id, 1),
            )
            if (task.handler or "").startswith("consolidate_"):
                async with session_scope() as s:
                    run = await s.get(Run, run_id)
                    doc = await store.current_version(s, run_id, PHASE_DOCUMENT[phase.id])
                    exp = await export_markdown(s, run, doc.id, doc.content["markdown"])
                    await emit(s, run_id, "export_created", export_id=exp.id, formato="md")
            return {}

        return node

    def make_human_node(task: TaskSpec, kind: str, request_task_id: str, name: str,
                        outcomes: dict[str, Outcome], decided_by_role: str | None):
        sp = phase.subprocess_of(task.id)

        async def human(state: RunState) -> RunState:
            run_id = uuid.UUID(state["run_id"])
            iteration = state["iteration"].get(sp.id, 1)
            key = f"{run_id}:{request_task_id}:{iteration}"
            policy = {"decided_by_role": decided_by_role}
            due_at = None
            if task.consensus:
                policy.update(task.consensus.model_dump())
                if task.consensus.due_days:
                    due_at = datetime.now(timezone.utc) + timedelta(days=task.consensus.due_days)
            payload = {"reviews": task.reviews, "name": name, "phase": phase.id,
                       "outcomes": {k: o.model_dump() for k, o in outcomes.items()}}
            if task.human_input:
                payload["input_kind"] = task.human_input.kind
            async with session_scope() as s:
                # UPSERT idempotente: a retomada reexecuta este nó desde o início
                inserted = await s.execute(
                    text(
                        """
                        INSERT INTO hitl_request (id, run_id, task_id, bpmn_element_id, kind, idempotency_key,
                                                  payload, policy, status, round, iteracao, due_at, created_at)
                        VALUES (:id, :run, :task, :el, :kind, :key, CAST(:payload AS jsonb),
                                CAST(:policy AS jsonb), 'open', 1, :it, :due, now())
                        ON CONFLICT (idempotency_key) DO NOTHING
                        RETURNING id
                        """
                    ),
                    {
                        "id": uuid.uuid4(), "run": run_id, "task": request_task_id, "el": task.bpmn_element,
                        "kind": kind, "key": key, "it": iteration, "due": due_at,
                        "payload": _json(payload), "policy": _json(policy),
                    },
                )
                created = inserted.first() is not None
                req = await s.scalar(select(HitlRequest).where(HitlRequest.idempotency_key == key))
                if created:
                    if kind != "input":
                        cur = await store.current_versions(s, run_id)
                        phase_types = set(phase.writers())
                        await store.set_status(s, [v.id for t, v in cur.items()
                                                   if t in phase_types and v.status == "draft"], "in_review")
                    s.add(TaskExecution(run_id=run_id, task_id=request_task_id, bpmn_element_id=task.bpmn_element,
                                        iteracao=iteration, status="waiting_human",
                                        meta={"hitl_request_id": str(req.id), "kind": kind}))
                    run = await s.get(Run, run_id)
                    run.status = "waiting_human"
                    run.current_task = request_task_id
                    await emit(s, run_id, "hitl_requested", task_id=request_task_id, hitl_request_id=req.id,
                               iteracao=iteration, kind=kind)
                req_id = str(req.id)
            decision = interrupt({"hitl_request_id": req_id, "task_id": request_task_id})
            return {"decision": decision}

        return human

    def make_apply_node(request_task_id: str, outcomes: dict[str, Outcome]):
        async def apply_decision(state: RunState) -> RunState:
            run_id = uuid.UUID(state["run_id"])
            decision = state["decision"] or {}
            outcome = outcomes[decision["decision"]]
            iteration = dict(state["iteration"])
            async with session_scope() as s:
                te = await s.scalar(
                    select(TaskExecution)
                    .where(TaskExecution.run_id == run_id, TaskExecution.task_id == request_task_id,
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
                await emit(s, run_id, "decision_applied", task_id=request_task_id,
                           decision=decision.get("decision"), next=outcome.next)
                await audit(s, "system", None, "apply_decision", "run", str(run_id),
                            decision=decision, gate=request_task_id, iteration=iteration)
            return {"iteration": iteration, "decision": decision}

        return apply_decision

    def target(next_id: str) -> str:
        if next_id in order:
            return entry(phase.subprocess(next_id).tasks[0])
        return entry(next(t for t in tasks if t.id == next_id))

    def add_human(task: TaskSpec, kind: str, request_task_id: str, name: str, outcomes: dict[str, Outcome],
                  decided_by_role: str | None, base: str) -> None:
        builder.add_node(base, make_human_node(task, kind, request_task_id, name, outcomes, decided_by_role))
        builder.add_node(base + "_apply", make_apply_node(request_task_id, outcomes))
        builder.add_edge(base, base + "_apply")
        targets = {d: (node_name(o.next) if o.next == task.id else target(o.next)) for d, o in outcomes.items()}

        def route(state: RunState, _targets=targets) -> str:
            return _targets[(state.get("decision") or {})["decision"]]

        builder.add_conditional_edges(base + "_apply", route, list(set(targets.values())))

    # nós
    for t in tasks:
        if t.human_input:
            add_human(t, "input", f"{t.id}.in", t.human_input.name, t.human_input.outcomes,
                      t.human_input.decided_by_role, node_name(t.id) + "_input")
        kind = _human_kind(t)
        if kind:
            add_human(t, kind, t.id, t.name, t.outcomes, t.decided_by_role, node_name(t.id))
        else:
            builder.add_node(node_name(t.id), make_task_node(t))

    # arestas sequenciais segundo a ordem do manifesto (a saída das interações humanas é condicional)
    builder.add_edge(START, entry(tasks[0]))
    for prev, nxt in zip(tasks, tasks[1:]):
        if _human_kind(prev) is None:
            builder.add_edge(node_name(prev.id), entry(nxt))
    builder.add_edge(node_name(tasks[-1].id), END)
    return builder


def _json(value) -> str:
    import json

    return json.dumps(value, ensure_ascii=False)
