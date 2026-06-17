from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from typing import Any, Callable, Coroutine

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.core.vibe_events import (
    EVENT_AGENT_MESSAGE,
    EVENT_AGENT_OUTPUT,
    EVENT_AGENT_QUESTION,
    EVENT_ANALYSIS_STARTED,
    EVENT_APPROVAL_RECEIVED,
    EVENT_APPROVAL_REQUIRED,
    EVENT_COMMAND_COMPLETED,
    EVENT_COMMAND_OUTPUT,
    EVENT_COMMAND_STARTED,
    EVENT_CORRECTION_QUEUED,
    EVENT_FILE_CHANGED,
    EVENT_FILE_CREATED,
    EVENT_GIT_DIFF_UPDATED,
    EVENT_JOB_CANCELLED,
    EVENT_JOB_COMPLETED,
    EVENT_JOB_CREATED,
    EVENT_JOB_FAILED,
    EVENT_JOB_QUEUED,
    EVENT_JOB_STARTED,
    EVENT_PLAN_CREATED,
    EVENT_REVIEW_COMPLETED,
    EVENT_REVIEW_STARTED,
    EVENT_TEST_COMPLETED,
    EVENT_TEST_STARTED,
    VIBE_PROTOCOL_VERSION,
)
from app.models.db_models import WorkerRegistration
from app.models.vibe_models import (
    Approval,
    ChatMessage,
    CodingJob,
    CodingSession,
    FileChange,
    VibeJobEvent,
    WorkerProject,
)
from app.vibe.orchestra_bridge import run_vibe_orchestra_analysis
from app.vibe.review import (
    format_review_markdown,
    run_implementation_review,
    should_auto_dispatch_correction,
)
from app.vibe.secret_mask import mask_dict, mask_secrets

BroadcastFn = Callable[[str, dict[str, Any]], Coroutine[Any, Any, None]] | None
DispatchWorkerFn = Callable[[CodingJob], Coroutine[Any, Any, bool]] | None


class VibeCodingService:
    """Orchestrates vibe coding jobs between browser and workers."""

    def __init__(
        self,
        db: AsyncSession,
        broadcast: BroadcastFn = None,
        dispatch_worker: DispatchWorkerFn = None,
    ) -> None:
        self.db = db
        self.broadcast = broadcast
        self.dispatch_worker = dispatch_worker

    # --- Worker token ---

    @staticmethod
    def generate_worker_token() -> tuple[str, str]:
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        return token, token_hash

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    async def register_worker_with_token(
        self,
        *,
        name: str,
        token: str,
        hostname: str = "",
        operating_system: str = "",
        version: str = "1.0.0",
        capabilities: dict | None = None,
    ) -> WorkerRegistration:
        w = await self.authenticate_worker_token(token)
        if not w:
            token_hash = self.hash_token(token)
            w = WorkerRegistration(
                name=name,
                worker_type="vibe",
                hostname=hostname,
                capabilities={
                    "token_hash": token_hash,
                    "version": version,
                    "operating_system": operating_system,
                    **(capabilities or {}),
                },
                status="idle",
                last_heartbeat_at=datetime.now(UTC),
            )
            self.db.add(w)
            await self.db.flush()
        w.name = name
        w.hostname = hostname or w.hostname
        w.last_heartbeat_at = datetime.now(UTC)
        w.status = "idle"
        caps = dict(w.capabilities or {})
        caps["token_hash"] = self.hash_token(token)
        caps.update(
            {
                "version": version,
                "operating_system": operating_system,
                **(capabilities or {}),
            }
        )
        w.capabilities = caps
        await self.db.flush()
        return w

    async def authenticate_worker_token(self, token: str) -> WorkerRegistration | None:
        token_hash = self.hash_token(token)
        r = await self.db.execute(select(WorkerRegistration))
        for w in r.scalars().all():
            caps = w.capabilities or {}
            if caps.get("token_hash") == token_hash:
                return w
        return None

    async def sync_worker_projects(
        self, worker_id: str, projects: list[dict[str, str]]
    ) -> list[WorkerProject]:
        synced: list[WorkerProject] = []
        for p in projects:
            local_path = p.get("local_path", "")
            if not local_path:
                continue
            existing = await self.db.scalar(
                select(WorkerProject).where(
                    WorkerProject.worker_id == worker_id,
                    WorkerProject.local_path == local_path,
                )
            )
            if existing:
                existing.name = p.get("name", existing.name)
                existing.is_enabled = True
                synced.append(existing)
            else:
                wp = WorkerProject(
                    worker_id=worker_id,
                    name=p.get("name", local_path),
                    local_path=local_path,
                    default_branch=p.get("default_branch", "main"),
                    repository_url=p.get("repository_url", ""),
                )
                self.db.add(wp)
                synced.append(wp)
        await self.db.flush()
        return synced

    async def list_workers(self) -> list[WorkerRegistration]:
        r = await self.db.execute(
            select(WorkerRegistration).order_by(WorkerRegistration.registered_at.desc())
        )
        return list(r.scalars().all())

    async def list_worker_projects(self, worker_id: str) -> list[WorkerProject]:
        r = await self.db.execute(
            select(WorkerProject)
            .where(WorkerProject.worker_id == worker_id, WorkerProject.is_enabled.is_(True))
            .order_by(WorkerProject.last_used_at.desc().nullslast(), WorkerProject.name)
        )
        return list(r.scalars().all())

    # --- Jobs ---

    async def create_job(
        self,
        *,
        worker_id: str,
        project_id: str,
        prompt: str,
        mode: str = "direct",
        title: str = "",
        adapter_type: str = "mock",
        user_id: str = "default",
    ) -> CodingJob:
        worker = await self._get_worker(worker_id)
        project = await self._get_project(project_id)
        if project.worker_id != worker.id:
            raise ValueError("project does not belong to worker")

        job = CodingJob(
            worker_id=worker_id,
            project_id=project_id,
            mode=mode,
            title=title or prompt[:80],
            original_prompt=prompt,
            status="draft",
            adapter_type=adapter_type,
            max_review_rounds=get_settings().max_automatic_review_rounds,
            user_id=user_id,
        )
        self.db.add(job)
        await self.db.flush()

        await self._add_message(
            job.id, sender_type="user", sender_name="Benutzer", content=prompt
        )
        await self._emit(job, EVENT_JOB_CREATED, {"mode": mode, "title": job.title})
        return job

    async def analyze_job(self, job_id: str) -> CodingJob:
        job = await self._get_job(job_id)
        job.status = "analyzing"
        job.current_step = "KI analysiert Aufgabe…"
        await self.db.flush()
        await self._emit(job, EVENT_ANALYSIS_STARTED, {})

        if job.mode in ("orchestra", "ai_review"):
            project = await self._get_project(job.project_id or "")
            job.current_step = (
                "AI Orchestra — 12-Phasen-Analyse…"
                if job.mode == "orchestra"
                else "AI Orchestra — Multi-Agent-Review…"
            )
            await self.db.flush()
            try:
                plan = await run_vibe_orchestra_analysis(
                    self.db,
                    job,
                    project,
                    mode=job.mode,
                    broadcast=self.broadcast,
                )
            except Exception as exc:
                job.status = "failed"
                job.current_step = f"Orchestra-Analyse fehlgeschlagen: {exc}"
                await self._add_message(
                    job_id,
                    sender_type="system",
                    sender_name="System",
                    content=str(exc),
                    message_type="error",
                )
                await self.db.flush()
                raise

            for insight in plan.get("agent_insights", []):
                await self._add_message(
                    job_id,
                    sender_type="agent",
                    sender_name=str(insight.get("agent", "Agent")),
                    content=str(insight.get("excerpt", "")),
                    message_type="agent_review",
                )

            job.implementation_plan = plan
            job.optimized_prompt = plan.get("optimized_prompt", job.original_prompt)
            job.status = "awaiting_approval"
            job.current_step = "Orchestra-Umsetzungsplan bereit"
            job.branch_name = f"orchestra/job-{job.id[:8]}-{self._slug(job.title)}"
            await self.db.flush()
            await self._add_message(
                job_id,
                sender_type="orchestra",
                sender_name="AI Orchestra",
                content=self._format_orchestra_plan_markdown(plan),
                message_type="plan",
            )
            await self._emit(job, EVENT_PLAN_CREATED, plan)
            return job

        plan = self._build_implementation_plan(job)
        job.implementation_plan = plan
        job.optimized_prompt = plan.get("optimized_prompt", job.original_prompt)
        if job.mode == "direct":
            job.status = "queued"
            job.branch_name = f"orchestra/job-{job.id[:8]}-{self._slug(job.title)}"
            job.current_step = "Direktmodus — Worker wird beauftragt"
        elif job.mode == "autonomous":
            job.status = "queued"
            job.branch_name = f"orchestra/job-{job.id[:8]}-{self._slug(job.title)}"
            job.current_step = "Autonomer Modus — Worker wird beauftragt"
        else:
            job.status = "awaiting_approval"
            job.current_step = "Umsetzungsplan bereit"
        await self.db.flush()

        await self._add_message(
            job_id,
            sender_type="orchestra",
            sender_name="AI Orchestra",
            content=self._format_plan_markdown(plan),
            message_type="plan",
        )
        await self._emit(job, EVENT_PLAN_CREATED, plan)

        if job.mode in ("autonomous", "direct"):
            await self._emit(job, EVENT_JOB_QUEUED, {"branch": job.branch_name})
        return job

    async def approve_plan(self, job_id: str, user_id: str = "default") -> CodingJob:
        job = await self._get_job(job_id)
        if job.status not in ("awaiting_approval", "draft"):
            raise ValueError(f"cannot approve job in status {job.status}")

        approval = Approval(
            job_id=job_id,
            approval_type="implementation_plan",
            description="Umsetzungsplan freigegeben",
            status="approved",
            answered_at=datetime.now(UTC),
            answered_by=user_id,
        )
        self.db.add(approval)
        job.status = "queued"
        job.current_step = "Warte auf Worker…"
        job.branch_name = f"orchestra/job-{job_id[:8]}-{self._slug(job.title)}"
        await self.db.flush()

        await self._add_message(
            job_id,
            sender_type="system",
            sender_name="System",
            content="Umsetzungsplan freigegeben. Worker wird beauftragt…",
        )
        await self._emit(job, EVENT_APPROVAL_RECEIVED, {"approval_type": "implementation_plan"})
        await self._emit(job, EVENT_JOB_QUEUED, {"branch": job.branch_name})
        return job

    async def reject_plan(self, job_id: str, reason: str = "") -> CodingJob:
        job = await self._get_job(job_id)
        job.status = "cancelled"
        job.finished_at = datetime.now(UTC)
        await self.db.flush()
        await self._add_message(
            job_id,
            sender_type="system",
            sender_name="System",
            content=f"Aufgabe abgebrochen.{f' Grund: {reason}' if reason else ''}",
        )
        await self._emit(job, EVENT_JOB_CANCELLED, {"reason": reason})
        return job

    async def start_job_on_worker(self, job_id: str) -> dict[str, Any]:
        job = await self._get_job(job_id, with_relations=True)
        if job.status != "queued":
            raise ValueError("job is not queued")

        project = await self._get_project(job.project_id or "")
        worker = await self._get_worker(job.worker_id or "")

        session = CodingSession(
            job_id=job_id,
            adapter_type=job.adapter_type,
            status="starting",
        )
        self.db.add(session)
        job.status = "preparing"
        job.started_at = datetime.now(UTC)
        job.current_step = "Worker bereitet Umgebung vor…"
        project.last_used_at = datetime.now(UTC)
        worker.status = "busy"
        await self.db.flush()

        await self._emit(job, EVENT_JOB_STARTED, {"session_id": session.id})
        return {
            "job_id": job.id,
            "session_id": session.id,
            "worker_id": worker.id,
            "project_path": project.local_path,
            "project_name": project.name,
            "branch_name": job.branch_name,
            "prompt": job.optimized_prompt or job.original_prompt,
            "adapter_type": job.adapter_type,
            "mode": job.mode,
        }

    async def handle_worker_event(self, worker_id: str, event: dict[str, Any]) -> None:
        job_id = event.get("jobId") or event.get("job_id")
        if not job_id:
            return
        job = await self._get_job(job_id)
        if job.worker_id != worker_id:
            raise ValueError("worker mismatch")

        event_type = event.get("type", "")
        payload = event.get("payload") or {}
        session_id = event.get("sessionId") or event.get("session_id")

        await self._emit(job, event_type, payload, worker_id=worker_id, session_id=session_id)

        if event_type == EVENT_AGENT_MESSAGE:
            await self._add_message(
                job_id,
                sender_type=payload.get("sender_type", "cursor"),
                sender_name=payload.get("sender_name", "Cursor"),
                content=payload.get("message", ""),
                message_type=payload.get("message_type", "text"),
            )
        elif event_type == EVENT_AGENT_QUESTION:
            job.status = "awaiting_user_input"
            job.current_step = "Cursor hat eine Rückfrage"
            await self._add_message(
                job_id,
                sender_type="cursor",
                sender_name="Cursor",
                content=payload.get("message", ""),
                message_type="question",
            )
        elif event_type == EVENT_AGENT_OUTPUT:
            await self._add_message(
                job_id,
                sender_type="worker",
                sender_name="Worker",
                content=payload.get("message", ""),
                message_type="output",
            )
        elif event_type in (EVENT_FILE_CREATED, EVENT_FILE_CHANGED):
            path = payload.get("path", "")
            change_type = "created" if event_type == EVENT_FILE_CREATED else "modified"
            fc = FileChange(
                job_id=job_id,
                path=path,
                change_type=change_type,
                diff=payload.get("diff", ""),
                content_after=payload.get("content", ""),
            )
            self.db.add(fc)
        elif event_type == EVENT_GIT_DIFF_UPDATED:
            for item in payload.get("files", []):
                fc = FileChange(
                    job_id=job_id,
                    path=item.get("path", ""),
                    change_type=item.get("change_type", "modified"),
                    diff=item.get("diff", ""),
                )
                self.db.add(fc)
        elif event_type == EVENT_TEST_STARTED:
            job.status = "testing"
            job.current_step = "Tests laufen…"
        elif event_type == EVENT_TEST_COMPLETED:
            job.current_step = "Tests abgeschlossen"
        elif event_type == EVENT_JOB_COMPLETED:
            await self._handle_worker_completion(job, worker_id, payload)
        elif event_type == EVENT_JOB_FAILED:
            job.status = "failed"
            job.finished_at = datetime.now(UTC)
            job.current_step = payload.get("error", "Fehler")
            worker = await self._get_worker(worker_id)
            worker.status = "idle"
            await self._add_message(
                job_id,
                sender_type="system",
                sender_name="System",
                content=f"Aufgabe fehlgeschlagen: {payload.get('error', 'Unbekannter Fehler')}",
                message_type="error",
            )

        if payload.get("progress_percent") is not None:
            job.progress_percent = int(payload["progress_percent"])
        if payload.get("current_step"):
            job.current_step = payload["current_step"]
        if event_type == EVENT_JOB_STARTED or event_type == "agent.started":
            job.status = "running"
        await self.db.flush()

    async def send_user_message(self, job_id: str, message: str) -> CodingJob:
        job = await self._get_job(job_id)
        await self._add_message(
            job_id, sender_type="user", sender_name="Benutzer", content=message
        )
        if job.status == "awaiting_user_input":
            job.status = "running"
            job.current_step = "Antwort an Cursor gesendet"
        await self.db.flush()
        return job

    async def approve_correction(self, job_id: str, user_id: str = "default") -> CodingJob:
        job = await self._get_job(job_id)
        plan = job.implementation_plan or {}
        if not plan.get("pending_correction"):
            raise ValueError("no pending correction")
        correction = str(plan.get("correction_prompt") or job.optimized_prompt)
        approval = Approval(
            job_id=job_id,
            approval_type="correction",
            description="Korrekturauftrag freigegeben",
            status="approved",
            answered_at=datetime.now(UTC),
            answered_by=user_id,
        )
        self.db.add(approval)
        job.review_rounds += 1
        await self._queue_correction(job, correction)
        plan["pending_correction"] = False
        job.implementation_plan = plan
        await self.db.flush()
        await self._emit(job, EVENT_APPROVAL_RECEIVED, {"approval_type": "correction"})
        if self.dispatch_worker:
            await self.dispatch_worker(job)
        return job

    async def accept_review_result(self, job_id: str) -> CodingJob:
        """Accept result despite open review issues (user override)."""
        job = await self._get_job(job_id)
        worker_result = (job.completion_report or {}).get("worker_result") or job.completion_report or {}
        review_data = (job.implementation_plan or {}).get("last_review") or {}
        await self._finalize_job_success(job, worker_result, review_data, user_accepted=True)
        if job.worker_id:
            worker = await self._get_worker(job.worker_id)
            worker.status = "idle"
        await self.db.flush()
        return job

    async def get_review(self, job_id: str) -> dict[str, Any]:
        job = await self._get_job(job_id)
        plan = job.implementation_plan or {}
        return {
            "last_review": plan.get("last_review"),
            "pending_correction": plan.get("pending_correction", False),
            "correction_prompt": plan.get("correction_prompt"),
            "review_rounds": job.review_rounds,
            "max_review_rounds": job.max_review_rounds,
        }

    async def cancel_job(self, job_id: str) -> CodingJob:
        job = await self._get_job(job_id)
        job.status = "cancelled"
        job.finished_at = datetime.now(UTC)
        await self.db.flush()
        await self._emit(job, EVENT_JOB_CANCELLED, {})
        return job

    async def pause_job(self, job_id: str) -> CodingJob:
        job = await self._get_job(job_id)
        job.current_step = "Pausiert"
        await self.db.flush()
        return job

    async def resume_job(self, job_id: str) -> CodingJob:
        job = await self._get_job(job_id)
        job.status = "running"
        job.current_step = "Fortgesetzt"
        await self.db.flush()
        return job

    async def get_job_detail(self, job_id: str) -> CodingJob:
        return await self._get_job(job_id, with_relations=True)

    async def list_jobs(
        self,
        *,
        status: str | None = None,
        worker_id: str | None = None,
        user_id: str | None = None,
        admin: bool = False,
    ) -> list[CodingJob]:
        q = select(CodingJob).order_by(CodingJob.created_at.desc())
        if status:
            q = q.where(CodingJob.status == status)
        if worker_id:
            q = q.where(CodingJob.worker_id == worker_id)
        if user_id and not admin:
            q = q.where(CodingJob.user_id == user_id)
        r = await self.db.execute(q)
        return list(r.scalars().all())

    async def list_events(self, job_id: str, limit: int = 500) -> list[VibeJobEvent]:
        r = await self.db.execute(
            select(VibeJobEvent)
            .where(VibeJobEvent.job_id == job_id)
            .order_by(VibeJobEvent.created_at)
            .limit(limit)
        )
        return list(r.scalars().all())

    async def list_messages(self, job_id: str) -> list[ChatMessage]:
        r = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.job_id == job_id)
            .order_by(ChatMessage.created_at)
        )
        return list(r.scalars().all())

    async def list_file_changes(self, job_id: str) -> list[FileChange]:
        r = await self.db.execute(
            select(FileChange).where(FileChange.job_id == job_id).order_by(FileChange.path)
        )
        return list(r.scalars().all())

    async def get_combined_diff(self, job_id: str) -> str:
        changes = await self.list_file_changes(job_id)
        parts = [f"--- a/{c.path}\n+++ b/{c.path}\n{c.diff}" for c in changes if c.diff]
        return "\n\n".join(parts)

    # --- Internals ---

    async def _emit(
        self,
        job: CodingJob,
        event_type: str,
        payload: dict[str, Any],
        *,
        worker_id: str | None = None,
        session_id: str | None = None,
    ) -> VibeJobEvent:
        masked = mask_dict(payload)
        row = VibeJobEvent(
            job_id=job.id,
            worker_id=worker_id or job.worker_id,
            session_id=session_id,
            event_type=event_type,
            payload=masked if isinstance(masked, dict) else {"data": masked},
        )
        self.db.add(row)
        await self.db.flush()

        if self.broadcast:
            msg = {
                "version": VIBE_PROTOCOL_VERSION,
                "eventId": row.id,
                "type": event_type,
                "timestamp": row.created_at.isoformat(),
                "workerId": worker_id or job.worker_id,
                "jobId": job.id,
                "sessionId": session_id,
                "payload": masked,
            }
            await self.broadcast(f"vibe-job-{job.id}", msg)
            await self.broadcast("vibe-global", {**msg, "jobStatus": job.status})
        return row

    async def _add_message(
        self,
        job_id: str,
        *,
        sender_type: str,
        sender_name: str,
        content: str,
        message_type: str = "text",
    ) -> ChatMessage:
        msg = ChatMessage(
            job_id=job_id,
            sender_type=sender_type,
            sender_name=sender_name,
            content=mask_secrets(content),
            message_type=message_type,
        )
        self.db.add(msg)
        await self.db.flush()
        if self.broadcast:
            await self.broadcast(
                f"vibe-job-{job_id}",
                {
                    "version": VIBE_PROTOCOL_VERSION,
                    "type": "chat.message",
                    "jobId": job_id,
                    "payload": {
                        "id": msg.id,
                        "sender_type": sender_type,
                        "sender_name": sender_name,
                        "content": msg.content,
                        "message_type": message_type,
                        "created_at": msg.created_at.isoformat(),
                    },
                },
            )
        return msg

    async def _handle_worker_completion(
        self, job: CodingJob, worker_id: str, payload: dict[str, Any]
    ) -> None:
        settings = get_settings()
        if not settings.vibe_auto_review:
            await self._finalize_job_success(job, payload, {})
            worker = await self._get_worker(worker_id)
            worker.status = "idle"
            return

        job.status = "reviewing"
        job.current_step = "AI Orchestra prüft Ergebnis…"
        job.completion_report = {"worker_result": payload}
        await self.db.flush()
        await self._emit(job, EVENT_REVIEW_STARTED, {})

        file_changes = await self.list_file_changes(job.id)
        review = await run_implementation_review(job, payload, file_changes)

        plan = dict(job.implementation_plan or {})
        plan["last_review"] = review.report
        job.implementation_plan = plan

        await self._emit(job, EVENT_REVIEW_COMPLETED, review.report)
        await self._add_message(
            job.id,
            sender_type="orchestra",
            sender_name="AI Orchestra",
            content=format_review_markdown(review, job),
            message_type="review" if review.passed else "correction_plan",
        )

        if review.passed:
            await self._finalize_job_success(job, payload, review.report)
            worker = await self._get_worker(worker_id)
            worker.status = "idle"
            return

        if job.review_rounds >= job.max_review_rounds:
            job.current_step = "Max. Korrekturrunden erreicht — manuelle Prüfung nötig"
            await self._finalize_job_success(
                job, payload, review.report, user_accepted=False, with_issues=True
            )
            worker = await self._get_worker(worker_id)
            worker.status = "idle"
            return

        if should_auto_dispatch_correction(job):
            job.review_rounds += 1
            await self._queue_correction(job, review.correction_prompt)
            await self._emit(job, EVENT_CORRECTION_QUEUED, {"round": job.review_rounds})
            if self.dispatch_worker:
                await self.dispatch_worker(job)
            return

        plan["pending_correction"] = True
        plan["correction_prompt"] = review.correction_prompt
        job.implementation_plan = plan
        job.status = "awaiting_approval"
        job.current_step = "Korrekturauftrag wartet auf Freigabe"
        await self._emit(
            job,
            EVENT_APPROVAL_REQUIRED,
            {"approval_type": "correction", "description": review.report.get("summary", "")},
        )

    async def _queue_correction(self, job: CodingJob, correction_prompt: str) -> None:
        if not correction_prompt.strip():
            correction_prompt = (
                f"Bitte behebe die offenen Probleme aus der Nachprüfung.\n\n"
                f"Originalaufgabe:\n{job.original_prompt}"
            )
        job.optimized_prompt = correction_prompt
        job.status = "queued"
        job.current_step = f"Korrekturrunde {job.review_rounds}/{job.max_review_rounds}"
        job.progress_percent = 0
        await self.db.flush()
        await self._emit(job, EVENT_JOB_QUEUED, {"correction_round": job.review_rounds})
        await self._add_message(
            job.id,
            sender_type="system",
            sender_name="System",
            content=f"Korrekturauftrag an Worker übergeben (Runde {job.review_rounds}).",
        )

    async def _finalize_job_success(
        self,
        job: CodingJob,
        worker_payload: dict[str, Any],
        review_report: dict[str, Any],
        *,
        user_accepted: bool = False,
        with_issues: bool = False,
    ) -> None:
        job.status = "completed"
        job.finished_at = datetime.now(UTC)
        job.progress_percent = 100
        job.completion_report = {
            "worker_result": worker_payload,
            "review": review_report,
            "user_accepted": user_accepted,
            "completed_with_issues": with_issues,
            **{k: v for k, v in worker_payload.items() if k != "worker_result"},
        }
        job.current_step = (
            "Abgeschlossen (mit offenen Punkten)" if with_issues else "Abgeschlossen"
        )
        await self._add_completion_report(job, worker_payload, review_report, with_issues)

    async def _add_completion_report(
        self,
        job: CodingJob,
        payload: dict[str, Any],
        review_report: dict[str, Any] | None = None,
        with_issues: bool = False,
    ) -> None:
        report = self._format_completion_report(job, payload, review_report, with_issues)
        await self._add_message(
            job.id,
            sender_type="orchestra",
            sender_name="AI Orchestra",
            content=report,
            message_type="completion_report",
        )

    def _build_implementation_plan(self, job: CodingJob) -> dict[str, Any]:
        prompt = job.original_prompt
        mode_labels = {
            "direct": "Direkt",
            "ai_review": "AI Review",
            "orchestra": "Orchestra",
            "autonomous": "Autonom",
        }
        requirements = [line.strip() for line in prompt.split("\n") if line.strip()]
        optimized = (
            f"# Umsetzungsauftrag\n\n"
            f"## Aufgabe\n{prompt}\n\n"
            f"## Modus\n{mode_labels.get(job.mode, job.mode)}\n\n"
            f"## Anweisungen\n"
            f"- Halte dich an bestehende Projekt-Konventionen\n"
            f"- Erstelle Tests wo sinnvoll\n"
            f"- Keine destruktiven Git-Operationen ohne Freigabe\n"
        )
        if job.mode in ("ai_review", "orchestra"):
            optimized += (
                "\n## AI-Review-Hinweise\n"
                "- Sicherheitsaspekte prüfen\n"
                "- Architektur-Konsistenz sicherstellen\n"
                "- Edge Cases abdecken\n"
            )
        return {
            "summary": job.title,
            "requirements": requirements,
            "affected_components": ["Backend", "Frontend", "Datenbank"],
            "planned_changes": ["Implementierung gemäß Aufgabenstellung"],
            "expected_files": [],
            "database_changes": "Nach Bedarf" if "migration" in prompt.lower() else "Keine",
            "security_aspects": ["Berechtigungsprüfung", "Input-Validierung"],
            "planned_tests": ["Unit-Tests", "Integrationstests"],
            "risks": ["Unvollständige Anforderungen"],
            "assumptions": ["Bestehende Architektur wird beibehalten"],
            "optimized_prompt": optimized,
        }

    def _format_orchestra_plan_markdown(self, plan: dict[str, Any]) -> str:
        base = self._format_plan_markdown(plan)
        extra_parts = []
        if plan.get("consensus_summary"):
            extra_parts.append(f"### Konsens\n{plan['consensus_summary']}")
        if plan.get("agreed_solution"):
            extra_parts.append(f"### Lösung\n{plan['agreed_solution']}")
        if plan.get("risks"):
            extra_parts.append(f"### Risiken\n{plan['risks']}")
        if plan.get("phases_completed"):
            phases = "\n".join(
                f"- {p['phase']}: {p.get('summary', '')[:80]}"
                for p in plan["phases_completed"]
            )
            extra_parts.append(f"### Orchestra-Phasen\n{phases}")
        if extra_parts:
            return base + "\n\n" + "\n\n".join(extra_parts)
        return base

    def _format_plan_markdown(self, plan: dict[str, Any]) -> str:
        reqs = "\n".join(f"- {r}" for r in plan.get("requirements", []))
        return (
            f"## Umsetzungsplan\n\n"
            f"**Zusammenfassung:** {plan.get('summary', '')}\n\n"
            f"### Anforderungen\n{reqs}\n\n"
            f"### Geplante Änderungen\n"
            + "\n".join(f"- {c}" for c in plan.get("planned_changes", []))
            + f"\n\n### Tests\n"
            + "\n".join(f"- {t}" for t in plan.get("planned_tests", []))
            + f"\n\n### Risiken\n"
            + "\n".join(f"- {r}" for r in plan.get("risks", []))
        )

    def _format_completion_report(
        self,
        job: CodingJob,
        payload: dict[str, Any],
        review_report: dict[str, Any] | None = None,
        with_issues: bool = False,
    ) -> str:
        files = payload.get("changed_files", [])
        file_list = "\n".join(f"- `{f}`" for f in files) if files else "- (keine)"
        tests = payload.get("tests", {})
        review_section = ""
        if review_report:
            score = review_report.get("score", "—")
            review_section = (
                f"\n### AI-Nachprüfung\n"
                f"- Score: {score}/100\n"
                f"- {review_report.get('summary', '')}\n"
            )
            if with_issues:
                review_section += "- **Hinweis:** Max. Korrekturrunden erreicht — bitte manuell prüfen.\n"
        return (
            f"## Aufgabe abgeschlossen\n\n"
            f"### Umgesetzt\n{payload.get('summary', 'Erfolgreich abgeschlossen')}\n\n"
            f"### Geänderte Dateien\n{file_list}\n\n"
            f"### Prüfungen\n"
            f"- Build: {payload.get('build_status', 'n/a')}\n"
            f"- Lint: {payload.get('lint_status', 'n/a')}\n"
            f"- Tests: {tests.get('passed', 0)} erfolgreich, {tests.get('failed', 0)} fehlgeschlagen\n"
            f"{review_section}\n"
            f"### Git\nBranch: `{job.branch_name}`\n\n"
            f"Es wurde noch kein Commit und kein Push durchgeführt."
        )

    @staticmethod
    def _slug(text: str) -> str:
        import re

        s = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
        return s[:40] or "task"

    async def _get_worker(self, worker_id: str) -> WorkerRegistration:
        w = await self.db.get(WorkerRegistration, worker_id)
        if not w:
            raise ValueError("worker not found")
        return w

    async def _get_project(self, project_id: str) -> WorkerProject:
        p = await self.db.get(WorkerProject, project_id)
        if not p:
            raise ValueError("project not found")
        return p

    async def _get_job(self, job_id: str, *, with_relations: bool = False) -> CodingJob:
        if with_relations:
            r = await self.db.execute(
                select(CodingJob)
                .where(CodingJob.id == job_id)
                .options(
                    selectinload(CodingJob.messages),
                    selectinload(CodingJob.events),
                    selectinload(CodingJob.file_changes),
                    selectinload(CodingJob.sessions),
                )
            )
            job = r.scalar_one_or_none()
        else:
            job = await self.db.get(CodingJob, job_id)
        if not job:
            raise ValueError("job not found")
        return job
