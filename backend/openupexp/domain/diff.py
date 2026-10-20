"""Diff estruturado entre versões de artefato, item a item."""

from openupexp.agents.registry import ARTIFACT_TYPES


def _field_changes(a: dict, b: dict) -> list[dict]:
    keys = sorted(set(a) | set(b))
    return [{"campo": k, "antes": a.get(k), "depois": b.get(k)} for k in keys if a.get(k) != b.get(k)]


def diff_contents(artifact_type: str, old: dict, new: dict) -> dict:
    at = ARTIFACT_TYPES.get(artifact_type)
    if at is None or not at.list_field:
        return {"tipo": "documento", "campos": _field_changes(old or {}, new or {})}
    old_items = {i.get("id"): i for i in (old or {}).get(at.list_field, [])}
    new_items = {i.get("id"): i for i in (new or {}).get(at.list_field, [])}
    return {
        "tipo": "itens",
        "adicionados": [new_items[k] for k in new_items if k not in old_items],
        "removidos": [old_items[k] for k in old_items if k not in new_items],
        "alterados": [
            {"id": k, "campos": _field_changes(old_items[k], new_items[k])}
            for k in new_items if k in old_items and old_items[k] != new_items[k]
        ],
        "campos": _field_changes(
            {k: v for k, v in (old or {}).items() if k != at.list_field},
            {k: v for k, v in (new or {}).items() if k != at.list_field},
        ),
    }
