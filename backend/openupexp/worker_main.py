"""Worker: consome a fila no PostgreSQL e executa/retoma os grafos LangGraph.

Uso: python -m openupexp.worker_main
"""

import asyncio
import logging
import os
import socket
import traceback
import uuid

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command

from openupexp.agents.gateway import get_gateway
from openupexp.agents.graph import build_phase_graph, initial_state
from openupexp.config import get_settings
from openupexp.db.models import Run
from openupexp.db.session import session_scope
from openupexp.domain.events import emit
from openupexp.process.manifest import get_manifest
from openupexp.queue import jobs
from openupexp.retrieval.embeddings import get_embedder
from openupexp.retrieval.ingest import build_corpus_version

log = logging.getLogger("openupexp.worker")
WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"
_checkpointer_ready = False


async def _ensure_checkpointer(saver: AsyncPostgresSaver) -> None:
    global _checkpointer_ready
    if not _checkpointer_ready:
        await saver.setup()
        _checkpointer_ready = True


async def run_graph(run_id: uuid.UUID, mode: str, resume: dict | None = None) -> str:
    """mode: start | resume | retry. Retorna o status final da execução."""
    async with session_scope() as s:
        run = await s.get(Run, run_id)
        gateway = get_gateway(run.agent_gateway, run.model_profile)
        thread_id, phase_id, manifest_version = run.thread_id, run.phase, run.manifest_version
        corpus = run.corpus_version_id
        if mode != "resume":
            run.status = "running"
        await emit(s, run_id, "run_running", mode=mode)

    embedder = get_embedder()
    if corpus is not None:
        from openupexp.db.models import CorpusVersion

        async with session_scope() as s:
            cv = await s.get(CorpusVersion, corpus)
            embedder = get_embedder(cv.embedding_provider, cv.embedding_model)

    manifest = get_manifest(manifest_version)
    phase = manifest.phase(phase_id)
    settings = get_settings()
    async with AsyncPostgresSaver.from_conn_string(settings.psycopg_url) as saver:
        await _ensure_checkpointer(saver)
        graph = build_phase_graph(manifest, phase_id, gateway, embedder).compile(checkpointer=saver)
        config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 500}
        if mode == "start":
            payload = initial_state(run_id, phase)
        elif mode == "resume":
            payload = Command(resume=resume)
        else:
            payload = None  # retoma do último checkpoint (reexecuta o nó que falhou)
        try:
            result = await graph.ainvoke(payload, config)
        except Exception as exc:
            async with session_scope() as s:
                run = await s.get(Run, run_id)
                if run.status != "failed":
                    run.status = "failed"
                    run.error = f"{type(exc).__name__}: {exc}"[:4000]
                    await emit(s, run_id, "run_failed", erro=run.error)
            raise

    interrupted = bool(result.get("__interrupt__")) if isinstance(result, dict) else False
    async with session_scope() as s:
        run = await s.get(Run, run_id)
        if interrupted:
            run.status = "waiting_human"
        else:
            run.status = "completed"
            run.current_task = None
            await emit(s, run_id, "run_completed")
        return run.status


async def process_job(job) -> None:
    kind, payload = job.kind, job.payload
    if kind == "run.start":
        await run_graph(uuid.UUID(payload["run_id"]), "start")
    elif kind == "run.resume":
        await run_graph(uuid.UUID(payload["run_id"]), "resume", payload["resume"])
    elif kind == "run.retry":
        await run_graph(uuid.UUID(payload["run_id"]), "retry")
    elif kind == "corpus.index":
        async with session_scope() as s:
            embedder = get_embedder(payload.get("provider"), payload.get("model"))
            cv = await build_corpus_version(s, uuid.UUID(payload["project_id"]), embedder)
            log.info("corpus %s pronto: %s", cv.id, cv.stats)
    elif kind == "llm.compat":
        from openupexp.llm.admin import run_compat_test

        async with session_scope() as s:
            result = await run_compat_test(s, uuid.UUID(payload["profile_id"]))
            log.info("teste de compatibilidade %s: %s", payload["profile_id"], result.get("ok"))
    else:
        raise ValueError(f"tipo de job desconhecido: {kind}")


async def run_once(kinds: list[str] | None = None) -> bool:
    """Processa no máximo um job. Retorna False se a fila estava vazia."""
    async with session_scope() as s:
        job = await jobs.claim(s, WORKER_ID, kinds)
    if job is None:
        return False
    log.info("job %s (%s)", job.id, job.kind)
    try:
        await process_job(job)
    except Exception as exc:
        log.error("job %s falhou: %s", job.id, exc)
        # falha de tarefa já marcou a execução como failed; não reprocessa automaticamente
        retry = job.kind == "corpus.index"
        async with session_scope() as s:
            await jobs.fail(s, job, "".join(traceback.format_exception(exc))[-4000:], retry=retry)
        return True
    async with session_scope() as s:
        await jobs.finish(s, job.id)
    return True


async def drain(kinds: list[str] | None = None, max_jobs: int = 100) -> int:
    """Processa jobs até a fila esvaziar (CLI inline e testes)."""
    n = 0
    while n < max_jobs and await run_once(kinds):
        n += 1
    return n


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    log.info("worker %s iniciado (gateway padrão: %s)", WORKER_ID, settings.agent_gateway)
    last_reap = 0.0
    loop = asyncio.get_running_loop()
    while True:
        if loop.time() - last_reap > 60:
            async with session_scope() as s:
                n = await jobs.reap_stale(s, settings.job_stale_minutes)
                if n:
                    log.warning("reaper devolveu %d job(s) à fila", n)
            last_reap = loop.time()
        try:
            worked = await run_once()
        except Exception:
            log.exception("erro no laço do worker")
            worked = False
        if not worked:
            await asyncio.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    asyncio.run(main())
