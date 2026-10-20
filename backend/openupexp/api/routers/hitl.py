import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openupexp.api.auth import current_user, require_member
from openupexp.api.deps import get_session
from openupexp.db.models import AppUser, HitlRequest, HitlResponse, Project, ProjectMember, Run
from openupexp.domain import artifacts as store
from openupexp.domain import services

router = APIRouter(prefix="/api")


def _req(r: HitlRequest, run: Run | None = None, project: Project | None = None) -> dict:
    return {"id": str(r.id), "run_id": str(r.run_id), "task_id": r.task_id, "bpmn_element_id": r.bpmn_element_id,
            "kind": r.kind, "status": r.status, "payload": r.payload, "policy": r.policy, "round": r.round,
            "iteracao": r.iteracao, "created_at": r.created_at.isoformat(),
            "decided_at": r.decided_at.isoformat() if r.decided_at else None,
            "projeto": {"id": str(project.id), "nome": project.nome} if project else None,
            "run_status": run.status if run else None}


@router.get("/hitl")
async def inbox(status: str = "open", user: AppUser = Depends(current_user),
                session: AsyncSession = Depends(get_session)):
    q = (select(HitlRequest, Run, Project).join(Run, Run.id == HitlRequest.run_id)
         .join(Project, Project.id == Run.project_id).where(HitlRequest.status == status)
         .order_by(HitlRequest.created_at.desc()))
    if user.papel_global != "admin":
        q = q.join(ProjectMember, (ProjectMember.project_id == Project.id) & (ProjectMember.user_id == user.id))
    return [_req(r, run, p) for r, run, p in (await session.execute(q)).all()]


@router.get("/hitl/{request_id}")
async def get_request(request_id: uuid.UUID, user: AppUser = Depends(current_user),
                      session: AsyncSession = Depends(get_session)):
    r = await session.get(HitlRequest, request_id)
    if r is None:
        raise HTTPException(404, "Solicitação inexistente")
    run = await session.get(Run, r.run_id)
    await require_member(session, run.project_id, user)
    responses = (await session.scalars(select(HitlResponse).where(HitlResponse.hitl_request_id == r.id)
                                       .order_by(HitlResponse.created_at))).all()
    report = await store.current_version(session, run.id, "vision.review_report")
    stale = [t for t, v in (await store.current_versions(session, run.id)).items() if v.status == "stale"]
    return {**_req(r, run, await session.get(Project, run.project_id)),
            "review_report": report.content if report else None, "stale": stale,
            "respostas": [{"id": str(x.id), "user_id": str(x.user_id) if x.user_id else None, "decision": x.decision,
                           "comentario": x.comentario, "item_comments": x.item_comments,
                           "created_at": x.created_at.isoformat()} for x in responses]}


class DecisionIn(BaseModel):
    decision: str
    comentario: str | None = None
    item_comments: list[dict] = []


@router.post("/hitl/{request_id}/responses")
async def respond(request_id: uuid.UUID, body: DecisionIn, user: AppUser = Depends(current_user),
                  session: AsyncSession = Depends(get_session)):
    r = await session.get(HitlRequest, request_id)
    if r is None:
        raise HTTPException(404, "Solicitação inexistente")
    run = await session.get(Run, r.run_id)
    role = await require_member(session, run.project_id, user)
    resp = await services.decide(session, request_id, user.id, body.decision, body.comentario, body.item_comments,
                                 bypass_role_check=role == "admin")
    return {"id": str(resp.id), "decision": resp.decision}
