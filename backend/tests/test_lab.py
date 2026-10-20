"""Laboratório de modelos (cap. 14 §14.5): mesma tarefa, mesmo pacote, sem efeitos na execução original."""

import httpx
import pytest
from sqlalchemy import func, select

from openupexp.api.auth import create_user
from openupexp.api.main import app
from openupexp.db.models import (
    Artifact,
    ArtifactVersion,
    InferenceProfile,
    LabTrial,
    LlmCall,
    ProjectMember,
    Run,
    TaskExecution,
)
from openupexp.db.session import session_scope
from openupexp.lab import service
from openupexp.llm.catalog import ensure_catalog
from openupexp.worker_main import drain

from .test_phase1_flow import _setup


async def _source(scope_bytes, law_bytes, task_id):
    run_id = await _setup(scope_bytes, law_bytes)
    await drain()  # até a aprovação 1.3: todas as tarefas de IA da fase já rodaram
    async with session_scope() as s:
        te = await s.scalar(select(TaskExecution).where(TaskExecution.run_id == run_id, TaskExecution.task_id == task_id))
        return run_id, te.id


async def _counts(run_id):
    async with session_scope() as s:
        versions = await s.scalar(select(func.count(ArtifactVersion.id)).join(Artifact, Artifact.id == ArtifactVersion.artifact_id)
                                  .where(Artifact.run_id == run_id))
        calls = await s.scalar(select(func.count(LlmCall.id)).where(LlmCall.run_id == run_id))
        return versions, calls


async def test_replay_reuses_package_and_writes_nothing(scope_bytes, law_bytes):
    # 1.2.2 busca na base de referência dentro do handler: a recuperação precisa coincidir
    run_id, te_id = await _source(scope_bytes, law_bytes, "1.2.2")
    before = await _counts(run_id)
    async with session_scope() as s:
        sources = await service.eligible_sources(s, run_id)
        assert {x["task_id"] for x in sources} >= {"1.1.1", "1.1.2", "1.2.2"}
        assert "1.2.4" not in {x["task_id"] for x in sources}  # determinística
        comp = await service.create_comparison(s, te_id, [service.FAKE, service.FAKE], "teste", None)
    await drain(["lab.trial"])
    async with session_scope() as s:
        trials = (await s.scalars(select(LabTrial).where(LabTrial.comparison_id == comp.id))).all()
        assert [t.status for t in trials] == ["completed", "completed"]
        m = trials[0].metrics
        assert m["contrato_valido"] and m["itens"] > 0 and m["chamadas"] >= 1
        assert m["recuperacao"]["identica"] and m["recuperacao"]["trechos"] > 0
        assert m["evidencias"]["total"] > 0
        assert "vision.complementary_requirements" in {o["artifact"] for o in trials[0].output}
        ref = await service.reference(s, comp)
        assert ref["metrics"]["itens"] == m["itens"]  # mesmo modelo simulado, mesmo pacote → mesmo resultado
    assert await _counts(run_id) == before  # nenhuma versão nem chamada gravada na execução original


async def test_failed_model_is_a_result_not_a_crash(scope_bytes, law_bytes, monkeypatch):
    _, te_id = await _source(scope_bytes, law_bytes, "1.1.2")
    async with session_scope() as s:
        await ensure_catalog(s)
        groq = await s.scalar(select(InferenceProfile).where(InferenceProfile.slug == "groq-gpt-oss-20b"))
        comp = await service.create_comparison(s, te_id, [str(groq.id), service.FAKE], None, None)

    original = service.LabGateway.call

    async def call(self, function, entrada, contexto, **kw):
        if self.snapshot.get("provider") != service.FAKE:
            self.calls.append({"function": function, "status": "error", "latency_ms": 5})
            raise RuntimeError("saída fora do contrato")
        return await original(self, function, entrada, contexto, **kw)

    monkeypatch.setattr(service.LabGateway, "call", call)
    await drain(["lab.trial"])
    async with session_scope() as s:
        trials = (await s.scalars(select(LabTrial).where(LabTrial.comparison_id == comp.id)
                                  .order_by(LabTrial.position))).all()
        assert trials[0].status == "failed" and "fora do contrato" in trials[0].error
        assert trials[0].metrics["contrato_valido"] is False and trials[0].metrics["chamadas_com_erro"] == 1
        assert trials[0].profile_snapshot["model"] == "openai/gpt-oss-20b"
        assert trials[1].status == "completed"
        with pytest.raises(service.LabError):
            await service.rate_trial(s, trials[0].id, None, 4, None)


async def test_cancel_queued_and_validate_choices(scope_bytes, law_bytes):
    run_id, te_id = await _source(scope_bytes, law_bytes, "1.1.1")
    async with session_scope() as s:
        comp = await service.create_comparison(s, te_id, [service.FAKE], None, None)
        trial = await s.scalar(select(LabTrial).where(LabTrial.comparison_id == comp.id))
        await service.cancel_trial(s, trial.id)
        with pytest.raises(service.LabError):
            await service.create_comparison(s, te_id, [], None, None)
        det = await s.scalar(select(TaskExecution).where(TaskExecution.run_id == run_id, TaskExecution.task_id == "1.2.4"))
        with pytest.raises(service.LabError):
            await service.create_comparison(s, det.id, [service.FAKE], None, None)
    await drain(["lab.trial"])
    async with session_scope() as s:
        assert (await s.get(LabTrial, trial.id)).status == "cancelled"


@pytest.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        yield c


async def test_lab_api_access_and_rating(scope_bytes, law_bytes, client):
    run_id, te_id = await _source(scope_bytes, law_bytes, "1.1.2")
    async with session_scope() as s:
        eng = await create_user(s, "eng@x.org", "Engenheira", "senha123")
        await create_user(s, "fora@x.org", "De fora", "senha123")
        run = await s.get(Run, run_id)
        s.add(ProjectMember(project_id=run.project_id, user_id=eng.id, papel_plataforma="requirements_engineer"))

    async def login(email):
        r = await client.post("/api/auth/login", json={"email": email, "password": "senha123"})
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    h, outsider = await login("eng@x.org"), await login("fora@x.org")
    assert (await client.get(f"/api/lab/sources/{run_id}", headers=outsider)).status_code == 403
    r = await client.post("/api/lab/comparisons", headers=h,
                          json={"task_execution_id": str(te_id), "profiles": ["fake"]})
    assert r.status_code == 200
    cid = r.json()["id"]
    await drain(["lab.trial"])
    d = (await client.get(f"/api/lab/comparisons/{cid}", headers=h)).json()
    assert d["original"]["modelo"] == "Modo de teste (simulado)" and d["tentativas"][0]["status"] == "completed"
    assert d["prompts_mudaram"] is False
    tid = d["tentativas"][0]["id"]
    assert (await client.post(f"/api/lab/trials/{tid}/rating", headers=h, json={"nota": 4, "comentario": "ok"})).status_code == 200
    assert (await client.post(f"/api/lab/trials/{tid}/rating", headers=h, json={"nota": 5})).status_code == 200
    d = (await client.get(f"/api/lab/comparisons/{cid}", headers=h)).json()
    assert d["tentativas"][0]["notas"] == [{"nota": 5, "comentario": None, "minha": True}]
    assert len((await client.get("/api/lab/comparisons", headers=h)).json()) == 1
    assert (await client.get("/api/lab/comparisons", headers=outsider)).json() == []
