"""Renderização da parte da Fase 4 do DRE (especificação dos requisitos) em Markdown."""

from openupexp.agents.registry import ARTIFACT_TYPES, SPECIFICATION_EDITABLE
from openupexp.exports.vision import _env

TEMPLATE_VERSION = "especificacao-0.1-provisorio"


def _by_hu(contents: dict, atype: str) -> dict[str, dict]:
    field = ARTIFACT_TYPES[atype].list_field
    return {i.get("hu_id"): i for i in (contents.get(atype) or {}).get(field, [])}


def _lacunas(contents: dict[str, dict]) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    for atype in SPECIFICATION_EDITABLE:
        at = ARTIFACT_TYPES[atype]
        for item in (contents.get(atype) or {}).get(at.list_field, []):
            out += [(f"{at.title} {item.get('id')}", lac) for lac in item.get("lacunas") or []]
    return out


def render_specification_markdown(contents: dict[str, dict], meta: dict, consensus: list[dict] | None = None) -> str:
    plan = contents.get("specification.plan") or {}
    fichas = {f["req_id"]: f for f in plan.get("fichas", [])}
    ca = _by_hu(contents, "specification.acceptance_criteria")
    cex = _by_hu(contents, "specification.characteristics")
    groups: dict[str, list[dict]] = {}
    for h in (contents.get("specification.user_stories") or {}).get("historias", []):
        groups.setdefault(h.get("req_id"), []).append({"hu": h, "ca": ca.get(h.get("id")) or {},
                                                       "cex": cex.get(h.get("id")) or {}})
    requirements = [{"ficha": f, "historias": groups.get(rid, [])} for rid, f in fichas.items()]
    trace = contents.get("specification.traceability") or {}
    return _env.get_template("especificacao.md.j2").render(
        meta=meta, requirements=requirements, rows=trace.get("linhas", []),
        fora=plan.get("nao_especificados", []), consensus=consensus or [], lacunas=_lacunas(contents),
    )
