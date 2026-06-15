from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import EVENT_WORKER_HEARTBEAT, EVENT_WORKER_OFFLINE, EVENT_WORKER_REGISTERED
from app.events.service import EventService
from app.models.db_models import WorkerRegistration


class WorkerService:
    """Register remote coding workers and track health."""

    HEARTBEAT_TIMEOUT_SEC = 120

    def __init__(self, db: AsyncSession, events: EventService) -> None:
        self.db = db
        self.events = events

    async def register(
        self,
        *,
        name: str,
        worker_type: str,
        hostname: str = "",
        capabilities: dict | None = None,
    ) -> WorkerRegistration:
        w = WorkerRegistration(
            name=name,
            worker_type=worker_type,
            hostname=hostname,
            capabilities=capabilities or {},
            status="idle",
            last_heartbeat_at=datetime.now(UTC),
        )
        self.db.add(w)
        await self.db.flush()
        await self.events.emit(
            EVENT_WORKER_REGISTERED,
            worker_id=w.id,
            payload={"name": name, "worker_type": worker_type, "capabilities": capabilities},
            live_channel="global",
        )
        return w

    async def heartbeat(
        self, worker_id: str, *, status: str = "idle", capabilities: dict | None = None
    ) -> WorkerRegistration:
        w = await self._get(worker_id)
        w.last_heartbeat_at = datetime.now(UTC)
        w.status = status
        if capabilities:
            w.capabilities = capabilities
        await self.db.flush()
        await self.events.emit(
            EVENT_WORKER_HEARTBEAT,
            worker_id=worker_id,
            payload={"status": status},
            live_channel="global",
        )
        return w

    async def list_workers(self, *, online_only: bool = False) -> list[WorkerRegistration]:
        r = await self.db.execute(
            select(WorkerRegistration).order_by(WorkerRegistration.registered_at.desc())
        )
        workers = list(r.scalars().all())
        if not online_only:
            return workers
        cutoff = datetime.now(UTC) - timedelta(seconds=self.HEARTBEAT_TIMEOUT_SEC)
        return [w for w in workers if w.last_heartbeat_at and w.last_heartbeat_at >= cutoff]

    async def mark_stale_offline(self) -> int:
        cutoff = datetime.now(UTC) - timedelta(seconds=self.HEARTBEAT_TIMEOUT_SEC)
        r = await self.db.execute(select(WorkerRegistration))
        count = 0
        for w in r.scalars().all():
            if w.status != "offline" and (
                not w.last_heartbeat_at or w.last_heartbeat_at < cutoff
            ):
                w.status = "offline"
                count += 1
                await self.events.emit(
                    EVENT_WORKER_OFFLINE,
                    worker_id=w.id,
                    live_channel="global",
                )
        await self.db.flush()
        return count

    async def _get(self, worker_id: str) -> WorkerRegistration:
        w = await self.db.get(WorkerRegistration, worker_id)
        if not w:
            raise ValueError("worker not found")
        return w
