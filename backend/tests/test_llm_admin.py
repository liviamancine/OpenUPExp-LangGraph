"""Administração de modelos (cap. 14 §14.4): acesso, validação, proteção, compatibilidade e padrão."""

import httpx
import pytest
from sqlalchemy import select

from openupexp.api.auth import create_user
from openupexp.api.main import app
from openupexp.baml_client import types as T
from openupexp.db.models import AuditEvent, InferenceProfile
from openupexp.db.session import session_scope
from openupexp.llm import admin
from openupexp.llm.catalog import CLOUD_FALLBACK_PROFILE, LOCAL_PROFILE, ensure_catalog
from openupexp.worker_main import drain


@pytest.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        yield c


async def _headers(client, email, admin_role=False):
    async with session_scope() as s:
        await create_user(s, email, "Pessoa", "senha123", "admin" if admin_role else "user")
    r = await client.post("/api/auth/login", json={"email": email, "password": "senha123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _by_slug(overview):
    return {m["slug"]: m for m in overview["modelos"]}


async def test_only_admins_and_local_model_is_protected(client):
    user = await _headers(client, "eng@x.org")
    assert (await client.get("/api/admin/llm", headers=user)).status_code == 403
    adm = await _headers(client, "adm@x.org", admin_role=True)
    ov = (await client.get("/api/admin/llm", headers=adm)).json()
    local = _by_slug(ov)["qwen3-4b-local"]
    assert local["protegido"] and local["local"] and ov["padrao_efetivo"] == CLOUD_FALLBACK_PROFILE
    for call in (client.patch(f"/api/admin/llm/models/{local['id']}", json={"model": "x"}, headers=adm),
                 client.delete(f"/api/admin/llm/models/{local['id']}", headers=adm),
                 client.patch(f"/api/admin/llm/profiles/{local['perfis'][0]['id']}", json={"params": {}}, headers=adm)):
        assert (await call).status_code == 403


async def test_endpoint_and_key_validation(client):
    adm = await _headers(client, "adm@x.org", admin_role=True)
    base = {"slug": "meu-vllm", "nome": "vLLM", "provider": "openai-generic", "model": "qwen3-8b"}
    r = await client.post("/api/admin/llm/models", json={**base, "base_url": "https://evil.example.com/v1"}, headers=adm)
    assert r.status_code == 403 and "lista permitida" in r.json()["detail"]
    # nome de variável que não é chave de API seria um vazamento de segredo
    r = await client.post("/api/admin/llm/models", headers=adm,
                          json={**base, "base_url": "http://localhost:8000/v1", "api_key_env": "JWT_SECRET"})
    assert r.status_code == 422
    r = await client.post("/api/admin/llm/models", headers=adm,
                          json={**base, "base_url": "http://localhost:8000/v1", "api_key_env": "VLLM_API_KEY"})
    assert r.status_code == 200
    m = _by_slug((await client.get("/api/admin/llm", headers=adm)).json())["meu-vllm"]
    assert m["perfis"][0]["habilitado"] is False
    r = await client.post(f"/api/admin/llm/models/{m['id']}/profiles", headers=adm,
                          json={"slug": "meu-vllm-quente", "params": {"temperature": 5}})
    assert r.status_code == 422


async def test_profile_enabled_only_after_compat_and_can_become_default(client):
    adm = await _headers(client, "adm@x.org", admin_role=True)
    r = await client.post("/api/admin/llm/models", headers=adm, json={
        "slug": "ollama-remoto", "nome": "Ollama remoto", "provider": "ollama", "model": "qwen3:8b",
        "base_url": "http://ollama:11434"})
    model = _by_slug((await client.get("/api/admin/llm", headers=adm)).json())["ollama-remoto"]
    assert model["endereco"] == "http://ollama:11434/v1"
    pid = model["perfis"][0]["id"]
    assert (await client.patch(f"/api/admin/llm/profiles/{pid}", json={"enabled": True}, headers=adm)).status_code == 409

    # o teste vai para a fila; o worker roda com uma chamada simulada
    assert (await client.post(f"/api/admin/llm/profiles/{pid}/test-compat", headers=adm)).json()["status"] == "na_fila"

    async def fake_call(snapshot):
        assert snapshot["model"] == "qwen3:8b" and snapshot["base_url"].endswith("/v1")
        return T.ExplainabilityProblem.model_construct(stakeholders_mencionados=["solicitante"]), {"input_tokens": 10}

    async with session_scope() as s:
        result = await admin.run_compat_test(s, pid, call=fake_call)
    assert result["ok"] and result["input_tokens"] == 10
    assert (await client.patch(f"/api/admin/llm/profiles/{pid}", json={"enabled": True}, headers=adm)).status_code == 200
    assert (await client.post(f"/api/admin/llm/profiles/{pid}/default", headers=adm)).status_code == 200
    ov = (await client.get("/api/admin/llm", headers=adm)).json()
    assert ov["padrao_efetivo"] == "ollama-remoto-padrao"
    async with session_scope() as s:
        defaults = (await s.scalars(select(InferenceProfile).where(InferenceProfile.is_default))).all()
        assert [p.slug for p in defaults] == ["ollama-remoto-padrao"]
        assert await s.scalar(select(AuditEvent).where(AuditEvent.action == "inference_profile_default"))
    # mudar o modelo invalida o teste e desabilita o perfil
    await client.post(f"/api/admin/llm/profiles/{(await _local_id())}/default", headers=adm)
    r = await client.patch(f"/api/admin/llm/models/{model['id']}", json={"model": "qwen3:14b"}, headers=adm)
    assert r.status_code == 200
    perfil = _by_slug((await client.get("/api/admin/llm", headers=adm)).json())["ollama-remoto"]["perfis"][0]
    assert perfil["habilitado"] is False and perfil["compat"] is None


async def _local_id():
    async with session_scope() as s:
        await ensure_catalog(s)
        return (await s.scalar(select(InferenceProfile).where(InferenceProfile.slug == LOCAL_PROFILE))).id


async def test_compat_failure_is_recorded():
    async with session_scope() as s:
        await ensure_catalog(s)
        p = await s.scalar(select(InferenceProfile).where(InferenceProfile.slug == "groq-gpt-oss-20b"))

    async def broken(snapshot):
        raise RuntimeError("saída fora do contrato")

    async with session_scope() as s:
        result = await admin.run_compat_test(s, p.id, call=broken)
    assert result["ok"] is False and "fora do contrato" in result["detalhe"]


async def test_compat_job_runs_in_worker(monkeypatch):
    async with session_scope() as s:
        await ensure_catalog(s)
        p = await s.scalar(select(InferenceProfile).where(InferenceProfile.slug == "groq-gpt-oss-20b"))
        await admin.request_compat_test(s, p.id, None)

    async def fake_call(snapshot):
        return T.ExplainabilityProblem.model_construct(stakeholders_mencionados=[]), {}

    monkeypatch.setattr(admin, "default_compat_call", fake_call)
    monkeypatch.setattr(admin.run_compat_test, "__defaults__", (fake_call,))
    await drain(["llm.compat"])
    async with session_scope() as s:
        compat = (await s.get(InferenceProfile, p.id)).checks["compat"]
    assert compat["status"] == "concluido" and compat["ok"] is False
