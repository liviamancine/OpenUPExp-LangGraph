"""Catálogo de modelos de linguagem e perfis de inferência — docs/architecture/14-modelos-e-laboratorio.md.

O modelo local (Ollama) vem cadastrado e protegido: a configuração-base é restaurada a partir do
seed a cada `ensure_catalog`. Os demais modelos do seed só são criados se faltarem, para não
desfazer ajustes da administração. A execução guarda um snapshot do perfil resolvido.
"""

import os
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openupexp.config import get_settings
from openupexp.db.models import InferenceProfile, LlmModel

LOCAL_PROFILE = "local-qwen3-4b"
# Perfil usado quando o modelo local está desligado nesta instalação (LOCAL_LLM_ENABLED=false).
CLOUD_FALLBACK_PROFILE = "nuvem-com-reserva"


@dataclass(frozen=True)
class Seed:
    slug: str
    nome: str
    provider: str
    model: str
    base_url: str | None = None
    api_key_env: str | None = None
    local: bool = False
    protected: bool = False
    meta: dict = field(default_factory=dict)
    profile_slug: str = ""
    profile_nome: str = ""
    params: dict = field(default_factory=dict)


def _seeds() -> list[Seed]:
    s = get_settings()
    return [
        Seed("qwen3-4b-local", "Qwen3 4B (local)", "ollama", s.ollama_model, f"{s.ollama_url}/v1",
             local=True, protected=True,
             meta={"base": s.ollama_base_model, "quantizacao": "Q4_K_M", "papel": "referência (baseline)"},
             profile_slug=LOCAL_PROFILE, profile_nome="Qwen3 4B local · referência",
             params={"temperature": 0.0, "num_ctx": 16384, "think": False}),
        Seed("groq-gpt-oss-120b", "GPT-OSS 120B (Groq)", "openai-generic", "openai/gpt-oss-120b",
             "https://api.groq.com/openai/v1", "GROQ_API_KEY",
             profile_slug="groq-gpt-oss-120b", profile_nome="GPT-OSS 120B · Groq", params={"temperature": 0.0}),
        Seed("groq-gpt-oss-20b", "GPT-OSS 20B (Groq)", "openai-generic", "openai/gpt-oss-20b",
             "https://api.groq.com/openai/v1", "GROQ_API_KEY",
             profile_slug="groq-gpt-oss-20b", profile_nome="GPT-OSS 20B · Groq", params={"temperature": 0.0}),
        Seed("openai-gpt-5-mini", "GPT-5 mini (OpenAI)", "openai-responses", "gpt-5-mini", None, "OPENAI_API_KEY",
             profile_slug="openai-gpt-5-mini", profile_nome="GPT-5 mini · OpenAI"),
        Seed("anthropic-sonnet", "Claude Sonnet (Anthropic)", "anthropic", "claude-sonnet-5-5", None,
             "ANTHROPIC_API_KEY", profile_slug="anthropic-sonnet", profile_nome="Claude Sonnet · Anthropic",
             params={"temperature": 0.0, "max_tokens": 8192}),
        Seed("gemini-flash", "Gemini 3.5 Flash (Google)", "google-ai", "gemini-3.5-flash", None, "GEMINI_API_KEY",
             profile_slug="gemini-flash", profile_nome="Gemini Flash · Google", params={"temperature": 0.0}),
        Seed("nuvem-com-reserva", "Nuvem com reserva (fallback)", "baml-named", "OpenUPExpDefault",
             meta={"chaves": ["GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"],
                   "descricao": "Groq → OpenAI → Anthropic; troca de modelo em caso de falha"},
             profile_slug="nuvem-com-reserva", profile_nome="Nuvem com reserva (Groq → OpenAI → Anthropic)"),
    ]


async def ensure_catalog(session: AsyncSession) -> None:
    models = {m.slug: m for m in (await session.scalars(select(LlmModel))).all()}
    profiles = {p.slug: p for p in (await session.scalars(select(InferenceProfile))).all()}
    has_default = any(p.is_default for p in profiles.values())
    for seed in _seeds():
        m = models.get(seed.slug)
        if m is None:
            m = LlmModel(id=uuid.uuid4(), slug=seed.slug, nome=seed.nome, provider=seed.provider, model=seed.model,
                         base_url=seed.base_url, api_key_env=seed.api_key_env, local=seed.local,
                         protected=seed.protected, enabled=not seed.protected, meta=seed.meta)
            session.add(m)
            await session.flush()  # o perfil referencia o modelo (sem relationship no ORM)
        elif seed.protected:
            # configuração-base do modelo protegido não muda pela interface
            m.nome, m.provider, m.model, m.base_url = seed.nome, seed.provider, seed.model, seed.base_url
            m.api_key_env, m.local, m.protected, m.meta = None, True, True, seed.meta
        if seed.protected:
            # o modelo local é opcional na instalação (perfil local-llm do Compose)
            m.enabled = get_settings().local_llm_enabled
        p = profiles.get(seed.profile_slug)
        if p is None:
            is_default = seed.protected and not has_default
            p = InferenceProfile(id=uuid.uuid4(), model_id=m.id, slug=seed.profile_slug, nome=seed.profile_nome,
                                 params=seed.params, protected=seed.protected, is_default=is_default, enabled=True)
            session.add(p)
            has_default = has_default or is_default
        elif seed.protected:
            p.model_id, p.nome, p.params, p.protected, p.enabled = m.id, seed.profile_nome, seed.params, True, True
    await session.flush()


def key_configured(model: LlmModel) -> bool:
    """Se o modelo pode ser usado: chave presente no ambiente (nunca expõe o valor) ou local ligado."""
    if model.local:
        return model.enabled
    keys = model.meta.get("chaves") if model.provider == "baml-named" else [model.api_key_env]
    return any(k and os.environ.get(k) for k in keys or [])


async def list_profiles(session: AsyncSession, only_enabled: bool = True) -> list[tuple[InferenceProfile, LlmModel]]:
    q = select(InferenceProfile, LlmModel).join(LlmModel, LlmModel.id == InferenceProfile.model_id)
    if only_enabled:
        q = q.where(InferenceProfile.enabled, LlmModel.enabled)
    rows = (await session.execute(q)).all()
    # padrão primeiro, depois locais, depois por nome
    return sorted(((p, m) for p, m in rows), key=lambda r: (not r[0].is_default, not r[1].local, r[0].nome))


def usable(p: InferenceProfile, m: LlmModel) -> bool:
    return p.enabled and m.enabled


async def effective_default_slug(session: AsyncSession) -> str:
    """O perfil marcado como padrão (inicialmente o local), se utilizável; senão, a nuvem com reserva."""
    row = (await session.execute(
        select(InferenceProfile, LlmModel).join(LlmModel, LlmModel.id == InferenceProfile.model_id)
        .where(InferenceProfile.is_default))).first()
    return row[0].slug if row and usable(*row) else CLOUD_FALLBACK_PROFILE


async def ollama_digest(model: LlmModel) -> str | None:
    """Versão dos pesos do modelo local (digest do Ollama), para auditoria. Falha silenciosa."""
    if model.provider != "ollama" or not model.base_url:
        return None
    root = model.base_url.removesuffix("/v1")
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"{root}/api/tags")
            r.raise_for_status()
        for m in r.json().get("models", []):
            if m.get("name") in (model.model, f"{model.model}:latest"):
                return m.get("digest")
    except (httpx.HTTPError, ValueError):
        return None
    return None


async def resolve_profile(session: AsyncSession, profile_id: uuid.UUID | None) -> dict:
    """Resolve o perfil (ou o padrão) e devolve o snapshot congelado na execução."""
    await ensure_catalog(session)
    q = select(InferenceProfile, LlmModel).join(LlmModel, LlmModel.id == InferenceProfile.model_id)
    if profile_id:
        row = (await session.execute(q.where(InferenceProfile.id == profile_id))).first()
    else:
        row = (await session.execute(q.where(InferenceProfile.slug == await effective_default_slug(session)))).first()
    if row is None:
        raise LookupError("Perfil de modelo inexistente.")
    p, m = row
    if not usable(p, m):
        if m.local and not get_settings().local_llm_enabled:
            raise LookupError("O modelo local está desligado nesta instalação (LOCAL_LLM_ENABLED=false).")
        raise LookupError(f"O perfil '{p.nome}' está desabilitado.")
    return await snapshot_of(p, m)


async def snapshot_of(p: InferenceProfile, m: LlmModel) -> dict:
    return {
        "profile_id": str(p.id), "profile_slug": p.slug, "profile_nome": p.nome,
        "model_slug": m.slug, "provider": m.provider, "base_url": m.base_url, "model": m.model,
        "params": dict(p.params), "api_key_env": m.api_key_env, "local": m.local,
        "model_digest": await ollama_digest(m),
        "resolved_at": datetime.now(UTC).isoformat(),
    }


def client_options(snapshot: dict) -> tuple[str, dict]:
    """Converte o snapshot em (provider BAML, opções) para o ClientRegistry.

    `think` e `num_ctx` não são enviados: a variante local já é criada com contexto fixo e o
    Qwen3 4B Instruct-2507 não tem modo de raciocínio (cap. 14 §14.2).
    """
    provider = snapshot["provider"]
    params = snapshot.get("params") or {}
    key = os.environ.get(snapshot["api_key_env"]) if snapshot.get("api_key_env") else None
    opts: dict = {"model": snapshot["model"]}
    if provider in ("ollama", "openai-generic"):
        opts["base_url"] = snapshot["base_url"]
        opts["api_key"] = key or "sem-chave"
        provider = "openai-generic"
    elif key:
        opts["api_key"] = key
    if provider == "google-ai":
        if "temperature" in params:
            opts["generationConfig"] = {"temperature": params["temperature"]}
    else:
        for name in ("temperature", "max_tokens"):
            if name in params:
                opts[name] = params[name]
    return provider, opts
