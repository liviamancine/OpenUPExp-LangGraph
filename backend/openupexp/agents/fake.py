"""Agentes simulados: saídas determinísticas derivadas das entradas.

Servem para testar o processo (conformidade, HITL, versionamento, contexto) sem
LLM. Não pretendem ter qualidade de conteúdo. Cada função tem a mesma
assinatura da função BAML homônima.
"""

import re
from collections import Counter

from openupexp.baml_client import types as T

_ROLE_WORDS = [
    "solicitante", "procurador", "examinador", "regulador", "analista", "auditor",
    "cliente", "usuário final", "gestor", "paciente", "médico", "operador",
]
_STOP = set(
    "para pelo pela como mais sobre entre desde quando onde deve devem será serão "
    "sistema projeto processo também essas esses estas estes cada todos todas".split()
)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[\.\!\?])\s+|\n+", text) if len(s.strip()) > 20]


def _find_sentence(text: str, word: str) -> str | None:
    for s in _sentences(text):
        if word.lower() in s.lower():
            return s[:300]
    return None


def _lacuna(campo: str, pergunta: str | None = None) -> T.Lacuna:
    return T.Lacuna(campo=campo, motivo="Informação não encontrada nas entradas (agente simulado).",
                    pergunta_sugerida=pergunta)


def DefineExplainabilityProblem(entrada: T.DefineProblemInput, contexto) -> T.ExplainabilityProblem:
    text = entrada.documento_escopo
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    roles = [r.capitalize() for r in _ROLE_WORDS if r in text.lower()] or ["Usuário final"]
    descricao = next((s for s in _sentences(text) if len(s) > 60), lines[0] if lines else "")
    return T.ExplainabilityProblem(
        necessidade_de_explicabilidade=(
            "Os stakeholders precisam compreender os critérios das decisões apoiadas pelo sistema."
        ),
        descricao_geral=descricao,
        dominio_do_problema=lines[0] if lines else "",
        stakeholders_mencionados=roles,
        impactos=[],
        criterios_de_sucesso=None,
        declaracao_problema=T.ProblemStatement(
            o_problema_da="falta de explicabilidade das decisões do sistema",
            afeta=roles, cujo_impacto_e=[], solucao_bem_sucedida=None,
        ),
        lacunas=[_lacuna("criterios_de_sucesso", "Quais critérios indicam sucesso da explicabilidade?")],
    )


def IdentifyStakeholders(entrada: T.IdentifyStakeholdersInput, contexto) -> T.StakeholdersArtifact:
    existing = {s.nome.lower(): s.id for s in entrada.stakeholders_existentes}
    out = []
    for nome in entrada.problema.stakeholders_mencionados:
        sentence = _find_sentence(entrada.documento_escopo, nome)
        out.append(T.Stakeholder(
            id=existing.get(nome.lower()), nome=nome,
            descricao=sentence or f"{nome} mencionado no problema de explicabilidade.",
            responsabilidade=None, ambiente_usuario=None,
            origem=[T.OrigemRef(referencia="escopo", relacao="mencionado no documento de escopo")],
            lacunas=[_lacuna("responsabilidade")],
        ))
    return T.StakeholdersArtifact(stakeholders=out)


def IdentifyStakeholderNeeds(entrada: T.IdentifyStakeholderNeedsInput, contexto) -> T.StakeholderNeedsArtifact:
    existing = {s.stakeholder_id: s.id for s in entrada.solicitacoes_existentes}
    out = []
    for s in entrada.stakeholders:
        sentence = _find_sentence(entrada.documento_escopo, s.nome)
        if sentence:
            out.append(T.StakeholderNeed(
                id=existing.get(s.id), stakeholder_id=s.id or "", solicitacao=sentence,
                origem=[T.OrigemRef(referencia="escopo", relacao="trecho literal do escopo")],
            ))
    return T.StakeholderNeedsArtifact(solicitacoes=out)


def CaptureDomainTerminology(entrada: T.CaptureTermsInput, contexto) -> T.DomainTermsArtifact:
    words = [w.lower() for w in re.findall(r"[A-Za-zÀ-ÿ]{7,}", entrada.documento_escopo)]
    common = [w for w, _ in Counter(w for w in words if w not in _STOP).most_common(8)]
    return T.DomainTermsArtifact(termos=[
        T.DomainTerm(id=None, termo=w, contexto_de_uso=_find_sentence(entrada.documento_escopo, w) or w)
        for w in common
    ])


def CreateInitialGlossary(entrada: T.CreateGlossaryInput, contexto) -> T.GlossaryArtifact:
    existing = {g.termo.lower(): g.id for g in entrada.glossario_existente}
    return T.GlossaryArtifact(termos=[
        T.GlossaryTerm(id=existing.get(t.termo.lower()), termo=t.termo, definicao=None, sinonimos=[],
                       termo_origem_id=t.id, lacunas=[_lacuna("definicao", f"O que significa '{t.termo}'?")])
        for t in entrada.termos
    ])


def IdentifyExplainabilityNeeds(entrada: T.IdentifyNeedsInput, contexto) -> T.ExplainabilityNeedsArtifact:
    existing = {tuple(n.stakeholder_ids): n.id for n in entrada.necessidades_existentes}
    out = []
    for s in entrada.stakeholders:
        sns = [sn.id for sn in entrada.solicitacoes if sn.stakeholder_id == s.id and sn.id]
        if not sns:
            continue
        out.append(T.ExplainabilityNeed(
            id=existing.get((s.id,)),
            necessidade=f"{s.nome} precisa compreender os fatores considerados nas decisões que o afetam.",
            stakeholder_ids=[s.id or ""], solicitacao_ids=sns, prioridade=None, planned_release=None,
            aspecto_associado=None, lacunas=[_lacuna("prioridade")],
        ))
    return T.ExplainabilityNeedsArtifact(necessidades=out)


def GenerateExplainabilityPositioning(entrada: T.PositioningInput, contexto) -> T.PositioningArtifact:
    existing = {p.stakeholder_id: p.id for p in entrada.posicionamentos_existentes}
    out = []
    for s in entrada.stakeholders:
        needs = [n.id or "" for n in entrada.necessidades if s.id in n.stakeholder_ids]
        out.append(T.Positioning(
            id=existing.get(s.id), stakeholder_id=s.id or "", para_quem=s.nome,
            para_que="compreender, auditar ou contestar as decisões do sistema",
            nome_produto=None, categoria_produto=None, beneficio_chave=None, unlike=None,
            our_product=None, need_ids=needs, lacunas=[_lacuna("unlike")],
        ))
    return T.PositioningArtifact(posicionamentos=out)


def PlanReferenceQueries(entrada: T.PlanQueriesInput, contexto) -> T.ReferenceQueryPlan:
    dominio = entrada.problema.dominio_do_problema
    text = " ".join([entrada.problema.necessidade_de_explicabilidade, entrada.problema.descricao_geral])
    refs = re.findall(r"(?:Lei\s*n?[º°]?\s*[\d\.]+(?:\s*art\.?\s*\d+)?)", text, re.IGNORECASE)
    return T.ReferenceQueryPlan(consultas=[
        T.ReferenceQuery(secao=T.ComplementaryCategory.NORMAS_REGULAMENTOS,
                         consulta=f"direito à revisão e explicação de decisões automatizadas {dominio}",
                         tipos_fonte=["lei"], referencias_explicitas=refs),
        T.ReferenceQuery(secao=T.ComplementaryCategory.QUALIDADE_EXPLICACOES,
                         consulta="qualidade e compreensibilidade das explicações para stakeholders",
                         tipos_fonte=["academico"], referencias_explicitas=[]),
        T.ReferenceQuery(secao=T.ComplementaryCategory.DOCUMENTACAO_SUPORTE,
                         consulta=f"critérios e fundamentação das decisões {dominio}",
                         tipos_fonte=["manual"], referencias_explicitas=[]),
    ])


def _retrieved(contexto) -> list[tuple[str, str, str]]:
    out = []
    for c in contexto:
        if c.origem == "retrieved":
            header, _, body = c.conteudo.partition("\n")
            out.append((c.referencia, header, body))
    return out


def DevelopComplementaryRequirements(entrada: T.ComplementaryInput, contexto) -> T.ComplementaryRequirementsArtifact:
    need = entrada.necessidades[0].id if entrada.necessidades else ""
    out = []
    for ref, header, body in _retrieved(contexto)[:3]:
        is_law = ":art" in ref
        quote = body.strip().split("\n")[0][:160]
        out.append(T.ComplementaryRequirement(
            id=None,
            categoria=T.ComplementaryCategory.NORMAS_REGULAMENTOS if is_law
            else T.ComplementaryCategory.QUALIDADE_EXPLICACOES,
            requisito=f"O sistema deve considerar a orientação de {header.replace('Fonte: ', '')} "
                      "na explicação das decisões.",
            justificativa=f"Relacionado a {need}; trecho recuperado da base de referência.",
            need_ids=[need] if need else [],
            evidencias=[T.EvidenceRef(chunk_ref=ref, citacao=quote,
                                      tipo=T.EvidenceKind.OBRIGACAO_NORMATIVA if is_law
                                      else T.EvidenceKind.RECOMENDACAO_TECNICA)],
        ))
    return T.ComplementaryRequirementsArtifact(requisitos=out)


def DefineExplainabilityLimits(entrada: T.LimitsInput, contexto) -> T.ExplainabilityLimitsArtifact:
    nomes = ", ".join(s.nome for s in entrada.stakeholders)
    out = []
    for q in entrada.checklist:
        if q.dimensao == "Stakeholders" and q.pergunta.startswith("Quem precisa"):
            out.append(T.LimitAnswer(dimensao=q.dimensao, pergunta=q.pergunta, resposta=nomes,
                                     baseada_em=[T.OrigemRef(referencia=s.id or "", relacao="stakeholder")
                                                 for s in entrada.stakeholders], lacuna=None))
        else:
            out.append(T.LimitAnswer(dimensao=q.dimensao, pergunta=q.pergunta, resposta=None, baseada_em=[],
                                     lacuna=_lacuna(q.dimensao, q.pergunta)))
    return T.ExplainabilityLimitsArtifact(respostas=out)


def BuildPhaseDigest(entrada: T.DigestInput, contexto) -> T.PhaseDigest:
    return T.PhaseDigest(
        resumo="Resumo simulado da fase aprovada. Itens: " + ", ".join(entrada.ids_obrigatorios),
        ids_cobertos=list(entrada.ids_obrigatorios),
    )


# ---------------------------------------------------------------------------
# Fase 2 — Elicitação
# ---------------------------------------------------------------------------

_PERGUNTAS_PADRAO = [
    "Quais decisões do sistema afetam o seu trabalho ou os seus direitos?",
    "Em que situação você precisa de uma explicação sobre essas decisões?",
    "O que uma boa explicação deveria permitir que você fizesse?",
]


def PlanElicitation(entrada: T.PlanElicitationInput, contexto) -> T.ElicitationPlanArtifact:
    existing = {p.stakeholder_id: p.id for p in entrada.plano_existente}
    out = []
    for s in entrada.stakeholders:
        alvo = [lac for lac in entrada.lacunas_visao if s.id and s.id in lac][:2]
        out.append(T.ElicitationPlanItem(
            id=existing.get(s.id), stakeholder_id=s.id or "",
            objetivo=f"Compreender quais decisões do sistema {s.nome} precisa ver explicadas e por quê.",
            tecnicas=[T.ElicitationTechnique.ENTREVISTA], perguntas=list(_PERGUNTAS_PADRAO),
            need_ids=[n.id or "" for n in entrada.necessidades if s.id in n.stakeholder_ids],
            lacunas_alvo=alvo, lacunas=[],
        ))
    return T.ElicitationPlanArtifact(itens=out)


def ExtractElicitedNeeds(entrada: T.ExtractNeedsInput, contexto) -> T.ElicitedNeedsArtifact:
    s = entrada.stakeholder
    needs = [n.id or "" for n in entrada.necessidades_visao if s.id in n.stakeholder_ids][:1]
    existing = [n.id for n in entrada.necessidades_existentes]
    found: list[tuple[str, str]] = []
    for ref, _, body in _retrieved(contexto):
        sentence = _find_sentence(body, s.nome)
        if sentence:
            found.append((ref, sentence))
    if not found:
        found = [(sn.id or "", sn.solicitacao) for sn in entrada.solicitacoes_visao if sn.id]
    out = []
    for i, (ref, quote) in enumerate(found[:2]):
        out.append(T.ElicitedNeed(
            id=existing[i] if i < len(existing) else None, stakeholder_id=s.id or "",
            necessidade=f"{s.nome} precisa entender o motivo das decisões descritas em: {quote[:160]}",
            decisao_alvo=None, objetivo=T.ExplanationGoal.COMPREENSAO, need_ids=needs,
            evidencias=[T.ElicitationEvidence(fonte_ref=ref, citacao=quote)],
            lacunas=[_lacuna("decisao_alvo", f"Qual decisão do sistema {s.nome} precisa ver explicada?")],
        ))
    return T.ElicitedNeedsArtifact(necessidades=out)


def IdentifyExplainabilityRequirements(entrada: T.IdentifyRequirementsInput, contexto) -> T.ExplainabilityRequirementsArtifact:
    names = {s.id: s.nome for s in entrada.stakeholders}
    existing = {tuple(r.rn_ids): r.id for r in entrada.requisitos_existentes}
    out = []
    for rn in entrada.necessidades_elicitadas:
        nome = names.get(rn.stakeholder_id, rn.stakeholder_id)
        out.append(T.ExplainabilityRequirement(
            id=existing.get((rn.id,)),
            enunciado=f"O sistema deve explicar a {nome} os fatores considerados nas decisões que o afetam.",
            stakeholder_ids=[rn.stakeholder_id], need_ids=list(rn.need_ids), rn_ids=[rn.id or ""],
            objetivo=rn.objetivo or T.ExplanationGoal.COMPREENSAO, decisao_alvo=rn.decisao_alvo,
            contexto_de_uso=None, lacunas=[],
        ))
    return T.ExplainabilityRequirementsArtifact(requisitos=out)


def RefineComplementaryRequirements(entrada: T.RefineComplementaryInput, contexto) -> T.PhaseComplementaryArtifact:
    ri = [entrada.requisitos[0].id or ""] if entrada.requisitos else []
    existing = {tuple(r.cr_ids): r.id for r in entrada.requisitos_existentes}
    out = [T.PhaseComplementaryRequirement(
        id=existing.get((cr.id,)), categoria=cr.categoria, requisito=cr.requisito,
        justificativa=f"Refina {cr.id} à luz dos requisitos elicitados.", ri_ids=ri, cr_ids=[cr.id or ""],
        evidencias=list(cr.evidencias),
    ) for cr in entrada.requisitos_complementares_visao]
    return T.PhaseComplementaryArtifact(requisitos=out)


def ConsolidateRequirements(entrada: T.ConsolidateInput, contexto) -> T.ConsolidatedRequirementsArtifact:
    existing = {tuple(r.origem_ids): r.id for r in entrada.consolidados_existentes}
    merged_into: dict[str, str] = {}
    ri_ids = {r.id for r in entrada.requisitos}
    for p in entrada.pares_similares:
        if p.a in ri_ids and p.b in ri_ids and p.b not in merged_into and p.a not in merged_into:
            merged_into[p.b] = p.a
    out = []
    for r in entrada.requisitos:
        if r.id in merged_into:
            continue
        group = [r] + [x for x in entrada.requisitos if merged_into.get(x.id) == r.id]
        origem = [x.id or "" for x in group]
        out.append(T.ConsolidatedRequirement(
            id=existing.get(tuple(origem)), enunciado=r.enunciado, tipo=T.RequirementKind.EXPLICABILIDADE,
            objetivo=r.objetivo, categoria=None,
            stakeholder_ids=sorted({s for x in group for s in x.stakeholder_ids}),
            need_ids=sorted({n for x in group for n in x.need_ids}), origem_ids=origem,
            justificativa_agrupamento="Requisitos equivalentes (similaridade alta)." if len(group) > 1 else None,
            lacunas=[],
        ))
    for c in entrada.complementares:
        out.append(T.ConsolidatedRequirement(
            id=existing.get((c.id,)), enunciado=c.requisito, tipo=T.RequirementKind.COMPLEMENTAR, objetivo=None,
            categoria=c.categoria, stakeholder_ids=[], need_ids=[], origem_ids=[c.id or ""],
            justificativa_agrupamento=None, lacunas=[],
        ))
    return T.ConsolidatedRequirementsArtifact(requisitos=out, descartados=[])
