"""Eventos de execução (run_event + NOTIFY) e auditoria (append-only)."""

import json
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from openupexp.db.models import AuditEvent, RunEvent

CHANNEL = "run_events"


async def emit(session: AsyncSession, run_id: uuid.UUID, tipo: str, **dados) -> None:
    ev = RunEvent(run_id=run_id, tipo=tipo, dados=json.loads(json.dumps(dados, default=str)))
    session.add(ev)
    await session.flush()
    await session.execute(text("SELECT pg_notify(:c, :p)"), {"c": CHANNEL, "p": str(run_id)})


async def audit(
    session: AsyncSession,
    actor_type: str,
    actor_id: str | None,
    action: str,
    entity: str,
    entity_id: str | None,
    **dados,
) -> None:
    session.add(
        AuditEvent(
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            dados=json.loads(json.dumps(dados, default=str)),
        )
    )
