"""Renderização do Documento de Visão em Markdown (artefato documental versionado)."""

import uuid
from datetime import datetime
from pathlib import Path

from jinja2 import ChainableUndefined, Environment, FileSystemLoader, Undefined
from sqlalchemy.ext.asyncio import AsyncSession

from openupexp.db.models import Export, Project, Run
from openupexp.domain import artifacts as store
from openupexp.domain import labels

TEMPLATE_VERSION = "visao-1.0"
PENDENTE = "_Não identificado; requer investigação._"

SECTIONS_5 = [
    ("NORMAS_REGULAMENTOS", "5.1 Padrões, Normas e Regulamentos Aplicáveis"),
    ("PLATAFORMA_DESEMPENHO", "5.2 Requisitos de Plataforma, Hardware e Desempenho"),
    ("QUALIDADE_EXPLICACOES", "5.3 Requisitos de Qualidade das Explicações"),
    ("RESTRICOES_DEPENDENCIAS", "5.4 Restrições de Design, Dependências e Assunções"),
    ("DOCUMENTACAO_SUPORTE", "5.5 Requisitos de Documentação e Suporte"),
]
# A partir do manifesto 0.6.0 a seção 5 traz Informações complementares, não requisitos.
SECTIONS_5_INFO = [
    ("NORMAS_REGULAMENTOS", "5.1 Padrões, Normas e Regulamentos Aplicáveis"),
    ("PLATAFORMA_DESEMPENHO", "5.2 Plataforma, Hardware e Desempenho"),
    ("QUALIDADE_EXPLICACOES", "5.3 Qualidade das Explicações"),
    ("RESTRICOES_DEPENDENCIAS", "5.4 Restrições de Design, Dependências e Assunções"),
    ("DOCUMENTACAO_SUPORTE", "5.5 Documentação e Suporte"),
]


def complementary_as_information(manifest_version: str | None) -> bool:
    try:
        return tuple(int(x) for x in (manifest_version or "").split(".")) >= (0, 6, 0)
    except ValueError:
        return False

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


_env.filters.update(t=_t, c=_cell, lst=_lst, v=labels.value_label)


def _lacunas(contents: dict[str, dict]) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    index = labels.label_index(contents)
    problem = contents.get("vision.problem") or {}
    out += [("Definição", lac) for lac in problem.get("lacunas", [])]
    statement = contents.get("vision.problem_statement") or {}
    out += [("Declaração do problema", lac) for lac in statement.get("lacunas", [])]
    for atype, field, label in [
        ("vision.stakeholders", "stakeholders", "Stakeholder"),
        ("vision.explainability_needs", "necessidades", "Necessidade"),
        ("vision.positioning", "posicionamentos", "Posicionamento"),
        ("glossary", "termos", "Glossário"),
    ]:
        for item in (contents.get(atype) or {}).get(field, []):
            out += [(f"{label} {labels.ref(index, item.get('id'))}", lac) for lac in item.get("lacunas", [])]
    for r in (contents.get("vision.limits") or {}).get("respostas", []):
        if r.get("lacuna"):
            out.append((f"Limite · {r.get('dimensao')}", r["lacuna"]))
    return out


def render_vision_markdown(contents: dict[str, dict], meta: dict) -> str:
    stakeholders = (contents.get("vision.stakeholders") or {}).get("stakeholders", [])
    names = {s.get("id"): s.get("nome") for s in stakeholders}
    limits = (contents.get("vision.limits") or {}).get("respostas", [])
    index = labels.label_index(contents)
    grouped: dict[str, list] = {}
    for r in limits:
        grouped.setdefault(r.get("dimensao", "Outros"), []).append(r)
    problem = contents.get("vision.problem")
    # 0.5.0: Declaração do Problema própria (1.1.2); até o 0.4.0 ela vinha dentro do problema (1.1.1)
    statement = contents.get("vision.problem_statement") or (problem or {}).get("declaracao_problema")
    profiles = {p.get("id"): p.get("para_quem") for p in (contents.get("vision.positioning") or {}).get("posicionamentos", [])}
    return _env.get_template("visao.md.j2").render(
        meta=meta,
        problem=problem,
        statement=statement,
        profile_name=lambda pid: profiles.get(pid, pid),
        positioning=(contents.get("vision.positioning") or {}).get("posicionamentos", []),
        stakeholders=stakeholders,
        stakeholder_needs=(contents.get("vision.stakeholder_needs") or {}).get("solicitacoes", []),
        needs=(contents.get("vision.explainability_needs") or {}).get("necessidades", []),
        complementary=(contents.get("vision.complementary_requirements") or {}).get("requisitos", []),
        limits_by_dimension=list(grouped.items()),
        glossary=(contents.get("glossary") or {}).get("termos", []),
        glossary_off=bool((contents.get("glossary") or {}).get("desligado")),
        lacunas=_lacunas(contents),
        info_mode=complementary_as_information(meta.get("manifesto")),
        sections5=SECTIONS_5_INFO if complementary_as_information(meta.get("manifesto")) else SECTIONS_5,
        stakeholder_name=lambda sid: names.get(sid, sid),
        stakeholder_names=lambda ids: ", ".join(names.get(i, i) for i in ids or []),
        refs=lambda keys: labels.refs(index, keys),
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
