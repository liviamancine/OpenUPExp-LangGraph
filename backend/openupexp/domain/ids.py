"""Atribuição determinística de IDs estáveis (docs/architecture/08-contratos-baml.md §8.4)."""

import re
from difflib import SequenceMatcher

SIMILARITY_THRESHOLD = 0.85


def _num(key: str, prefix: str) -> int | None:
    m = re.fullmatch(rf"{re.escape(prefix)}-(\d+)", key or "")
    return int(m.group(1)) if m else None


def assign_keys(
    prefix: str,
    new_items: list[dict],
    existing: dict[str, dict],
    text_of,
) -> list[tuple[str, dict]]:
    """Atribui chaves PREFIX-n aos itens devolvidos pelo agente.

    1. ID devolvido que existe (e ainda não foi usado) é mantido.
    2. Sem ID válido, casa por similaridade de texto com um item existente.
    3. Caso contrário, recebe o próximo número livre.
    """
    used: set[str] = set()
    out: list[tuple[str, dict]] = []
    numbers = [n for k in existing if (n := _num(k, prefix)) is not None]
    next_n = max(numbers, default=0) + 1

    for item in new_items:
        key = item.get("id")
        if key not in existing or key in used:
            key = None
            text = text_of(item)
            best, best_score = None, 0.0
            for ek, ev in existing.items():
                if ek in used:
                    continue
                score = SequenceMatcher(None, text.lower(), text_of(ev).lower()).ratio()
                if score > best_score:
                    best, best_score = ek, score
            if best and best_score >= SIMILARITY_THRESHOLD:
                key = best
        if key is None:
            key = f"{prefix}-{next_n:02d}"
            next_n += 1
        used.add(key)
        item = dict(item, id=key)
        out.append((key, item))
    return out
