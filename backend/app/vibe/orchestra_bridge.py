"""Bridge Vibe Coding jobs to the 12-phase AI Orchestra Coordinator."""

from __future__ import annotations

from typing import Any, Callable, Coroutine

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.coordinator.coordinator import Coordinator
from app.core.events import EVENT_TASK_STARTED
from app.core.phases import PHASE_BY_KEY, PHASE_KEYS, phase_after
from app.models.db_models import CouncilSession, Project, ProjectKnowledge
from app.models.vibe_models import CodingJob, WorkerProject

BroadcastFn = Callable[[str, dict[str, Any]], Coroutine[Any, Any, None]] | None


async def ensure_council_project(db: AsyncSession, worker_project: WorkerProject) -> Project:
    r = await db.execute(
        select(Project).where(Project.repository_path == worker_project.local_path).limit(1)
    )
    existing = r.scalar_one_or_none()
    if existing:
        return existing

    project = Project(
        name=worker_project.name,
        description=f"Vibe Coding — {worker_project.local_path}",
        repository_path=worker_project.local_path,
        coding_rules="",
        security_rules="",
        tech_stack="",
    )
    db.add(project)
    await db.flush()
    db.add(ProjectKnowledge(project_id=project.id))
    await db.flush()
    return project


async def ensure_orchestra_task(
    db: AsyncSession,
    job: CodingJob,
    worker_project: WorkerProject,
) -> CouncilSession:
    if job.orchestra_task_id:
        task = await db.get(CouncilSession, job.orchestra_task_id)
        if task:
            return task

    council_project = await ensure_council_project(db, worker_project)
    task = CouncilSession(
        project_id=council_project.id,
        title=job.title,
        original_user_task=job.original_prompt,
        current_phase="understand_problem",
        status="created",
    )
    db.add(task)
    await db.flush()
    job.orchestra_task_id = task.id
    await db.flush()
    return task


async def run_coordinator_phases(
    db: AsyncSession,
    task_id: str,
    last_phase: str,
    broadcast: BroadcastFn = None,
) -> CouncilSession:
    """Run Coordinator phases up to last_phase (inclusive), skipping worker handoff."""
    coord = Coordinator(db, broadcast)
    if last_phase not in PHASE_BY_KEY:
        raise ValueError(f"unknown phase: {last_phase}")

    end_idx = PHASE_KEYS.index(last_phase)
    task = await coord._load_task(task_id)

    if task.status == "created":
        await coord.events.emit(
            EVENT_TASK_STARTED,
            task_id=task_id,
            project_id=task.project_id,
            live_channel=task_id,
        )

    current = task.current_phase or "understand_problem"
    while PHASE_KEYS.index(current) <= end_idx:
        phase_key = current
        if phase_key in ("handoff_worker", "implementation", "git_commit", "pull_request"):
            break
        await coord._run_phase(task_id, phase_key)
        task = await coord._load_task(task_id)
        if task.status in {"consensus_blocked", "needs_revision"}:
            break
        if phase_key == last_phase:
            break
        nxt = phase_after(phase_key)
        if not nxt or PHASE_KEYS.index(nxt) > end_idx:
            break
        current = nxt
        task.current_phase = current
        await db.flush()

    return await coord._load_task(task_id)


async def load_task_with_details(db: AsyncSession, task_id: str) -> CouncilSession:
    r = await db.execute(
        select(CouncilSession)
        .where(CouncilSession.id == task_id)
        .options(
            selectinload(CouncilSession.agent_responses),
            selectinload(CouncilSession.consensus),
            selectinload(CouncilSession.final_prompts),
            selectinload(CouncilSession.phase_executions),
        )
    )
    task = r.scalar_one_or_none()
    if not task:
        raise ValueError("orchestra task not found")
    return task


def build_plan_from_task(task: CouncilSession, mode: str) -> dict[str, Any]:
    consensus = task.consensus
    final_prompts = sorted(task.final_prompts or [], key=lambda x: x.version)
    fp = final_prompts[-1].prompt_text if final_prompts else task.normalized_task or task.original_user_task

    agent_insights = [
        {
            "agent": ar.agent_name,
            "round": ar.round_name,
            "excerpt": ar.content[:800],
            "rating": ar.rating,
        }
        for ar in (task.agent_responses or [])
    ]

    phases_done = [
        {"phase": pe.phase_key, "status": pe.status, "summary": pe.summary}
        for pe in (task.phase_executions or [])
    ]

    requirements = [line.strip() for line in task.original_user_task.split("\n") if line.strip()]

    return {
        "summary": task.title,
        "mode": mode,
        "orchestra_task_id": task.id,
        "requirements": requirements,
        "normalized_task": task.normalized_task,
        "consensus_summary": consensus.summary if consensus else "",
        "agreed_solution": consensus.agreed_solution if consensus else "",
        "risks": consensus.risks if consensus else "",
        "implementation_plan": consensus.implementation_plan if consensus else "",
        "test_plan": consensus.test_plan if consensus else "",
        "open_questions": consensus.open_questions if consensus else "",
        "agent_insights": agent_insights,
        "phases_completed": phases_done,
        "planned_changes": [consensus.implementation_plan] if consensus else ["Siehe Konsens"],
        "planned_tests": [consensus.test_plan] if consensus and consensus.test_plan else ["Unit-Tests"],
        "security_aspects": ["Agenten-Security-Review"] if mode == "orchestra" else ["AI Review"],
        "risks_list": [consensus.risks] if consensus and consensus.risks else [],
        "optimized_prompt": fp,
    }


async def run_vibe_orchestra_analysis(
    db: AsyncSession,
    job: CodingJob,
    worker_project: WorkerProject,
    *,
    mode: str,
    broadcast: BroadcastFn = None,
) -> dict[str, Any]:
    last_phase = "prompt_review" if mode == "orchestra" else "prompt_engineering"
    task = await ensure_orchestra_task(db, job, worker_project)
    task = await run_coordinator_phases(db, task.id, last_phase, broadcast)
    task = await load_task_with_details(db, task.id)
    return build_plan_from_task(task, mode)
