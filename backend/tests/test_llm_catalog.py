"""Catálogo de modelos (cap. 14): modelo local protegido, perfil padrão e snapshot por execução."""

import httpx
import pytest
from sqlalchemy import func, select

from openupexp.agents.gateway import BamlGateway
from openupexp.api.auth import create_user
from openupexp.api.main import app
from openupexp.config import get_settings
from openupexp.db.models import InferenceProfile, LlmModel
from openupexp.db.session import session_scope
from openupexp.domain import services
from openupexp.llm.catalog import (
    CLOUD_FALLBACK_PROFILE,
    LOCAL_PROFILE,
    client_options,
    ensure_catalog,
)
from openupexp.retrieval.ingest import add_source

from .test_phase2_flow import _expect_error


@pytest.fixture
def local_llm(monkeypatch):
    """Liga o modelo local (LOCAL_LLM_ENABLED=true) só neste teste."""
    monkeypatch.setenv("LOCAL_LLM_ENABLED", "true")
    get_settings.cache_clear()
    yield
    monkeypatch.delenv("LOCAL_LLM_ENABLED")
    get_settings.cache_clear()


async def _project(scope_bytes):
    async with session_scope() as s:
        p = await services.create_project(s, "Modelos", None, None, None)
        await add_source(s, p.id, "escopo.txt", scope_bytes, "escopo")
        return p.id


async def test_catalog_is_idempotent_and_protects_local_model(local_llm):
    async with session_scope() as s:
        await ensure_catalog(s)
        await ensure_catalog(s)
        assert await s.scalar(select(func.count(InferenceProfile.id)).where(InferenceProfile.is_default)) == 1
        default = await s.scalar(select(InferenceProfile).where(InferenceProfile.is_default))
        assert default.slug == LOCAL_PROFILE and default.protected
        local = await s.get(LlmModel, default.model_id)
        assert local.local and local.protected and local.provider == "ollama"
        # alteração indevida na configuração-base é desfeita
        local.model, local.enabled, default.params = "outro", False, {"temperature": 1}
    async with session_scope() as s:
        await ensure_catalog(s)
    async with session_scope() as s:
        default = await s.scalar(select(InferenceProfile).where(InferenceProfile.slug == LOCAL_PROFILE))
        local = await s.get(LlmModel, default.model_id)
        assert local.model == "openupexp-qwen3-4b" and local.enabled and default.params["temperature"] == 0.0


async def test_run_freezes_default_or_chosen_profile(scope_bytes, local_llm):
    project_id = await _project(scope_bytes)
    async with session_scope() as s:
        run = await services.start_run(s, project_id, agent_gateway="baml")
        snap = run.model_profile
        assert snap["profile_slug"] == LOCAL_PROFILE and snap["provider"] == "ollama" and snap["local"]
        assert snap["model_digest"] is None  # sem Ollama no ambiente de teste
        groq = await s.scalar(select(InferenceProfile).where(InferenceProfile.slug == "groq-gpt-oss-20b"))
        run2 = await services.start_run(s, project_id, agent_gateway="baml", llm_profile_id=groq.id)
        assert run2.model_profile["model"] == "openai/gpt-oss-20b"
        groq.enabled = False
    async with session_scope() as s:
        await _expect_error(services.start_run(s, project_id, agent_gateway="baml", llm_profile_id=groq.id), 422)
        # no modo simulado não há perfil
        assert (await services.start_run(s, project_id, agent_gateway="fake")).model_profile == {}


def test_client_options_never_need_the_secret_in_the_snapshot(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "segredo")
    local = {"provider": "ollama", "base_url": "http://ollama:11434/v1", "model": "openupexp-qwen3-4b",
             "params": {"temperature": 0.0, "num_ctx": 16384, "think": False}, "api_key_env": None}
    provider, opts = client_options(local)
    assert provider == "openai-generic" and opts["base_url"].endswith("/v1") and "num_ctx" not in opts
    provider, opts = client_options({"provider": "anthropic", "model": "m", "api_key_env": "ANTHROPIC_API_KEY",
                                     "params": {"temperature": 0.0, "max_tokens": 10}})
    assert provider == "anthropic" and opts["api_key"] == "segredo" and opts["max_tokens"] == 10
    provider, opts = client_options({"provider": "google-ai", "model": "g", "api_key_env": None,
                                     "params": {"temperature": 0.2}})
    assert opts["generationConfig"] == {"temperature": 0.2}
    # o gateway monta o ClientRegistry sem chamar o modelo
    from baml_py import Collector
    assert "client_registry" in BamlGateway({**local, "profile_slug": LOCAL_PROFILE})._options(Collector(name="t"))
    assert "client_registry" in BamlGateway({"provider": "baml-named", "model": "OpenUPExpDefault"})._options(
        Collector(name="t"))


@pytest.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        yield c


async def test_profiles_api_lists_local_first(client, local_llm):
    async with session_scope() as s:
        await create_user(s, "eng@x.org", "Engenheira", "senha123")
    r = await client.post("/api/auth/login", json={"email": "eng@x.org", "password": "senha123"})
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    profiles = (await client.get("/api/llm/profiles", headers=headers)).json()
    assert profiles[0]["slug"] == LOCAL_PROFILE and profiles[0]["padrao"] and profiles[0]["modelo"]["local"]
    assert all("segredo" not in str(p) and "api_key" not in str(p) for p in profiles)


async def test_local_model_is_off_by_default(scope_bytes, client):
    """Sem LOCAL_LLM_ENABLED o modelo local continua cadastrado, mas desligado; o padrão vai para a nuvem."""
    project_id = await _project(scope_bytes)
    async with session_scope() as s:
        run = await services.start_run(s, project_id, agent_gateway="baml")
        assert run.model_profile["profile_slug"] == CLOUD_FALLBACK_PROFILE
        local = await s.scalar(select(InferenceProfile).where(InferenceProfile.slug == LOCAL_PROFILE))
        assert local is not None and (await s.get(LlmModel, local.model_id)).enabled is False
    async with session_scope() as s:
        await _expect_error(services.start_run(s, project_id, agent_gateway="baml", llm_profile_id=local.id), 422)
        await create_user(s, "eng@x.org", "Engenheira", "senha123")
    r = await client.post("/api/auth/login", json={"email": "eng@x.org", "password": "senha123"})
    profiles = (await client.get("/api/llm/profiles", headers={"Authorization": f"Bearer {r.json()['access_token']}"})).json()
    by_slug = {p["slug"]: p for p in profiles}
    assert by_slug[LOCAL_PROFILE]["disponivel"] is False and by_slug[LOCAL_PROFILE]["padrao"] is False
    assert by_slug[CLOUD_FALLBACK_PROFILE]["padrao"] is True
