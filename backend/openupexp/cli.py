"""CLI de operação: usuários, projetos, fontes, execuções e decisões sem a interface web."""

import asyncio
import json
import uuid
from pathlib import Path

import typer
from sqlalchemy import select

from openupexp.config import get_settings
from openupexp.db.models import AppUser, HitlRequest, Run, TaskExecution
from openupexp.db.session import dispose_engine, session_scope

app = typer.Typer(no_args_is_help=True, help="OpenUPExp — operação da plataforma")


def _run(coro):
    async def wrapper():
        try:
            return await coro
        finally:
            await dispose_engine()

    return asyncio.run(wrapper())


@app.command("check-manifest")
def check_manifest():
    """Verifica a conformidade manifesto ↔ BPMN de referência."""
    from openupexp.process.manifest import check_conformance, load_manifest

    problems = check_conformance(load_manifest(), get_settings().bpmn_dir)
    for p in problems:
        typer.echo(f"✗ {p}")
    typer.echo("conforme" if not problems else f"{len(problems)} problema(s)")
    raise typer.Exit(1 if problems else 0)


@app.command("create-user")
def create_user(email: str, nome: str, password: str = typer.Option(..., prompt=True, hide_input=True),
                admin: bool = False):
    from openupexp.api.auth import create_user as _create

    async def go():
        async with session_scope() as s:
            u = await _create(s, email, nome, password, "admin" if admin else "user")
            typer.echo(f"usuário {u.id} ({u.email})")

    _run(go())


@app.command("create-project")
def create_project(nome: str, dominio: str = "", owner_email: str = ""):
    from openupexp.domain.services import create_project as _create

    async def go():
        async with session_scope() as s:
            owner = None
            if owner_email:
                owner = await s.scalar(select(AppUser).where(AppUser.email == owner_email.lower()))
                if owner is None:
                    raise typer.BadParameter(f"usuário {owner_email} inexistente")
            p = await _create(s, nome, dominio or None, None, owner.id if owner else None)
            typer.echo(str(p.id))

    _run(go())


@app.command("add-source")
def add_source(project_id: uuid.UUID, files: list[Path], kind: str = typer.Option("", help="escopo|lei|manual|academico")):
    from openupexp.retrieval.ingest import add_source as _add

    async def go():
        async with session_scope() as s:
            for f in files:
                d = await _add(s, project_id, f.name, f.read_bytes(), kind or None)
                typer.echo(f"{d.source_kind:9} {d.arquivo} ({d.paginas} pág.)")

    _run(go())


@app.command("index")
def index(project_id: uuid.UUID, provider: str = "", model: str = ""):
    """Constrói uma nova versão do corpus (síncrono)."""
    from openupexp.retrieval.embeddings import get_embedder
    from openupexp.retrieval.ingest import build_corpus_version

    async def go():
        async with session_scope() as s:
            cv = await build_corpus_version(s, project_id, get_embedder(provider or None, model or None))
            typer.echo(f"corpus {cv.id}: {json.dumps(cv.stats)}")

    _run(go())


@app.command("seed-inpi")
def seed_inpi(owner_email: str = "", provider: str = ""):
    """Cria o estudo de caso INPI com o escopo e o corpus deste repositório."""
    from openupexp.domain.services import create_project as _create
    from openupexp.retrieval.embeddings import get_embedder
    from openupexp.retrieval.ingest import add_source as _add
    from openupexp.retrieval.ingest import build_corpus_version

    import os

    root = Path(os.environ.get("SEED_DIR") or Path(__file__).resolve().parents[2] / "experiments" / "cases" / "inpi")

    async def go():
        async with session_scope() as s:
            owner = None
            if owner_email:
                owner = await s.scalar(select(AppUser).where(AppUser.email == owner_email.lower()))
            p = await _create(s, "INPI — Registro de Marcas", "propriedade industrial",
                              "Estudo de caso inicial do OpenUPExp", owner.id if owner else None)
            await _add(s, p.id, "escopo_projeto.pdf", (root / "escopo_projeto.pdf").read_bytes(), "escopo")
            for f in sorted((root / "corpus").glob("*.pdf")):
                await _add(s, p.id, f.name, f.read_bytes())
            cv = await build_corpus_version(s, p.id, get_embedder(provider or None))
            typer.echo(f"projeto {p.id} · corpus {cv.id} {json.dumps(cv.stats)}")

    _run(go())


@app.command("start")
def start(project_id: uuid.UUID, strategy: str = "D", gateway: str = "", phase: str = "1",
          client: str = typer.Option("", help="cliente BAML fixo (experimentos)")):
    from openupexp.domain.services import start_run

    async def go():
        async with session_scope() as s:
            run = await start_run(s, project_id, phase, strategy, gateway or None,
                                  {"client": client} if client else None)
            typer.echo(str(run.id))

    _run(go())


@app.command("status")
def status(run_id: uuid.UUID):
    async def go():
        async with session_scope() as s:
            run = await s.get(Run, run_id)
            typer.echo(f"execução {run.id} · fase {run.phase} · {run.status} · tarefa {run.current_task}")
            if run.error:
                typer.echo(f"erro: {run.error}")
            rows = (await s.scalars(select(TaskExecution).where(TaskExecution.run_id == run_id)
                                    .order_by(TaskExecution.inicio))).all()
            for t in rows:
                typer.echo(f"  {t.task_id:9} it{t.iteracao} {t.status}")
            req = await s.scalar(select(HitlRequest).where(HitlRequest.run_id == run_id,
                                                           HitlRequest.status == "open"))
            if req:
                typer.echo(f"aguardando decisão {req.id}: opções {sorted(req.payload.get('outcomes', {}))}")

    _run(go())


@app.command("decide")
def decide(run_id: uuid.UUID, decision: str, comment: str = "", user_email: str = ""):
    from openupexp.domain.services import decide as _decide

    async def go():
        async with session_scope() as s:
            req = await s.scalar(select(HitlRequest).where(HitlRequest.run_id == run_id,
                                                           HitlRequest.status == "open"))
            if req is None:
                raise typer.BadParameter("não há decisão pendente")
            user = None
            if user_email:
                user = await s.scalar(select(AppUser).where(AppUser.email == user_email.lower()))
            await _decide(s, req.id, user.id if user else None, decision, comment or None,
                          bypass_role_check=user is None)
            typer.echo(f"decisão registrada: {decision}")

    _run(go())


@app.command("worker")
def worker():
    """Executa o worker (laço contínuo)."""
    from openupexp.worker_main import main

    asyncio.run(main())


@app.command("drain")
def drain():
    """Processa os jobs pendentes e termina (modo inline para desenvolvimento)."""
    from openupexp.worker_main import drain as _drain

    n = _run(_drain())
    typer.echo(f"{n} job(s) processado(s)")


if __name__ == "__main__":
    app()
