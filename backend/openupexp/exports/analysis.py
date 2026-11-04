"""Renderização da parte da Fase 3 do ERD (análise dos requisitos) em Markdown."""

from openupexp.agents.registry import ANALYSIS_EDITABLE, ARTIFACT_TYPES
from openupexp.exports.vision import _env

TEMPLATE_VERSION = "analise-0.1-provisorio"
MOSCOW_LEVELS = [("MUST", "Must have"), ("SHOULD", "Should have"), ("COULD", "Could have"),
                 ("WONT", "Won't have (por ora)")]


def _by_req(contents: dict, atype: str) -> dict[str, dict]:
    field = ARTIFACT_TYPES[atype].list_field
    return {i.get("req_id"): i for i in (contents.get(atype) or {}).get(field, [])}


def _lacunas(contents: dict[str, dict]) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    for atype in ANALYSIS_EDITABLE:
        at = ARTIFACT_TYPES[atype]
        for item in (contents.get(atype) or {}).get(at.list_field, []):
            out += [(f"{at.title} {item.get('req_id') or item.get('id')}", lac) for lac in item.get("lacunas") or []]
    return out


def render_analysis_markdown(contents: dict[str, dict], base: dict[str, dict], meta: dict,
                             consensus: list[dict] | None = None) -> str:
    reqs = [r for r in (base.get("requirements.consolidated") or {}).get("requisitos", [])
            if r.get("tipo") == "EXPLICABILIDADE"]
    parts = {key: _by_req(contents, f"analysis.{name}") for key, name in [
        ("char", "characterized"), ("asp", "aspects"), ("map", "explanation_types"),
        ("dep", "dependencies"), ("fea", "feasibility"), ("prio", "priorities")]}
    refined = [{"req": r, **{k: v.get(r["id"]) or {} for k, v in parts.items()}} for r in reqs]
    for item in refined:
        item["prio"] = item["prio"] or None
    moscow: dict[str, list[str]] = {}
    for rid, p in parts["prio"].items():
        moscow.setdefault(p.get("prioridade"), []).append(rid)
    conflicts_content = contents.get("analysis.conflicts") or {}
    return _env.get_template("analise.md.j2").render(
        meta=meta, refined=refined,
        conflicts=conflicts_content.get("conflitos", []), pairs=conflicts_content.get("cobertura_pares"),
        moscow=moscow, moscow_levels=MOSCOW_LEVELS,
        consensus=consensus or [], lacunas=_lacunas(contents),
    )
