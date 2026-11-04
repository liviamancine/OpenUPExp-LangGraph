"""Gabaritos do laboratório: emparelhamento dos itens gerados com os itens de referência.

Emparelhamento guloso 1:1 por similaridade textual (maior entre a razão de SequenceMatcher e a
fração das palavras do item de referência presentes no item gerado), com limiar 0,6. É uma
aproximação mecânica e transparente: a tela mostra cada par para conferência humana. O cap. 09
§9.4 prevê emparelhamento humano ou por LLM-juiz calibrado; este é o primeiro nível.
"""

import re
import unicodedata
from difflib import SequenceMatcher

from openupexp.agents.registry import ARTIFACT_TYPES

THRESHOLD = 0.6
_ID = re.compile(r"\b[A-Z]{2,5}-\d+\b")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", _ID.sub(" ", text or "")).encode("ascii", "ignore").decode().lower()
    return " ".join(re.findall(r"[a-z0-9]+", text))


def similarity(gold: str, out: str) -> float:
    g, o = normalize(gold), normalize(out)
    if not g or not o:
        return 0.0
    words = [w for w in g.split() if len(w) > 2] or g.split()
    contained = sum(1 for w in words if w in o.split()) / len(words)
    return max(SequenceMatcher(None, g, o).ratio(), contained)


def item_text(artifact_type: str, item: dict) -> str:
    at = ARTIFACT_TYPES.get(artifact_type)
    text = at.text_of(item) if at else ""
    return text if normalize(text) else " ".join(str(v) for v in item.values() if isinstance(v, str))


def score(gold_items: list[str], outputs: list[dict], artifact_type: str) -> dict:
    out_texts = [item_text(artifact_type, it) for it in outputs]
    pairs = sorted(((similarity(g, o), gi, oi) for gi, g in enumerate(gold_items) for oi, o in enumerate(out_texts)),
                   reverse=True)
    used_g, used_o, matches = set(), set(), []
    for sim, gi, oi in pairs:
        if sim < THRESHOLD:
            break
        if gi in used_g or oi in used_o:
            continue
        used_g.add(gi)
        used_o.add(oi)
        matches.append({"gabarito": gold_items[gi], "gerado": out_texts[oi], "similaridade": round(sim, 2)})
    tp = len(matches)
    precision = tp / len(out_texts) if out_texts else 0.0
    recall = tp / len(gold_items) if gold_items else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precisao": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3),
        "acertos": tp, "gerados": len(out_texts), "esperados": len(gold_items), "pares": matches,
        "nao_encontrados": [g for i, g in enumerate(gold_items) if i not in used_g],
        "sem_correspondencia": [o for i, o in enumerate(out_texts) if i not in used_o],
    }


def score_output(output: list[dict], gold) -> dict | None:
    """Pontua a saída (lista de artefatos de uma tentativa) contra o gabarito do artefato."""
    if gold is None or not gold.itens:
        return None
    at = ARTIFACT_TYPES.get(gold.artifact_type)
    for o in output:
        if o["artifact"] == gold.artifact_type and at and at.list_field:
            return score(gold.itens, o["content"].get(at.list_field) or [], gold.artifact_type)
    return score(gold.itens, [], gold.artifact_type)
