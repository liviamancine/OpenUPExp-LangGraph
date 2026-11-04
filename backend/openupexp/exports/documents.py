"""Documento de cada fase: prévia com as versões atuais e exportação versionada."""

import hashlib
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from openupexp.config import get_settings
from openupexp.db.models import Export, Run
from openupexp.exports import analysis, requirements, specification, vision

EXPORT_NAMES = {"1": ("documento-visao", vision.TEMPLATE_VERSION),
                "2": ("erd-fase2", requirements.TEMPLATE_VERSION),
                "3": ("erd-fase3", analysis.TEMPLATE_VERSION),
                "4": ("dre", specification.TEMPLATE_VERSION)}


async def render_current_document(session: AsyncSession, run: Run) -> str:
    if run.phase == "4":
        contents = await vision.current_contents(session, run)
        meta = await vision._meta(session, run, "rascunho", "—")
        meta["base_run_id"] = str(run.base_run_id)
        return specification.render_specification_markdown(
            contents, meta, await requirements.consensus_records(session, run))
    if run.phase == "3":
        contents = await vision.current_contents(session, run)
        base = await requirements.base_contents(session, run)
        meta = await vision._meta(session, run, "rascunho", "—")
        meta["base_run_id"] = str(run.base_run_id)
        return analysis.render_analysis_markdown(
            contents, base, meta, await requirements.consensus_records(session, run))
    if run.phase == "2":
        contents = await vision.current_contents(session, run)
        base = await requirements.base_contents(session, run)
        meta = await vision._meta(session, run, "rascunho", "—")
        meta["base_run_id"] = str(run.base_run_id)
        return requirements.render_requirements_markdown(
            contents, base, meta, await requirements.consensus_records(session, run))
    return await vision.render_current_document(session, run)


async def export_markdown(session: AsyncSession, run: Run, version_id: uuid.UUID, markdown: str) -> Export:
    prefix, template_version = EXPORT_NAMES.get(run.phase, EXPORT_NAMES["1"])
    folder = get_settings().data_dir / "projects" / str(run.project_id) / "exports" / str(run.id)
    folder.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(markdown.encode()).hexdigest()
    path = folder / f"{prefix}-{sha[:10]}.md"
    path.write_text(markdown, encoding="utf-8")
    exp = Export(
        run_id=run.id, artifact_version_id=version_id, formato="md",
        template_version=template_version, storage_path=str(path), sha256=sha,
    )
    session.add(exp)
    await session.flush()
    return exp
