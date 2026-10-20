"""Registro dos tipos de artefato da Fase 1: schema BAML, campo de itens e prefixo de ID."""

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
                     lambda i: i.get("nome") or "", "Stakeholders"),
        ArtifactType("vision.stakeholder_needs", T.StakeholderNeedsArtifact, "solicitacoes", T.StakeholderNeed,
                     "SN", lambda i: f"{i.get('stakeholder_id')} {i.get('solicitacao')}",
                     "Solicitações dos stakeholders"),
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


def items_from_content(artifact_type: str, content: dict) -> list[tuple[str, dict]]:
    at = ARTIFACT_TYPES[artifact_type]
    if not at.list_field:
        return []
    return [(i["id"], i) for i in content.get(at.list_field, []) if i.get("id")]


def json_schema(artifact_type: str) -> dict | None:
    at = ARTIFACT_TYPES.get(artifact_type)
    return at.schema.model_json_schema() if at and at.schema else None
