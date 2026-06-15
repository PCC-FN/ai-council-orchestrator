from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.routes import _broadcast, get_session
from app.coordinator.coordinator import Coordinator
from app.core.phases import PHASES
from app.database import get_db
from app.events.service import EventService
from app.jobs.service import JobService
from app.knowledge.service import KnowledgeService
from app.models.db_models import (
    AgentDefinition,
    CouncilSession,
    OrchestraJob,
    Project,
    ProjectKnowledge,
    WorkerRegistration,
)
from app.schemas.orchestra_schemas import (
    AgentDefinitionCreate,
    AgentDefinitionOut,
    EventOut,
    JobCompleteIn,
    JobFailIn,
    JobOut,
    JobProgressIn,
    OrchestraDashboardOut,
    PhaseDefinitionOut,
    PhaseExecutionOut,
    ProjectKnowledgeOut,
    ProjectKnowledgeUpdate,
    TaskCreate,
    WorkerHeartbeatIn,
    WorkerOut,
    WorkerRegisterIn,
)
from app.schemas.schemas import CouncilSessionOut
from app.workers.service import WorkerService

orchestra_router = APIRouter(prefix="/orchestra", tags=["orchestra"])
workers_router = APIRouter(prefix="/workers", tags=["workers"])
agents_router = APIRouter(prefix="/agents", tags=["agents"])
tasks_router = APIRouter(prefix="/tasks", tags=["tasks"])


def _coordinator(db: AsyncSession) -> Coordinator:
    return Coordinator(db, _broadcast)


def _events(db: AsyncSession) -> EventService:
    return EventService(db, _broadcast)


# --- Dashboard ---


@orchestra_router.get("/dashboard", response_model=OrchestraDashboardOut)
async def orchestra_dashboard(db: AsyncSession = Depends(get_db)):
    await WorkerService(db, _events(db)).mark_stale_offline()

    active = await db.scalar(
        select(func.count()).select_from(CouncilSession).where(
            CouncilSession.status != "completed"
        )
    )
    done = await db.scalar(
        select(func.count()).select_from(CouncilSession).where(
            CouncilSession.status == "completed"
        )
    )
    pending_jobs = await db.scalar(
        select(func.count()).select_from(OrchestraJob).where(
            OrchestraJob.status == "pending"
        )
    )
    running_jobs = await db.scalar(
        select(func.count()).select_from(OrchestraJob).where(
            OrchestraJob.status.in_(["assigned", "running"])
        )
    )

    wr = await db.execute(select(WorkerRegistration))
    workers = list(wr.scalars().all())
    online = [w for w in workers if w.status != "offline"]

    ar = await db.execute(select(AgentDefinition).where(AgentDefinition.active.is_(True)))
    agents = list(ar.scalars().all())

    recent = await _events(db).list_recent(limit=30)

    return OrchestraDashboardOut(
        active_tasks=active or 0,
        completed_tasks=done or 0,
        active_workers=len(online),
        pending_jobs=pending_jobs or 0,
        running_jobs=running_jobs or 0,
        recent_events=[EventOut.model_validate(e) for e in recent],
        agents=[AgentDefinitionOut.model_validate(a) for a in agents],
        workers=[WorkerOut.model_validate(w) for w in workers],
    )


@orchestra_router.get("/phases", response_model=list[PhaseDefinitionOut])
async def list_phases():
    return [
        PhaseDefinitionOut(key=p.key, number=p.number, label=p.label, description=p.description)
        for p in PHASES
    ]


@orchestra_router.get("/events", response_model=list[EventOut])
async def list_events(
    task_id: str | None = None,
    project_id: str | None = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    rows = await _events(db).list_recent(task_id=task_id, project_id=project_id, limit=limit)
    return [EventOut.model_validate(e) for e in rows]


# --- Tasks (Orchestra naming; wraps CouncilSession) ---


@tasks_router.post("", response_model=CouncilSessionOut)
async def create_task(body: TaskCreate, db: AsyncSession = Depends(get_db)):
    q = await db.execute(select(Project).where(Project.id == body.project_id))
    if not q.scalar_one_or_none():
        raise HTTPException(404, "project not found")
    s = CouncilSession(
        project_id=body.project_id,
        title=body.title,
        original_user_task=body.build_task(),
        current_phase="understand_problem",
    )
    db.add(s)
    await db.commit()
    return await get_session(s.id, db)


@tasks_router.post("/{task_id}/orchestrate", response_model=CouncilSessionOut)
async def orchestrate_task(task_id: str, db: AsyncSession = Depends(get_db)):
    coord = _coordinator(db)
    try:
        await coord.run_until_blocked(task_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    await db.commit()
    return await get_session(task_id, db)


@tasks_router.post("/{task_id}/advance-phase", response_model=CouncilSessionOut)
async def advance_task_phase(task_id: str, db: AsyncSession = Depends(get_db)):
    coord = _coordinator(db)
    try:
        await coord.advance_phase(task_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    await db.commit()
    return await get_session(task_id, db)


@tasks_router.get("/{task_id}/phases", response_model=list[PhaseExecutionOut])
async def task_phase_history(task_id: str, db: AsyncSession = Depends(get_db)):
    rows = await _coordinator(db).list_phase_history(task_id)
    return [PhaseExecutionOut.model_validate(r) for r in rows]


# --- Agents ---


@agents_router.get("", response_model=list[AgentDefinitionOut])
async def list_agents(db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(AgentDefinition).order_by(AgentDefinition.priority.desc()))
    return list(r.scalars().all())


@agents_router.post("", response_model=AgentDefinitionOut)
async def create_agent(body: AgentDefinitionCreate, db: AsyncSession = Depends(get_db)):
    a = AgentDefinition(**body.model_dump())
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return a


# --- Workers ---


@workers_router.post("/register", response_model=WorkerOut)
async def register_worker(body: WorkerRegisterIn, db: AsyncSession = Depends(get_db)):
    w = await WorkerService(db, _events(db)).register(
        name=body.name,
        worker_type=body.worker_type,
        hostname=body.hostname,
        capabilities=body.capabilities,
    )
    await db.commit()
    return w


@workers_router.get("", response_model=list[WorkerOut])
async def list_workers(db: AsyncSession = Depends(get_db)):
    rows = await WorkerService(db, _events(db)).list_workers()
    return rows


@workers_router.post("/{worker_id}/heartbeat", response_model=WorkerOut)
async def worker_heartbeat(
    worker_id: str, body: WorkerHeartbeatIn, db: AsyncSession = Depends(get_db)
):
    try:
        w = await WorkerService(db, _events(db)).heartbeat(
            worker_id, status=body.status, capabilities=body.capabilities
        )
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    await db.commit()
    return w


@workers_router.get("/{worker_id}/jobs/poll")
async def poll_job(worker_id: str, db: AsyncSession = Depends(get_db)):
    jobs = JobService(db, _events(db))
    job = await jobs.poll_for_worker(worker_id)
    if not job:
        return {"job": None}
    payload = await jobs.job_payload_for_worker(job)
    await db.commit()
    return {"job": payload}


@workers_router.post("/{worker_id}/jobs/{job_id}/start", response_model=JobOut)
async def start_job(worker_id: str, job_id: str, db: AsyncSession = Depends(get_db)):
    try:
        job = await JobService(db, _events(db)).start_job(worker_id, job_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    await db.commit()
    return job


@workers_router.post("/{worker_id}/jobs/{job_id}/progress", response_model=JobOut)
async def job_progress(
    worker_id: str,
    job_id: str,
    body: JobProgressIn,
    db: AsyncSession = Depends(get_db),
):
    try:
        job = await JobService(db, _events(db)).report_progress(
            worker_id, job_id, body.message
        )
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    await db.commit()
    return job


@workers_router.post("/{worker_id}/jobs/{job_id}/complete", response_model=JobOut)
async def complete_job(
    worker_id: str,
    job_id: str,
    body: JobCompleteIn,
    db: AsyncSession = Depends(get_db),
):
    js = JobService(db, _events(db))
    result: dict[str, Any] = {
        "summary": body.summary,
        "changed_files": body.changed_files,
        "commit_hash": body.commit_hash,
        **body.extra,
    }
    try:
        job = await js.complete_job(worker_id, job_id, result)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e

    if job.job_type == "implementation":
        coord = _coordinator(db)
        await coord.on_job_completed(job.task_id, result)

    await db.commit()
    return job


@workers_router.post("/{worker_id}/jobs/{job_id}/fail", response_model=JobOut)
async def fail_job(
    worker_id: str,
    job_id: str,
    body: JobFailIn,
    db: AsyncSession = Depends(get_db),
):
    try:
        job = await JobService(db, _events(db)).fail_job(worker_id, job_id, body.error)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    await db.commit()
    return job


# --- Jobs (read) ---


@orchestra_router.get("/jobs", response_model=list[JobOut])
async def list_jobs(
    task_id: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    rows = await JobService(db, _events(db)).list_jobs(task_id=task_id, status=status)
    return rows


# --- Knowledge ---


@orchestra_router.get("/projects/{project_id}/knowledge", response_model=ProjectKnowledgeOut)
async def get_knowledge(project_id: str, db: AsyncSession = Depends(get_db)):
    k = await KnowledgeService(db).get_or_create(project_id)
    return k


@orchestra_router.put("/projects/{project_id}/knowledge", response_model=ProjectKnowledgeOut)
async def update_knowledge(
    project_id: str,
    body: ProjectKnowledgeUpdate,
    db: AsyncSession = Depends(get_db),
):
    k = await KnowledgeService(db).get_or_create(project_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(k, field, value)
    await db.commit()
    await db.refresh(k)
    return k
