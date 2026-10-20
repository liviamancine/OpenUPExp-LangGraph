"""Handlers das tarefas da Fase 1 (Visão) — um por tarefa do manifesto.

Ver docs/architecture/02-mapeamento-fase-1-visao.md.
"""

from openupexp.agents.registry import ARTIFACT_TYPES, VISION_EDITABLE
from openupexp.agents.runtime import TaskContext, WriteResult
from openupexp.baml_client import types as T
from openupexp.context.builder import PackageItem
from openupexp.exports.vision import render_vision_markdown
from openupexp.retrieval.citations import verify_quote
from openupexp.retrieval.search import hybrid_search

# Checklist "Limite da Explicabilidade" — OpenUPExp/artefatos/DRE.md
LIMITS_CHECKLIST: list[tuple[str, str]] = [
    ("Escopo da Explicação", "Quais decisões, recomendações, previsões do sistema exigem explicação?"),
    ("Escopo da Explicação", "Todas as decisões precisam ser explicadas, apenas as críticas, ou apenas as decisões solicitados pelo cliente?"),
    ("Escopo da Explicação", "A explicação é obrigatória, opcional ou sob demanda?"),
    ("Stakeholders", "Quem precisa receber explicações?"),
    ("Stakeholders", "Todos os stakeholders recebem o mesmo tipo de explicação?"),
    ("Stakeholders", "Algum stakeholder não deve receber certos detalhes?"),
    ("Tipo e Forma de Explicação", "Explicação local, global ou ambas?"),
    ("Tipo e Forma de Explicação", "Forma: textual, visual, numérica, simbólica?"),
    ("Tipo e Forma de Explicação", "Linguagem técnica ou acessível?"),
    ("Momento da explicação", "A explicação será fornecida antes, durante ou após a decisão?"),
    ("Momento da explicação", "A explicação pode ser solicitada sob demanda?"),
    ("Entradas e saídas", "Quais dados de entrada influenciam a explicação?"),
    ("Entradas e saídas", "Quais informações fazem parte da saída explicativa?"),
    ("Entradas e saídas", "Existem dados sensíveis que não devem aparecer na explicação?"),
    ("Restrições", "Existem limitações técnicas para explicar certos modelos?"),
    ("Restrições", "Há restrições legais ou regulatórias?"),
    ("Restrições", "O custo computacional da explicação é aceitável?"),
    ("Rastreabilidade", "A explicação pode ser auditada posteriormente?"),
    ("Rastreabilidade", "Existe necessidade de versionamento?"),
]


def _items(content: dict | None, field: str) -> list[dict]:
    return list((content or {}).get(field, []))


def _models(cls, rows: list[dict]):
    return [cls.model_validate(r) for r in rows]


def _dump_list(objs) -> list[dict]:
    return [o.model_dump(mode="json") for o in objs]


# ---------------------------------------------------------------------------
# 1.1 Prepare Explainability Vision
# ---------------------------------------------------------------------------


async def t_1_1_1(ctx: TaskContext) -> list[WriteResult]:
    out = await ctx.call("DefineExplainabilityProblem", T.DefineProblemInput(
        documento_escopo=ctx.package.required("project.scope_document")))
    return [WriteResult("vision.problem", out.model_dump(mode="json"))]


async def t_1_1_2(ctx: TaskContext) -> list[WriteResult]:
    prev = _items(ctx.package.previous("vision.stakeholders"), "stakeholders")
    out = await ctx.call("IdentifyStakeholders", T.IdentifyStakeholdersInput(
        problema=T.ExplainabilityProblem.model_validate(ctx.package.required("vision.problem")),
        documento_escopo=ctx.package.required("project.scope_document"),
        stakeholders_existentes=_models(T.Stakeholder, prev),
    ))
    return [WriteResult("vision.stakeholders", {}, raw_items=_dump_list(out.stakeholders))]


async def t_1_1_3(ctx: TaskContext) -> list[WriteResult]:
    stakeholders = _items(ctx.package.required("vision.stakeholders"), "stakeholders")
    prev = _items(ctx.package.previous("vision.stakeholder_needs"), "solicitacoes")
    out = await ctx.call("IdentifyStakeholderNeeds", T.IdentifyStakeholderNeedsInput(
        stakeholders=_models(T.Stakeholder, stakeholders),
        documento_escopo=ctx.package.required("project.scope_document"),
        solicitacoes_existentes=_models(T.StakeholderNeed, prev),
    ))
    valid = {s["id"] for s in stakeholders}
    raw = _dump_list(out.solicitacoes)
    for r in raw:
        if r.get("stakeholder_id") not in valid:
            r["alerta"] = f"stakeholder_id inexistente: {r.get('stakeholder_id')}"
    return [WriteResult("vision.stakeholder_needs", {}, raw_items=raw)]


async def t_1_1_4(ctx: TaskContext) -> list[WriteResult]:
    out = await ctx.call("CaptureDomainTerminology", T.CaptureTermsInput(
        documento_escopo=ctx.package.required("project.scope_document"),
        problema=T.ExplainabilityProblem.model_validate(ctx.package.required("vision.problem")),
    ))
    return [WriteResult("vision.domain_terms", {}, raw_items=_dump_list(out.termos))]


async def t_1_1_5(ctx: TaskContext) -> list[WriteResult]:
    terms = _items(ctx.package.required("vision.domain_terms"), "termos")
    prev = _items(ctx.package.previous("glossary"), "termos")
    out = await ctx.call("CreateInitialGlossary", T.CreateGlossaryInput(
        termos=_models(T.DomainTerm, terms), glossario_existente=_models(T.GlossaryTerm, prev)))
    return [WriteResult("glossary", {}, raw_items=_dump_list(out.termos))]


# ---------------------------------------------------------------------------
# 1.2 Develop Explainability Vision
# ---------------------------------------------------------------------------


async def t_1_2_1(ctx: TaskContext) -> list[WriteResult]:
    out = await ctx.call("IdentifyExplainabilityNeeds", T.IdentifyNeedsInput(
        stakeholders=_models(T.Stakeholder, _items(ctx.package.required("vision.stakeholders"), "stakeholders")),
        solicitacoes=_models(T.StakeholderNeed,
                             _items(ctx.package.required("vision.stakeholder_needs"), "solicitacoes")),
        glossario=_models(T.GlossaryTerm, _items(ctx.package.required("glossary"), "termos")),
        necessidades_existentes=_models(
            T.ExplainabilityNeed, _items(ctx.package.previous("vision.explainability_needs"), "necessidades")),
    ))
    return [WriteResult("vision.explainability_needs", {}, raw_items=_dump_list(out.necessidades))]


async def t_1_2_pos(ctx: TaskContext) -> list[WriteResult]:
    stakeholders = _items(ctx.package.required("vision.stakeholders"), "stakeholders")
    base = dict(
        problema=T.ExplainabilityProblem.model_validate(ctx.package.required("vision.problem")),
        necessidades=_models(T.ExplainabilityNeed,
                             _items(ctx.package.required("vision.explainability_needs"), "necessidades")),
        posicionamentos_existentes=_models(
            T.Positioning, _items(ctx.package.previous("vision.positioning"), "posicionamentos")),
    )
    out = await ctx.call("GenerateExplainabilityPositioning", T.PositioningInput(
        stakeholders=_models(T.Stakeholder, stakeholders), **base))
    result = _dump_list(out.posicionamentos)

    # coverage guard: um posicionamento por stakeholder (nova tentativa só com os faltantes)
    missing = [s for s in stakeholders if s["id"] not in {p.get("stakeholder_id") for p in result}]
    if missing:
        retry = await ctx.call("GenerateExplainabilityPositioning", T.PositioningInput(
            stakeholders=_models(T.Stakeholder, missing), **base))
        result += _dump_list(retry.posicionamentos)
        covered = {p.get("stakeholder_id") for p in result}
        ctx.package.coverage.output_missing_ids = [s["id"] for s in stakeholders if s["id"] not in covered]
    return [WriteResult("vision.positioning", {}, raw_items=result)]


async def t_1_2_2(ctx: TaskContext) -> list[WriteResult]:
    problema = T.ExplainabilityProblem.model_validate(ctx.package.required("vision.problem"))
    needs = _models(T.ExplainabilityNeed, _items(ctx.package.required("vision.explainability_needs"), "necessidades"))
    plan = await ctx.call("PlanReferenceQueries", T.PlanQueriesInput(problema=problema, necessidades=needs))

    retrieval = ctx.task.retrieval
    hits = {}
    if ctx.run.corpus_version_id:
        for q in plan.consultas:
            query = " ".join([q.consulta, *q.referencias_explicitas])
            kinds = [k for k in q.tipos_fonte if k in ("lei", "manual", "academico")] or None
            for h in await hybrid_search(ctx.session, ctx.run.corpus_version_id, query, ctx.embedder,
                                         k=retrieval.per_query_k, kinds=kinds, mode=retrieval.mode):
                if h.id not in hits or hits[h.id][0].score < h.score:
                    hits[h.id] = (h, q.secao.value)
    chosen = sorted(hits.values(), key=lambda x: x[0].score, reverse=True)[: retrieval.top_k]
    by_ref = {}
    for h, secao in chosen:
        arquivo = h.meta.get("arquivo", "?")
        ctx.package.add(PackageItem(
            origin="retrieved", ref=h.ref,
            content=f"Fonte: {arquivo}, página {h.pagina}\n{h.texto}",
            reason=f"busca {retrieval.mode} para {secao} (score {h.score:.4f}, via {'+'.join(h.via)})",
        ))
        by_ref[h.ref] = h

    prev = _items(ctx.package.previous("vision.complementary_requirements"), "requisitos")
    out = await ctx.call("DevelopComplementaryRequirements", T.ComplementaryInput(
        problema=problema, necessidades=needs,
        requisitos_existentes=_models(T.ComplementaryRequirement, prev)))

    raw = _dump_list(out.requisitos)
    pending_evidence: list[tuple[int, dict]] = []
    for idx, req in enumerate(raw):
        verified_any = False
        for ev in req.get("evidencias", []):
            ref = (ev.get("chunk_ref") or "").split()[0] if ev.get("chunk_ref") else ""
            if ref and not ref.startswith("chunk:"):
                ref = f"chunk:{ref}"
            hit = by_ref.get(ref)
            if hit is None:
                verification = "source_not_provided"
            elif verify_quote(ev.get("citacao", ""), hit.texto):
                verification = "verified"
                verified_any = True
            else:
                verification = "unverified_quote"
            ev["chunk_ref"] = ref or ev.get("chunk_ref")
            ev["verificacao"] = verification
            pending_evidence.append((idx, dict(ev, chunk_id=hit.id if hit else None)))
        req["fundamentacao_verificada"] = verified_any

    return [
        WriteResult("vision.reference_queries", plan.model_dump(mode="json")),
        WriteResult("vision.complementary_requirements", {}, raw_items=raw,
                    item_evidences=pending_evidence),
    ]


async def t_1_2_3(ctx: TaskContext) -> list[WriteResult]:
    checklist = [T.ChecklistQuestion(dimensao=d, pergunta=q) for d, q in LIMITS_CHECKLIST]
    out = await ctx.call("DefineExplainabilityLimits", T.LimitsInput(
        stakeholders=_models(T.Stakeholder, _items(ctx.package.required("vision.stakeholders"), "stakeholders")),
        necessidades=_models(T.ExplainabilityNeed,
                             _items(ctx.package.required("vision.explainability_needs"), "necessidades")),
        requisitos_complementares=_models(
            T.ComplementaryRequirement,
            _items(ctx.package.required("vision.complementary_requirements"), "requisitos")),
        checklist=checklist,
    ))
    # completude determinística: toda pergunta do checklist tem uma resposta (ou lacuna)
    answered = {a.pergunta.strip(): a for a in out.respostas}
    respostas = []
    for q in checklist:
        a = answered.get(q.pergunta.strip())
        if a is None:
            a = T.LimitAnswer(dimensao=q.dimensao, pergunta=q.pergunta, resposta=None, baseada_em=[],
                              lacuna=T.Lacuna(campo=q.dimensao, motivo="Pergunta não respondida pelo agente.",
                                              pergunta_sugerida=q.pergunta))
        respostas.append(a.model_dump(mode="json"))
    return [WriteResult("vision.limits", {"respostas": respostas})]


async def t_1_2_4(ctx: TaskContext) -> list[WriteResult]:
    contents = {r.artifact: ctx.package.required(r.artifact) for r in ctx.task.reads}
    contents = {k: v for k, v in contents.items() if v is not None}
    markdown = render_vision_markdown(contents, {
        "projeto": str(ctx.run.project_id), "data": "—", "versao": f"rascunho (iteração {ctx.iteration})",
        "run_id": str(ctx.run.id), "estrategia": ctx.run.context_strategy,
        "manifesto": ctx.run.manifest_version, "status": "rascunho",
    })
    versions = {r.artifact: r.version_id for r in ctx.package.items if r.origin == "required" and r.version_id}
    return [WriteResult("vision.draft", {"markdown": markdown, "versoes": versions}, origin="deterministic")]


# ---------------------------------------------------------------------------
# 1.3 Validate Explainability Vision
# ---------------------------------------------------------------------------


async def t_1_3_1(ctx: TaskContext) -> list[WriteResult]:
    """Checklist objetivo de pré-revisão. Não substitui a revisão humana (A-08)."""
    from openupexp.domain import artifacts as store

    cur = await store.current_versions(ctx.session, ctx.run.id)
    c = {k: v.content for k, v in cur.items()}
    stk = {s["id"] for s in _items(c.get("vision.stakeholders"), "stakeholders")}
    pos = {p.get("stakeholder_id") for p in _items(c.get("vision.positioning"), "posicionamentos")}
    needs = _items(c.get("vision.explainability_needs"), "necessidades")
    crs = _items(c.get("vision.complementary_requirements"), "requisitos")
    limits = _items(c.get("vision.limits"), "respostas")

    checks = [
        {"id": "stk_tem_pos", "descricao": "Todo stakeholder tem posicionamento (§2.2)",
         "ok": stk <= pos, "detalhes": sorted(stk - pos)},
        {"id": "need_tem_stk", "descricao": "Toda necessidade aponta para stakeholder existente",
         "ok": all(set(n.get("stakeholder_ids") or []) & stk for n in needs),
         "detalhes": [n["id"] for n in needs if not set(n.get("stakeholder_ids") or []) & stk]},
        {"id": "need_tem_origem", "descricao": "Toda necessidade é sustentada por solicitações (SN)",
         "ok": all(n.get("solicitacao_ids") for n in needs),
         "detalhes": [n["id"] for n in needs if not n.get("solicitacao_ids")]},
        {"id": "cr_tem_evidencia", "descricao": "Todo requisito complementar tem evidência verificada",
         "ok": all(r.get("fundamentacao_verificada") for r in crs),
         "detalhes": [r["id"] for r in crs if not r.get("fundamentacao_verificada")]},
        {"id": "cr_tem_need", "descricao": "Todo requisito complementar se relaciona a uma necessidade",
         "ok": all(r.get("need_ids") for r in crs), "detalhes": [r["id"] for r in crs if not r.get("need_ids")]},
        {"id": "limites_completos", "descricao": "Checklist de limites com todas as perguntas",
         "ok": len(limits) == len(LIMITS_CHECKLIST), "detalhes": []},
        {"id": "sem_stale", "descricao": "Nenhuma versão desatualizada (stale)",
         "ok": not [k for k, v in cur.items() if v.status == "stale" and k in VISION_EDITABLE],
         "detalhes": [k for k, v in cur.items() if v.status == "stale" and k in VISION_EDITABLE]},
    ]
    lacunas = {}
    for atype in VISION_EDITABLE:
        content = c.get(atype) or {}
        at = ARTIFACT_TYPES[atype]
        n = len(content.get("lacunas", []))
        for item in content.get(at.list_field, []) if at.list_field else []:
            n += len(item.get("lacunas", []))
        if atype == "vision.limits":
            n = sum(1 for r in limits if not r.get("resposta"))
        lacunas[atype] = n
    return [WriteResult("vision.review_report", {"checks": checks, "lacunas_por_artefato": lacunas},
                        origin="deterministic")]


HANDLERS = {
    "1.1.1": t_1_1_1,
    "1.1.2": t_1_1_2,
    "1.1.3": t_1_1_3,
    "1.1.4": t_1_1_4,
    "1.1.5": t_1_1_5,
    "1.2.1": t_1_2_1,
    "1.2.pos": t_1_2_pos,
    "1.2.2": t_1_2_2,
    "1.2.3": t_1_2_3,
    "1.2.4": t_1_2_4,
    "1.3.1": t_1_3_1,
}

