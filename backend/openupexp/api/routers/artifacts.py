import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openupexp.agents.registry import ARTIFACT_TYPES, PHASE_DOCUMENT, PHASE_EDITABLE, json_schema
from openupexp.api.auth import current_user, require_member
from openupexp.api.deps import get_session
from openupexp.db.models import (
    AppUser,
    Artifact,
    ArtifactDependency,
    ArtifactVersion,
    Chunk,
    Evidence,
    Run,
    TraceLink,
)
from openupexp.domain import artifacts as store
from openupexp.domain import services
from openupexp.domain.diff import diff_contents

router = APIRouter(prefix="/api")


def _version(v: ArtifactVersion, artifact_type: str) -> dict:
    return {"id": str(v.id), "artifact_type": artifact_type, "version_no": v.version_no, "status": v.status,
            "origin": v.origin, "schema_name": v.schema_name, "iteracao": v.iteracao,
            "created_at": v.created_at.isoformat(), "created_by_user": str(v.created_by_user) if v.created_by_user else None,
            "supersedes_id": str(v.supersedes_id) if v.supersedes_id else None}


async def _load(session: AsyncSession, version_id: uuid.UUID, user: AppUser) -> tuple[ArtifactVersion, Artifact]:
    v = await session.get(ArtifactVersion, version_id)
    if v is None:
        raise HTTPException(404, "Versão inexistente")
    a = await session.get(Artifact, v.artifact_id)
    await require_member(session, a.project_id, user)
    return v, a


@router.get("/runs/{run_id}/artifacts")
async def list_artifacts(run_id: uuid.UUID, user: AppUser = Depends(current_user),
                         session: AsyncSession = Depends(get_session)):
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(404, "Execução inexistente")
    await require_member(session, run.project_id, user)
    cur = await store.current_versions(session, run_id)
    editable = PHASE_EDITABLE.get(run.phase, [])
    order = {t: i for i, t in enumerate(editable)}
    out = []
    for atype, v in sorted(cur.items(), key=lambda kv: (order.get(kv[0], 99), kv[0])):
        at = ARTIFACT_TYPES.get(atype)
        n_items = len(v.content.get(at.list_field, [])) if at and at.list_field else None
        out.append({**_version(v, atype), "title": at.title if at else atype, "itens": n_items,
                    "list_field": at.list_field if at else None,
                    "secao": atype in editable or atype == PHASE_DOCUMENT.get(run.phase),
                    "editavel": bool(at and at.schema and atype in editable)})
    return out


@router.get("/artifact-versions/{version_id}")
async def get_version(version_id: uuid.UUID, user: AppUser = Depends(current_user),
                      session: AsyncSession = Depends(get_session)):
    v, a = await _load(session, version_id, user)
    run = await session.get(Run, a.run_id)
    at = ARTIFACT_TYPES.get(a.artifact_type)
    history = (await session.scalars(select(ArtifactVersion).where(ArtifactVersion.artifact_id == a.id)
                                     .order_by(ArtifactVersion.version_no))).all()
    deps = (await session.execute(
        select(ArtifactDependency.depends_on_version_id, ArtifactDependency.via_read, ArtifactVersion.version_no,
               ArtifactVersion.status)
        .join(ArtifactVersion, ArtifactVersion.id == ArtifactDependency.depends_on_version_id)
        .where(ArtifactDependency.version_id == v.id))).all()
    evidences = (await session.execute(
        select(Evidence, Chunk).outerjoin(Chunk, Chunk.id == Evidence.chunk_id)
        .where(Evidence.artifact_version_id == v.id).order_by(Evidence.item_key))).all()
    return {
        **_version(v, a.artifact_type),
        "title": at.title if at else a.artifact_type,
        "run_id": str(a.run_id),
        "content": v.content,
        "list_field": at.list_field if at else None,
        "documento": a.artifact_type in PHASE_DOCUMENT.values(),
        "editavel": a.artifact_type in PHASE_EDITABLE.get(run.phase, []) and v.status in services.EDITABLE_STATUSES
                    and history[-1].id == v.id,
        "historico": [_version(h, a.artifact_type) for h in history],
        "dependencias": [{"version_id": str(d), "artifact": via, "version_no": n, "status": st}
                         for d, via, n, st in deps],
        "evidencias": [{
            "id": str(e.id), "item_key": e.item_key, "chunk_ref": e.chunk_ref, "citacao": e.citacao,
            "kind": e.kind, "verification": e.verification, "human_status": e.human_status,
            "chunk": None if c is None else {"id": str(c.id), "stable_key": c.stable_key, "texto": c.texto,
                                             "pagina": c.pagina, "meta": c.meta, "source_kind": c.source_kind},
        } for e, c in evidences],
    }


@router.get("/artifact-versions/{version_id}/diff/{other_id}")
async def diff(version_id: uuid.UUID, other_id: uuid.UUID, user: AppUser = Depends(current_user),
               session: AsyncSession = Depends(get_session)):
    old, a = await _load(session, other_id, user)
    new, b = await _load(session, version_id, user)
    if a.id != b.id:
        raise HTTPException(422, "As versões pertencem a artefatos diferentes")
    return diff_contents(a.artifact_type, old.content, new.content)


class EditIn(BaseModel):
    content: dict


@router.post("/artifact-versions/{version_id}/edits")
async def edit(version_id: uuid.UUID, body: EditIn, user: AppUser = Depends(current_user),
               session: AsyncSession = Depends(get_session)):
    _, a = await _load(session, version_id, user)
    await require_member(session, a.project_id, user, ("requirements_engineer",))
    v = await services.human_edit(session, version_id, body.content, user.id, bypass_role_check=True)
    return _version(v, a.artifact_type)


@router.get("/artifact-types/{artifact_type}/schema")
async def schema(artifact_type: str, user: AppUser = Depends(current_user)):
    s = json_schema(artifact_type)
    if s is None:
        raise HTTPException(404, "Tipo sem schema editável")
    return s


class EvidenceReviewIn(BaseModel):
    human_status: str  # accepted | rejected | pending


@router.post("/evidence/{evidence_id}/review")
async def review_evidence(evidence_id: uuid.UUID, body: EvidenceReviewIn, user: AppUser = Depends(current_user),
                          session: AsyncSession = Depends(get_session)):
    ev = await session.get(Evidence, evidence_id)
    if ev is None:
        raise HTTPException(404, "Evidência inexistente")
    v, a = await _load(session, ev.artifact_version_id, user)
    await require_member(session, a.project_id, user, ("requirements_engineer",))
    if body.human_status not in ("accepted", "rejected", "pending"):
        raise HTTPException(422, "human_status inválido")
    ev.human_status = body.human_status
    return {"ok": True}


@router.get("/runs/{run_id}/trace-links")
async def links(run_id: uuid.UUID, user: AppUser = Depends(current_user), session: AsyncSession = Depends(get_session)):
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(404, "Execução inexistente")
    await require_member(session, run.project_id, user)
    rows = (await session.scalars(select(TraceLink).where(TraceLink.run_id == run_id)
                                  .order_by(TraceLink.from_item_key))).all()
    return [{"from": t.from_item_key, "to": t.to_item_key, "tipo": t.link_type, "status": t.status,
             "proposto_por": t.proposto_por} for t in rows]
