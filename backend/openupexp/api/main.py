from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from openupexp.api.auth import bootstrap_admin
from openupexp.api.events import broadcaster
from openupexp.db.session import session_scope
from openupexp.llm.catalog import ensure_catalog
from openupexp.api.routers import admin_llm, artifacts, hitl, llm, process, projects, runs
from openupexp.context.builder import MissingRequiredInput
from openupexp.domain.services import DomainError
from openupexp.queue.jobs import JobAlreadyActive


@asynccontextmanager
async def lifespan(app: FastAPI):
    await bootstrap_admin()
    async with session_scope() as session:
        await ensure_catalog(session)
    broadcaster.start()
    yield
    await broadcaster.stop()


app = FastAPI(title="OpenUPExp", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

for r in (projects, runs, artifacts, hitl, process, llm, admin_llm):
    app.include_router(r.router)


@app.exception_handler(DomainError)
async def domain_error(request: Request, exc: DomainError):
    return JSONResponse({"detail": str(exc)}, status_code=exc.status)


@app.exception_handler(JobAlreadyActive)
async def job_active(request: Request, exc: JobAlreadyActive):
    return JSONResponse({"detail": "Já existe um processamento em andamento para esta execução."}, status_code=409)


@app.exception_handler(MissingRequiredInput)
async def missing_input(request: Request, exc: MissingRequiredInput):
    return JSONResponse({"detail": str(exc)}, status_code=422)


@app.get("/api/health")
async def health():
    return {"ok": True}
