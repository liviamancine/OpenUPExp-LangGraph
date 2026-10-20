"""Testes com banco: versões e invalidação, fila, ingestão e busca híbrida."""

import asyncio
import uuid

from sqlalchemy import select

from openupexp.db.models import Job, Project, Run
from openupexp.db.session import session_scope
from openupexp.domain import artifacts as store
from openupexp.queue import jobs
from openupexp.retrieval.embeddings import HashEmbedder
from openupexp.retrieval.ingest import add_source, build_corpus_version
from openupexp.retrieval.search import hybrid_search


async def _project_and_run(s) -> tuple[Project, Run]:
    from openupexp.domain.services import ensure_manifest

    p = Project(nome="t")
    s.add(p)
    await s.flush()
    await ensure_manifest(s)
    r = Run(project_id=p.id, manifest_version="0.1.0", phase="1", thread_id=f"t-{uuid.uuid4()}")
    s.add(r)
    await s.flush()
    return p, r


async def test_versions_and_recursive_invalidation():
    async with session_scope() as s:
        p, r = await _project_and_run(s)
        kw = dict(project_id=p.id, run_id=r.id, phase="1", origin="agent")
        a1 = await store.save_version(s, artifact_type="vision.problem", content={"v": 1}, **kw)
        b1 = await store.save_version(s, artifact_type="vision.stakeholders", content={}, depends_on={a1.id: "p"}, **kw)
        c1 = await store.save_version(s, artifact_type="vision.positioning", content={}, depends_on={b1.id: "s"}, **kw)
        a2 = await store.save_version(s, artifact_type="vision.problem", content={"v": 2}, **kw)
        await s.refresh(a1)
        await s.refresh(b1)
        await s.refresh(c1)
        assert (a1.status, a2.status, a2.version_no) == ("superseded", "draft", 2)
        assert b1.status == "stale" and c1.status == "stale"  # transitivo
        assert (await store.current_version(s, r.id, "vision.problem")).id == a2.id


async def test_human_edit_does_not_invalidate_dependents():
    async with session_scope() as s:
        p, r = await _project_and_run(s)
        kw = dict(project_id=p.id, run_id=r.id, phase="1", origin="agent")
        a1 = await store.save_version(s, artifact_type="vision.problem", content={"v": 1}, **kw)
        b1 = await store.save_version(s, artifact_type="vision.stakeholders", content={}, depends_on={a1.id: "p"}, **kw)
        await store.save_version(s, artifact_type="vision.problem", content={"v": 2}, invalidate=False,
                                 **dict(kw, origin="human_edit"))
        await s.refresh(b1)
        assert b1.status == "draft"


async def test_queue_skip_locked_and_single_active_job_per_run():
    async with session_scope() as s:
        p, r = await _project_and_run(s)
        await jobs.enqueue(s, "run.start", {}, run_id=r.id)
        try:
            await jobs.enqueue(s, "run.resume", {}, run_id=r.id)
            raise AssertionError("deveria recusar segundo job ativo")
        except jobs.JobAlreadyActive:
            pass
        await jobs.enqueue(s, "corpus.index", {"project_id": str(p.id)})

    async def claimer(name):
        async with session_scope() as s:
            j = await jobs.claim(s, name)
            await asyncio.sleep(0.2)  # mantém o lock enquanto o outro tenta
            return j.id if j else None

    got = await asyncio.gather(claimer("w1"), claimer("w2"))
    assert None not in got and got[0] != got[1]


async def test_reaper_requeues_stale_jobs():
    async with session_scope() as s:
        j = await jobs.enqueue(s, "corpus.index", {})
    async with session_scope() as s:
        await jobs.claim(s, "w")
        await s.execute(Job.__table__.update().values(locked_at=Job.locked_at - __import__("datetime").timedelta(hours=2)))
    async with session_scope() as s:
        assert await jobs.reap_stale(s, 30) == 1
        assert (await s.get(Job, j.id, populate_existing=True)).status == "queued"


async def test_ingest_incremental_and_hybrid_search(law_bytes):
    async with session_scope() as s:
        p = Project(nome="busca")
        s.add(p)
        await s.flush()
        await add_source(s, p.id, "lei_13709_lgpd.txt", law_bytes, "lei")
        again = await add_source(s, p.id, "copia.txt", law_bytes, "lei")  # mesmo hash → mesma fonte
        cv1 = await build_corpus_version(s, p.id, HashEmbedder())
        cv2 = await build_corpus_version(s, p.id, HashEmbedder())
        assert again.arquivo == "lei_13709_lgpd.txt"
        assert cv2.stats["embeddings_novos"] == 0 and cv2.stats["embeddings_reaproveitados"] == cv1.stats["chunks"]

        hits = await hybrid_search(s, cv2.id, "art. 20 da Lei 13.709 decisões automatizadas", HashEmbedder(), k=3)
        assert hits[0].stable_key.endswith(":art20")
        assert "explicit_ref" in hits[0].via and "lexical" in hits[0].via


async def test_scope_document_kind(scope_bytes):
    from openupexp.db.models import SourceDocument

    async with session_scope() as s:
        p = Project(nome="escopo")
        s.add(p)
        await s.flush()
        await add_source(s, p.id, "escopo.txt", scope_bytes, "escopo")
        doc = await s.scalar(select(SourceDocument).where(SourceDocument.project_id == p.id))
        assert doc.source_kind == "escopo" and "examinador" in doc.texto
