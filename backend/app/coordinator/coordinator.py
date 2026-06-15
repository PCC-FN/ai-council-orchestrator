from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Callable, Coroutine

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.events import (
    EVENT_PHASE_COMPLETED,
    EVENT_PHASE_FAILED,
    EVENT_PHASE_STARTED,
    EVENT_REVIEW_FAILED,
    EVENT_REVIEW_PASSED,
    EVENT_TASK_COMPLETED,
    EVENT_TASK_STARTED,
)
from app.core.phases import PHASE_BY_KEY, PHASE_KEYS, phase_after, phase_number
from app.events.service import EventService
from app.jobs.service import JobService
from app.knowledge.service import KnowledgeService
from app.models.db_models import CouncilSession, PhaseExecution
from app.services.orchestrator import CouncilOrchestrator

BroadcastFn = Callable[[str, dict[str, Any]], Coroutine[Any, Any, None]] | None


class Coordinator:
    """
    Central workflow manager for AI Orchestra.

    The Coordinator owns phase transitions, job dispatch, and audit records.
    It delegates AI work to CouncilOrchestrator and worker tasks to JobService.
    It never calls LLM providers directly.
    """

    def __init__(self, db: AsyncSession, broadcast: BroadcastFn = None) -> None:
        self.db = db
        self.broadcast = broadcast
        self.events = EventService(db, broadcast)
        self.jobs = JobService(db, self.events)
        self.knowledge = KnowledgeService(db)
        self._orch = CouncilOrchestrator(db, broadcast)

    async def start_task(self, task_id: str) -> CouncilSession:
        task = await self._load_task(task_id)
        await self.events.emit(
            EVENT_TASK_STARTED,
            task_id=task_id,
            project_id=task.project_id,
            live_channel=task_id,
        )
        await self._run_phase(task_id, "understand_problem")
        return await self._load_task(task_id)

    async def advance_phase(self, task_id: str) -> str:
        """Run exactly the current phase, then move to the next."""
        task = await self._load_task(task_id)
        phase = task.current_phase or "understand_problem"
        await self._run_phase(task_id, phase)
        task = await self._load_task(task_id)
        nxt = phase_after(phase)
        if nxt and task.status not in {"needs_revision", "consensus_blocked", "waiting_worker"}:
            task.current_phase = nxt
            task.updated_at = datetime.now(UTC)
            await self.db.flush()
        return phase

    async def run_until_blocked(self, task_id: str) -> CouncilSession:
        """Auto-advance through phases until worker handoff or completion."""
        for _ in range(len(PHASE_KEYS)):
            task = await self._load_task(task_id)
            if task.status in {
                "waiting_worker",
                "completed",
                "needs_revision",
                "consensus_blocked",
            }:
                break
            phase = task.current_phase or "understand_problem"
            await self._run_phase(task_id, phase)
            task = await self._load_task(task_id)
            if task.status in {"waiting_worker", "consensus_blocked", "needs_revision"}:
                break
            nxt = phase_after(phase)
            if not nxt:
                break
            task.current_phase = nxt
            task.updated_at = datetime.now(UTC)
            await self.db.flush()
        return await self._load_task(task_id)

    async def on_job_completed(self, task_id: str, job_result: dict[str, Any]) -> CouncilSession:
        """Called when a worker finishes — triggers code review phase."""
        task = await self._load_task(task_id)
        changed = job_result.get("changed_files", [])
        summary = job_result.get("summary", job_result.get("message", ""))
        await self._orch.mark_implemented(task_id, changed, summary)
        task.current_phase = "code_review"
        task.status = "implemented"
        await self.db.flush()
        await self._run_phase(task_id, "code_review")
        return await self._load_task(task_id)

    async def _run_phase(self, task_id: str, phase_key: str) -> None:
        task = await self._load_task(task_id)
        pe = await self._begin_phase_record(task_id, phase_key)
        await self.events.emit(
            EVENT_PHASE_STARTED,
            task_id=task_id,
            project_id=task.project_id,
            payload={"phase": phase_key, "number": phase_number(phase_key)},
            live_channel=task_id,
        )
        try:
            summary = await self._execute_phase(task_id, phase_key)
            await self._complete_phase_record(pe, summary)
            await self.events.emit(
                EVENT_PHASE_COMPLETED,
                task_id=task_id,
                project_id=task.project_id,
                payload={"phase": phase_key, "summary": summary[:500]},
                live_channel=task_id,
            )
        except Exception as exc:
            pe.status = "failed"
            pe.summary = str(exc)
            pe.completed_at = datetime.now(UTC)
            await self.db.flush()
            await self.events.emit(
                EVENT_PHASE_FAILED,
                task_id=task_id,
                project_id=task.project_id,
                payload={"phase": phase_key, "error": str(exc)},
                live_channel=task_id,
            )
            raise

    async def _execute_phase(self, task_id: str, phase_key: str) -> str:
        task = await self._load_task(task_id)

        if phase_key == "understand_problem":
            await self._orch.normalize_task(task_id)
            return "Aufgabe normalisiert"

        if phase_key == "develop_architecture":
            await self._orch.run_initial_assessment(task_id)
            return "Architektur-Assessment abgeschlossen"

        if phase_key == "agent_discussion":
            await self._orch.run_cross_review(task_id)
            return "Agenten-Diskussion abgeschlossen"

        if phase_key == "find_consensus":
            await self._orch.build_consensus(task_id)
            await self._orch.run_consensus_approval(task_id)
            t = await self._load_task(task_id)
            if t.consensus and t.consensus.approval_status == "approved":
                return "Konsens gefunden und freigegeben"
            return "Konsens erstellt — Freigabe ausstehend"

        if phase_key == "prompt_engineering":
            t = await self._load_task(task_id)
            if t.consensus and t.consensus.approval_status != "approved":
                await self._orch.approve_consensus(task_id)
            await self._orch.build_final_prompt(task_id)
            return "Finaler Prompt erzeugt"

        if phase_key == "prompt_review":
            await self._orch.run_prompt_review(task_id)
            return "Prompt Review abgeschlossen"

        if phase_key == "handoff_worker":
            t = await self._load_task(task_id)
            fp = max(t.final_prompts, key=lambda x: x.version) if t.final_prompts else None
            if not fp:
                raise ValueError("Kein finaler Prompt für Worker-Übergabe")
            job = await self.jobs.create_implementation_job(
                task_id=task_id,
                project_id=t.project_id,
                final_prompt=fp.prompt_text,
                description=t.title,
                branch=f"feature/{task_id[:8]}",
            )
            t.status = "waiting_worker"
            t.current_phase = "implementation"
            await self.db.flush()
            return f"Job {job.id[:8]} für Worker erstellt"

        if phase_key == "implementation":
            return "Wartet auf Worker-Implementierung"

        if phase_key == "code_review":
            await self._orch.run_code_review(task_id)
            t = await self._load_task(task_id)
            if t.status == "needs_revision":
                t.iteration_count += 1
                if t.iteration_count >= t.max_iterations:
                    await self.events.emit(
                        EVENT_REVIEW_FAILED,
                        task_id=task_id,
                        project_id=t.project_id,
                        payload={"reason": "max_iterations"},
                        live_channel=task_id,
                    )
                    return "Review fehlgeschlagen — max. Iterationen erreicht"
                await self.events.emit(
                    EVENT_REVIEW_FAILED,
                    task_id=task_id,
                    project_id=t.project_id,
                    payload={"iteration": t.iteration_count},
                    live_channel=task_id,
                )
                fp = max(t.final_prompts, key=lambda x: x.version) if t.final_prompts else None
                if fp:
                    await self.jobs.create_implementation_job(
                        task_id=task_id,
                        project_id=t.project_id,
                        final_prompt=fp.prompt_text,
                        description=f"Verbesserungsrunde {t.iteration_count}",
                        branch=f"fix/{task_id[:8]}-{t.iteration_count}",
                    )
                t.status = "waiting_worker"
                t.current_phase = "improvement_rounds"
                await self.db.flush()
                return f"Review: Verbesserungsjob Iteration {t.iteration_count}"
            await self.events.emit(
                EVENT_REVIEW_PASSED,
                task_id=task_id,
                project_id=t.project_id,
                live_channel=task_id,
            )
            t.current_phase = "git_commit"
            return "Code Review bestanden"

        if phase_key == "improvement_rounds":
            return "Verbesserungsrunde — Worker-Job bereit"

        if phase_key == "git_commit":
            t = await self._load_task(task_id)
            await self.jobs.create_implementation_job(
                task_id=task_id,
                project_id=t.project_id,
                final_prompt="",
                description="Git commit — von Worker ausführen",
                branch=f"feature/{task_id[:8]}",
                required_capabilities=["git"],
            )
            t.current_phase = "pull_request"
            return "Git-Commit-Job erstellt"

        if phase_key == "pull_request":
            t = await self._load_task(task_id)
            t.status = "completed"
            t.updated_at = datetime.now(UTC)
            await self.db.flush()
            await self.events.emit(
                EVENT_TASK_COMPLETED,
                task_id=task_id,
                project_id=t.project_id,
                live_channel=task_id,
            )
            return "Workflow abgeschlossen — PR-Phase (Stub)"

        raise ValueError(f"Unbekannte Phase: {phase_key}")

    async def _begin_phase_record(self, task_id: str, phase_key: str) -> PhaseExecution:
        pdef = PHASE_BY_KEY.get(phase_key)
        pe = PhaseExecution(
            task_id=task_id,
            phase_key=phase_key,
            phase_number=pdef.number if pdef else 0,
            status="running",
            started_at=datetime.now(UTC),
        )
        self.db.add(pe)
        await self.db.flush()
        return pe

    async def _complete_phase_record(self, pe: PhaseExecution, summary: str) -> None:
        pe.status = "completed"
        pe.summary = summary
        pe.completed_at = datetime.now(UTC)
        await self.db.flush()

    async def _load_task(self, task_id: str) -> CouncilSession:
        r = await self.db.execute(
            select(CouncilSession)
            .where(CouncilSession.id == task_id)
            .options(
                selectinload(CouncilSession.project),
                selectinload(CouncilSession.agent_responses),
                selectinload(CouncilSession.consensus),
                selectinload(CouncilSession.final_prompts),
                selectinload(CouncilSession.implementation),
                selectinload(CouncilSession.phase_executions),
                selectinload(CouncilSession.jobs),
            )
        )
        task = r.scalar_one_or_none()
        if not task:
            raise ValueError("task not found")
        if task.project:
            await self.knowledge.sync_from_project(task.project)
        return task

    async def list_phase_history(self, task_id: str) -> list[PhaseExecution]:
        r = await self.db.execute(
            select(PhaseExecution)
            .where(PhaseExecution.task_id == task_id)
            .order_by(PhaseExecution.started_at)
        )
        return list(r.scalars().all())
