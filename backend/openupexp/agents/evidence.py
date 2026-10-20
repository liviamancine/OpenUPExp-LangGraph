"""Verificação mecânica das evidências devolvidas pelos agentes (cap. 05 §5.6)."""

import re
import uuid
from typing import Callable

from openupexp.retrieval.citations import verify_quote

_ITEM_ID = re.compile(r"^[A-Z]{2,4}-\d+$")


def normalize_ref(ref: str | None) -> str:
    """Primeiro token da referência; chunks sem prefixo recebem 'chunk:'. IDs de item (SN-01) ficam."""
    ref = (ref or "").split()[0] if (ref or "").strip() else ""
    if ref and not ref.startswith("chunk:") and not _ITEM_ID.match(ref):
        ref = f"chunk:{ref}"
    return ref


def verify_item_evidences(
    raw: list[dict],
    sources: dict[str, tuple[str, uuid.UUID | None]],
    *,
    ref_key: str = "chunk_ref",
    kind_of: Callable[[dict], str] = lambda ev: str(ev.get("tipo")),
) -> list[tuple[int, dict]]:
    """Confere cada citação contra o texto da fonte entregue ao agente.

    sources: referência -> (texto da fonte, chunk_id ou None). Marca em cada evidência o
    resultado (verified | unverified_quote | source_not_provided) e, no item,
    fundamentacao_verificada. Devolve as evidências por posição do item para persistência.
    """
    pending: list[tuple[int, dict]] = []
    for idx, item in enumerate(raw):
        verified_any = False
        for ev in item.get("evidencias", []):
            ref = normalize_ref(ev.get(ref_key))
            source = sources.get(ref)
            if source is None:
                verification = "source_not_provided"
            elif verify_quote(ev.get("citacao", ""), source[0]):
                verification = "verified"
                verified_any = True
            else:
                verification = "unverified_quote"
            ev[ref_key] = ref or ev.get(ref_key)
            ev["verificacao"] = verification
            pending.append((idx, {"chunk_ref": ev[ref_key], "chunk_id": source[1] if source else None,
                                  "citacao": ev.get("citacao", ""), "tipo": kind_of(ev),
                                  "verificacao": verification}))
        item["fundamentacao_verificada"] = verified_any
    return pending
