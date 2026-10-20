"""Handlers das tarefas da Fase 2 (Elicitação) — um por tarefa do manifesto.

Ver docs/architecture/03-fases-2-4-preliminar.md §3.1 e 12-decisoes-pendentes.md §12.4.
Tarefas com muitos itens rodam em map (uma chamada por stakeholder ou por necessidade),
cada uma só com o próprio contexto; um join determinístico garante que nenhum item se perde.
"""

import math

from sqlalchemy import select

from openupexp.agents.evidence import verify_item_evidences
from openupexp.agents.phase1 import _dump_list, _items, _models
from openupexp.agents.registry import ARTIFACT_TYPES, REQUIREMENTS_EDITABLE, VISION_EDITABLE
from openupexp.agents.runtime import TaskContext, WriteResult
from openupexp.baml_client import types as T
from openupexp.context.builder import PackageItem
from openupexp.db.models import Chunk, HitlRequest, HitlResponse, SourceDocument
from openupexp.domain import artifacts as store
from openupexp.exports import requirements as erd
from openupexp.exports import vision as visao
from openupexp.retrieval.ingest import ELICITATION_KINDS, build_corpus_version
from openupexp.retrieval.search import ChunkHit, hybrid_search

MAX_SIMILAR_PAIRS = 40


class BaseVisionNotApproved(Exception):
    pass


def _add_hit(ctx: TaskContext, hit: ChunkHit, reason: str) -> None:
    if any(it.ref == hit.ref for it in ctx.package.items):
        return
    ctx.package.add(PackageItem(
        origin="retrieved", ref=hit.ref,
        content=f"Fonte: {hit.meta.get('arquivo', '?')}, página {hit.pagina}\n{hit.texto}", reason=reason,
    ))


# ---------------------------------------------------------------------------
# 2.1 Prepare Explainability Elicitation
# ---------------------------------------------------------------------------


async def t_2_1_1(ctx: TaskContext) -> list[WriteResult]:
    """Carrega a Visão aprovada da execução de base e lista suas lacunas abertas."""
    if not ctx.run.base_run_id:
        raise BaseVisionNotApproved("A Fase 2 precisa de uma execução da Fase 1 como base.")
    cur = await store.current_versions(ctx.session, ctx.run.base_run_id)
    draft = cur.get("vision.draft")
    if draft is None or draft.status != "approved":
        raise BaseVisionNotApproved("A Visão da execução de base ainda não foi aprovada (gateway 1.3).")
    contents = {t: v.content for t, v in cur.items()}
    itens = {}
    for atype in VISION_EDITABLE:
        at = ARTIFACT_TYPES[atype]
        if at.list_field:
            itens[atype] = [i.get("id") for i in (contents.get(atype) or {}).get(at.list_field, [])]
    lacunas = [f"{origem} · {lac.get('campo')}: {lac.get('pergunta_sugerida') or lac.get('motivo')}"
               for origem, lac in visao._lacunas(contents)]
    return [WriteResult("elicitation.vision_baseline", {
        "base_run_id": str(ctx.run.base_run_id), "visao_version_id": str(draft.id),
        "versoes": {t: str(cur[t].id) for t in VISION_EDITABLE if t in cur},
        "itens": itens, "lacunas_abertas": lacunas,
    }, origin="deterministic")]


async def t_2_1_2(ctx: TaskContext) -> list[WriteResult]:
    stakeholders = _items(ctx.package.required("vision.stakeholders"), "stakeholders")
    base = dict(
        necessidades=_models(T.ExplainabilityNeed,
                             _items(ctx.package.required("vision.explainability_needs"), "necessidades")),
        lacunas_visao=list((ctx.package.required("elicitation.vision_baseline") or {}).get("lacunas_abertas", [])),
        plano_existente=_models(T.ElicitationPlanItem, _items(ctx.package.previous("elicitation.plan"), "itens")),
    )
    out = await ctx.call("PlanElicitation", T.PlanElicitationInput(
        stakeholders=_models(T.Stakeholder, stakeholders), **base))
    result = _dump_list(out.itens)

    # coverage guard: um item de plano por stakeholder (nova tentativa só com os faltantes)
    missing = [s for s in stakeholders if s["id"] not in {p.get("stakeholder_id") for p in result}]
    if missing:
        retry = await ctx.call("PlanElicitation", T.PlanElicitationInput(
            stakeholders=_models(T.Stakeholder, missing), **base))
        result += _dump_list(retry.itens)
        covered = {p.get("stakeholder_id") for p in result}
        ctx.package.coverage.output_missing_ids = [s["id"] for s in stakeholders if s["id"] not in covered]
    return [WriteResult("elicitation.plan", {}, raw_items=result)]


# ---------------------------------------------------------------------------
# 2.2 Elicit Explainability Requirements
# ---------------------------------------------------------------------------


async def _input_justification(ctx: TaskContext) -> str | None:
    resp = await ctx.session.scalar(
        select(HitlResponse).join(HitlRequest, HitlRequest.id == HitlResponse.hitl_request_id)
        .where(HitlRequest.run_id == ctx.run.id, HitlRequest.kind == "input", HitlRequest.task_id == f"{ctx.task.id}.in")
        .order_by(HitlResponse.created_at.desc()).limit(1)
    )
    return resp.comentario if resp else None


async def t_2_2_1(ctx: TaskContext) -> list[WriteResult]:
    """Map por stakeholder: busca no material de elicitação e extração com citação verificada."""
    s, run, retrieval = ctx.session, ctx.run, ctx.task.retrieval
    docs = (await s.scalars(select(SourceDocument).where(
        SourceDocument.project_id == run.project_id, SourceDocument.ativo.is_(True),
        SourceDocument.source_kind.in_(ELICITATION_KINDS)).order_by(SourceDocument.created_at))).all()
    cv = None
    if docs:
        cv = await build_corpus_version(s, run.project_id, ctx.embedder, kinds=ELICITATION_KINDS,
                                        purpose="elicitation", run_id=run.id)
    sources_content = {
        "documentos": [{"id": str(d.id), "arquivo": d.arquivo, "source_kind": d.source_kind,
                        "paginas": d.paginas, "sha256": d.sha256} for d in docs],
        "corpus_version_id": str(cv.id) if cv else None,
        "chunks": cv.stats.get("chunks") if cv else 0,
        "justificativa": None if docs else await _input_justification(ctx),
    }

    plan = {p.get("stakeholder_id"): p for p in _items(ctx.package.required("elicitation.plan"), "itens")}
    stakeholders = _items(ctx.package.required("vision.stakeholders"), "stakeholders")
    sns = _items(ctx.package.required("vision.stakeholder_needs"), "solicitacoes")
    needs = _models(T.ExplainabilityNeed, _items(ctx.package.required("vision.explainability_needs"), "necessidades"))
    prev = _items(ctx.package.previous("elicitation.needs"), "necessidades")

    raw_all: list[dict] = []
    pending_all: list[tuple[int, dict]] = []
    for stk in stakeholders:
        own_sns = [sn for sn in sns if sn.get("stakeholder_id") == stk["id"]]
        sources = {sn["id"]: (sn.get("solicitacao") or "", None) for sn in own_sns if sn.get("id")}
        refs: set[str] = set()
        p = plan.get(stk["id"])
        if cv is not None:
            query = " ".join([stk.get("nome") or "", *(p.get("perguntas", []) if p else [])])
            for hit in await hybrid_search(s, cv.id, query, ctx.embedder, k=retrieval.top_k,
                                           kinds=list(ELICITATION_KINDS), mode=retrieval.mode):
                _add_hit(ctx, hit, f"material de elicitação para {stk['id']} (score {hit.score:.4f})")
                refs.add(hit.ref)
                sources[hit.ref] = (hit.texto, hit.id)
        out = await ctx.call("ExtractElicitedNeeds", T.ExtractNeedsInput(
            stakeholder=T.Stakeholder.model_validate(stk),
            plano=T.ElicitationPlanItem.model_validate(p) if p else None,
            solicitacoes_visao=_models(T.StakeholderNeed, own_sns),
            necessidades_visao=needs,
            necessidades_existentes=_models(T.ElicitedNeed, [n for n in prev if n.get("stakeholder_id") == stk["id"]]),
        ), retrieved=refs)
        raw = _dump_list(out.necessidades)
        for r in raw:
            r["stakeholder_id"] = r.get("stakeholder_id") or stk["id"]
        pending = verify_item_evidences(
            raw, sources, ref_key="fonte_ref",
            kind_of=lambda ev: "ELICITACAO" if str(ev.get("fonte_ref", "")).startswith("chunk:") else "VISAO")
        pending_all += [(len(raw_all) + i, ev) for i, ev in pending]
        raw_all += raw

    return [
        WriteResult("elicitation.sources", sources_content, origin="deterministic"),
        WriteResult("elicitation.needs", {}, raw_items=raw_all, item_evidences=pending_all),
    ]


async def t_2_2_2(ctx: TaskContext) -> list[WriteResult]:
    """Map por necessidade da Visão; necessidades elicitadas novas vão numa chamada própria."""
    rns = _items(ctx.package.required("elicitation.needs"), "necessidades")
    needs = _items(ctx.package.required("vision.explainability_needs"), "necessidades")
    base = dict(
        stakeholders=_models(T.Stakeholder, _items(ctx.package.required("vision.stakeholders"), "stakeholders")),
        glossario=_models(T.GlossaryTerm, _items(ctx.package.required("glossary"), "termos")),
        requisitos_existentes=_models(T.ExplainabilityRequirement,
                                      _items(ctx.package.previous("requirements.identified"), "requisitos")),
    )
    need_ids = {n["id"] for n in needs}

    async def identify(need: dict | None, group: list[dict]) -> list[dict]:
        out = await ctx.call("IdentifyExplainabilityRequirements", T.IdentifyRequirementsInput(
            necessidade=T.ExplainabilityNeed.model_validate(need) if need else None,
            necessidades_elicitadas=_models(T.ElicitedNeed, group), **base))
        return _dump_list(out.requisitos)

    raw: list[dict] = []
    for need in needs:
        group = [rn for rn in rns if need["id"] in (rn.get("need_ids") or [])]
        if group:
            raw += await identify(need, group)
    novel = [rn for rn in rns if not set(rn.get("need_ids") or []) & need_ids]
    if novel:
        raw += await identify(None, novel)

    # join determinístico: toda RN precisa sustentar algum requisito
    covered = {i for r in raw for i in r.get("rn_ids") or []}
    missing = [rn for rn in rns if rn["id"] not in covered]
    if missing:
        raw += await identify(None, missing)
        covered = {i for r in raw for i in r.get("rn_ids") or []}
        ctx.package.coverage.output_missing_ids = [rn["id"] for rn in rns if rn["id"] not in covered]
    return [WriteResult("requirements.identified", {}, raw_items=raw)]


async def t_2_2_3(ctx: TaskContext) -> list[WriteResult]:
    """Refina os CR-n da Visão com a base de referência, consultada pelos requisitos elicitados."""
    s, run, retrieval = ctx.session, ctx.run, ctx.task.retrieval
    ris = _items(ctx.package.required("requirements.identified"), "requisitos")
    crs = _items(ctx.package.required("vision.complementary_requirements"), "requisitos")
    sources: dict = {}
    if run.corpus_version_id:
        # trechos que já fundamentavam os CR-n da Visão
        keys = {e.get("chunk_ref", "")[len("chunk:"):] for cr in crs for e in cr.get("evidencias", [])}
        if keys:
            for c in (await s.scalars(select(Chunk).where(Chunk.corpus_version_id == run.corpus_version_id,
                                                          Chunk.stable_key.in_(keys)))).all():
                hit = ChunkHit(c.id, c.stable_key, c.texto, c.pagina, c.source_kind, c.meta, 0.0, ["visao"])
                _add_hit(ctx, hit, "evidência de requisito complementar da Visão")
                sources[hit.ref] = (hit.texto, hit.id)
        hits: dict = {}
        for ri in ris:
            query = " ".join(x for x in [ri.get("enunciado"), ri.get("decisao_alvo")] if x)
            for h in await hybrid_search(s, run.corpus_version_id, query, ctx.embedder,
                                         k=retrieval.per_query_k, mode=retrieval.mode):
                if h.id not in hits or hits[h.id][0].score < h.score:
                    hits[h.id] = (h, ri["id"])
        for h, ri_id in sorted(hits.values(), key=lambda x: x[0].score, reverse=True)[: retrieval.top_k]:
            _add_hit(ctx, h, f"busca {retrieval.mode} para {ri_id} (score {h.score:.4f})")
            sources[h.ref] = (h.texto, h.id)

    out = await ctx.call("RefineComplementaryRequirements", T.RefineComplementaryInput(
        requisitos=_models(T.ExplainabilityRequirement, ris),
        requisitos_complementares_visao=_models(T.ComplementaryRequirement, crs),
        requisitos_existentes=_models(T.PhaseComplementaryRequirement,
                                      _items(ctx.package.previous("requirements.complementary"), "requisitos")),
    ))
    raw = _dump_list(out.requisitos)
    pending = verify_item_evidences(raw, sources)
    return [WriteResult("requirements.complementary", {}, raw_items=raw, item_evidences=pending)]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


async def t_2_2_4(ctx: TaskContext) -> list[WriteResult]:
    """Consolidação com candidatos a duplicidade por similaridade e garantia de cobertura."""
    ris = _items(ctx.package.required("requirements.identified"), "requisitos")
    rcs = _items(ctx.package.required("requirements.complementary"), "requisitos")
    texts = [(r["id"], r.get("enunciado") or "") for r in ris] + [(r["id"], r.get("requisito") or "") for r in rcs]
    pairs: list[T.SimilarPair] = []
    if len(texts) > 1:
        vectors = ctx.embedder.encode_passages([t for _, t in texts])
        threshold = ctx.task.similarity_threshold or 0.9
        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                sim = _cosine(vectors[i], vectors[j])
                if sim >= threshold:
                    pairs.append(T.SimilarPair(a=texts[i][0], b=texts[j][0], similaridade=round(sim, 4)))
        pairs = sorted(pairs, key=lambda p: p.similaridade, reverse=True)[:MAX_SIMILAR_PAIRS]
    ctx.package.add(PackageItem(
        origin="related", ref=f"similaridade:{ctx.task.id}",
        content=[p.model_dump() for p in pairs],
        reason=f"pares com similaridade ≥ {ctx.task.similarity_threshold or 0.9} ({ctx.embedder.model})",
    ))

    base = dict(consolidados_existentes=_models(
        T.ConsolidatedRequirement, _items(ctx.package.previous("requirements.consolidated"), "requisitos")))
    out = await ctx.call("ConsolidateRequirements", T.ConsolidateInput(
        requisitos=_models(T.ExplainabilityRequirement, ris),
        complementares=_models(T.PhaseComplementaryRequirement, rcs), pares_similares=pairs, **base))
    raw, discarded = _dump_list(out.requisitos), _dump_list(out.descartados)

    # join determinístico: todo RI/RC é consolidado ou descartado com motivo
    expected = [i for i, _ in texts]

    def covered() -> set[str]:
        return {i for r in raw for i in r.get("origem_ids") or []} | {d.get("origem_id") for d in discarded}

    missing = [i for i in expected if i not in covered()]
    if missing:
        retry = await ctx.call("ConsolidateRequirements", T.ConsolidateInput(
            requisitos=_models(T.ExplainabilityRequirement, [r for r in ris if r["id"] in missing]),
            complementares=_models(T.PhaseComplementaryRequirement, [r for r in rcs if r["id"] in missing]),
            pares_similares=[], **base))
        raw += _dump_list(retry.requisitos)
        discarded += _dump_list(retry.descartados)
        ctx.package.coverage.output_missing_ids = [i for i in expected if i not in covered()]
    return [WriteResult("requirements.consolidated", {"descartados": discarded}, raw_items=raw)]


# ---------------------------------------------------------------------------
# 2.3 Validate Explainability Requirements
# ---------------------------------------------------------------------------


async def _last_consensus(ctx: TaskContext) -> HitlRequest | None:
    return await ctx.session.scalar(
        select(HitlRequest).where(HitlRequest.run_id == ctx.run.id, HitlRequest.kind == "consensus",
                                  HitlRequest.status == "decided")
        .order_by(HitlRequest.created_at.desc()).limit(1))


async def t_2_3_1(ctx: TaskContext) -> list[WriteResult]:
    """Checklist objetivo de pré-revisão. Não substitui a revisão humana."""
    cur = await store.current_versions(ctx.session, ctx.run.id)
    c = {k: v.content for k, v in cur.items()}
    base = await erd.base_contents(ctx.session, ctx.run)
    stk = {s["id"] for s in _items(base.get("vision.stakeholders"), "stakeholders")}
    needs = {n["id"] for n in _items(base.get("vision.explainability_needs"), "necessidades")}
    plan = _items(c.get("elicitation.plan"), "itens")
    rns = _items(c.get("elicitation.needs"), "necessidades")
    ris = _items(c.get("requirements.identified"), "requisitos")
    rcs = _items(c.get("requirements.complementary"), "requisitos")
    reqs = _items(c.get("requirements.consolidated"), "requisitos")
    discarded = (c.get("requirements.consolidated") or {}).get("descartados", [])
    sources = c.get("elicitation.sources") or {}
    req_needs = {i for r in reqs for i in r.get("need_ids") or []}
    origins = {i for r in reqs for i in r.get("origem_ids") or []} | {d.get("origem_id") for d in discarded}
    consensus = await _last_consensus(ctx)
    fechamento = (consensus.payload or {}).get("fechamento", {}) if consensus else {}
    stale = [k for k, v in cur.items() if v.status == "stale" and k in REQUIREMENTS_EDITABLE]

    checks = [
        {"id": "plano_por_stk", "descricao": "Todo stakeholder da Visão tem plano de elicitação",
         "ok": stk <= {p.get("stakeholder_id") for p in plan},
         "detalhes": sorted(stk - {p.get("stakeholder_id") for p in plan})},
        {"id": "material_elicitacao", "descricao": "Houve material de elicitação (não só a Visão)",
         "ok": bool(sources.get("documentos")), "detalhes": []},
        {"id": "rn_citacao", "descricao": "Toda necessidade elicitada tem citação verificada",
         "ok": all(r.get("fundamentacao_verificada") for r in rns),
         "detalhes": [r["id"] for r in rns if not r.get("fundamentacao_verificada")]},
        {"id": "need_coberta", "descricao": "Toda necessidade da Visão é atendida por algum requisito",
         "ok": needs <= req_needs, "detalhes": sorted(needs - req_needs)},
        {"id": "origem_consolidada", "descricao": "Todo RI/RC foi consolidado ou descartado com motivo",
         "ok": {r["id"] for r in ris + rcs} <= origins, "detalhes": sorted({r["id"] for r in ris + rcs} - origins)},
        {"id": "req_tem_stk", "descricao": "Todo requisito de explicabilidade aponta stakeholder",
         "ok": all(set(r.get("stakeholder_ids") or []) & stk for r in reqs if r.get("tipo") == "EXPLICABILIDADE"),
         "detalhes": [r["id"] for r in reqs if r.get("tipo") == "EXPLICABILIDADE"
                      and not set(r.get("stakeholder_ids") or []) & stk]},
        {"id": "rc_evidencia", "descricao": "Todo requisito complementar tem evidência verificada",
         "ok": all(r.get("fundamentacao_verificada") for r in rcs),
         "detalhes": [r["id"] for r in rcs if not r.get("fundamentacao_verificada")]},
        {"id": "consenso_sem_objecao", "descricao": "Consenso (2.2.5) encerrado sem objeções pendentes",
         "ok": consensus is not None and not fechamento.get("override"),
         "detalhes": [f"{n} objeção(ões)" for n in [fechamento.get("objecoes")] if n]},
        {"id": "sem_stale", "descricao": "Nenhuma versão desatualizada (stale)", "ok": not stale, "detalhes": stale},
    ]
    lacunas = {}
    for atype in REQUIREMENTS_EDITABLE:
        at = ARTIFACT_TYPES[atype]
        lacunas[atype] = sum(len(i.get("lacunas", [])) for i in (c.get(atype) or {}).get(at.list_field, []))
    return [WriteResult("requirements.review_report", {"checks": checks, "lacunas_por_artefato": lacunas},
                        origin="deterministic")]


async def t_2_3_2(ctx: TaskContext) -> list[WriteResult]:
    """Consolida a Fase 2: aprova as versões e compõe o ERD (Visão aprovada + Requisitos)."""
    cur = await store.current_versions(ctx.session, ctx.run.id)
    phase_types = set(ctx.phase.writers())
    await store.set_status(ctx.session, [v.id for t, v in cur.items() if t in phase_types], "approved")
    contents = {t: v.content for t, v in cur.items()}
    base = await erd.base_contents(ctx.session, ctx.run)
    meta = await visao._meta(ctx.session, ctx.run, "aprovado", f"2.{ctx.iteration - 1}")
    meta["base_run_id"] = str(ctx.run.base_run_id)
    part2 = erd.render_requirements_markdown(contents, base, meta, await erd.consensus_records(ctx.session, ctx.run))
    vision_md = (ctx.package.required("vision.draft") or {}).get("markdown", "")
    markdown = (
        "# Documento de Requisitos de Explicabilidade (ERD)\n\n"
        "> Composição provisória (A-12): Parte 1 — Visão aprovada na Fase 1, com o Glossário;\n"
        "> Parte 2 — Requisitos elicitados na Fase 2.\n\n---\n\n"
        f"{vision_md}\n\n---\n\n{part2}"
    )
    req_ids = [r["id"] for r in _items(contents.get("requirements.consolidated"), "requisitos")]
    digest = await ctx.call("BuildPhaseDigest", T.DigestInput(documento=part2, ids_obrigatorios=req_ids))
    mentioned = set(digest.ids_cobertos) | {i for i in req_ids if i in digest.resumo}
    digest_content = digest.model_dump(mode="json")
    digest_content["ids_faltantes"] = sorted(set(req_ids) - mentioned)
    return [
        WriteResult("requirements.draft", {"markdown": markdown,
                                           "versoes": {t: str(v.id) for t, v in cur.items() if t in phase_types}},
                    origin="consolidation", status="approved"),
        WriteResult("digest.requirements", digest_content, status="approved"),
    ]


HANDLERS = {
    "2.1.1": t_2_1_1,
    "2.1.2": t_2_1_2,
    "2.2.1": t_2_2_1,
    "2.2.2": t_2_2_2,
    "2.2.3": t_2_2_3,
    "2.2.4": t_2_2_4,
    "2.3.1": t_2_3_1,
    "2.3.2": t_2_3_2,
}
