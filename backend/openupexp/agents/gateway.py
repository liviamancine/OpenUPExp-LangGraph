"""Gateway de agentes: único ponto onde funções BAML são chamadas.

- BamlGateway: LLM real, com Collector (observabilidade) e ClientRegistry (perfil por execução).
- FakeGateway: saídas determinísticas derivadas das entradas (testes e modo simulado).
"""

import asyncio
import json
import logging
import re
import time
import uuid
from typing import Protocol

from baml_py import ClientRegistry, Collector
from pydantic import BaseModel

from openupexp.baml_client.types import ContextItem
from openupexp.config import get_settings
from openupexp.observability.llm import record_llm_call

log = logging.getLogger("openupexp.gateway")

# Esperar não resolve falta de crédito nem chave inválida, mesmo quando o provedor responde 429.
# A cota diária do plano gratuito (ex.: Gemini, 20 chamadas por dia) também: só volta horas depois.
_PERMANENT = re.compile(r"insufficient_quota|credit_balance|invalid.?api.?key|per ?day|PerDay", re.IGNORECASE)
_RETRY_AFTER = re.compile(r"try again in\s+(?:(\d+)m)?\s*([\d.]+)\s*s", re.IGNORECASE)


def wait_before_retry(exc: Exception, attempt: int) -> float | None:
    """Segundos a esperar antes de repetir a chamada, ou None se não vale repetir.

    Repete só erro passageiro do provedor (429 limite por minuto, 503 sobrecarga), pelo tempo
    que ele pedir ("try again in 13.9s"); sem indicação, 15 s, 30 s, 60 s...
    """
    settings = get_settings()
    status = getattr(exc, "status_code", None)
    text = str(exc)
    # resposta vazia (o modelo "pensou" e não escreveu): passageiro, repetir costuma resolver
    if type(exc).__name__ == "BamlValidationError" and re.search(r"raw_output=\s*,", text):
        return 5.0 if attempt < 2 else None
    if status not in (429, 503) or _PERMANENT.search(text) or attempt >= settings.llm_wait_retries:
        return None
    asked = _RETRY_AFTER.search(text)
    seconds = (int(asked.group(1) or 0) * 60 + float(asked.group(2)) + 1) if asked else 15 * 2 ** attempt
    return min(seconds, settings.llm_max_wait_seconds)


class AgentGateway(Protocol):
    name: str

    async def call(
        self,
        function: str,
        entrada: BaseModel,
        contexto: list[ContextItem],
        *,
        run_id: uuid.UUID,
        task_execution_id: uuid.UUID | None,
    ) -> BaseModel: ...


class BamlGateway:
    name = "baml"

    def __init__(self, model_profile: dict | None = None):
        self.profile = model_profile or {}

    def _options(self, collector: Collector) -> dict:
        opts: dict = {"collector": collector}
        provider = self.profile.get("provider")
        if provider == "baml-named":
            # perfil que aponta para um cliente de clients.baml (ex.: fallback entre famílias)
            cr = ClientRegistry()
            cr.set_primary(self.profile["model"])
            opts["client_registry"] = cr
        elif provider:
            # perfil cadastrado (cap. 14): um único modelo, sem fallback silencioso
            from openupexp.llm.catalog import client_options

            name = f"Perfil_{self.profile.get('profile_slug', 'execucao').replace('-', '_')}"
            baml_provider, options = client_options(self.profile)
            cr = ClientRegistry()
            cr.add_llm_client(name, baml_provider, options, retry_policy="PadraoRetry")
            cr.set_primary(name)
            opts["client_registry"] = cr
        elif self.profile.get("client"):
            # Experimentos: força um único cliente nomeado (sem fallback silencioso).
            cr = ClientRegistry()
            cr.set_primary(self.profile["client"])
            opts["client_registry"] = cr
        return opts

    async def call(self, function, entrada, contexto, *, run_id, task_execution_id):
        from openupexp.baml_client.async_client import b

        fn = getattr(b, function)
        attempt = 0
        while True:
            collector = Collector(name=f"{run_id}:{function}")
            try:
                result = await fn(entrada, contexto, baml_options=self._options(collector))
                break
            except Exception as exc:
                await record_llm_call(
                    run_id=run_id, task_execution_id=task_execution_id, function=function,
                    log=collector.last, status="error", error=f"{type(exc).__name__}: {exc}"[:4000],
                )
                wait = wait_before_retry(exc, attempt)
                if wait is None:
                    raise
                attempt += 1
                log.warning("%s: provedor indisponível ou no limite (%s); nova tentativa %d em %.0f s",
                            function, getattr(exc, "status_code", "?"), attempt, wait)
                await asyncio.sleep(wait)
        await record_llm_call(
            run_id=run_id, task_execution_id=task_execution_id, function=function, log=collector.last,
        )
        return result


class FakeGateway:
    name = "fake"

    async def call(self, function, entrada, contexto, *, run_id, task_execution_id):
        from openupexp.agents import fake

        started = time.perf_counter()
        result = getattr(fake, function)(entrada, contexto)
        prompt_chars = len(entrada.model_dump_json()) + sum(len(c.conteudo) for c in contexto)
        await record_llm_call(
            run_id=run_id, task_execution_id=task_execution_id, function=function,
            client_name="Fake", provider="fake", model="fake-deterministic",
            usage={"input_tokens": prompt_chars // 4,
                   "output_tokens": len(json.dumps(result.model_dump(), ensure_ascii=False)) // 4},
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
        return result


def get_gateway(name: str, model_profile: dict | None = None) -> AgentGateway:
    if name == "fake":
        return FakeGateway()
    if name == "baml":
        return BamlGateway(model_profile)
    raise ValueError(f"gateway desconhecido: {name}")
