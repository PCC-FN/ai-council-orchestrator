from __future__ import annotations

from typing import Any, Callable, Coroutine

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_models import OrchestraEvent

BroadcastFn = Callable[[str, dict[str, Any]], Coroutine[Any, Any, None]] | None


class EventService:
    """Records every action permanently and optionally broadcasts live updates."""

    def __init__(self, db: AsyncSession, broadcast: BroadcastFn = None) -> None:
        self.db = db
        self.broadcast = broadcast

    async def emit(
        self,
        event_type: str,
        *,
        task_id: str | None = None,
        project_id: str | None = None,
        worker_id: str | None = None,
        job_id: str | None = None,
        agent_key: str | None = None,
        payload: dict[str, Any] | None = None,
        live_channel: str | None = None,
    ) -> OrchestraEvent:
        row = OrchestraEvent(
            event_type=event_type,
            task_id=task_id,
            project_id=project_id,
            worker_id=worker_id,
            job_id=job_id,
            agent_key=agent_key,
            payload=payload or {},
        )
        self.db.add(row)
        await self.db.flush()

        if self.broadcast:
            channel = live_channel or task_id or "global"
            msg = {
                "event": event_type,
                "event_id": row.id,
                "task_id": task_id,
                "project_id": project_id,
                "worker_id": worker_id,
                "job_id": job_id,
                "agent_key": agent_key,
                **(payload or {}),
            }
            await self.broadcast(channel, msg)
        return row

    async def list_recent(
        self,
        *,
        task_id: str | None = None,
        project_id: str | None = None,
        limit: int = 100,
    ) -> list[OrchestraEvent]:
        q = select(OrchestraEvent).order_by(OrchestraEvent.created_at.desc()).limit(limit)
        if task_id:
            q = q.where(OrchestraEvent.task_id == task_id)
        if project_id:
            q = q.where(OrchestraEvent.project_id == project_id)
        r = await self.db.execute(q)
        return list(r.scalars().all())
