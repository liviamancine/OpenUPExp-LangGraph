"""Administração de modelos e perfis (cap. 14 §14.4): validação, cadastro, conexão e compatibilidade.

Regras de segurança:
- só servidores da lista LLM_ALLOWED_HOSTS recebem conteúdo dos projetos;
- `api_key_env` só aceita nomes de variáveis de chave (`*_API_KEY` / `*_TOKEN`), para que um
  cadastro não envie outro segredo do servidor (ex.: JWT_SECRET) a um endereço externo;
- o modelo local protegido não é editável nem excluível;
- um perfil só é habilitado depois de passar no teste de compatibilidade.
"""

import os
import re
import time
import uuid
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openupexp.config import get_settings
from openupexp.db.models import InferenceProfile, LlmModel
from openupexp.domain.events import audit
from openupexp.llm.catalog import client_options, key_configured, snapshot_of

PROVIDERS = {
    "ollama": "Ollama (local ou em outro servidor)",
    "openai-generic": "Compatível com a API da OpenAI (vLLM, Groq, LM Studio…)",
    "openai": "OpenAI (Chat Completions)",
    "openai-responses": "OpenAI (Responses)",
    "anthropic": "Anthropic",
    "google-ai": "Google AI (Gemini)",
}
# provedores com endereço fixo
FIXED_URL = {
    "openai": "https://api.openai.com/v1",
    "openai-responses": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "google-ai": "https://generativelanguage.googleapis.com/v1beta",
}
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{1,60}$")
KEY_ENV = re.compile(r"^[A-Z][A-Z0-9_]{0,60}_(API_KEY|TOKEN)$")
PARAMS = {"temperature": (float, 0.0, 2.0), "max_tokens": (int, 1, 200_000), "num_ctx": (int, 512, 262_144),
          "think": (bool, None, None)}

# Entrada fixa e neutra de domínio para o teste de compatibilidade.
COMPAT_SCOPE = (
    "ESCOPO DO PROJETO - Sistema de apoio a decisões. Um órgão público usa um sistema que recomenda aprovar "
    "ou negar solicitações. O analista confirma a recomendação. O solicitante precisa entender o motivo da "
    "decisão para poder recorrer. O auditor precisa verificar os critérios usados pelo sistema."
)


class AdminError(Exception):
    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status


DEFAULT_ALLOWED_HOSTS = ("ollama,localhost,127.0.0.1,host.docker.internal,api.groq.com,api.openai.com,"
                         "api.anthropic.com,generativelanguage.googleapis.com")


def allowed_hosts() -> list[str]:
    raw = get_settings().llm_allowed_hosts.strip() or DEFAULT_ALLOWED_HOSTS
    return [h.strip().lower() for h in raw.split(",") if h.strip()]


def host_allowed(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in allowed_hosts())


def endpoint(model: LlmModel) -> str | None:
    return FIXED_URL.get(model.provider) or model.base_url


def _validate_model_fields(data: dict, provider: str) -> dict:
    out = {}
    if "nome" in data:
        if not (data["nome"] or "").strip():
            raise AdminError("Informe um nome.")
        out["nome"] = data["nome"].strip()[:120]
    if "model" in data:
        if not (data["model"] or "").strip():
            raise AdminError("Informe o identificador do modelo no provedor.")
        out["model"] = data["model"].strip()[:160]
    if "base_url" in data:
        url = (data["base_url"] or "").strip().rstrip("/") or None
        if provider in ("ollama", "openai-generic"):
            if not url or urlparse(url).scheme not in ("http", "https"):
                raise AdminError("Informe o endereço do servidor (http:// ou https://).")
            if not host_allowed(url):
                raise AdminError(f"Servidor '{urlparse(url).hostname}' fora da lista permitida (LLM_ALLOWED_HOSTS). "
                                 "Peça ao responsável pela instalação para incluí-lo.", 403)
            if provider == "ollama" and not url.endswith("/v1"):
                url += "/v1"
        else:
            url = None
        out["base_url"] = url
    if "api_key_env" in data:
        env = (data["api_key_env"] or "").strip() or None
        if env and not KEY_ENV.match(env):
            raise AdminError("A variável da chave deve terminar em _API_KEY ou _TOKEN (ex.: MISTRAL_API_KEY).")
        if not env and provider not in ("ollama", "openai-generic"):
            raise AdminError("Este provedor exige a variável de ambiente com a chave.")
        out["api_key_env"] = env
    return out


def validate_params(params: dict) -> dict:
    out = {}
    for k, v in (params or {}).items():
        if k not in PARAMS:
            raise AdminError(f"Parâmetro desconhecido: {k}.")
        typ, lo, hi = PARAMS[k]
        try:
            v = typ(v) if typ is not bool else bool(v)
        except (TypeError, ValueError) as exc:
            raise AdminError(f"Valor inválido para {k}.") from exc
        if lo is not None and not (lo <= v <= hi):
            raise AdminError(f"{k} deve estar entre {lo} e {hi}.")
        out[k] = v
    return out


def _protected(obj) -> None:
    if obj.protected:
        raise AdminError("O modelo local de referência é protegido e não pode ser alterado nem excluído.", 403)


async def create_model(session: AsyncSession, data: dict, user_id: uuid.UUID) -> LlmModel:
    provider = data.get("provider")
    if provider not in PROVIDERS:
        raise AdminError("Provedor não suportado.")
    slug = (data.get("slug") or "").strip()
    if not SLUG.match(slug):
        raise AdminError("Identificador inválido: use letras minúsculas, números e hífens.")
    if await session.scalar(select(LlmModel).where(LlmModel.slug == slug)):
        raise AdminError("Já existe um modelo com este identificador.", 409)
    fields = _validate_model_fields({"base_url": None, "api_key_env": None, **data}, provider)
    m = LlmModel(id=uuid.uuid4(), slug=slug, provider=provider, local=False, protected=False, enabled=True,
                 meta={"criado_pela_administracao": True}, **fields)
    session.add(m)
    await session.flush()
    # perfil inicial, desabilitado até passar no teste de compatibilidade
    session.add(InferenceProfile(id=uuid.uuid4(), model_id=m.id, slug=f"{slug}-padrao", nome=f"{m.nome} · padrão",
                                 params=validate_params(data.get("params") or {"temperature": 0.0}),
                                 protected=False, is_default=False, enabled=False, checks={}))
    await session.flush()
    await audit(session, "user", str(user_id), "llm_model_create", "llm_model", str(m.id),
                provider=provider, model=m.model, base_url=m.base_url, api_key_env=m.api_key_env)
    return m


async def update_model(session: AsyncSession, model_id: uuid.UUID, data: dict, user_id: uuid.UUID) -> LlmModel:
    m = await _model(session, model_id)
    _protected(m)
    before = {"model": m.model, "base_url": m.base_url, "api_key_env": m.api_key_env, "enabled": m.enabled}
    for k, v in _validate_model_fields({k: v for k, v in data.items() if k != "enabled"}, m.provider).items():
        setattr(m, k, v)
    if "enabled" in data:
        m.enabled = bool(data["enabled"])
    if (m.model, m.base_url) != (before["model"], before["base_url"]):
        # mudou o que é chamado: os testes anteriores deixam de valer
        for p in await _profiles(session, m.id):
            p.checks, p.enabled = {}, False
    await session.flush()
    await audit(session, "user", str(user_id), "llm_model_update", "llm_model", str(m.id), antes=before,
                depois={"model": m.model, "base_url": m.base_url, "api_key_env": m.api_key_env, "enabled": m.enabled})
    return m


async def delete_model(session: AsyncSession, model_id: uuid.UUID, user_id: uuid.UUID) -> None:
    m = await _model(session, model_id)
    _protected(m)
    if any(p.is_default for p in await _profiles(session, m.id)):
        raise AdminError("Este modelo tem o perfil padrão. Escolha outro padrão antes de excluí-lo.", 409)
    await audit(session, "user", str(user_id), "llm_model_delete", "llm_model", str(m.id), slug=m.slug)
    await session.delete(m)
    await session.flush()


async def create_profile(session: AsyncSession, model_id: uuid.UUID, data: dict, user_id: uuid.UUID) -> InferenceProfile:
    m = await _model(session, model_id)
    _protected(m)
    slug = (data.get("slug") or "").strip()
    if not SLUG.match(slug):
        raise AdminError("Identificador inválido: use letras minúsculas, números e hífens.")
    if await session.scalar(select(InferenceProfile).where(InferenceProfile.slug == slug)):
        raise AdminError("Já existe um perfil com este identificador.", 409)
    p = InferenceProfile(id=uuid.uuid4(), model_id=m.id, slug=slug, nome=(data.get("nome") or slug).strip()[:120],
                         params=validate_params(data.get("params") or {}), protected=False, is_default=False,
                         enabled=False, checks={})
    session.add(p)
    await session.flush()
    await audit(session, "user", str(user_id), "inference_profile_create", "inference_profile", str(p.id),
                params=p.params)
    return p


async def update_profile(session: AsyncSession, profile_id: uuid.UUID, data: dict, user_id: uuid.UUID) -> InferenceProfile:
    p = await _profile(session, profile_id)
    _protected(p)
    if "nome" in data:
        p.nome = (data["nome"] or p.nome).strip()[:120]
    if "params" in data:
        new = validate_params(data["params"])
        if new != p.params:
            p.params, p.checks, p.enabled = new, {}, False
    if "enabled" in data:
        if data["enabled"] and not (p.checks.get("compat") or {}).get("ok"):
            raise AdminError("Teste a compatibilidade do perfil antes de habilitá-lo.", 409)
        if not data["enabled"] and p.is_default:
            raise AdminError("Escolha outro perfil padrão antes de desabilitar este.", 409)
        p.enabled = bool(data["enabled"])
    await session.flush()
    await audit(session, "user", str(user_id), "inference_profile_update", "inference_profile", str(p.id),
                params=p.params, enabled=p.enabled)
    return p


async def delete_profile(session: AsyncSession, profile_id: uuid.UUID, user_id: uuid.UUID) -> None:
    p = await _profile(session, profile_id)
    _protected(p)
    if p.is_default:
        raise AdminError("Escolha outro perfil padrão antes de excluir este.", 409)
    await audit(session, "user", str(user_id), "inference_profile_delete", "inference_profile", str(p.id), slug=p.slug)
    await session.delete(p)
    await session.flush()


async def set_default(session: AsyncSession, profile_id: uuid.UUID, user_id: uuid.UUID) -> InferenceProfile:
    p = await _profile(session, profile_id)
    m = await _model(session, p.model_id)
    if not (p.enabled and m.enabled):
        raise AdminError("Só um perfil habilitado pode ser o padrão.", 409)
    for other in (await session.scalars(select(InferenceProfile).where(InferenceProfile.is_default))).all():
        other.is_default = False
    await session.flush()
    p.is_default = True
    await session.flush()
    await audit(session, "user", str(user_id), "inference_profile_default", "inference_profile", str(p.id), slug=p.slug)
    return p


async def _model(session: AsyncSession, model_id: uuid.UUID) -> LlmModel:
    m = await session.get(LlmModel, model_id)
    if m is None:
        raise AdminError("Modelo inexistente.", 404)
    return m


async def _profile(session: AsyncSession, profile_id: uuid.UUID) -> InferenceProfile:
    p = await session.get(InferenceProfile, profile_id)
    if p is None:
        raise AdminError("Perfil inexistente.", 404)
    return p


async def _profiles(session: AsyncSession, model_id: uuid.UUID) -> list[InferenceProfile]:
    return list((await session.scalars(select(InferenceProfile).where(InferenceProfile.model_id == model_id))).all())


# ---------------------------------------------------------------------------
# Teste de conexão: lista os modelos do servidor (não envia conteúdo de projetos)
# ---------------------------------------------------------------------------


async def test_connection(session: AsyncSession, model_id: uuid.UUID, user_id: uuid.UUID) -> dict:
    m = await _model(session, model_id)
    started = time.perf_counter()
    result: dict = {"at": datetime.now(UTC).isoformat()}
    if m.provider == "baml-named":
        keys = m.meta.get("chaves") or []
        result.update(ok=key_configured(m), detalhe="Perfil composto: depende das chaves " + ", ".join(keys),
                      chaves={k: bool(os.environ.get(k)) for k in keys})
    else:
        url = endpoint(m)
        key = os.environ.get(m.api_key_env) if m.api_key_env else None
        try:
            if not url or not host_allowed(url):
                raise AdminError(f"Servidor fora da lista permitida: {urlparse(url or '').hostname}.", 403)
            if m.api_key_env and not key:
                raise AdminError(f"A variável {m.api_key_env} não está configurada no servidor.")
            names = await _list_remote_models(m.provider, url, key)
            wanted = m.model.split(":")[0] if m.provider == "ollama" else m.model
            found = any(n == m.model or n.split(":")[0] == wanted or n.endswith("/" + m.model) for n in names)
            result.update(ok=True, modelos=names[:40], modelo_encontrado=found,
                          detalhe="Conectado." if found else "Conectado, mas o modelo não aparece na lista do servidor.")
        except AdminError as exc:
            result.update(ok=False, detalhe=str(exc))
        except (httpx.HTTPError, ValueError) as exc:
            result.update(ok=False, detalhe=f"Falha na conexão: {type(exc).__name__}: {str(exc)[:200]}")
    result["latency_ms"] = int((time.perf_counter() - started) * 1000)
    m.meta = {**m.meta, "conexao": result}
    await session.flush()
    await audit(session, "user", str(user_id), "llm_model_test_connection", "llm_model", str(m.id), ok=result["ok"])
    return result


async def _list_remote_models(provider: str, url: str, key: str | None) -> list[str]:
    headers = {}
    async with httpx.AsyncClient(timeout=10.0) as client:
        if provider == "ollama":
            r = await client.get(f"{url.removesuffix('/v1')}/api/tags")
            r.raise_for_status()
            return [x["name"] for x in r.json().get("models", [])]
        if provider == "anthropic":
            headers = {"x-api-key": key or "", "anthropic-version": "2023-06-01"}
        elif provider == "google-ai":
            headers = {"x-goog-api-key": key or ""}
        elif key:
            headers = {"Authorization": f"Bearer {key}"}
        r = await client.get(f"{url}/models", headers=headers)
        r.raise_for_status()
        data = r.json()
        rows = data.get("data") or data.get("models") or []
        return [str(x.get("id") or x.get("name", "")).removeprefix("models/") for x in rows]


# ---------------------------------------------------------------------------
# Teste de compatibilidade: uma função BAML curta, com entrada fixa, pelo caminho do worker
# ---------------------------------------------------------------------------


async def request_compat_test(session: AsyncSession, profile_id: uuid.UUID, user_id: uuid.UUID) -> dict:
    from openupexp.queue.jobs import enqueue

    p = await _profile(session, profile_id)
    p.checks = {**p.checks, "compat": {"status": "na_fila", "at": datetime.now(UTC).isoformat()}}
    await enqueue(session, "llm.compat", {"profile_id": str(p.id)})
    await audit(session, "user", str(user_id), "inference_profile_test_compat", "inference_profile", str(p.id))
    return p.checks["compat"]


async def default_compat_call(snapshot: dict) -> tuple[object, dict]:
    """Chama DefineExplainabilityProblem pelo mesmo ClientRegistry do worker."""
    from baml_py import Collector

    from openupexp.agents.gateway import BamlGateway
    from openupexp.baml_client import types as T
    from openupexp.baml_client.async_client import b

    collector = Collector(name="compat")
    out = await b.DefineExplainabilityProblem(T.DefineProblemInput(documento_escopo=COMPAT_SCOPE), [],
                                              baml_options=BamlGateway(snapshot)._options(collector))
    usage = collector.last.usage if collector.last else None
    return out, {"input_tokens": getattr(usage, "input_tokens", None),
                 "output_tokens": getattr(usage, "output_tokens", None)}


async def run_compat_test(session: AsyncSession, profile_id: uuid.UUID, call=default_compat_call) -> dict:
    from openupexp.observability.llm import baml_src_sha

    p = await _profile(session, profile_id)
    m = await _model(session, p.model_id)
    snapshot = await snapshot_of(p, m)
    started = time.perf_counter()
    result: dict = {"at": datetime.now(UTC).isoformat(), "funcao": "DefineExplainabilityProblem",
                    "baml_src_sha": baml_src_sha(), "model_digest": snapshot.get("model_digest")}
    try:
        if snapshot["provider"] not in ("baml-named",):
            client_options(snapshot)  # falha cedo se a configuração não monta um cliente
        out, usage = await call(snapshot)
        stakeholders = getattr(out, "stakeholders_mencionados", None) or []
        ok = bool(stakeholders)
        result.update(status="concluido", ok=ok, **usage,
                      detalhe=(f"Saída aceita pelo contrato; {len(stakeholders)} stakeholder(s) identificados."
                               if ok else "Saída aceita pelo contrato, mas nenhum stakeholder foi identificado."))
    except Exception as exc:  # noqa: BLE001 — qualquer falha do provedor ou do parser reprova o perfil
        result.update(status="concluido", ok=False, detalhe=f"{type(exc).__name__}: {str(exc)[:300]}")
    result["latency_ms"] = int((time.perf_counter() - started) * 1000)
    p.checks = {**p.checks, "compat": result}
    await session.flush()
    return result
