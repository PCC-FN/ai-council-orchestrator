from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import (
    CurrentUser,
    assert_job_access,
    assert_job_write,
    get_current_user,
    require_admin,
    require_developer,
    require_viewer,
)

from app.api.vibe_websocket import VibeWSManager
from app.core.vibe_events import EVENT_WORKER_CONNECTED, EVENT_WORKER_DISCONNECTED
from app.config import get_settings
from app.database import get_db
from app.models.db_models import WorkerRegistration
from app.models.vibe_models import CodingJob, WorkerProject
from app.schemas.vibe_schemas import (
    ChatMessageOut,
    CodingJobApproveIn,
    CodingJobCommitIn,
    CodingJobCreate,
    CodingJobMessageIn,
    CodingJobOut,
    CodingJobPushIn,
    CodingJobRejectIn,
    FileChangeOut,
    VibeJobEventOut,
    VibeWorkerOut,
    WorkerProjectOut,
    WorkerRegisterVibeIn,
    WorkerTokenOut,
)
from app.vibe.service import VibeCodingService

vibe_router = APIRouter(prefix="/coding", tags=["vibe-coding"])
vibe_workers_router = APIRouter(prefix="/vibe/workers", tags=["vibe-workers"])

_vibe_ws: VibeWSManager | None = None


def set_vibe_ws(mgr: VibeWSManager) -> None:
    global _vibe_ws
    _vibe_ws = mgr


def get_vibe_ws() -> VibeWSManager:
    if not _vibe_ws:
        raise RuntimeError("VibeWSManager not initialized")
    return _vibe_ws


async def _broadcast(channel: str, payload: dict[str, Any]) -> None:
    if _vibe_ws:
        await _vibe_ws.broadcast(channel, payload)


async def _dispatch_worker_job(db: AsyncSession, job: CodingJob) -> bool:
    svc = VibeCodingService(db, _broadcast, None)
    ws = get_vibe_ws()
    try:
        payload = await svc.start_job_on_worker(job.id)
        await db.flush()
        return await ws.send_to_worker(
            job.worker_id or "",
            {"type": "job.execute", "payload": payload},
        )
    except ValueError:
        return False


def _vibe(db: AsyncSession) -> VibeCodingService:
    async def dispatch(job: CodingJob) -> bool:
        return await _dispatch_worker_job(db, job)

    return VibeCodingService(db, _broadcast, dispatch)


async def _job_write_guard(job_id: str, user: CurrentUser, db: AsyncSession) -> CodingJob:
    job = await _vibe(db).get_job_detail(job_id)
    await assert_job_access(job.user_id, user)
    await assert_job_write(job.user_id, user)
    return job


def _worker_online(w: WorkerRegistration) -> bool:
    if _vibe_ws and _vibe_ws.is_worker_online(w.id):
        return True
    if not w.last_heartbeat_at:
        return False
    hb = w.last_heartbeat_at
    if hb.tzinfo is None:
        hb = hb.replace(tzinfo=UTC)
    return hb >= datetime.now(UTC) - timedelta(seconds=120)


def _worker_out(w: WorkerRegistration, project_count: int = 0) -> VibeWorkerOut:
    caps = w.capabilities or {}
    return VibeWorkerOut(
        id=w.id,
        name=w.name,
        hostname=w.hostname,
        status=w.status,
        version=str(caps.get("version", "1.0.0")),
        operating_system=str(caps.get("operating_system", "")),
        capabilities={k: v for k, v in caps.items() if k != "token_hash"},
        last_heartbeat_at=w.last_heartbeat_at,
        online=_worker_online(w),
        project_count=project_count,
    )


def _job_out(job: CodingJob) -> CodingJobOut:
    return CodingJobOut(
        id=job.id,
        user_id=job.user_id,
        worker_id=job.worker_id,
        project_id=job.project_id,
        mode=job.mode,
        title=job.title,
        original_prompt=job.original_prompt,
        optimized_prompt=job.optimized_prompt,
        implementation_plan=job.implementation_plan or {},
        status=job.status,
        branch_name=job.branch_name,
        current_step=job.current_step,
        progress_percent=job.progress_percent,
        adapter_type=job.adapter_type,
        started_at=job.started_at,
        finished_at=job.finished_at,
        completion_report=job.completion_report or {},
        created_at=job.created_at,
        updated_at=job.updated_at,
        messages=[ChatMessageOut.model_validate(m) for m in (job.messages or [])],
        file_changes=[FileChangeOut.model_validate(f) for f in (job.file_changes or [])],
    )


# --- Workers (browser API) ---


@vibe_workers_router.get("", response_model=list[VibeWorkerOut])
async def list_vibe_workers(
    db: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_viewer),
):
    svc = _vibe(db)
    workers = await svc.list_workers()
    out: list[VibeWorkerOut] = []
    for w in workers:
        projects = await svc.list_worker_projects(w.id)
        out.append(_worker_out(w, len(projects)))
    return out


@vibe_workers_router.post("/register-token", response_model=WorkerTokenOut)
async def create_worker_token(
    name: str = "Development-PC",
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    if get_settings().auth_required and not user.is_admin:
        raise HTTPException(403, "Nur Administratoren dürfen Worker registrieren")
    svc = _vibe(db)
    token, token_hash = svc.generate_worker_token()
    w = WorkerRegistration(
        name=name,
        worker_type="vibe",
        capabilities={"token_hash": token_hash, "version": "1.0.0"},
        status="offline",
    )
    db.add(w)
    await db.commit()
    return WorkerTokenOut(worker_id=w.id, token=token)


@vibe_workers_router.get("/{worker_id}", response_model=VibeWorkerOut)
async def get_vibe_worker(
    worker_id: str,
    db: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_viewer),
):
    w = await db.get(WorkerRegistration, worker_id)
    if not w:
        raise HTTPException(404, "worker not found")
    projects = await _vibe(db).list_worker_projects(worker_id)
    return _worker_out(w, len(projects))


@vibe_workers_router.get("/{worker_id}/projects", response_model=list[WorkerProjectOut])
async def list_worker_projects(
    worker_id: str,
    db: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_viewer),
):
    rows = await _vibe(db).list_worker_projects(worker_id)
    return [WorkerProjectOut.model_validate(p) for p in rows]


# --- Coding Jobs ---


@vibe_router.post("/jobs", response_model=CodingJobOut)
async def create_coding_job(
    body: CodingJobCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_developer),
):
    svc = _vibe(db)
    try:
        job = await svc.create_job(
            worker_id=body.worker_id,
            project_id=body.project_id,
            prompt=body.prompt,
            mode=body.mode,
            title=body.title,
            adapter_type=body.adapter_type,
            user_id=user.id,
        )
        await db.commit()
        job = await svc.get_job_detail(job.id)
        return _job_out(job)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@vibe_router.get("/jobs", response_model=list[CodingJobOut])
async def list_coding_jobs(
    status: str | None = None,
    worker_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_viewer),
):
    rows = await _vibe(db).list_jobs(
        status=status,
        worker_id=worker_id,
        user_id=user.id,
        admin=user.is_admin,
    )
    return [
        CodingJobOut.model_validate(
            {**r.__dict__, "messages": [], "file_changes": [], "implementation_plan": r.implementation_plan or {}}
        )
        for r in rows
    ]


@vibe_router.get("/jobs/{job_id}", response_model=CodingJobOut)
async def get_coding_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_viewer),
):
    try:
        job = await _vibe(db).get_job_detail(job_id)
        await assert_job_access(job.user_id, user)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    return _job_out(job)


@vibe_router.post("/jobs/{job_id}/start", response_model=CodingJobOut)
async def start_coding_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_developer),
):
    await _job_write_guard(job_id, user, db)
    svc = _vibe(db)
    try:
        job = await svc.get_job_detail(job_id)
        if job.status == "draft":
            job = await svc.analyze_job(job_id)
        if job.status == "awaiting_approval":
            raise HTTPException(400, "Plan muss zuerst freigegeben werden")
        if job.status == "queued":
            payload = await svc.start_job_on_worker(job_id)
            ws = get_vibe_ws()
            sent = await ws.send_to_worker(
                job.worker_id or "",
                {"type": "job.execute", "payload": payload},
            )
            if not sent:
                job.status = "queued"
                job.current_step = "Worker offline — Aufgabe wartet in Warteschlange"
            await db.commit()
        job = await svc.get_job_detail(job_id)
        return _job_out(job)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@vibe_router.post("/jobs/{job_id}/analyze", response_model=CodingJobOut)
async def analyze_coding_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_developer),
):
    await _job_write_guard(job_id, user, db)
    svc = _vibe(db)
    try:
        job = await svc.analyze_job(job_id)
        await db.commit()
        job = await svc.get_job_detail(job.id)
        return _job_out(job)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@vibe_router.post("/jobs/{job_id}/approve", response_model=CodingJobOut)
async def approve_coding_job(
    job_id: str,
    body: CodingJobApproveIn | None = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_developer),
):
    await _job_write_guard(job_id, user, db)
    svc = _vibe(db)
    try:
        job = await svc.approve_plan(job_id)
        if body and body.edited_plan:
            job.implementation_plan = body.edited_plan
        payload = await svc.start_job_on_worker(job_id)
        ws = get_vibe_ws()
        sent = await ws.send_to_worker(job.worker_id or "", {"type": "job.execute", "payload": payload})
        if not sent:
            job.status = "queued"
            job.current_step = "Worker offline — Aufgabe wartet in Warteschlange"
        await db.commit()
        job = await svc.get_job_detail(job_id)
        return _job_out(job)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@vibe_router.post("/jobs/{job_id}/reject", response_model=CodingJobOut)
async def reject_coding_job(
    job_id: str, body: CodingJobRejectIn | None = None, db: AsyncSession = Depends(get_db)
):
    svc = _vibe(db)
    try:
        job = await svc.reject_plan(job_id, reason=body.reason if body else "")
        await db.commit()
        return _job_out(job)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@vibe_router.post("/jobs/{job_id}/message", response_model=CodingJobOut)
async def send_job_message(
    job_id: str,
    body: CodingJobMessageIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_developer),
):
    await _job_write_guard(job_id, user, db)
    svc = _vibe(db)
    try:
        job = await svc.send_user_message(job_id, body.message)
        ws = get_vibe_ws()
        session_id = ""
        if job.sessions:
            session_id = job.sessions[-1].id
        await ws.send_to_worker(
            job.worker_id or "",
            {
                "type": "job.message",
                "payload": {
                    "job_id": job_id,
                    "session_id": session_id,
                    "message": body.message,
                },
            },
        )
        await db.commit()
        job = await svc.get_job_detail(job_id)
        return _job_out(job)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@vibe_router.post("/jobs/{job_id}/pause", response_model=CodingJobOut)
async def pause_job(job_id: str, db: AsyncSession = Depends(get_db)):
    svc = _vibe(db)
    try:
        job = await svc.pause_job(job_id)
        ws = get_vibe_ws()
        await ws.send_to_worker(job.worker_id or "", {"type": "job.pause", "payload": {"job_id": job_id}})
        await db.commit()
        return _job_out(job)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@vibe_router.post("/jobs/{job_id}/resume", response_model=CodingJobOut)
async def resume_job(job_id: str, db: AsyncSession = Depends(get_db)):
    svc = _vibe(db)
    try:
        job = await svc.resume_job(job_id)
        ws = get_vibe_ws()
        await ws.send_to_worker(job.worker_id or "", {"type": "job.resume", "payload": {"job_id": job_id}})
        await db.commit()
        return _job_out(job)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@vibe_router.post("/jobs/{job_id}/cancel", response_model=CodingJobOut)
async def cancel_job(job_id: str, db: AsyncSession = Depends(get_db)):
    svc = _vibe(db)
    try:
        job = await svc.cancel_job(job_id)
        ws = get_vibe_ws()
        await ws.send_to_worker(job.worker_id or "", {"type": "job.cancel", "payload": {"job_id": job_id}})
        await db.commit()
        return _job_out(job)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@vibe_router.get("/jobs/{job_id}/events", response_model=list[VibeJobEventOut])
async def list_job_events(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_viewer),
):
    job = await _vibe(db).get_job_detail(job_id)
    await assert_job_access(job.user_id, user)
    rows = await _vibe(db).list_events(job_id)
    return [VibeJobEventOut.model_validate(e) for e in rows]


@vibe_router.get("/jobs/{job_id}/files", response_model=list[FileChangeOut])
async def list_job_files(job_id: str, db: AsyncSession = Depends(get_db)):
    rows = await _vibe(db).list_file_changes(job_id)
    return [FileChangeOut.model_validate(f) for f in rows]


@vibe_router.get("/jobs/{job_id}/diff")
async def get_job_diff(job_id: str, db: AsyncSession = Depends(get_db)):
    diff = await _vibe(db).get_combined_diff(job_id)
    return {"diff": diff}


@vibe_router.get("/jobs/{job_id}/tests")
async def get_job_tests(job_id: str, db: AsyncSession = Depends(get_db)):
    try:
        job = await _vibe(db).get_job_detail(job_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    report = job.completion_report or {}
    return {
        "build_status": report.get("build_status", "unknown"),
        "lint_status": report.get("lint_status", "unknown"),
        "tests": report.get("tests", {"passed": 0, "failed": 0, "skipped": 0, "details": []}),
    }


@vibe_router.post("/jobs/{job_id}/approve-correction", response_model=CodingJobOut)
async def approve_correction(job_id: str, db: AsyncSession = Depends(get_db)):
    svc = _vibe(db)
    try:
        job = await svc.approve_correction(job_id)
        await db.commit()
        job = await svc.get_job_detail(job_id)
        return _job_out(job)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@vibe_router.post("/jobs/{job_id}/accept-result", response_model=CodingJobOut)
async def accept_review_result(job_id: str, db: AsyncSession = Depends(get_db)):
    svc = _vibe(db)
    try:
        job = await svc.accept_review_result(job_id)
        await db.commit()
        job = await svc.get_job_detail(job_id)
        return _job_out(job)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@vibe_router.get("/jobs/{job_id}/review")
async def get_job_review(job_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await _vibe(db).get_review(job_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@vibe_router.post("/jobs/{job_id}/commit")
async def commit_job(
    job_id: str, body: CodingJobCommitIn, db: AsyncSession = Depends(get_db)
):
    svc = _vibe(db)
    try:
        job = await svc.get_job_detail(job_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    ws = get_vibe_ws()
    sent = await ws.send_to_worker(
        job.worker_id or "",
        {
            "type": "git.commit",
            "payload": {"job_id": job_id, "message": body.message},
        },
    )
    if not sent:
        raise HTTPException(503, "Worker offline")
    await svc._add_message(
        job_id,
        sender_type="system",
        sender_name="System",
        content=f"Commit angefordert: `{body.message}`",
    )
    await db.commit()
    return {"status": "commit_requested", "message": body.message}


@vibe_router.post("/jobs/{job_id}/push")
async def push_job(job_id: str, body: CodingJobPushIn | None = None, db: AsyncSession = Depends(get_db)):
    svc = _vibe(db)
    try:
        job = await svc.get_job_detail(job_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    ws = get_vibe_ws()
    sent = await ws.send_to_worker(
        job.worker_id or "",
        {
            "type": "git.push",
            "payload": {
                "job_id": job_id,
                "allow_dangerous": body.allow_dangerous if body else False,
            },
        },
    )
    if not sent:
        raise HTTPException(503, "Worker offline")
    await svc._add_message(
        job_id,
        sender_type="system",
        sender_name="System",
        content="Push angefordert",
    )
    await db.commit()
    return {"status": "push_requested", "branch": job.branch_name}


@vibe_router.post("/jobs/{job_id}/rollback")
async def rollback_job(job_id: str, db: AsyncSession = Depends(get_db)):
    svc = _vibe(db)
    try:
        job = await svc.get_job_detail(job_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    ws = get_vibe_ws()
    sent = await ws.send_to_worker(
        job.worker_id or "",
        {"type": "git.rollback", "payload": {"job_id": job_id}},
    )
    if not sent:
        raise HTTPException(503, "Worker offline")
    await svc._add_message(
        job_id,
        sender_type="system",
        sender_name="System",
        content="Rollback angefordert — Stash wird wiederhergestellt",
    )
    await db.commit()
    return {"status": "rollback_requested"}


# --- WebSocket handlers ---


async def vibe_job_websocket(websocket: WebSocket, job_id: str) -> None:
    ws_mgr = get_vibe_ws()
    channel = f"vibe-job-{job_id}"
    await ws_mgr.connect_browser(channel, websocket)
    await ws_mgr.connect_browser("vibe-global", websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_mgr.disconnect_browser(channel, websocket)
        ws_mgr.disconnect_browser("vibe-global", websocket)


async def vibe_worker_websocket(websocket: WebSocket, db: AsyncSession) -> None:
    ws_mgr = get_vibe_ws()
    svc = _vibe(db)
    worker_id: str | None = None
    try:
        auth_raw = await websocket.receive_json()
        if auth_raw.get("type") != "auth":
            await websocket.close(code=4001)
            return
        token = auth_raw.get("token", "")
        worker = await svc.authenticate_worker_token(token)
        if not worker:
            await websocket.close(code=4003)
            return

        reg = auth_raw.get("payload") or {}
        worker = await svc.register_worker_with_token(
            name=reg.get("name", worker.name),
            token=token,
            hostname=reg.get("hostname", worker.hostname),
            operating_system=reg.get("operating_system", ""),
            version=reg.get("version", "1.0.0"),
            capabilities=reg.get("capabilities"),
        )
        if reg.get("projects"):
            await svc.sync_worker_projects(worker.id, reg["projects"])
        await db.commit()

        worker_id = worker.id
        await ws_mgr.connect_worker(worker_id, websocket)
        await _broadcast(
            "vibe-global",
            {
                "type": EVENT_WORKER_CONNECTED,
                "workerId": worker_id,
                "payload": {"name": worker.name},
            },
        )

        while True:
            msg = await websocket.receive_json()
            msg_type = msg.get("type", "")

            if msg_type == "worker.heartbeat":
                worker.last_heartbeat_at = datetime.now(UTC)
                worker.status = msg.get("payload", {}).get("status", "idle")
                await db.commit()
                await websocket.send_json({"type": "worker.heartbeat.ack"})
            elif msg_type == "worker.event":
                inner = msg.get("payload") or {}
                await svc.handle_worker_event(
                    worker_id,
                    {
                        "job_id": msg.get("jobId"),
                        "session_id": msg.get("sessionId"),
                        "type": inner.get("type"),
                        "payload": inner.get("payload", {}),
                    },
                )
                await db.commit()
            elif msg_type == "worker.projects":
                projects = msg.get("payload", {}).get("projects", [])
                await svc.sync_worker_projects(worker_id, projects)
                await db.commit()
            elif msg_type == "worker.request_job":
                r = await db.execute(
                    select(CodingJob)
                    .where(CodingJob.worker_id == worker_id, CodingJob.status == "queued")
                    .order_by(CodingJob.created_at)
                    .limit(1)
                )
                pending = r.scalar_one_or_none()
                if pending:
                    payload = await svc.start_job_on_worker(pending.id)
                    await db.commit()
                    await websocket.send_json({"type": "job.execute", "payload": payload})
    except WebSocketDisconnect:
        pass
    finally:
        if worker_id:
            disconnected = ws_mgr.disconnect_worker(websocket)
            if disconnected:
                w = await db.get(WorkerRegistration, disconnected)
                if w:
                    w.status = "offline"
                    await db.commit()
                await _broadcast(
                    "vibe-global",
                    {"type": EVENT_WORKER_DISCONNECTED, "workerId": disconnected},
                )
