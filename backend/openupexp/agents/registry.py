"""Registro dos tipos de artefato: schema BAML, campo de itens e prefixo de ID."""

from dataclasses import dataclass
from typing import Callable

from openupexp.baml_client import types as T


@dataclass(frozen=True)
class ArtifactType:
    name: str
    schema: type | None
    list_field: str | None = None
    item_schema: type | None = None
    prefix: str | None = None
    text_of: Callable[[dict], str] = lambda item: ""
    title: str = ""


ARTIFACT_TYPES: dict[str, ArtifactType] = {
    a.name: a
    for a in [
        ArtifactType("vision.problem", T.ExplainabilityProblem, title="Problema de explicabilidade"),
        ArtifactType("vision.stakeholders", T.StakeholdersArtifact, "stakeholders", T.Stakeholder, "STK",
                     lambda i: i.get("nome") or "", "Pessoas envolvidas"),
        ArtifactType("vision.stakeholder_needs", T.StakeholderNeedsArtifact, "solicitacoes", T.StakeholderNeed,
                     "SN", lambda i: f"{i.get('stakeholder_id')} {i.get('solicitacao')}",
                     "Solicitações das pessoas envolvidas"),
        ArtifactType("vision.domain_terms", T.DomainTermsArtifact, "termos", T.DomainTerm, "DT",
                     lambda i: i.get("termo") or "", "Terminologia do domínio"),
        ArtifactType("glossary", T.GlossaryArtifact, "termos", T.GlossaryTerm, "TERM",
                     lambda i: i.get("termo") or "", "Glossário"),
        ArtifactType("vision.explainability_needs", T.ExplainabilityNeedsArtifact, "necessidades",
                     T.ExplainabilityNeed, "NEED", lambda i: i.get("necessidade") or "",
                     "Necessidades de explicabilidade"),
        ArtifactType("vision.positioning", T.PositioningArtifact, "posicionamentos", T.Positioning, "POS",
                     lambda i: f"{i.get('stakeholder_id')} {i.get('para_que')}", "Posicionamento"),
        ArtifactType("vision.reference_queries", T.ReferenceQueryPlan, title="Consultas à base de referência"),
        ArtifactType("vision.complementary_requirements", T.ComplementaryRequirementsArtifact, "requisitos",
                     T.ComplementaryRequirement, "CR", lambda i: i.get("requisito") or "",
                     "Requisitos complementares"),
        ArtifactType("vision.limits", T.ExplainabilityLimitsArtifact, title="Limites da explicabilidade"),
        ArtifactType("vision.draft", None, title="Rascunho do Documento de Visão"),
        ArtifactType("vision.review_report", None, title="Checklist de pré-revisão"),
        ArtifactType("digest.vision", T.PhaseDigest, title="Digest da Visão"),
        # Fase 2 — formatos provisórios (A-14), ver docs/architecture/12-decisoes-pendentes.md
        ArtifactType("elicitation.vision_baseline", None, title="Visão aprovada (linha de base)"),
        ArtifactType("elicitation.plan", T.ElicitationPlanArtifact, "itens", T.ElicitationPlanItem, "EP",
                     lambda i: f"{i.get('stakeholder_id')} {i.get('objetivo')}", "Plano de elicitação"),
        ArtifactType("elicitation.sources", None, title="Material de elicitação"),
        ArtifactType("elicitation.needs", T.ElicitedNeedsArtifact, "necessidades", T.ElicitedNeed, "RN",
                     lambda i: f"{i.get('stakeholder_id')} {i.get('necessidade')}", "Necessidades elicitadas"),
        ArtifactType("requirements.identified", T.ExplainabilityRequirementsArtifact, "requisitos",
                     T.ExplainabilityRequirement, "RI", lambda i: i.get("enunciado") or "",
                     "Requisitos de explicabilidade identificados"),
        ArtifactType("requirements.complementary", T.PhaseComplementaryArtifact, "requisitos",
                     T.PhaseComplementaryRequirement, "RC", lambda i: i.get("requisito") or "",
                     "Requisitos complementares (Fase 2)"),
        ArtifactType("requirements.consolidated", T.ConsolidatedRequirementsArtifact, "requisitos",
                     T.ConsolidatedRequirement, "REQ", lambda i: i.get("enunciado") or "",
                     "Requisitos consolidados"),
        ArtifactType("requirements.review_report", None, title="Checklist de pré-revisão"),
        ArtifactType("requirements.draft", None, title="Documento de Requisitos de Explicabilidade"),
        ArtifactType("digest.requirements", T.PhaseDigest, title="Digest dos Requisitos"),
        # Fase 3 — taxonomias de tarefas/analisar-requisito.md; RER provisório (A-14)
        ArtifactType("analysis.baseline", None, title="Requisitos aprovados (linha de base)"),
        ArtifactType("analysis.characterized", T.CharacterizedRequirementsArtifact, "caracterizacoes",
                     T.CharacterizedRequirement, "RER", lambda i: i.get("req_id") or "",
                     "Requisitos caracterizados (RER)"),
        ArtifactType("analysis.aspects", T.AspectsArtifact, "classificacoes", T.AspectClassification, "ASP",
                     lambda i: i.get("req_id") or "", "Aspectos explicativos"),
        ArtifactType("analysis.explanation_types", T.ExplanationTypesArtifact, "mapeamentos",
                     T.ExplanationTypeMapping, "MAP", lambda i: i.get("req_id") or "",
                     "Mapeamento para tipos de explicação"),
        ArtifactType("analysis.conflicts", T.ConflictsArtifact, "conflitos", T.RequirementConflict, "CNF",
                     lambda i: f"{' '.join(i.get('req_ids') or [])} {i.get('descricao')}",
                     "Conflitos e alternativas de resolução"),
        ArtifactType("analysis.dependencies", T.DependenciesArtifact, "dependencias", T.DependencyAnalysis, "DEP",
                     lambda i: i.get("req_id") or "", "Dependências e restrições"),
        ArtifactType("analysis.feasibility", T.FeasibilityArtifact, "avaliacoes", T.FeasibilityAssessment, "FEA",
                     lambda i: i.get("req_id") or "", "Avaliação de viabilidade"),
        ArtifactType("analysis.priorities", T.PrioritiesArtifact, "prioridades", T.PriorityAssignment, "PRI",
                     lambda i: i.get("req_id") or "", "Prioridades MoSCoW"),
        ArtifactType("analysis.review_report", None, title="Checklist de pré-revisão"),
        ArtifactType("analysis.draft", None, title="Documento de Requisitos de Explicabilidade"),
        ArtifactType("digest.analysis", T.PhaseDigest, title="Digest da Análise"),
        # Fase 4 — formatos dos passos de tarefas/especificar-requisitos.md; provisórios (A-14, A-21)
        ArtifactType("specification.baseline", None, title="Análise aprovada (linha de base)"),
        ArtifactType("specification.plan", None, title="Fichas de especificação"),
        ArtifactType("specification.user_stories", T.UserStoriesArtifact, "historias", T.UserStory, "HU",
                     lambda i: f"{i.get('req_id')} {i.get('stakeholder_id')} {i.get('quero')}",
                     "Histórias de Usuário"),
        ArtifactType("specification.acceptance_criteria", T.AcceptanceCriteriaArtifact, "criterios",
                     T.AcceptanceCriteria, "CA", lambda i: i.get("hu_id") or "", "Critérios de aceitação"),
        ArtifactType("specification.characteristics", T.ExplanationCharacteristicsArtifact, "caracteristicas",
                     T.ExplanationCharacteristics, "CEX", lambda i: i.get("hu_id") or "",
                     "Características da explicação"),
        ArtifactType("specification.traceability", T.TraceabilityMatrix, "linhas", T.TraceabilityRow, "TR",
                     lambda i: i.get("hu") or "", "Matriz de rastreabilidade"),
        ArtifactType("specification.review_report", None, title="Checklist de pré-revisão"),
        ArtifactType("specification.draft", None, title="Documento de Requisitos de Explicabilidade (DRE)"),
        ArtifactType("digest.specification", T.PhaseDigest, title="Digest da Especificação"),
    ]
}

# Ordem de apresentação das seções editáveis no Documento de Visão.
VISION_EDITABLE = [
    "vision.problem",
    "vision.positioning",
    "vision.stakeholders",
    "vision.stakeholder_needs",
    "vision.explainability_needs",
    "vision.complementary_requirements",
    "vision.limits",
    "glossary",
]


REQUIREMENTS_EDITABLE = [
    "elicitation.plan",
    "elicitation.needs",
    "requirements.identified",
    "requirements.complementary",
    "requirements.consolidated",
]

ANALYSIS_EDITABLE = [
    "analysis.characterized",
    "analysis.aspects",
    "analysis.explanation_types",
    "analysis.conflicts",
    "analysis.dependencies",
    "analysis.feasibility",
    "analysis.priorities",
]

SPECIFICATION_EDITABLE = [
    "specification.user_stories",
    "specification.acceptance_criteria",
    "specification.characteristics",
    "specification.traceability",
]

# Por fase: seções editáveis (em ordem), documento da fase e checklist de pré-revisão.
PHASE_EDITABLE = {"1": VISION_EDITABLE, "2": REQUIREMENTS_EDITABLE, "3": ANALYSIS_EDITABLE,
                  "4": SPECIFICATION_EDITABLE}
PHASE_DOCUMENT = {"1": "vision.draft", "2": "requirements.draft", "3": "analysis.draft",
                  "4": "specification.draft"}
PHASE_REVIEW_REPORT = {"1": "vision.review_report", "2": "requirements.review_report",
                       "3": "analysis.review_report", "4": "specification.review_report"}


def items_from_content(artifact_type: str, content: dict) -> list[tuple[str, dict]]:
    at = ARTIFACT_TYPES[artifact_type]
    if not at.list_field:
        return []
    return [(i["id"], i) for i in content.get(at.list_field, []) if i.get("id")]


def json_schema(artifact_type: str) -> dict | None:
    at = ARTIFACT_TYPES.get(artifact_type)
    return at.schema.model_json_schema() if at and at.schema else None
