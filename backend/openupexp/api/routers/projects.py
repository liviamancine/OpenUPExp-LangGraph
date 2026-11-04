import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openupexp.api.auth import PLATFORM_ROLES, create_user, current_user, issue_token, require_member, verify_password
from openupexp.api.deps import get_session
from openupexp.db.models import AppUser, CorpusVersion, Project, ProjectMember, Run, SourceDocument
from openupexp.domain import services
from openupexp.queue.jobs import enqueue
from openupexp.retrieval.chunkers import guess_source_kind
from openupexp.retrieval.ingest import add_source

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------- auth
class LoginIn(BaseModel):
    email: str
    password: str


@router.post("/auth/login")
async def login(body: LoginIn, session: AsyncSession = Depends(get_session)):
    user = await session.scalar(select(AppUser).where(AppUser.email == body.email.lower().strip()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Credenciais inválidas")
    return {"access_token": issue_token(user), "token_type": "bearer", "user": _user(user)}


@router.get("/auth/me")
async def me(user: AppUser = Depends(current_user)):
    return _user(user)


class UserIn(BaseModel):
    email: str
    nome: str
    password: str
    papel_global: str = "user"


@router.post("/users")
async def new_user(body: UserIn, user: AppUser = Depends(current_user), session: AsyncSession = Depends(get_session)):
    if user.papel_global != "admin":
        raise HTTPException(403, "Apenas administradores criam usuários")
    if await session.scalar(select(AppUser).where(AppUser.email == body.email.lower().strip())):
        raise HTTPException(409, "E-mail já cadastrado")
    created = await create_user(session, body.email, body.nome, body.password, body.papel_global)
    return _user(created)


@router.get("/users")
async def list_users(user: AppUser = Depends(current_user), session: AsyncSession = Depends(get_session)):
    rows = (await session.scalars(select(AppUser).order_by(AppUser.nome))).all()
    return [_user(u) for u in rows]


def _user(u: AppUser) -> dict:
    return {"id": str(u.id), "email": u.email, "nome": u.nome, "papel_global": u.papel_global}


# ---------------------------------------------------------------- projetos
class ProjectIn(BaseModel):
    nome: str
    dominio: str | None = None
    descricao: str | None = None


@router.get("/projects")
async def list_projects(user: AppUser = Depends(current_user), session: AsyncSession = Depends(get_session)):
    q = select(Project).order_by(Project.created_at.desc())
    if user.papel_global != "admin":
        q = q.join(ProjectMember, ProjectMember.project_id == Project.id).where(ProjectMember.user_id == user.id)
    return [_project(p) for p in (await session.scalars(q)).all()]


@router.post("/projects")
async def create_project(body: ProjectIn, user: AppUser = Depends(current_user),
                         session: AsyncSession = Depends(get_session)):
    p = await services.create_project(session, body.nome, body.dominio, body.descricao, user.id)
    return _project(p)


@router.get("/projects/{project_id}")
async def get_project(project_id: uuid.UUID, user: AppUser = Depends(current_user),
                      session: AsyncSession = Depends(get_session)):
    p = await session.get(Project, project_id)
    if p is None:
        raise HTTPException(404, "Projeto inexistente")
    role = await require_member(session, project_id, user)
    members = (await session.execute(
        select(ProjectMember, AppUser).join(AppUser, AppUser.id == ProjectMember.user_id)
        .where(ProjectMember.project_id == project_id))).all()
    sources = (await session.scalars(select(SourceDocument).where(SourceDocument.project_id == project_id)
                                     .order_by(SourceDocument.created_at))).all()
    corpora = (await session.scalars(select(CorpusVersion).where(CorpusVersion.project_id == project_id,
                                                                  CorpusVersion.purpose == "reference")
                                     .order_by(CorpusVersion.created_at.desc()))).all()
    runs = (await session.scalars(select(Run).where(Run.project_id == project_id)
                                  .order_by(Run.created_at.desc()))).all()
    return {
        **_project(p),
        "meu_papel": role,
        "membros": [{"user": _user(u), "papel_plataforma": m.papel_plataforma,
                     "papel_openupexp": m.papel_openupexp} for m, u in members],
        "fontes": [_source(sd) for sd in sources],
        "corpora": [{"id": str(c.id), "status": c.status, "embedding_model": c.embedding_model,
                     "embedding_provider": c.embedding_provider, "stats": c.stats,
                     "created_at": c.created_at.isoformat()} for c in corpora],
        "execucoes": [run_summary(r) for r in runs],
    }


class MemberIn(BaseModel):
    user_id: uuid.UUID
    papel_plataforma: str
    papel_openupexp: str | None = None


@router.post("/projects/{project_id}/members")
async def add_member(project_id: uuid.UUID, body: MemberIn, user: AppUser = Depends(current_user),
                     session: AsyncSession = Depends(get_session)):
    await require_member(session, project_id, user, ("requirements_engineer",))
    if body.papel_plataforma not in PLATFORM_ROLES:
        raise HTTPException(422, f"Papel inválido. Opções: {PLATFORM_ROLES}")
    m = await session.get(ProjectMember, (project_id, body.user_id))
    if m is None:
        session.add(ProjectMember(project_id=project_id, user_id=body.user_id,
                                  papel_plataforma=body.papel_plataforma, papel_openupexp=body.papel_openupexp))
    else:
        m.papel_plataforma, m.papel_openupexp = body.papel_plataforma, body.papel_openupexp
    return {"ok": True}


@router.post("/projects/{project_id}/sources")
async def upload_source(project_id: uuid.UUID, file: UploadFile = File(...), source_kind: str | None = Form(None),
                        user: AppUser = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await require_member(session, project_id, user, ("requirements_engineer",))
    kind = source_kind or guess_source_kind(file.filename or "")
    if kind not in ("escopo", "lei", "manual", "academico", "elicitacao"):
        raise HTTPException(422, "source_kind deve ser escopo, lei, manual, academico ou elicitacao")
    doc = await add_source(session, project_id, file.filename or "documento", await file.read(), kind)
    return _source(doc)


@router.delete("/projects/{project_id}/sources/{source_id}")
async def deactivate_source(project_id: uuid.UUID, source_id: uuid.UUID, user: AppUser = Depends(current_user),
                            session: AsyncSession = Depends(get_session)):
    await require_member(session, project_id, user, ("requirements_engineer",))
    doc = await session.get(SourceDocument, source_id)
    if doc is None or doc.project_id != project_id:
        raise HTTPException(404, "Fonte inexistente")
    doc.ativo = False
    return {"ok": True}


@router.post("/projects/{project_id}/corpus")
async def index_corpus(project_id: uuid.UUID, user: AppUser = Depends(current_user),
                       session: AsyncSession = Depends(get_session)):
    await require_member(session, project_id, user, ("requirements_engineer",))
    job = await enqueue(session, "corpus.index", {"project_id": str(project_id)})
    return {"job_id": str(job.id)}


def _project(p: Project) -> dict:
    return {"id": str(p.id), "nome": p.nome, "dominio": p.dominio, "descricao": p.descricao,
            "created_at": p.created_at.isoformat() if p.created_at else None}


def _source(d: SourceDocument) -> dict:
    return {"id": str(d.id), "arquivo": d.arquivo, "source_kind": d.source_kind, "paginas": d.paginas,
            "ativo": d.ativo, "meta": d.meta, "sha256": d.sha256}


def run_summary(r: Run) -> dict:
    return {"id": str(r.id), "phase": r.phase, "status": r.status, "context_strategy": r.context_strategy,
            "agent_gateway": r.agent_gateway, "current_task": r.current_task, "error": r.error,
            "manifest_version": r.manifest_version, "model_profile": r.model_profile,
            "base_run_id": str(r.base_run_id) if r.base_run_id else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None}
