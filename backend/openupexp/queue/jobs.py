"""Fila de jobs no PostgreSQL (FOR UPDATE SKIP LOCKED).

Ver docs/architecture/04-arquitetura-de-software.md §4.3.
"""

import uuid
from datetime import timedelta

from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from openupexp.db.models import Job


class JobAlreadyActive(Exception):
    """Já existe um job enfileirado ou em execução para esta execução (run)."""


async def enqueue(
    session: AsyncSession,
    kind: str,
    payload: dict,
    run_id: uuid.UUID | None = None,
    priority: int = 0,
) -> Job:
    job = Job(kind=kind, payload=payload, run_id=run_id, priority=priority)
    try:
        async with session.begin_nested():
            session.add(job)
            await session.flush()
    except IntegrityError as exc:
        raise JobAlreadyActive(str(run_id)) from exc
    await session.execute(text("SELECT pg_notify('jobs', :k)"), {"k": kind})
    return job


async def claim(session: AsyncSession, worker_id: str, kinds: list[str] | None = None) -> Job | None:
    sub = (
        select(Job.id)
        .where(Job.status == "queued", Job.run_after <= func.now())
        .order_by(Job.priority.desc(), Job.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if kinds:
        sub = sub.where(Job.kind.in_(kinds))
    job_id = await session.scalar(sub)
    if job_id is None:
        return None
    await session.execute(
        update(Job)
        .where(Job.id == job_id)
        .values(status="running", locked_by=worker_id, locked_at=func.now(), attempts=Job.attempts + 1)
    )
    return await session.get(Job, job_id, populate_existing=True)


async def finish(session: AsyncSession, job_id: uuid.UUID) -> None:
    await session.execute(
        update(Job).where(Job.id == job_id).values(status="done", finished_at=func.now())
    )


async def fail(session: AsyncSession, job: Job, error: str, retry: bool = True) -> None:
    again = retry and job.attempts < job.max_attempts
    await session.execute(
        update(Job)
        .where(Job.id == job.id)
        .values(
            status="queued" if again else "failed",
            last_error=error[:4000],
            locked_by=None,
            run_after=func.now() + timedelta(seconds=10 * job.attempts) if again else Job.run_after,
            finished_at=None if again else func.now(),
        )
    )


async def reap_stale(session: AsyncSession, stale_minutes: int) -> int:
    """Devolve à fila jobs de workers que morreram (locked_at antigo)."""
    result = await session.execute(
        text(
            """
            UPDATE job SET
              status = CASE WHEN attempts < max_attempts THEN 'queued' ELSE 'failed' END,
              locked_by = NULL,
              last_error = coalesce(last_error, '') || ' [reaper: worker sem resposta]'
            WHERE status = 'running' AND locked_at < now() - make_interval(mins => :m)
            """
        ),
        {"m": stale_minutes},
    )
    return result.rowcount or 0
