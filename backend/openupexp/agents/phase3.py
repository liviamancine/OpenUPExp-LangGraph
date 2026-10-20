"""Handlers das tarefas da Fase 3 (Análise) — um por tarefa do manifesto.

Ver OpenUPExp/tarefas/analisar-requisito.md e docs/architecture/12-decisoes-pendentes.md §12.5.
As tarefas por requisito rodam em lotes pequenos (map), cada lote só com o próprio contexto;
um join determinístico garante uma saída por requisito. A priorização (3.2.6) é um reduce
sobre uma visão compacta de todos os requisitos.
"""

from itertools import combinations

from sqlalchemy import select

from openupexp.agents.evidence import verify_item_evidences
from openupexp.agents.phase1 import _dump_list, _items, _models
from openupexp.agents.phase2 import _add_hit, _cosine
from openupexp.agents.registry import ANALYSIS_EDITABLE, ARTIFACT_TYPES
from openupexp.agents.runtime import TaskContext, WriteResult
from openupexp.baml_client import types as T
from openupexp.context.builder import PackageItem
from openupexp.db.models import HitlRequest
from openupexp.domain import artifacts as store
from openupexp.exports import analysis as doc
from openupexp.exports import requirements as erd
from openupexp.exports import vision as visao
from openupexp.retrieval.search import hybrid_search

BATCH_SIZE = 6
PAIRS_PER_CALL = 30
ALL_PAIRS_LIMIT = 40
CRITERIA = ["TECNICA", "REGULATORIA", "OPERACIONAL", "ECONOMICA"]
MOSCOW_RANK = {"MUST": 0, "SHOULD": 1, "COULD": 2, "WONT": 3}


class BaseRequirementsNotApproved(Exception):
    pass


def _chunks(items: list, size: int) -> list[list]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def _all_reqs(ctx: TaskContext) -> list[dict]:
    return _items(ctx.package.required("requirements.consolidated"), "requisitos")


def _explainability(ctx: TaskContext) -> list[dict]:
    """Requisitos analisados nesta fase: os de explicabilidade (os complementares são restrições)."""
    return [r for r in _all_reqs(ctx) if r.get("tipo") == "EXPLICABILIDADE"]


def _by_req(content: dict | None, field: str) -> dict[str, dict]:
    return {i.get("req_id"): i for i in _items(content, field)}


async def _per_requirement(ctx: TaskContext, reqs: list[dict], call, field: str, key: str = "req_id") -> list[dict]:
    """Executa call(lote) em lotes e garante exatamente uma saída por requisito.

    Faltas geram uma nova chamada só com os faltantes; persistindo, a tarefa falha (coverage).
    O ID anterior do item do mesmo requisito é preservado. `key` é o campo da saída que aponta
    para o id da entrada (req_id; hu_id na Fase 4).
    """
    wanted = {r["id"] for r in reqs}
    found: dict[str, dict] = {}

    async def run(batch_reqs: list[dict]) -> None:
        for item in await call(batch_reqs):
            rid = item.get(key)
            if rid in wanted and rid not in found:
                found[rid] = item

    for batch in _chunks(reqs, BATCH_SIZE):
        await run(batch)
    missing = [r for r in reqs if r["id"] not in found]
    for batch in _chunks(missing, BATCH_SIZE):
        await run(batch)
    if missing:
        ctx.package.coverage.output_missing_ids = [r["id"] for r in reqs if r["id"] not in found]

    previous = {i.get(key): i for i in _items(ctx.package.previous(ctx.task.writes[0].artifact), field)}
    out = []
    for r in reqs:
        item = found.get(r["id"])
        if item is not None:
            if r["id"] in previous:
                item["id"] = previous[r["id"]].get("id")
            out.append(item)
    return out


def _subset(rows: list[dict], ids: set[str], key: str = "req_id") -> list[dict]:
    return [r for r in rows if r.get(key) in ids]


async def _reference_hits(ctx: TaskContext, reqs: list[dict], extra: dict[str, str], kinds: list[str] | None,
                          reason: str) -> tuple[set[str], dict]:
    """Busca na base de referência por requisito; devolve as refs do lote e as fontes para verificação."""
    retrieval = ctx.task.retrieval
    refs: set[str] = set()
    sources: dict = {}
    if not (ctx.run.corpus_version_id and retrieval):
        return refs, sources
    for r in reqs:
        query = " ".join(x for x in [r.get("enunciado"), extra.get(r["id"])] if x)
        for h in await hybrid_search(ctx.session, ctx.run.corpus_version_id, query, ctx.embedder,
                                     k=retrieval.per_query_k, kinds=kinds, mode=retrieval.mode):
            _add_hit(ctx, h, f"{reason} {r['id']} (score {h.score:.4f})")
            refs.add(h.ref)
            sources[h.ref] = (h.texto, h.id)
    return refs, sources


# ---------------------------------------------------------------------------
# 3.1 Prepare Explainability Analysis
# ---------------------------------------------------------------------------


async def t_3_1_1(ctx: TaskContext) -> list[WriteResult]:
    """Carrega os requisitos aprovados na Fase 2 (execução de base)."""
    if not ctx.run.base_run_id:
        raise BaseRequirementsNotApproved("A Fase 3 precisa de uma execução da Fase 2 como base.")
    cur = await store.current_versions(ctx.session, ctx.run.base_run_id)
    draft = cur.get("requirements.draft")
    if draft is None or draft.status != "approved":
        raise BaseRequirementsNotApproved("Os requisitos da execução de base ainda não foram aprovados (gateway 2.3).")
    contents = {t: v.content for t, v in cur.items()}
    reqs = _items(contents.get("requirements.consolidated"), "requisitos")
    lacunas = [f"{origem} · {lac.get('campo')}: {lac.get('pergunta_sugerida') or lac.get('motivo')}"
               for origem, lac in erd._lacunas(contents)]
    return [WriteResult("analysis.baseline", {
        "base_run_id": str(ctx.run.base_run_id), "requisitos_version_id": str(draft.id),
        "explicabilidade": [r["id"] for r in reqs if r.get("tipo") == "EXPLICABILIDADE"],
        "complementares": [r["id"] for r in reqs if r.get("tipo") == "COMPLEMENTAR"],
        "lacunas_abertas": lacunas,
    }, origin="deterministic")]


async def t_3_1_2(ctx: TaskContext) -> list[WriteResult]:
    """Map por requisito: cada chamada recebe só o requisito, seus stakeholders e necessidades."""
    stakeholders = _items(ctx.package.required("vision.stakeholders"), "stakeholders")
    needs = _items(ctx.package.required("vision.explainability_needs"), "necessidades")
    complementary = [r for r in _all_reqs(ctx) if r.get("tipo") == "COMPLEMENTAR"]
    previous = _by_req(ctx.package.previous("analysis.characterized"), "caracterizacoes")

    async def call(batch: list[dict]) -> list[dict]:
        out = []
        for r in batch:
            stk = set(r.get("stakeholder_ids") or [])
            nd = set(r.get("need_ids") or [])
            prev = previous.get(r["id"])
            item = await ctx.call("CharacterizeRequirement", T.CharacterizeInput(
                requisito=T.ConsolidatedRequirement.model_validate(r),
                stakeholders=_models(T.Stakeholder, [s for s in stakeholders if s["id"] in stk]),
                necessidades=_models(T.ExplainabilityNeed, [n for n in needs if n["id"] in nd]),
                requisitos_complementares=_models(T.ConsolidatedRequirement, complementary),
                caracterizacao_existente=T.CharacterizedRequirement.model_validate(prev) if prev else None,
            ))
            item = item.model_dump(mode="json")
            item["req_id"] = r["id"]
            out.append(item)
        return out

    raw = await _per_requirement(ctx, _explainability(ctx), call, "caracterizacoes")
    return [WriteResult("analysis.characterized", {}, raw_items=raw)]


# ---------------------------------------------------------------------------
# 3.2 Analyze Explainability Requirements
# ---------------------------------------------------------------------------


def _characterized(ctx: TaskContext) -> list[dict]:
    return _items(ctx.package.required("analysis.characterized"), "caracterizacoes")


async def t_3_2_1(ctx: TaskContext) -> list[WriteResult]:
    chars = _characterized(ctx)
    prev = _items(ctx.package.previous("analysis.aspects"), "classificacoes")

    async def call(batch: list[dict]) -> list[dict]:
        ids = {r["id"] for r in batch}
        out = await ctx.call("ClassifyExplainabilityAspects", T.ClassifyAspectsInput(
            requisitos=_models(T.ConsolidatedRequirement, batch),
            caracterizacoes=_models(T.CharacterizedRequirement, _subset(chars, ids)),
            classificacoes_existentes=_models(T.AspectClassification, _subset(prev, ids))))
        return _dump_list(out.classificacoes)

    raw = await _per_requirement(ctx, _explainability(ctx), call, "classificacoes")
    return [WriteResult("analysis.aspects", {}, raw_items=raw)]


async def t_3_2_2(ctx: TaskContext) -> list[WriteResult]:
    """Lotes com trechos da base de referência (literatura) recuperados para cada requisito."""
    chars = _characterized(ctx)
    aspects = _items(ctx.package.required("analysis.aspects"), "classificacoes")
    prev = _items(ctx.package.previous("analysis.explanation_types"), "mapeamentos")
    aspect_text = {a.get("req_id"): " ".join(a.get("aspectos") or []) for a in aspects}
    all_sources: dict = {}

    async def call(batch: list[dict]) -> list[dict]:
        ids = {r["id"] for r in batch}
        refs, sources = await _reference_hits(ctx, batch, aspect_text, ["academico"], "tipos de explicação para")
        all_sources.update(sources)
        out = await ctx.call("AssociateExplanationTypes", T.MapTypesInput(
            requisitos=_models(T.ConsolidatedRequirement, batch),
            caracterizacoes=_models(T.CharacterizedRequirement, _subset(chars, ids)),
            aspectos=_models(T.AspectClassification, _subset(aspects, ids)),
            mapeamentos_existentes=_models(T.ExplanationTypeMapping, _subset(prev, ids))), retrieved=refs)
        return _dump_list(out.mapeamentos)

    raw = await _per_requirement(ctx, _explainability(ctx), call, "mapeamentos")
    pending = verify_item_evidences(raw, all_sources)
    return [WriteResult("analysis.explanation_types", {}, raw_items=raw, item_evidences=pending)]


def _candidate_pairs(ctx: TaskContext, reqs: list[dict]) -> list[T.RequirementPair]:
    """Todos os pares se houver poucos requisitos; senão, mesmo stakeholder ou textos próximos."""
    pairs = []
    if len(reqs) <= ALL_PAIRS_LIMIT:
        for a, b in combinations(reqs, 2):
            pairs.append(T.RequirementPair(a=a["id"], b=b["id"], motivo="todos os pares (conjunto pequeno)"))
        return pairs
    vectors = ctx.embedder.encode_passages([r.get("enunciado") or "" for r in reqs])
    for (i, a), (j, b) in combinations(list(enumerate(reqs)), 2):
        if set(a.get("stakeholder_ids") or []) & set(b.get("stakeholder_ids") or []):
            pairs.append(T.RequirementPair(a=a["id"], b=b["id"], motivo="stakeholder em comum"))
        elif _cosine(vectors[i], vectors[j]) >= 0.8:
            pairs.append(T.RequirementPair(a=a["id"], b=b["id"], motivo="similaridade semântica"))
    return pairs


async def t_3_2_3(ctx: TaskContext) -> list[WriteResult]:
    """Conflitos verificados par a par; a cobertura de pares fica registrada."""
    reqs = _all_reqs(ctx)
    by_id = {r["id"]: r for r in reqs}
    aspects = _items(ctx.package.required("analysis.aspects"), "classificacoes")
    types = _items(ctx.package.required("analysis.explanation_types"), "mapeamentos")
    prev = _items(ctx.package.previous("analysis.conflicts"), "conflitos")
    pairs = _candidate_pairs(ctx, reqs)
    conflicts: list[dict] = []
    for group in _chunks(pairs, PAIRS_PER_CALL):
        ids = {p.a for p in group} | {p.b for p in group}
        out = await ctx.call("AnalyzeConflicts", T.ConflictsInput(
            requisitos=_models(T.ConsolidatedRequirement, [by_id[i] for i in by_id if i in ids]),
            aspectos=_models(T.AspectClassification, _subset(aspects, ids)),
            tipos=_models(T.ExplanationTypeMapping, _subset(types, ids)),
            pares_candidatos=group,
            conflitos_existentes=_models(T.RequirementConflict,
                                         [c for c in prev if set(c.get("req_ids") or []) <= ids])))
        conflicts += [c for c in _dump_list(out.conflitos) if set(c.get("req_ids") or []) <= set(by_id)]
    content = {"cobertura_pares": {"candidatos": len(pairs), "avaliados": len(pairs),
                                   "criterio": "todos os pares" if len(reqs) <= ALL_PAIRS_LIMIT
                                   else "stakeholder em comum ou similaridade ≥ 0,8"}}
    return [WriteResult("analysis.conflicts", content, raw_items=conflicts)]


async def t_3_2_4(ctx: TaskContext) -> list[WriteResult]:
    """Lotes com trechos normativos recuperados; restrições regulatórias precisam de evidência."""
    chars = _characterized(ctx)
    index = [T.RequirementIndexEntry(id=r["id"], enunciado=(r.get("enunciado") or "")[:200]) for r in _all_reqs(ctx)]
    prev = _items(ctx.package.previous("analysis.dependencies"), "dependencias")
    char_text = {c.get("req_id"): c.get("decisao_apoiada") or "" for c in chars}
    all_sources: dict = {}

    async def call(batch: list[dict]) -> list[dict]:
        ids = {r["id"] for r in batch}
        refs, sources = await _reference_hits(ctx, batch, char_text, ["lei", "manual"], "restrições para")
        all_sources.update(sources)
        out = await ctx.call("AnalyzeDependencies", T.DependenciesInput(
            requisitos=_models(T.ConsolidatedRequirement, batch),
            caracterizacoes=_models(T.CharacterizedRequirement, _subset(chars, ids)),
            indice=index,
            dependencias_existentes=_models(T.DependencyAnalysis, _subset(prev, ids))), retrieved=refs)
        return _dump_list(out.dependencias)

    raw = await _per_requirement(ctx, _explainability(ctx), call, "dependencias")
    valid = {e.id for e in index}
    for item in raw:
        item["depende_de"] = [d for d in item.get("depende_de") or [] if d in valid and d != item["req_id"]]
    # as evidências ficam dentro de cada restrição; a verificação as trata como do item
    nested = [{"evidencias": [ev for r in item.get("restricoes", []) for ev in r.get("evidencias", [])]}
              for item in raw]
    pending = verify_item_evidences(nested, all_sources)
    for item, flat in zip(raw, nested):
        item["fundamentacao_verificada"] = flat["fundamentacao_verificada"]
    return [WriteResult("analysis.dependencies", {}, raw_items=raw, item_evidences=pending)]


async def t_3_2_5(ctx: TaskContext) -> list[WriteResult]:
    chars = _characterized(ctx)
    types = _items(ctx.package.required("analysis.explanation_types"), "mapeamentos")
    deps = _items(ctx.package.required("analysis.dependencies"), "dependencias")
    conflicts = _items(ctx.package.required("analysis.conflicts"), "conflitos")
    prev = _items(ctx.package.previous("analysis.feasibility"), "avaliacoes")

    async def call(batch: list[dict]) -> list[dict]:
        ids = {r["id"] for r in batch}
        out = await ctx.call("AssessFeasibility", T.FeasibilityInput(
            requisitos=_models(T.ConsolidatedRequirement, batch),
            caracterizacoes=_models(T.CharacterizedRequirement, _subset(chars, ids)),
            tipos=_models(T.ExplanationTypeMapping, _subset(types, ids)),
            dependencias=_models(T.DependencyAnalysis, _subset(deps, ids)),
            conflitos=_models(T.RequirementConflict, [c for c in conflicts if set(c.get("req_ids") or []) & ids]),
            avaliacoes_existentes=_models(T.FeasibilityAssessment, _subset(prev, ids))))
        return _dump_list(out.avaliacoes)

    raw = await _per_requirement(ctx, _explainability(ctx), call, "avaliacoes")
    # completude determinística: os quatro critérios da matriz do passo 6
    for item in raw:
        given = {c.get("criterio"): c for c in item.get("criterios") or []}
        item["criterios"] = [given.get(c) or {"criterio": c, "situacao": "NAO_AVALIADO", "observacao": None}
                             for c in CRITERIA]
        for c in CRITERIA:
            if c not in given:
                item.setdefault("lacunas", []).append({
                    "campo": f"criterios.{c}", "motivo": "Critério não avaliado pelo agente.",
                    "pergunta_sugerida": f"Qual a viabilidade {c.lower()} deste requisito?"})
    return [WriteResult("analysis.feasibility", {}, raw_items=raw)]


def _summary(ctx: TaskContext) -> list[T.RequirementAnalysisSummary]:
    chars = _by_req(ctx.package.required("analysis.characterized"), "caracterizacoes")
    aspects = _by_req(ctx.package.required("analysis.aspects"), "classificacoes")
    feas = _by_req(ctx.package.required("analysis.feasibility"), "avaliacoes")
    deps = _by_req(ctx.package.required("analysis.dependencies"), "dependencias")
    conflicts = _items(ctx.package.required("analysis.conflicts"), "conflitos")
    out = []
    for r in _explainability(ctx):
        f = feas.get(r["id"]) or {}
        out.append(T.RequirementAnalysisSummary(
            id=r["id"], enunciado=(r.get("enunciado") or "")[:240], tipo=r.get("tipo") or "",
            aspecto_predominante=(aspects.get(r["id"]) or {}).get("predominante"),
            risco_decisao=(chars.get(r["id"]) or {}).get("risco_decisao"),
            viabilidade=" ".join(f"{c.get('criterio')}={c.get('situacao')}" for c in f.get("criterios") or []),
            conflitos=[c["id"] for c in conflicts if r["id"] in (c.get("req_ids") or [])],
            depende_de=(deps.get(r["id"]) or {}).get("depende_de") or [],
        ))
    return out


async def t_3_2_6(ctx: TaskContext) -> list[WriteResult]:
    """Reduce: uma chamada com a visão compacta de TODOS os requisitos (coverage guard)."""
    summary = _summary(ctx)
    prev = _items(ctx.package.previous("analysis.priorities"), "prioridades")
    by_id = {s.id: s for s in summary}

    async def call(batch: list[dict]) -> list[dict]:
        ids = {r["id"] for r in batch}
        out = await ctx.call("PrioritizeRequirements", T.PrioritizeInput(
            requisitos=[by_id[i] for i in by_id if i in ids],
            prioridades_existentes=_models(T.PriorityAssignment, _subset(prev, ids))))
        return _dump_list(out.prioridades)

    reqs = _explainability(ctx)
    found = {p.get("req_id"): p for p in await call(reqs) if p.get("req_id") in by_id}
    missing = [r for r in reqs if r["id"] not in found]
    if missing:
        found.update({p.get("req_id"): p for p in await call(missing) if p.get("req_id") in by_id})
        ctx.package.coverage.output_missing_ids = [r["id"] for r in reqs if r["id"] not in found]
    previous = {p.get("req_id"): p.get("id") for p in prev}
    raw = []
    for r in reqs:
        if r["id"] in found:
            item = found[r["id"]]
            if r["id"] in previous:
                item["id"] = previous[r["id"]]
            raw.append(item)
    # alerta determinístico: requisito do qual outro depende não pode ter prioridade menor
    rank = {p["req_id"]: MOSCOW_RANK.get(p.get("prioridade"), 9) for p in raw}
    for s in summary:
        for dep in s.depende_de:
            if dep in rank and s.id in rank and rank[dep] > rank[s.id]:
                for p in raw:
                    if p["req_id"] == dep:
                        p["alerta"] = f"{s.id} depende deste requisito e tem prioridade maior"
    return [WriteResult("analysis.priorities", {"sugestao_ia": True}, raw_items=raw)]


# ---------------------------------------------------------------------------
# 3.3 Validate Explainability Analysis
# ---------------------------------------------------------------------------


async def t_3_3_1(ctx: TaskContext) -> list[WriteResult]:
    """Checklist objetivo de pré-revisão. Não substitui a revisão humana."""
    cur = await store.current_versions(ctx.session, ctx.run.id)
    c = {k: v.content for k, v in cur.items()}
    base = await erd.base_contents(ctx.session, ctx.run)
    reqs = [r["id"] for r in _items(base.get("requirements.consolidated"), "requisitos")
            if r.get("tipo") == "EXPLICABILIDADE"]
    checks = []
    for atype in ANALYSIS_EDITABLE:
        at = ARTIFACT_TYPES[atype]
        if atype == "analysis.conflicts":
            continue
        covered = {i.get("req_id") for i in _items(c.get(atype), at.list_field)}
        checks.append({"id": f"cobertura_{atype.split('.')[1]}", "descricao": f"{at.title}: todo requisito tratado",
                       "ok": set(reqs) <= covered, "detalhes": sorted(set(reqs) - covered)})
    pairs = (c.get("analysis.conflicts") or {}).get("cobertura_pares") or {}
    conflicts = _items(c.get("analysis.conflicts"), "conflitos")
    deps = _items(c.get("analysis.dependencies"), "dependencias")
    feas = _by_req(c.get("analysis.feasibility"), "avaliacoes")
    prios = _items(c.get("analysis.priorities"), "prioridades")
    must_infeasible = [p["req_id"] for p in prios if p.get("prioridade") == "MUST" and any(
        x.get("situacao") == "NAO" for x in (feas.get(p["req_id"]) or {}).get("criterios") or [])]
    reg_without_evidence = [d["id"] for d in deps if any(r.get("tipo") == "REGULATORIA" for r in d.get("restricoes", []))
                            and not d.get("fundamentacao_verificada")]
    consensus = await ctx.session.scalar(
        select(HitlRequest).where(HitlRequest.run_id == ctx.run.id, HitlRequest.kind == "consensus",
                                  HitlRequest.status == "decided").order_by(HitlRequest.created_at.desc()).limit(1))
    fechamento = (consensus.payload or {}).get("fechamento", {}) if consensus else {}
    stale = [k for k, v in cur.items() if v.status == "stale" and k in ANALYSIS_EDITABLE]
    checks += [
        {"id": "pares_avaliados", "descricao": "Todos os pares candidatos foram avaliados quanto a conflito",
         "ok": bool(pairs) and pairs.get("avaliados") == pairs.get("candidatos"), "detalhes": []},
        {"id": "conflito_com_alternativa", "descricao": "Todo conflito tem alternativa de resolução",
         "ok": all(x.get("alternativas_resolucao") for x in conflicts),
         "detalhes": [x["id"] for x in conflicts if not x.get("alternativas_resolucao")]},
        {"id": "restricao_regulatoria_evidencia", "descricao": "Restrições regulatórias com evidência verificada",
         "ok": not reg_without_evidence, "detalhes": reg_without_evidence},
        {"id": "must_viavel", "descricao": "Nenhum requisito MUST com critério de viabilidade = NÃO",
         "ok": not must_infeasible, "detalhes": must_infeasible},
        {"id": "prioridade_dependencias", "descricao": "Prioridades coerentes com as dependências",
         "ok": not [p for p in prios if p.get("alerta")], "detalhes": [p["id"] for p in prios if p.get("alerta")]},
        {"id": "consenso_sem_objecao", "descricao": "Consenso encerrado sem objeções pendentes",
         "ok": consensus is not None and not fechamento.get("override"), "detalhes": []},
        {"id": "sem_stale", "descricao": "Nenhuma versão desatualizada (stale)", "ok": not stale, "detalhes": stale},
    ]
    lacunas = {}
    for atype in ANALYSIS_EDITABLE:
        at = ARTIFACT_TYPES[atype]
        lacunas[atype] = sum(len(i.get("lacunas") or []) for i in _items(c.get(atype), at.list_field))
    return [WriteResult("analysis.review_report", {"checks": checks, "lacunas_por_artefato": lacunas},
                        origin="deterministic")]


async def t_3_3_2(ctx: TaskContext) -> list[WriteResult]:
    """Consolida a Fase 3: aprova as versões e compõe o ERD (Fases 1–2 aprovadas + Análise)."""
    cur = await store.current_versions(ctx.session, ctx.run.id)
    phase_types = set(ctx.phase.writers())
    await store.set_status(ctx.session, [v.id for t, v in cur.items() if t in phase_types], "approved")
    contents = {t: v.content for t, v in cur.items()}
    base = await erd.base_contents(ctx.session, ctx.run)
    meta = await visao._meta(ctx.session, ctx.run, "aprovado", f"3.{ctx.iteration - 1}")
    meta["base_run_id"] = str(ctx.run.base_run_id)
    part3 = doc.render_analysis_markdown(contents, base, meta, await erd.consensus_records(ctx.session, ctx.run))
    previous_erd = (ctx.package.required("requirements.draft") or {}).get("markdown", "")
    markdown = (f"{previous_erd}\n\n---\n\n> Parte 3 — Análise dos requisitos (Fase 3), acrescentada ao ERD.\n\n"
                f"{part3}")
    req_ids = [p["req_id"] for p in _items(contents.get("analysis.priorities"), "prioridades")]
    digest = await ctx.call("BuildPhaseDigest", T.DigestInput(documento=part3, ids_obrigatorios=req_ids))
    mentioned = set(digest.ids_cobertos) | {i for i in req_ids if i in digest.resumo}
    digest_content = digest.model_dump(mode="json")
    digest_content["ids_faltantes"] = sorted(set(req_ids) - mentioned)
    ctx.package.add(PackageItem(origin="related", ref=f"run:{ctx.run.base_run_id}:erd",
                                content=f"{len(previous_erd)} caracteres",
                                reason="ERD aprovado da fase anterior, incorporado sem alteração"))
    return [
        WriteResult("analysis.draft", {"markdown": markdown,
                                       "versoes": {t: str(v.id) for t, v in cur.items() if t in phase_types}},
                    origin="consolidation", status="approved"),
        WriteResult("digest.analysis", digest_content, status="approved"),
    ]


HANDLERS = {
    "3.1.1": t_3_1_1,
    "3.1.2": t_3_1_2,
    "3.2.1": t_3_2_1,
    "3.2.2": t_3_2_2,
    "3.2.3": t_3_2_3,
    "3.2.4": t_3_2_4,
    "3.2.5": t_3_2_5,
    "3.2.6": t_3_2_6,
    "3.3.1": t_3_3_1,
    "3.3.2": t_3_3_2,
}
