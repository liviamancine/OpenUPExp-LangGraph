import asyncio
import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from openupexp.agents.registry import PHASE_DOCUMENT
from openupexp.api.auth import current_user, require_member
from openupexp.api.deps import get_session
from openupexp.api.events import broadcaster
from openupexp.api.routers.projects import run_summary
from openupexp.db.models import (
    AppUser,
    ContextPackageRow,
    Export,
    HitlRequest,
    LlmCall,
    Run,
    RunEvent,
    TaskExecution,
)
from openupexp.db.session import sessionmaker
from openupexp.domain import artifacts as store
from openupexp.domain import services
from openupexp.exports.documents import render_current_document

router = APIRouter(prefix="/api")


class RunIn(BaseModel):
    phase: str = "1"
    context_strategy: str = "D"
    agent_gateway: str | None = None
    model_profile: dict | None = None
    base_run_id: uuid.UUID | None = None


async def _run_for(session: AsyncSession, run_id: uuid.UUID, user: AppUser, roles=None) -> Run:
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(404, "Execução inexistente")
    await require_member(session, run.project_id, user, roles)
    return run


@router.post("/projects/{project_id}/runs")
async def start_run(project_id: uuid.UUID, body: RunIn, user: AppUser = Depends(current_user),
                    session: AsyncSession = Depends(get_session)):
    await require_member(session, project_id, user, ("requirements_engineer", "researcher"))
    run = await services.start_run(session, project_id, body.phase, body.context_strategy, body.agent_gateway,
                                   body.model_profile, user.id, base_run_id=body.base_run_id)
    return run_summary(run)


@router.get("/runs/{run_id}")
async def get_run(run_id: uuid.UUID, user: AppUser = Depends(current_user), session: AsyncSession = Depends(get_session)):
    run = await _run_for(session, run_id, user)
    pending = await session.scalar(select(HitlRequest).where(HitlRequest.run_id == run_id,
                                                             HitlRequest.status == "open"))
    return {**run_summary(run), "project_id": str(run.project_id),
            "corpus_version_id": str(run.corpus_version_id) if run.corpus_version_id else None,
            "baml_src_sha": run.baml_src_sha,
            "pending_hitl": str(pending.id) if pending else None,
            "metricas": await services.run_counts(session, run_id)}


@router.post("/runs/{run_id}/retry")
async def retry(run_id: uuid.UUID, user: AppUser = Depends(current_user), session: AsyncSession = Depends(get_session)):
    run = await _run_for(session, run_id, user, ("requirements_engineer",))
    await services.retry_run(session, run, user.id)
    return run_summary(run)


@router.get("/runs/{run_id}/tasks")
async def tasks(run_id: uuid.UUID, user: AppUser = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await _run_for(session, run_id, user)
    rows = (await session.scalars(select(TaskExecution).where(TaskExecution.run_id == run_id)
                                  .order_by(TaskExecution.inicio))).all()
    tokens = dict((await session.execute(
        select(LlmCall.task_execution_id, func.sum(func.coalesce(LlmCall.input_tokens, 0)
                                                   + func.coalesce(LlmCall.output_tokens, 0)))
        .where(LlmCall.run_id == run_id).group_by(LlmCall.task_execution_id))).all())
    return [{"id": str(t.id), "task_id": t.task_id, "bpmn_element_id": t.bpmn_element_id, "iteracao": t.iteracao,
             "tentativa": t.tentativa, "status": t.status, "inicio": t.inicio.isoformat(),
             "fim": t.fim.isoformat() if t.fim else None, "erro": t.erro, "meta": t.meta,
             "tokens": int(tokens.get(t.id) or 0)} for t in rows]


@router.get("/task-executions/{te_id}")
async def task_detail(te_id: uuid.UUID, user: AppUser = Depends(current_user),
                      session: AsyncSession = Depends(get_session)):
    te = await session.get(TaskExecution, te_id)
    if te is None:
        raise HTTPException(404, "Execução de tarefa inexistente")
    await _run_for(session, te.run_id, user)
    pkg = await session.scalar(select(ContextPackageRow).where(ContextPackageRow.task_execution_id == te_id))
    calls = (await session.scalars(select(LlmCall).where(LlmCall.task_execution_id == te_id)
                                   .order_by(LlmCall.created_at))).all()
    return {
        "id": str(te.id), "task_id": te.task_id, "status": te.status, "iteracao": te.iteracao, "erro": te.erro,
        "meta": te.meta,
        "context_package": None if pkg is None else {
            "strategy": pkg.strategy, "items": pkg.items, "coverage": pkg.coverage,
            "token_estimate": pkg.token_estimate, "sha256": pkg.sha256},
        "llm_calls": [{"id": str(c.id), "function": c.baml_function, "client": c.client_name,
                       "provider": c.provider, "model": c.model, "input_tokens": c.input_tokens,
                       "output_tokens": c.output_tokens, "latency_ms": c.latency_ms,
                       "custo_usd": float(c.custo_usd) if c.custo_usd is not None else None,
                       "status": c.status, "fallback_chain": c.fallback_chain, "error": c.error,
                       "prompt_sha256": c.prompt_sha256} for c in calls],
    }


@router.get("/runs/{run_id}/events")
async def events(run_id: uuid.UUID, request: Request, user: AppUser = Depends(current_user),
                 session: AsyncSession = Depends(get_session)):
    await _run_for(session, run_id, user)
    last_id = int(request.headers.get("last-event-id") or request.query_params.get("after") or 0)
    key = str(run_id)

    async def stream():
        nonlocal last_id
        waiter = broadcaster.subscribe(key)
        try:
            while not await request.is_disconnected():
                async with sessionmaker()() as s:
                    rows = (await s.scalars(select(RunEvent).where(RunEvent.run_id == run_id, RunEvent.id > last_id)
                                            .order_by(RunEvent.id).limit(200))).all()
                for ev in rows:
                    last_id = ev.id
                    yield {"id": str(ev.id), "event": ev.tipo,
                           "data": json.dumps({"tipo": ev.tipo, "dados": ev.dados,
                                               "at": ev.created_at.isoformat()}, ensure_ascii=False)}
                waiter.clear()
                try:
                    await asyncio.wait_for(waiter.wait(), timeout=5)  # polling de segurança
                except asyncio.TimeoutError:
                    pass
        finally:
            broadcaster.unsubscribe(key, waiter)

    return EventSourceResponse(stream(), ping=15)


@router.get("/runs/{run_id}/document", response_class=PlainTextResponse)
async def document(run_id: uuid.UUID, user: AppUser = Depends(current_user),
                   session: AsyncSession = Depends(get_session)):
    run = await _run_for(session, run_id, user)
    draft = await store.current_version(session, run.id, PHASE_DOCUMENT.get(run.phase, "vision.draft"))
    if draft is not None and draft.status == "approved":
        return draft.content.get("markdown", "")
    return await render_current_document(session, run)


@router.get("/runs/{run_id}/exports")
async def exports(run_id: uuid.UUID, user: AppUser = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await _run_for(session, run_id, user)
    rows = (await session.scalars(select(Export).where(Export.run_id == run_id).order_by(Export.created_at))).all()
    return [{"id": str(e.id), "formato": e.formato, "template_version": e.template_version, "sha256": e.sha256,
             "artifact_version_id": str(e.artifact_version_id), "created_at": e.created_at.isoformat()} for e in rows]


@router.get("/exports/{export_id}/download")
async def download(export_id: uuid.UUID, user: AppUser = Depends(current_user),
                   session: AsyncSession = Depends(get_session)):
    exp = await session.get(Export, export_id)
    if exp is None:
        raise HTTPException(404, "Exportação inexistente")
    await _run_for(session, exp.run_id, user)
    return FileResponse(exp.storage_path, media_type="text/markdown", filename=Path(exp.storage_path).name)


@router.get("/runs/{run_id}/metrics")
async def metrics(run_id: uuid.UUID, user: AppUser = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await _run_for(session, run_id, user)
    rows = (await session.execute(
        select(TaskExecution.task_id, TaskExecution.iteracao, LlmCall.baml_function,
               func.count(LlmCall.id), func.sum(LlmCall.input_tokens), func.sum(LlmCall.output_tokens),
               func.sum(LlmCall.latency_ms), func.sum(LlmCall.custo_usd))
        .join(TaskExecution, TaskExecution.id == LlmCall.task_execution_id)
        .where(LlmCall.run_id == run_id)
        .group_by(TaskExecution.task_id, TaskExecution.iteracao, LlmCall.baml_function)
        .order_by(TaskExecution.task_id, TaskExecution.iteracao))).all()
    return {"total": await services.run_counts(session, run_id), "por_tarefa": [
        {"task_id": t, "iteracao": i, "function": f, "chamadas": n, "input_tokens": int(a or 0),
         "output_tokens": int(b or 0), "latency_ms": int(lat or 0), "custo_usd": float(c) if c is not None else None}
        for t, i, f, n, a, b, lat, c in rows]}
