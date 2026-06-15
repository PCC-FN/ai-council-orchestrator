from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import (
    EVENT_JOB_ASSIGNED,
    EVENT_JOB_COMPLETED,
    EVENT_JOB_CREATED,
    EVENT_JOB_FAILED,
    EVENT_JOB_PROGRESS,
    EVENT_JOB_STARTED,
)
from app.events.service import EventService
from app.knowledge.service import KnowledgeService
from app.models.db_models import OrchestraJob, WorkerRegistration


class JobService:
    """Creates and tracks jobs for remote coding workers."""

    def __init__(self, db: AsyncSession, events: EventService) -> None:
        self.db = db
        self.events = events

    async def create_implementation_job(
        self,
        *,
        task_id: str,
        project_id: str,
        final_prompt: str,
        description: str = "",
        branch: str = "",
        affected_files: list[str] | None = None,
        required_capabilities: list[str] | None = None,
        priority: int = 50,
    ) -> OrchestraJob:
        job = OrchestraJob(
            task_id=task_id,
            project_id=project_id,
            job_type="implementation",
            description=description,
            branch=branch,
            final_prompt=final_prompt,
            affected_files=affected_files or [],
            required_capabilities=required_capabilities or ["git"],
            priority=priority,
            status="pending",
        )
        self.db.add(job)
        await self.db.flush()
        await self.events.emit(
            EVENT_JOB_CREATED,
            task_id=task_id,
            project_id=project_id,
            job_id=job.id,
            payload={"job_type": job.job_type, "branch": branch},
        )
        return job

    async def poll_for_worker(self, worker_id: str) -> OrchestraJob | None:
        """Return the next pending job assignable to this worker, if any."""
        w = await self.db.get(WorkerRegistration, worker_id)
        if not w or w.status == "offline":
            return None
        if w.current_job_id:
            return None

        r = await self.db.execute(
            select(OrchestraJob)
            .where(OrchestraJob.status == "pending")
            .order_by(OrchestraJob.priority.desc(), OrchestraJob.created_at)
            .limit(1)
        )
        job = r.scalar_one_or_none()
        if not job:
            return None

        job.worker_id = worker_id
        job.status = "assigned"
        w.status = "busy"
        w.current_job_id = job.id
        await self.db.flush()

        await self.events.emit(
            EVENT_JOB_ASSIGNED,
            task_id=job.task_id,
            project_id=job.project_id,
            worker_id=worker_id,
            job_id=job.id,
        )
        return job

    async def job_payload_for_worker(self, job: OrchestraJob) -> dict[str, Any]:
        """Bundle everything a worker needs: prompt, files, project knowledge."""
        knowledge = await KnowledgeService(self.db).get_context_bundle(job.project_id)
        return {
            "job_id": job.id,
            "task_id": job.task_id,
            "project_id": job.project_id,
            "job_type": job.job_type,
            "branch": job.branch,
            "description": job.description,
            "final_prompt": job.final_prompt,
            "affected_files": job.affected_files,
            "project_knowledge": knowledge,
            "timeout_seconds": job.timeout_seconds,
        }

    async def start_job(self, worker_id: str, job_id: str) -> OrchestraJob:
        job = await self._get_worker_job(worker_id, job_id)
        job.status = "running"
        job.progress_message = "Job gestartet"
        await self.db.flush()
        await self.events.emit(
            EVENT_JOB_STARTED,
            task_id=job.task_id,
            project_id=job.project_id,
            worker_id=worker_id,
            job_id=job.id,
        )
        return job

    async def report_progress(
        self, worker_id: str, job_id: str, message: str
    ) -> OrchestraJob:
        job = await self._get_worker_job(worker_id, job_id)
        job.progress_message = message
        await self.db.flush()
        await self.events.emit(
            EVENT_JOB_PROGRESS,
            task_id=job.task_id,
            project_id=job.project_id,
            worker_id=worker_id,
            job_id=job.id,
            payload={"message": message},
        )
        return job

    async def complete_job(
        self, worker_id: str, job_id: str, result: dict[str, Any]
    ) -> OrchestraJob:
        job = await self._get_worker_job(worker_id, job_id)
        job.status = "completed"
        job.result = result
        job.progress_message = result.get("summary", "Abgeschlossen")
        w = await self.db.get(WorkerRegistration, worker_id)
        if w:
            w.status = "idle"
            w.current_job_id = None
        await self.db.flush()
        await self.events.emit(
            EVENT_JOB_COMPLETED,
            task_id=job.task_id,
            project_id=job.project_id,
            worker_id=worker_id,
            job_id=job.id,
            payload=result,
        )
        return job

    async def fail_job(
        self, worker_id: str, job_id: str, error: str
    ) -> OrchestraJob:
        job = await self._get_worker_job(worker_id, job_id)
        job.status = "failed"
        job.progress_message = error
        w = await self.db.get(WorkerRegistration, worker_id)
        if w:
            w.status = "idle"
            w.current_job_id = None
        await self.db.flush()
        await self.events.emit(
            EVENT_JOB_FAILED,
            task_id=job.task_id,
            project_id=job.project_id,
            worker_id=worker_id,
            job_id=job.id,
            payload={"error": error},
        )
        return job

    async def list_jobs(
        self, *, task_id: str | None = None, status: str | None = None
    ) -> list[OrchestraJob]:
        q = select(OrchestraJob).order_by(OrchestraJob.created_at.desc())
        if task_id:
            q = q.where(OrchestraJob.task_id == task_id)
        if status:
            q = q.where(OrchestraJob.status == status)
        r = await self.db.execute(q)
        return list(r.scalars().all())

    async def _get_worker_job(self, worker_id: str, job_id: str) -> OrchestraJob:
        r = await self.db.execute(
            select(OrchestraJob).where(
                OrchestraJob.id == job_id, OrchestraJob.worker_id == worker_id
            )
        )
        job = r.scalar_one_or_none()
        if not job:
            raise ValueError("job not found for worker")
        return job
