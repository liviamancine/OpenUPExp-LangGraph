"""Difusão de eventos de execução: um único LISTEN no PostgreSQL, repassado via SSE."""

import asyncio
import logging
from collections import defaultdict

import psycopg

from openupexp.config import get_settings
from openupexp.domain.events import CHANNEL

log = logging.getLogger("openupexp.events")


class Broadcaster:
    def __init__(self) -> None:
        self._waiters: dict[str, set[asyncio.Event]] = defaultdict(set)
        self._task: asyncio.Task | None = None

    def subscribe(self, run_id: str) -> asyncio.Event:
        ev = asyncio.Event()
        self._waiters[run_id].add(ev)
        return ev

    def unsubscribe(self, run_id: str, ev: asyncio.Event) -> None:
        self._waiters[run_id].discard(ev)

    def _notify(self, run_id: str) -> None:
        for ev in list(self._waiters.get(run_id, ())):
            ev.set()

    async def _listen(self) -> None:
        url = get_settings().psycopg_url
        while True:
            try:
                async with await psycopg.AsyncConnection.connect(url, autocommit=True) as conn:
                    await conn.execute(f"LISTEN {CHANNEL}")
                    async for n in conn.notifies():
                        self._notify(n.payload)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # reconecta; o SSE também faz polling de segurança
                log.warning("listener de eventos caiu (%s); reconectando", exc)
                await asyncio.sleep(2)

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._listen())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None


broadcaster = Broadcaster()
