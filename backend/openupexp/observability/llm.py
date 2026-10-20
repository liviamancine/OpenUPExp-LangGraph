"""Registro das chamadas LLM a partir do Collector do BAML (docs/architecture/09 §9.1)."""

import hashlib
import re
import uuid
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select

from openupexp.db.models import LlmCall, ModelPrice
from openupexp.db.session import session_scope

BAML_SRC = Path(__file__).resolve().parents[2] / "baml_src"


@lru_cache
def baml_src_sha() -> str:
    h = hashlib.sha256()
    for f in sorted(BAML_SRC.glob("*.baml")):
        h.update(f.name.encode())
        h.update(f.read_bytes())
    return h.hexdigest()


@lru_cache
def prompt_hashes() -> dict[str, str]:
    """sha256 do bloco de cada função BAML (assinatura + prompt)."""
    out: dict[str, str] = {}
    for f in sorted(BAML_SRC.glob("*.baml")):
        src = f.read_text(encoding="utf-8")
        for m in re.finditer(r"(?ms)^function\s+(\w+)\s*\(.*?^}\s*$", src):
            out[m.group(1)] = hashlib.sha256(m.group(0).encode()).hexdigest()
    return out


def _model_of(call) -> str | None:
    try:
        return call.http_request.body.json().get("model")
    except Exception:
        return None


def _call_summary(call) -> dict:
    return {
        "client": getattr(call, "client_name", None),
        "provider": getattr(call, "provider", None),
        "selected": bool(getattr(call, "selected", False)),
        "model": _model_of(call),
    }


async def _price(session, provider: str | None, model: str | None):
    if not provider or not model:
        return None
    return await session.scalar(
        select(ModelPrice)
        .where(ModelPrice.provider == provider, ModelPrice.model == model)
        .order_by(ModelPrice.valid_from.desc())
        .limit(1)
    )


async def record_llm_call(
    *,
    run_id: uuid.UUID | None,
    task_execution_id: uuid.UUID | None,
    function: str,
    log=None,
    status: str = "ok",
    error: str | None = None,
    usage: dict | None = None,
    client_name: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    latency_ms: int | None = None,
) -> None:
    """Persiste uma chamada. `log` é o FunctionLog do Collector BAML (quando houver)."""
    chain: list[dict] = []
    in_tok = out_tok = cached = None
    raw = None
    if log is not None:
        calls = list(log.calls or [])
        chain = [_call_summary(c) for c in calls]
        selected = log.selected_call or (calls[-1] if calls else None)
        if selected is not None:
            client_name = selected.client_name
            provider = selected.provider
            model = _model_of(selected)
        if log.usage is not None:
            in_tok, out_tok = log.usage.input_tokens, log.usage.output_tokens
            cached = log.usage.cached_input_tokens
        if log.timing is not None:
            latency_ms = log.timing.duration_ms
        try:
            raw = log.raw_llm_response
        except Exception:
            raw = None
    if usage:
        in_tok, out_tok = usage.get("input_tokens"), usage.get("output_tokens")

    async with session_scope() as session:
        cost = None
        price = await _price(session, provider, model)
        if price is not None and in_tok is not None and out_tok is not None:
            cost = (Decimal(in_tok) * price.input_per_mtok + Decimal(out_tok) * price.output_per_mtok) / Decimal(
                1_000_000
            )
        session.add(
            LlmCall(
                run_id=run_id,
                task_execution_id=task_execution_id,
                baml_function=function,
                client_name=client_name,
                provider=provider,
                model=model,
                input_tokens=in_tok,
                output_tokens=out_tok,
                cached_input_tokens=cached,
                latency_ms=latency_ms,
                custo_usd=cost,
                status=status,
                fallback_chain=chain,
                prompt_sha256=prompt_hashes().get(function),
                raw_output=raw,
                error=error,
            )
        )
