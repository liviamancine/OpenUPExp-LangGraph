"""Execução de uma tarefa do manifesto: contexto → handler → versões → métricas."""

import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from openupexp.agents.gateway import AgentGateway
from openupexp.agents.registry import ARTIFACT_TYPES
from openupexp.context.builder import ContextPackage, build_context
from openupexp.db.models import ContextPackageRow, Evidence, Run, TaskExecution
from openupexp.db.session import session_scope
from openupexp.domain import artifacts as store
from openupexp.domain.events import emit
from openupexp.domain.ids import assign_keys
from openupexp.process.manifest import PhaseSpec, TaskSpec
from openupexp.retrieval.embeddings import Embedder


class CoverageError(Exception):
    pass


@dataclass
class EvidenceDraft:
    item_key: str
    chunk_ref: str
    chunk_id: uuid.UUID | None
    citacao: str
    kind: str
    verification: str


@dataclass
class WriteResult:
    artifact_type: str
    content: dict
    origin: str = "agent"
    raw_items: list[dict] | None = None  # itens ainda sem ID definitivo
    evidences: list[EvidenceDraft] = field(default_factory=list)
    # evidências por posição do item em raw_items, associadas após a atribuição de chaves
    item_evidences: list[tuple[int, dict]] = field(default_factory=list)
    # links (from, to, tipo); "{self}" no from é substituído pela chave atribuída
    links: list[tuple[str, str, str]] = field(default_factory=list)
    status: str = "draft"


@dataclass
class TaskContext:
    session: AsyncSession
    run: Run
    phase: PhaseSpec
    task: TaskSpec
    package: ContextPackage
    gateway: AgentGateway
    embedder: Embedder
    execution: TaskExecution
    iteration: int

    async def call(self, function: str, entrada) -> object:
        return await self.gateway.call(
            function, entrada, self.package.extras(), run_id=self.run.id,
            task_execution_id=self.execution.id,
        )


Handler = Callable[[TaskContext], Awaitable[list[WriteResult]]]


def _links_from_item(item: dict) -> list[tuple[str, str, str]]:
    """Rastreabilidade derivada dos campos de referência dos contratos BAML."""
    links = []
    for ref in item.get("origem") or []:
        r = (ref or {}).get("referencia") or ""
        if "-" in r and len(r) <= 40 and r.split("-")[0].isupper():
            links.append((item["id"], r, "derives_from"))
    for field_name, kind in [("stakeholder_id", "relates_to"), ("termo_origem_id", "derives_from")]:
        if item.get(field_name):
            links.append((item["id"], item[field_name], kind))
    for field_name, kind in [("stakeholder_ids", "relates_to"), ("solicitacao_ids", "derives_from"),
                             ("need_ids", "relates_to")]:
        for target in item.get(field_name) or []:
            if target:
                links.append((item["id"], target, kind))
    return links


async def persist_writes(ctx: TaskContext, results: list[WriteResult]) -> list[uuid.UUID]:
    s, run = ctx.session, ctx.run
    deps = ctx.package.dependencies()
    created = []
    for res in results:
        at = ARTIFACT_TYPES[res.artifact_type]
        content = dict(res.content)
        items: list[tuple[str, dict]] = []
        if at.list_field and res.raw_items is not None:
            prev = ctx.package.previous(res.artifact_type) or {}
            existing = {i["id"]: i for i in prev.get(at.list_field, []) if i.get("id")}
            items = assign_keys(at.prefix, res.raw_items, existing, at.text_of)
            content[at.list_field] = [i for _, i in items]
        version = await store.save_version(
            s, project_id=run.project_id, run_id=run.id, phase=ctx.phase.id,
            artifact_type=res.artifact_type, content=content, origin=res.origin, items=items,
            schema_name=at.schema.__name__ if at.schema else None,
            schema_sha=store.schema_hash(at.schema), depends_on=deps,
            produced_by_task=ctx.execution.id, status=res.status, iteracao=ctx.iteration,
        )
        links = []
        for _, item in items:
            links += _links_from_item(item)
        links += res.links
        await store.add_trace_links(s, run.id, links, version.id)
        evidences = list(res.evidences)
        for idx, ev in res.item_evidences:
            if idx < len(items):
                evidences.append(EvidenceDraft(
                    item_key=items[idx][0], chunk_ref=ev.get("chunk_ref") or "",
                    chunk_id=ev.get("chunk_id"), citacao=ev.get("citacao", ""),
                    kind=str(ev.get("tipo")), verification=ev["verificacao"],
                ))
        for ev in evidences:
            s.add(Evidence(
                artifact_version_id=version.id, item_key=ev.item_key, chunk_id=ev.chunk_id,
                chunk_ref=ev.chunk_ref, citacao=ev.citacao, kind=ev.kind, verification=ev.verification,
            ))
        await s.flush()
        created.append(version.id)
        await emit(s, run.id, "artifact_version", artifact=res.artifact_type, version_id=version.id,
                   version_no=version.version_no, task_id=ctx.task.id)
    return created


async def execute_task(
    *,
    run_id: uuid.UUID,
    phase: PhaseSpec,
    task: TaskSpec,
    handler: Handler,
    gateway: AgentGateway,
    embedder: Embedder,
    iteration: int,
) -> None:
    async with session_scope() as s:
        run = await s.get(Run, run_id)
        previous_attempts = await s.scalar(
            TaskExecution.__table__.select()
            .with_only_columns(TaskExecution.id)
            .where(TaskExecution.run_id == run_id, TaskExecution.task_id == task.id,
                   TaskExecution.iteracao == iteration)
            .limit(1)
        )
        te = TaskExecution(
            run_id=run_id, task_id=task.id, bpmn_element_id=task.bpmn_element or task.bpmn_anchor,
            iteracao=iteration, tentativa=2 if previous_attempts else 1, status="running",
        )
        s.add(te)
        run.status = "running"
        run.current_task = task.id
        await s.flush()
        te_id = te.id
        await emit(s, run_id, "task_started", task_id=task.id, iteracao=iteration, name=task.name)

    try:
        async with session_scope() as s:
            run = await s.get(Run, run_id)
            te = await s.get(TaskExecution, te_id)
            package = await build_context(s, run, task)
            ctx = TaskContext(s, run, phase, task, package, gateway, embedder, te, iteration)
            results = await handler(ctx)
            if task.completeness != "none" and package.coverage.output_missing_ids:
                raise CoverageError(
                    f"tarefa {task.id}: itens sem saída após nova tentativa: "
                    f"{package.coverage.output_missing_ids}"
                )
            versions = await persist_writes(ctx, results)
            s.add(ContextPackageRow(
                task_execution_id=te_id, strategy=package.strategy, items=package.canonical(),
                coverage=package.coverage.model_dump(), token_estimate=package.token_estimate(),
                sha256=package.sha256(),
            ))
            te.status = "completed"
            te.fim = datetime.now(timezone.utc)
            te.meta = {"versions": [str(v) for v in versions]}
            await emit(s, run_id, "task_completed", task_id=task.id, iteracao=iteration)
    except Exception as exc:
        async with session_scope() as s:
            te = await s.get(TaskExecution, te_id)
            te.status = "failed"
            te.fim = datetime.now(timezone.utc)
            te.erro = "".join(traceback.format_exception_only(exc)).strip()[:4000]
            run = await s.get(Run, run_id)
            run.status = "failed"
            run.error = te.erro
            await emit(s, run_id, "task_failed", task_id=task.id, erro=te.erro)
        raise
