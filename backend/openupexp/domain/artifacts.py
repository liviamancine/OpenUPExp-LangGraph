"""Artifact Store: versões, itens, dependências, rastreabilidade e invalidação.

Ver docs/architecture/06-modelo-de-dados.md §6.4–6.5.
A versão "atual" de um artefato é sempre a de maior version_no.
"""

import hashlib
import json
import uuid

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession

from openupexp.db.models import (
    Artifact,
    ArtifactDependency,
    ArtifactItem,
    ArtifactVersion,
    Evidence,
    TraceLink,
)

OPEN_STATUSES = ("draft", "in_review", "stale")


def schema_hash(model_cls) -> str | None:
    if model_cls is None:
        return None
    raw = json.dumps(model_cls.model_json_schema(), sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


async def get_artifact(session: AsyncSession, run_id: uuid.UUID, artifact_type: str) -> Artifact | None:
    return await session.scalar(
        select(Artifact).where(Artifact.run_id == run_id, Artifact.artifact_type == artifact_type)
    )


async def current_version(
    session: AsyncSession, run_id: uuid.UUID, artifact_type: str
) -> ArtifactVersion | None:
    return await session.scalar(
        select(ArtifactVersion)
        .join(Artifact, ArtifactVersion.artifact_id == Artifact.id)
        .where(Artifact.run_id == run_id, Artifact.artifact_type == artifact_type)
        .order_by(ArtifactVersion.version_no.desc())
        .limit(1)
    )


async def current_versions(session: AsyncSession, run_id: uuid.UUID) -> dict[str, ArtifactVersion]:
    rows = await session.execute(
        select(Artifact.artifact_type, ArtifactVersion)
        .join(ArtifactVersion, ArtifactVersion.artifact_id == Artifact.id)
        .where(Artifact.run_id == run_id)
        .order_by(Artifact.artifact_type, ArtifactVersion.version_no.desc())
        .ext(distinct_on(Artifact.artifact_type))
    )
    return {t: v for t, v in rows.all()}


async def items_of(session: AsyncSession, version_id: uuid.UUID) -> dict[str, dict]:
    rows = await session.execute(
        select(ArtifactItem.item_key, ArtifactItem.content)
        .where(ArtifactItem.artifact_version_id == version_id)
        .order_by(ArtifactItem.item_key)
    )
    return {k: c for k, c in rows.all()}


async def save_version(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    phase: str,
    artifact_type: str,
    content: dict,
    origin: str,
    items: list[tuple[str, dict]] | None = None,
    schema_name: str | None = None,
    schema_sha: str | None = None,
    depends_on: dict[uuid.UUID, str] | None = None,
    produced_by_task: uuid.UUID | None = None,
    created_by_user: uuid.UUID | None = None,
    status: str = "draft",
    iteracao: int = 1,
    invalidate: bool = True,
) -> ArtifactVersion:
    """Grava uma nova versão; a anterior passa a superseded e seus dependentes a stale.

    invalidate=False é usado em edições humanas: os dependentes não são invalidados
    automaticamente (o revisor decide se pede retorno); a proveniência registrada
    continua apontando para a versão que o agente efetivamente usou.
    """
    artifact = await get_artifact(session, run_id, artifact_type)
    if artifact is None:
        artifact = Artifact(project_id=project_id, run_id=run_id, artifact_type=artifact_type, phase=phase)
        session.add(artifact)
        await session.flush()

    previous = await current_version(session, run_id, artifact_type)
    version = ArtifactVersion(
        artifact_id=artifact.id,
        version_no=(previous.version_no + 1) if previous else 1,
        status=status,
        origin=origin,
        schema_name=schema_name,
        schema_hash=schema_sha,
        content=content,
        iteracao=iteracao,
        produced_by_task=produced_by_task,
        created_by_user=created_by_user,
        supersedes_id=previous.id if previous else None,
    )
    session.add(version)
    await session.flush()

    for key, item in items or []:
        session.add(ArtifactItem(artifact_version_id=version.id, item_key=key, content=item))
    for dep_id, via in (depends_on or {}).items():
        session.add(ArtifactDependency(version_id=version.id, depends_on_version_id=dep_id, via_read=via))
    await session.flush()

    if previous is not None:
        previous.status = "superseded"
        if invalidate:
            await invalidate_dependents(session, previous.id)
    return version


async def invalidate_dependents(session: AsyncSession, version_id: uuid.UUID) -> list[uuid.UUID]:
    """Marca como stale, transitivamente, as versões abertas que dependem de version_id."""
    rows = await session.execute(
        text(
            """
            WITH RECURSIVE dependentes AS (
              SELECT d.version_id FROM artifact_dependency d
              WHERE d.depends_on_version_id = :v
              UNION
              SELECT d.version_id FROM artifact_dependency d
              JOIN dependentes x ON d.depends_on_version_id = x.version_id
            )
            UPDATE artifact_version av SET status = 'stale'
            FROM dependentes x
            WHERE av.id = x.version_id AND av.status IN ('draft', 'in_review')
            RETURNING av.id
            """
        ),
        {"v": version_id},
    )
    return [r[0] for r in rows.all()]


async def set_status(session: AsyncSession, version_ids: list[uuid.UUID], status: str) -> None:
    if version_ids:
        await session.execute(
            update(ArtifactVersion).where(ArtifactVersion.id.in_(version_ids)).values(status=status)
        )


async def add_trace_links(
    session: AsyncSession,
    run_id: uuid.UUID,
    links: list[tuple[str, str, str]],
    origin_version_id: uuid.UUID,
    proposto_por: str = "agent",
) -> None:
    """links: (from_item_key, to_item_key, link_type). Duplicatas são ignoradas."""
    for frm, to, kind in links:
        await session.execute(
            text(
                """
                INSERT INTO trace_link (id, run_id, from_item_key, to_item_key, link_type, status,
                                        proposto_por, origin_version_id, created_at)
                VALUES (:id, :run, :f, :t, :k, 'proposed', :p, :o, now())
                ON CONFLICT ON CONSTRAINT uq_trace DO UPDATE SET origin_version_id = EXCLUDED.origin_version_id
                """
            ),
            {"id": uuid.uuid4(), "run": run_id, "f": frm, "t": to, "k": kind, "p": proposto_por,
             "o": origin_version_id},
        )


async def evidences_of(session: AsyncSession, version_id: uuid.UUID) -> list[Evidence]:
    return list(
        (await session.scalars(select(Evidence).where(Evidence.artifact_version_id == version_id))).all()
    )


async def trace_links(session: AsyncSession, run_id: uuid.UUID) -> list[TraceLink]:
    return list((await session.scalars(select(TraceLink).where(TraceLink.run_id == run_id))).all())
