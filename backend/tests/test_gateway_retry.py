"""Novas tentativas quando o provedor de IA está sobrecarregado (503) ou no limite por minuto (429)."""

import uuid

from openupexp.agents import gateway as gw
from openupexp.agents.gateway import BamlGateway, wait_before_retry


class ProviderError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


# mensagens reais dos provedores (execuções de 29/10 e 03/11/2026)
GROQ_429 = ('Request failed with status code: 429 Too Many Requests. {"error":{"message":"Rate limit reached '
            'for model `openai/gpt-oss-20b` in organization `org_x` service tier `on_demand` on tokens per minute '
            '(TPM): Limit 8000, Used 6437, Requested 3425. Please try again in 13.965s. Need more tokens? Upgrade to '
            'Dev Tier today at https://console.groq.com/settings/billing","type":"tokens","code":"rate_limit_exceeded"}}')
GEMINI_503 = ('Request failed with status code: 503 Service Unavailable. {"error":{"code":503,"message":"This model '
              'is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.",'
              '"status":"UNAVAILABLE"}}')
OPENAI_NO_CREDIT = ('Request failed with status code: 429 Too Many Requests. {"error":{"message":"You have no credits '
                    'remaining. Add credits to continue using the API at https://platform.openai.com/settings/'
                    'organization/billing/.","type":"insufficient_quota","param":null,"code":"credit_balance_exhausted"}}')


def test_waits_what_the_provider_asks_for():
    assert round(wait_before_retry(ProviderError(429, GROQ_429), 0), 1) == 15.0  # 13.965 s + 1 s de folga
    assert wait_before_retry(ProviderError(429, "Please try again in 1m30s."), 0) == 60.0  # teto
    assert wait_before_retry(ProviderError(503, GEMINI_503), 0) == 15
    assert wait_before_retry(ProviderError(503, GEMINI_503), 1) == 30


def test_does_not_wait_when_waiting_cannot_help():
    assert wait_before_retry(ProviderError(429, OPENAI_NO_CREDIT), 0) is None
    assert wait_before_retry(ProviderError(401, "x-api-key header is required"), 0) is None
    assert wait_before_retry(ValueError("resposta fora do contrato"), 0) is None
    assert wait_before_retry(ProviderError(503, GEMINI_503), 5) is None  # esgotou as tentativas


class BamlValidationError(Exception):
    pass


def test_empty_model_answer_is_retried_twice():
    empty = BamlValidationError("BamlValidationError(message=Failed to parse LLM response: Failed to coerce value: "
                                "[InferedObject(String(\"\", Complete))], raw_output=, prompt=system: ...")
    assert [wait_before_retry(empty, n) for n in range(3)] == [5.0, 5.0, None]
    bad = BamlValidationError("BamlValidationError(message=Failed to parse LLM response, raw_output={\"x\": 1}, prompt=...")
    assert wait_before_retry(bad, 0) is None  # resposta fora do contrato: repetir não ajuda


async def test_call_retries_after_waiting(monkeypatch):
    from openupexp.baml_client.async_client import b

    calls, waits = [], []

    async def flaky(entrada, contexto, baml_options):
        calls.append(1)
        if len(calls) < 3:
            raise ProviderError(429, GROQ_429)
        return "ok"

    async def no_record(**kwargs):
        return None

    async def fake_sleep(seconds):
        waits.append(seconds)

    monkeypatch.setattr(b, "DefineExplainability", flaky)
    monkeypatch.setattr(gw, "record_llm_call", no_record)
    monkeypatch.setattr(gw.asyncio, "sleep", fake_sleep)
    out = await BamlGateway({}).call("DefineExplainability", None, [], run_id=uuid.uuid4(), task_execution_id=None)
    assert out == "ok" and len(calls) == 3 and [round(w) for w in waits] == [15, 15]
