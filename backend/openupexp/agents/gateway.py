"""Gateway de agentes: único ponto onde funções BAML são chamadas.

- BamlGateway: LLM real, com Collector (observabilidade) e ClientRegistry (perfil por execução).
- FakeGateway: saídas determinísticas derivadas das entradas (testes e modo simulado).
"""

import json
import time
import uuid
from typing import Protocol

from baml_py import ClientRegistry, Collector
from pydantic import BaseModel

from openupexp.baml_client.types import ContextItem
from openupexp.observability.llm import record_llm_call


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
        client = self.profile.get("client")
        if client:
            # Experimentos: força um único cliente nomeado (sem fallback silencioso).
            cr = ClientRegistry()
            cr.set_primary(client)
            opts["client_registry"] = cr
        return opts

    async def call(self, function, entrada, contexto, *, run_id, task_execution_id):
        from openupexp.baml_client.async_client import b

        collector = Collector(name=f"{run_id}:{function}")
        fn = getattr(b, function)
        try:
            result = await fn(entrada, contexto, baml_options=self._options(collector))
        except Exception as exc:
            await record_llm_call(
                run_id=run_id, task_execution_id=task_execution_id, function=function,
                log=collector.last, status="error", error=f"{type(exc).__name__}: {exc}"[:4000],
            )
            raise
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
