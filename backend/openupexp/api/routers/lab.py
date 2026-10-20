"""Laboratório de modelos (cap. 14 §14.5)."""

import csv
import io
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openupexp.agents.registry import ARTIFACT_TYPES
from openupexp.api.auth import current_user, require_member
from openupexp.api.deps import get_session
from openupexp.db.models import (
    AppUser,
    LabComparison,
    LabGold,
    LabRating,
    LabTrial,
    Project,
    ProjectMember,
    Run,
    TaskExecution,
)
from openupexp.lab import gold as goldmod
from openupexp.lab import service
from openupexp.process.manifest import get_manifest

router = APIRouter(prefix="/api/lab")
EDITORS = ("requirements_engineer", "researcher")


class ComparisonIn(BaseModel):
    task_execution_id: uuid.UUID
    profiles: list[str]
    notes: str | None = None
    strategies: list[str] | None = None
    repeticoes: int = 1


class GoldIn(BaseModel):
    project_id: uuid.UUID
    task_id: str
    artifact_type: str
    itens: list[str]
    autoria: str | None = None


class RatingIn(BaseModel):
    nota: int
    comentario: str | None = None


def _err(exc: service.LabError) -> HTTPException:
    return HTTPException(exc.status, str(exc))


async def _projects_of(session: AsyncSession, user: AppUser) -> list[uuid.UUID] | None:
    if user.papel_global == "admin":
        return None
    return list((await session.scalars(select(ProjectMember.project_id).where(ProjectMember.user_id == user.id))).all())


@router.get("/sources/{run_id}")
async def sources(run_id: uuid.UUID, user: AppUser = Depends(current_user), session: AsyncSession = Depends(get_session)):
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(404, "Execução inexistente")
    await require_member(session, run.project_id, user)
    return await service.eligible_sources(session, run_id)


@router.post("/comparisons")
async def create(body: ComparisonIn, user: AppUser = Depends(current_user), session: AsyncSession = Depends(get_session)):
    te = await session.get(TaskExecution, body.task_execution_id)
    if te is None:
        raise HTTPException(404, "Tarefa inexistente")
    run = await session.get(Run, te.run_id)
    await require_member(session, run.project_id, user, EDITORS)
    try:
        comp = await service.create_comparison(session, body.task_execution_id, body.profiles, body.notes, user.id,
                                               body.strategies, body.repeticoes)
    except service.LabError as exc:
        raise _err(exc) from exc
    return {"id": str(comp.id)}


@router.get("/comparisons")
async def list_comparisons(user: AppUser = Depends(current_user), session: AsyncSession = Depends(get_session)):
    allowed = await _projects_of(session, user)
    q = select(LabComparison, Project).join(Project, Project.id == LabComparison.project_id) \
        .order_by(LabComparison.created_at.desc()).limit(100)
    if allowed is not None:
        q = q.where(LabComparison.project_id.in_(allowed))
    out = []
    for comp, project in (await session.execute(q)).all():
        trials = (await session.scalars(select(LabTrial).where(LabTrial.comparison_id == comp.id)
                                        .order_by(LabTrial.position))).all()
        run = await session.get(Run, comp.run_id)
        out.append({"id": str(comp.id), "projeto": project.nome, "task_id": comp.task_id, "fase": run.phase,
                    "nome": _task_name(run, comp.task_id), "created_at": comp.created_at.isoformat(),
                    "modelos": [t.profile_snapshot.get("profile_nome") for t in trials],
                    "situacao": [t.status for t in trials]})
    return out


def _task_name(run: Run, task_id: str) -> str:
    try:
        return get_manifest(run.manifest_version).task(task_id).name
    except KeyError:
        return task_id


@router.get("/comparisons/{comparison_id}")
async def detail(comparison_id: uuid.UUID, user: AppUser = Depends(current_user),
                 session: AsyncSession = Depends(get_session)):
    comp = await session.get(LabComparison, comparison_id)
    if comp is None:
        raise HTTPException(404, "Comparação inexistente")
    role = await require_member(session, comp.project_id, user)
    run = await session.get(Run, comp.run_id)
    project = await session.get(Project, comp.project_id)
    trials = (await session.scalars(select(LabTrial).where(LabTrial.comparison_id == comp.id)
                                    .order_by(LabTrial.position))).all()
    ratings = (await session.scalars(select(LabRating).where(LabRating.trial_id.in_([t.id for t in trials])))).all() \
        if trials else []
    spec = get_manifest(run.manifest_version).task(comp.task_id)
    golds = (await session.scalars(select(LabGold).where(LabGold.project_id == comp.project_id,
                                                         LabGold.task_id == comp.task_id))).all()
    original = await service.reference(session, comp)
    list_artifacts = [o["artifact"] for o in original["output"]
                      if ARTIFACT_TYPES.get(o["artifact"]) and ARTIFACT_TYPES[o["artifact"]].list_field]
    gold = next((g for g in golds if g.itens), None)
    original["gabarito"] = goldmod.score_output(original["output"], gold)
    trials_out = [{
        "id": str(t.id), "modelo": t.profile_snapshot.get("profile_nome"), "local": t.profile_snapshot.get("local"),
        "provider": t.profile_snapshot.get("provider"), "model": t.profile_snapshot.get("model"),
        "model_digest": t.profile_snapshot.get("model_digest"), "strategy": t.strategy, "repeticao": t.repeticao,
        "status": t.status, "error": t.error,
        "metrics": t.metrics, "output": t.output, "calls": t.calls,
        "gabarito": goldmod.score_output(t.output, gold) if t.status == "completed" else None,
        "started_at": t.started_at.isoformat() if t.started_at else None,
        "finished_at": t.finished_at.isoformat() if t.finished_at else None,
        "notas": [{"nota": r.nota, "comentario": r.comentario, "minha": r.user_id == user.id}
                  for r in ratings if r.trial_id == t.id],
    } for t in trials]
    return {
        "id": str(comp.id), "projeto": project.nome, "project_id": str(project.id), "run_id": str(run.id),
        "fase": run.phase, "task_id": comp.task_id, "nome": spec.name, "funcao": spec.baml_function,
        "notes": comp.notes, "created_at": comp.created_at.isoformat(),
        "prompts_mudaram": bool(comp.source_baml_src_sha and comp.baml_src_sha != comp.source_baml_src_sha),
        "package_sha256": comp.package_sha256, "pode_editar": user.papel_global == "admin" or role in EDITORS,
        "original": original,
        "tentativas": trials_out,
        "resumo": service.summarize(trials_out),
        "gabarito": {"artefatos": list_artifacts, "artifact_type": gold.artifact_type if gold else None,
                     "itens": gold.itens if gold else [], "autoria": gold.autoria if gold else None,
                     "atualizado_em": gold.updated_at.isoformat() if gold else None},
    }


@router.get("/comparisons/{comparison_id}/export.csv")
async def export_csv(comparison_id: uuid.UUID, user: AppUser = Depends(current_user),
                     session: AsyncSession = Depends(get_session)):
    """Uma linha por tentativa, para análise estatística fora da plataforma."""
    data = await detail(comparison_id, user, session)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["comparacao", "tarefa", "modelo", "provider", "model", "model_digest", "estrategia", "repeticao",
                "status", "contrato_valido", "itens", "itens_faltantes", "lacunas", "evidencias_total",
                "evidencias_verificadas", "recuperacao_identica", "perda_top_k", "tokens_contexto", "chamadas",
                "input_tokens", "output_tokens", "latency_ms", "precisao", "recall", "f1", "nota_media"])
    for t in data["tentativas"]:
        m, g, ctx = t["metrics"] or {}, t["gabarito"] or {}, (t["metrics"] or {}).get("contexto") or {}
        notas = [n["nota"] for n in t["notas"]]
        w.writerow([data["id"], data["task_id"], t["modelo"], t["provider"], t["model"], t["model_digest"],
                    t["strategy"] or "original", t["repeticao"], t["status"], m.get("contrato_valido"), m.get("itens"),
                    len(m.get("itens_faltantes") or []), m.get("lacunas"), (m.get("evidencias") or {}).get("total"),
                    (m.get("evidencias") or {}).get("verificadas"), (m.get("recuperacao") or {}).get("identica"),
                    ctx.get("perda_top_k"), ctx.get("tokens_estimados"), m.get("chamadas"), m.get("input_tokens"),
                    m.get("output_tokens"), m.get("latency_ms"), g.get("precisao"), g.get("recall"), g.get("f1"),
                    round(sum(notas) / len(notas), 2) if notas else None])
    return PlainTextResponse(buf.getvalue(), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="laboratorio-{comparison_id}.csv"'})


@router.put("/gold")
async def save_gold(body: GoldIn, user: AppUser = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await require_member(session, body.project_id, user, EDITORS)
    at = ARTIFACT_TYPES.get(body.artifact_type)
    if not (at and at.list_field):
        raise HTTPException(422, "Escolha um artefato em lista.")
    itens = [x.strip() for x in body.itens if x.strip()][:500]
    gold = await session.scalar(select(LabGold).where(LabGold.project_id == body.project_id,
                                                      LabGold.task_id == body.task_id))
    if gold is None:
        gold = LabGold(id=uuid.uuid4(), project_id=body.project_id, task_id=body.task_id,
                       artifact_type=body.artifact_type)
        session.add(gold)
    gold.artifact_type, gold.itens, gold.autoria, gold.updated_by = body.artifact_type, itens, body.autoria, user.id
    await session.flush()
    return {"ok": True, "itens": len(itens)}


async def _trial_for(session: AsyncSession, trial_id: uuid.UUID, user: AppUser, roles=None) -> LabTrial:
    trial = await session.get(LabTrial, trial_id)
    if trial is None:
        raise HTTPException(404, "Tentativa inexistente")
    comp = await session.get(LabComparison, trial.comparison_id)
    await require_member(session, comp.project_id, user, roles)
    return trial


@router.post("/trials/{trial_id}/cancel")
async def cancel(trial_id: uuid.UUID, user: AppUser = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await _trial_for(session, trial_id, user, EDITORS)
    try:
        await service.cancel_trial(session, trial_id)
    except service.LabError as exc:
        raise _err(exc) from exc
    return {"ok": True}


@router.post("/trials/{trial_id}/rating")
async def rate(trial_id: uuid.UUID, body: RatingIn, user: AppUser = Depends(current_user),
               session: AsyncSession = Depends(get_session)):
    await _trial_for(session, trial_id, user)
    try:
        await service.rate_trial(session, trial_id, user.id, body.nota, body.comentario)
    except service.LabError as exc:
        raise _err(exc) from exc
    return {"ok": True}
