"""Handlers das tarefas da Fase 4 (Especificação) — um por tarefa do manifesto.

Ver OpenUPExp/tarefas/especificar-requisitos.md e docs/architecture/12-decisoes-pendentes.md §12.6.
4.1.2 monta, sem LLM, uma ficha por requisito a partir da Análise aprovada; as tarefas 4.2.x
trabalham em lotes sobre essas fichas e sobre as HU, com join determinístico por requisito/HU.
A matriz de rastreabilidade (4.2.4) é calculada, não gerada.
"""

import re

from sqlalchemy import select

from openupexp.agents.phase1 import _dump_list, _items, _models
from openupexp.agents.phase3 import BATCH_SIZE, _by_req, _chunks, _per_requirement, _subset
from openupexp.agents.registry import ARTIFACT_TYPES, SPECIFICATION_EDITABLE
from openupexp.agents.runtime import TaskContext, WriteResult
from openupexp.baml_client import types as T
from openupexp.context.builder import PackageItem
from openupexp.db.models import HitlRequest
from openupexp.domain import artifacts as store
from openupexp.exports import requirements as erd
from openupexp.exports import specification as doc
from openupexp.exports import vision as visao

# Heurística do checklist 4.3.1 ("evitar critérios vagos"): termo vago sem nenhum número no "Então".
VAGUE_TERMS = ["adequad", "rápid", "fácil", "facilmente", "amigáve", "intuitiv", "suficiente", "satisfatóri",
               "eficiente", "apropriad", "razoáve"]


class BaseAnalysisNotApproved(Exception):
    pass


def _plan(ctx: TaskContext) -> list[dict]:
    return _items(ctx.package.required("specification.plan"), "fichas")


def _stories(ctx: TaskContext) -> list[dict]:
    return _items(ctx.package.required("specification.user_stories"), "historias")


def _plan_for(plan: list[dict], stories: list[dict]) -> list[dict]:
    ids = {s.get("req_id") for s in stories}
    return [p for p in plan if p["req_id"] in ids]


def _by_hu(content: dict | None, field: str) -> dict[str, dict]:
    return {i.get("hu_id"): i for i in _items(content, field)}


# ---------------------------------------------------------------------------
# 4.1 Prepare Explainability Specification
# ---------------------------------------------------------------------------


async def t_4_1_1(ctx: TaskContext) -> list[WriteResult]:
    """Carrega a Análise aprovada na Fase 3 (execução de base) e o que ficou em aberto."""
    if not ctx.run.base_run_id:
        raise BaseAnalysisNotApproved("A Fase 4 precisa de uma execução da Fase 3 como base.")
    cur = await store.current_versions(ctx.session, ctx.run.base_run_id)
    draft = cur.get("analysis.draft")
    if draft is None or draft.status != "approved":
        raise BaseAnalysisNotApproved("A análise da execução de base ainda não foi aprovada (gateway 3.3).")
    contents = {t: v.content for t, v in cur.items()}
    prios = _items(contents.get("analysis.priorities"), "prioridades")
    lacunas = [f"{at.title} {i.get('req_id') or i.get('id')} · {lac.get('campo')}: "
               f"{lac.get('pergunta_sugerida') or lac.get('motivo')}"
               for atype, at in ARTIFACT_TYPES.items() if atype.startswith("analysis.") and at.list_field
               for i in _items(contents.get(atype), at.list_field) for lac in i.get("lacunas") or []]
    return [WriteResult("specification.baseline", {
        "base_run_id": str(ctx.run.base_run_id), "analise_version_id": str(draft.id),
        "prioridades": {p["req_id"]: p.get("prioridade") for p in prios},
        "conflitos": [c["id"] for c in _items(contents.get("analysis.conflicts"), "conflitos")],
        "lacunas_abertas": lacunas,
    }, origin="deterministic")]


async def t_4_1_2(ctx: TaskContext) -> list[WriteResult]:
    """Uma ficha por requisito analisado; WONT fica fora da especificação desta versão (A-21)."""
    reqs = [r for r in _items(ctx.package.required("requirements.consolidated"), "requisitos")
            if r.get("tipo") == "EXPLICABILIDADE"]
    chars = _by_req(ctx.package.required("analysis.characterized"), "caracterizacoes")
    aspects = _by_req(ctx.package.required("analysis.aspects"), "classificacoes")
    types = _by_req(ctx.package.required("analysis.explanation_types"), "mapeamentos")
    deps = _by_req(ctx.package.required("analysis.dependencies"), "dependencias")
    prios = _by_req(ctx.package.required("analysis.priorities"), "prioridades")
    fichas, fora = [], []
    for r in reqs:
        prio = (prios.get(r["id"]) or {}).get("prioridade")
        if prio == "WONT":
            fora.append({"req_id": r["id"], "motivo": "Prioridade WONT na Análise aprovada: fora desta versão."})
            continue
        c = chars.get(r["id"]) or {}
        fichas.append({
            "req_id": r["id"], "enunciado": r.get("enunciado") or "", "prioridade": prio,
            "stakeholder_ids": r.get("stakeholder_ids") or [], "need_ids": r.get("need_ids") or [],
            "aspecto_predominante": (aspects.get(r["id"]) or {}).get("predominante"),
            "tipos_explicacao": (types.get(r["id"]) or {}).get("tipos") or [],
            "contexto_uso": c.get("contexto_uso"), "decisao_apoiada": c.get("decisao_apoiada"),
            "objetivo_principal": c.get("objetivo_principal"),
            "restricoes": [f"{x.get('tipo')}: {x.get('descricao')}"
                           for x in (deps.get(r["id"]) or {}).get("restricoes") or []],
            "rer_id": c.get("id"), "origem_ids": r.get("origem_ids") or [],
        })
    order = {"MUST": 0, "SHOULD": 1, "COULD": 2}
    fichas.sort(key=lambda f: order.get(f["prioridade"], 9))
    return [WriteResult("specification.plan", {"fichas": fichas, "nao_especificados": fora},
                        origin="deterministic")]


# ---------------------------------------------------------------------------
# 4.2 Specify Explainability Requirements
# ---------------------------------------------------------------------------


def _entries(rows: list[dict]) -> list[T.SpecificationPlanEntry]:
    return _models(T.SpecificationPlanEntry, rows)


async def t_4_2_1(ctx: TaskContext) -> list[WriteResult]:
    """HU em lotes de fichas; ao menos uma HU por requisito (pode haver uma por stakeholder)."""
    plan = _plan(ctx)
    stakeholders = _items(ctx.package.required("vision.stakeholders"), "stakeholders")
    prev = _items(ctx.package.previous("specification.user_stories"), "historias")
    known = {s["id"] for s in stakeholders}
    found: dict[str, list[dict]] = {}

    async def run(batch: list[dict]) -> None:
        ids = {f["req_id"] for f in batch}
        stk = {s for f in batch for s in f["stakeholder_ids"]}
        out = await ctx.call("SpecifyUserStories", T.SpecifyStoriesInput(
            requisitos=_entries(batch),
            stakeholders=_models(T.Stakeholder, [s for s in stakeholders if s["id"] in stk]),
            historias_existentes=_models(T.UserStory, _subset(prev, ids))))
        for h in _dump_list(out.historias):
            if h.get("req_id") in ids:
                found.setdefault(h["req_id"], []).append(h)

    for batch in _chunks(plan, BATCH_SIZE):
        await run(batch)
    missing = [f for f in plan if f["req_id"] not in found]
    for batch in _chunks(missing, BATCH_SIZE):
        await run(batch)
    if missing:
        ctx.package.coverage.output_missing_ids = [f["req_id"] for f in plan if f["req_id"] not in found]

    previous = {(h.get("req_id"), h.get("stakeholder_id")): h.get("id") for h in prev}
    allowed = {f["req_id"]: set(f["stakeholder_ids"]) for f in plan}
    raw = []
    for f in plan:
        for h in found.get(f["req_id"], []):
            if not h.get("id"):
                h["id"] = previous.get((h["req_id"], h.get("stakeholder_id")))
            if h.get("stakeholder_id") not in known or h["stakeholder_id"] not in allowed[f["req_id"]]:
                h.setdefault("lacunas", []).append({
                    "campo": "stakeholder_id", "motivo": "Stakeholder não associado ao requisito na Análise.",
                    "pergunta_sugerida": f"Quem é o stakeholder desta história de {f['req_id']}?"})
            raw.append(h)
    return [WriteResult("specification.user_stories", {}, raw_items=raw)]


async def t_4_2_2(ctx: TaskContext) -> list[WriteResult]:
    plan = _plan(ctx)
    stories = _stories(ctx)
    prev = _items(ctx.package.previous("specification.acceptance_criteria"), "criterios")

    async def call(batch: list[dict]) -> list[dict]:
        ids = {h["id"] for h in batch}
        out = await ctx.call("DefineAcceptanceCriteria", T.AcceptanceInput(
            historias=_models(T.UserStory, batch), requisitos=_entries(_plan_for(plan, batch)),
            criterios_existentes=_models(T.AcceptanceCriteria, _subset(prev, ids, "hu_id"))))
        return _dump_list(out.criterios)

    raw = await _per_requirement(ctx, stories, call, "criterios", key="hu_id")
    return [WriteResult("specification.acceptance_criteria", {}, raw_items=raw)]


async def t_4_2_3(ctx: TaskContext) -> list[WriteResult]:
    plan = _plan(ctx)
    stories = _stories(ctx)
    criteria = _items(ctx.package.required("specification.acceptance_criteria"), "criterios")
    limits = _items(ctx.package.required("vision.limits"), "respostas")
    prev = _items(ctx.package.previous("specification.characteristics"), "caracteristicas")

    async def call(batch: list[dict]) -> list[dict]:
        ids = {h["id"] for h in batch}
        out = await ctx.call("SpecifyExplanationCharacteristics", T.CharacteristicsInput(
            historias=_models(T.UserStory, batch), requisitos=_entries(_plan_for(plan, batch)),
            criterios=_models(T.AcceptanceCriteria, _subset(criteria, ids, "hu_id")),
            limites_visao=_models(T.LimitAnswer, limits),
            caracteristicas_existentes=_models(T.ExplanationCharacteristics, _subset(prev, ids, "hu_id"))))
        return _dump_list(out.caracteristicas)

    raw = await _per_requirement(ctx, stories, call, "caracteristicas", key="hu_id")
    return [WriteResult("specification.characteristics", {}, raw_items=raw)]


async def t_4_2_4(ctx: TaskContext) -> list[WriteResult]:
    """Matriz calculada: requisito refinado × HU × stakeholder × necessidade × critérios × prioridade."""
    plan = {f["req_id"]: f for f in _plan(ctx)}
    stories = _stories(ctx)
    ca = _by_hu(ctx.package.required("specification.acceptance_criteria"), "criterios")
    cex = _by_hu(ctx.package.required("specification.characteristics"), "caracteristicas")
    prev = {r.get("hu"): r.get("id") for r in _items(ctx.package.previous("specification.traceability"), "linhas")}
    rows = []
    for h in stories:
        f = plan.get(h.get("req_id")) or {}
        rows.append({
            "id": prev.get(h["id"]), "hu": h["id"], "req": h.get("req_id"), "rer": f.get("rer_id"),
            "stakeholder": h.get("stakeholder_id"), "necessidades": f.get("need_ids") or [],
            "origens": f.get("origem_ids") or [], "ca": (ca.get(h["id"]) or {}).get("id"),
            "cex": (cex.get(h["id"]) or {}).get("id"), "prioridade": f.get("prioridade"),
        })
    covered = {h.get("req_id") for h in stories}
    content = {"requisitos_sem_hu": sorted(set(plan) - covered),
               "hu_sem_requisito": sorted(h["id"] for h in stories if h.get("req_id") not in plan)}
    return [WriteResult("specification.traceability", content, raw_items=rows, origin="deterministic")]


# ---------------------------------------------------------------------------
# 4.3 Validate Explainability Specification
# ---------------------------------------------------------------------------


def _vague(scenario: dict) -> bool:
    text = (scenario.get("entao") or "").lower()
    return not re.search(r"\d", text) and any(t in text for t in VAGUE_TERMS)


async def t_4_3_1(ctx: TaskContext) -> list[WriteResult]:
    """Checklist objetivo de pré-revisão (boas práticas dos passos 1–5). Não substitui a revisão humana."""
    cur = await store.current_versions(ctx.session, ctx.run.id)
    c = {k: v.content for k, v in cur.items()}
    plan = _items(c.get("specification.plan"), "fichas")
    stories = _items(c.get("specification.user_stories"), "historias")
    ca = _by_hu(c.get("specification.acceptance_criteria"), "criterios")
    cex = _by_hu(c.get("specification.characteristics"), "caracteristicas")
    trace = c.get("specification.traceability") or {}
    hu_ids = [h["id"] for h in stories]
    allowed = {f["req_id"]: set(f.get("stakeholder_ids") or []) for f in plan}
    incomplete_hu = [h["id"] for h in stories if not all((h.get(k) or "").strip() for k in ("como", "quero", "para"))]
    wrong_stk = [h["id"] for h in stories if h.get("stakeholder_id") not in allowed.get(h.get("req_id"), set())]
    no_ca = [i for i in hu_ids if not (ca.get(i) or {}).get("cenarios")]
    incomplete_ca = [x["id"] for x in ca.values() if any(
        not all((s.get(k) or "").strip() for k in ("dado", "quando", "entao")) for s in x.get("cenarios") or [])]
    vague = [x["id"] for x in ca.values() if any(_vague(s) for s in x.get("cenarios") or [])]
    no_cex = [i for i in hu_ids if i not in cex]
    orphan_rows = [r["id"] for r in _items(trace, "linhas") if not (r.get("ca") and r.get("cex"))]
    consensus = await ctx.session.scalar(
        select(HitlRequest).where(HitlRequest.run_id == ctx.run.id, HitlRequest.kind == "consensus",
                                  HitlRequest.status == "decided").order_by(HitlRequest.created_at.desc()).limit(1))
    fechamento = (consensus.payload or {}).get("fechamento", {}) if consensus else {}
    stale = [k for k, v in cur.items() if v.status == "stale" and k in SPECIFICATION_EDITABLE]
    checks = [
        {"id": "requisito_com_hu", "descricao": "Todo requisito especificado tem ao menos uma HU",
         "ok": not trace.get("requisitos_sem_hu"), "detalhes": trace.get("requisitos_sem_hu") or []},
        {"id": "hu_formato", "descricao": "Toda HU tem Como / Quero / Para", "ok": not incomplete_hu,
         "detalhes": incomplete_hu},
        {"id": "hu_stakeholder", "descricao": "O stakeholder da HU está associado ao requisito",
         "ok": not wrong_stk, "detalhes": wrong_stk},
        {"id": "hu_com_criterios", "descricao": "Toda HU tem critérios de aceitação", "ok": not no_ca,
         "detalhes": no_ca},
        {"id": "criterios_formato", "descricao": "Todo cenário tem Dado / Quando / Então", "ok": not incomplete_ca,
         "detalhes": incomplete_ca},
        {"id": "criterios_sem_termos_vagos", "descricao": "Critérios sem termos vagos não mensurados (heurística)",
         "ok": not vague, "detalhes": vague},
        {"id": "hu_com_caracteristicas", "descricao": "Toda HU tem características da explicação",
         "ok": not no_cex, "detalhes": no_cex},
        {"id": "rastreabilidade_completa", "descricao": "Matriz sem linhas incompletas nem HU órfã",
         "ok": not orphan_rows and not trace.get("hu_sem_requisito"),
         "detalhes": orphan_rows + (trace.get("hu_sem_requisito") or [])},
        {"id": "consenso_sem_objecao", "descricao": "Consenso encerrado sem objeções pendentes",
         "ok": consensus is not None and not fechamento.get("override"), "detalhes": []},
        {"id": "sem_stale", "descricao": "Nenhuma versão desatualizada (stale)", "ok": not stale, "detalhes": stale},
    ]
    lacunas = {}
    for atype in SPECIFICATION_EDITABLE:
        at = ARTIFACT_TYPES[atype]
        lacunas[atype] = sum(len(i.get("lacunas") or []) for i in _items(c.get(atype), at.list_field))
    return [WriteResult("specification.review_report", {"checks": checks, "lacunas_por_artefato": lacunas},
                        origin="deterministic")]


async def t_4_3_2(ctx: TaskContext) -> list[WriteResult]:
    """Consolida o DRE: ERD aprovado das Fases 1–3 + a especificação (Parte 4)."""
    cur = await store.current_versions(ctx.session, ctx.run.id)
    phase_types = set(ctx.phase.writers())
    await store.set_status(ctx.session, [v.id for t, v in cur.items() if t in phase_types], "approved")
    contents = {t: v.content for t, v in cur.items()}
    meta = await visao._meta(ctx.session, ctx.run, "aprovado", f"4.{ctx.iteration - 1}")
    meta["base_run_id"] = str(ctx.run.base_run_id)
    part4 = doc.render_specification_markdown(contents, meta, await erd.consensus_records(ctx.session, ctx.run))
    previous_erd = (ctx.package.required("analysis.draft") or {}).get("markdown", "")
    markdown = (f"{previous_erd}\n\n---\n\n> Parte 4 — Especificação dos requisitos (Fase 4), que completa o DRE.\n\n"
                f"{part4}")
    hu_ids = [h["id"] for h in _items(contents.get("specification.user_stories"), "historias")]
    digest = await ctx.call("BuildPhaseDigest", T.DigestInput(documento=part4, ids_obrigatorios=hu_ids))
    mentioned = set(digest.ids_cobertos) | {i for i in hu_ids if i in digest.resumo}
    digest_content = digest.model_dump(mode="json")
    digest_content["ids_faltantes"] = sorted(set(hu_ids) - mentioned)
    ctx.package.add(PackageItem(origin="related", ref=f"run:{ctx.run.base_run_id}:erd",
                                content=f"{len(previous_erd)} caracteres",
                                reason="ERD aprovado da fase anterior, incorporado sem alteração"))
    return [
        WriteResult("specification.draft", {"markdown": markdown,
                                            "versoes": {t: str(v.id) for t, v in cur.items() if t in phase_types}},
                    origin="consolidation", status="approved"),
        WriteResult("digest.specification", digest_content, status="approved"),
    ]


HANDLERS = {
    "4.1.1": t_4_1_1,
    "4.1.2": t_4_1_2,
    "4.2.1": t_4_2_1,
    "4.2.2": t_4_2_2,
    "4.2.3": t_4_2_3,
    "4.2.4": t_4_2_4,
    "4.3.1": t_4_3_1,
    "4.3.2": t_4_3_2,
}
