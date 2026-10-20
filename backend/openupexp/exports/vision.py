"""Renderização do Documento de Visão em Markdown (artefato documental versionado)."""

import uuid
from datetime import datetime
from pathlib import Path

from jinja2 import ChainableUndefined, Environment, FileSystemLoader, Undefined
from sqlalchemy.ext.asyncio import AsyncSession

from openupexp.db.models import Export, Project, Run
from openupexp.domain import artifacts as store

TEMPLATE_VERSION = "visao-1.0"
PENDENTE = "_Não identificado; requer investigação._"

SECTIONS_5 = [
    ("NORMAS_REGULAMENTOS", "5.1 Padrões, Normas e Regulamentos Aplicáveis"),
    ("PLATAFORMA_DESEMPENHO", "5.2 Requisitos de Plataforma, Hardware e Desempenho"),
    ("QUALIDADE_EXPLICACOES", "5.3 Requisitos de Qualidade das Explicações"),
    ("RESTRICOES_DEPENDENCIAS", "5.4 Restrições de Design, Dependências e Assunções"),
    ("DOCUMENTACAO_SUPORTE", "5.5 Requisitos de Documentação e Suporte"),
]

_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    trim_blocks=True,
    lstrip_blocks=True,
    undefined=ChainableUndefined,
    keep_trailing_newline=True,
)


def _t(value) -> str:
    if isinstance(value, Undefined) or value is None or value == "" or value == []:
        return PENDENTE
    return str(value).replace("\r", " ").strip()


def _cell(value) -> str:
    return _t(value).replace("|", r"\|").replace("\n", " ")


def _lst(value) -> str:
    if isinstance(value, Undefined) or not value:
        return ""
    return ", ".join(str(v) for v in value)


_env.filters.update(t=_t, c=_cell, lst=_lst)


def _lacunas(contents: dict[str, dict]) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    problem = contents.get("vision.problem") or {}
    out += [("Problema", lac) for lac in problem.get("lacunas", [])]
    for atype, field, label in [
        ("vision.stakeholders", "stakeholders", "Stakeholder"),
        ("vision.explainability_needs", "necessidades", "Necessidade"),
        ("vision.positioning", "posicionamentos", "Posicionamento"),
        ("glossary", "termos", "Glossário"),
    ]:
        for item in (contents.get(atype) or {}).get(field, []):
            out += [(f"{label} {item.get('id')}", lac) for lac in item.get("lacunas", [])]
    for r in (contents.get("vision.limits") or {}).get("respostas", []):
        if r.get("lacuna"):
            out.append((f"Limite · {r.get('dimensao')}", r["lacuna"]))
    return out


def render_vision_markdown(contents: dict[str, dict], meta: dict) -> str:
    stakeholders = (contents.get("vision.stakeholders") or {}).get("stakeholders", [])
    names = {s.get("id"): s.get("nome") for s in stakeholders}
    limits = (contents.get("vision.limits") or {}).get("respostas", [])
    grouped: dict[str, list] = {}
    for r in limits:
        grouped.setdefault(r.get("dimensao", "Outros"), []).append(r)
    return _env.get_template("visao.md.j2").render(
        meta=meta,
        problem=contents.get("vision.problem"),
        positioning=(contents.get("vision.positioning") or {}).get("posicionamentos", []),
        stakeholders=stakeholders,
        stakeholder_needs=(contents.get("vision.stakeholder_needs") or {}).get("solicitacoes", []),
        needs=(contents.get("vision.explainability_needs") or {}).get("necessidades", []),
        complementary=(contents.get("vision.complementary_requirements") or {}).get("requisitos", []),
        limits_by_dimension=list(grouped.items()),
        glossary=(contents.get("glossary") or {}).get("termos", []),
        lacunas=_lacunas(contents),
        sections5=SECTIONS_5,
        stakeholder_name=lambda sid: names.get(sid, sid),
    )


async def current_contents(session: AsyncSession, run: Run) -> dict[str, dict]:
    return {t: v.content for t, v in (await store.current_versions(session, run.id)).items()}


async def _meta(session: AsyncSession, run: Run, status: str, versao: str) -> dict:
    project = await session.get(Project, run.project_id)
    return {
        "projeto": project.nome if project else "—",
        "data": datetime.now().strftime("%d/%m/%Y"),
        "versao": versao,
        "run_id": str(run.id),
        "estrategia": run.context_strategy,
        "manifesto": run.manifest_version,
        "status": status,
    }


async def render_current_document(session: AsyncSession, run: Run) -> str:
    contents = await current_contents(session, run)
    return render_vision_markdown(contents, await _meta(session, run, "rascunho", "—"))


async def export_markdown(
    session: AsyncSession, run: Run, version_id: uuid.UUID, markdown: str
) -> Export:
    from openupexp.exports.documents import export_markdown as _export

    return await _export(session, run, version_id, markdown)
