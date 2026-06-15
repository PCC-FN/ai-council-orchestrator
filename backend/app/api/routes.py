from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.db_models import (
    AgentResponse,
    Consensus,
    CouncilSession,
    FinalPrompt,
    Project,
)
from app.schemas.schemas import (
    AgentResponseOut,
    ConsensusOut,
    CouncilSessionOut,
    CouncilSessionSummary,
    FinalPromptOut,
    ImplementationManualUpdate,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
    SessionCreate,
)
from app.services.export_markdown import session_to_markdown
from app.services.orchestrator import CouncilOrchestrator

router = APIRouter(prefix="/projects", tags=["projects"])

ws_manager: Any | None = None


def set_ws(mgr: Any) -> None:
    global ws_manager
    ws_manager = mgr


async def _broadcast(session_id: str, payload: dict[str, Any]) -> None:
    if ws_manager:
        await ws_manager.broadcast(session_id, payload)


@router.get("/{project_id}/context/files", response_model=list[str])
async def project_list_files(project_id: str, db: AsyncSession = Depends(get_db)):
    q = await db.execute(select(Project).where(Project.id == project_id))
    p = q.scalar_one_or_none()
    if not p:
        raise HTTPException(404, "project not found")
    from app.services.project_context import list_project_files

    return list_project_files(p.repository_path)


@router.get("/{project_id}/context/file")
async def project_read_file(project_id: str, path: str, db: AsyncSession = Depends(get_db)):
    q = await db.execute(select(Project).where(Project.id == project_id))
    proj = q.scalar_one_or_none()
    if not proj:
        raise HTTPException(404, "project not found")
    from app.services.project_context import read_safe_file_sync

    content = read_safe_file_sync(proj.repository_path, path)
    if content is None:
        raise HTTPException(404, "file not found or blocked")
    return {"path": path, "content": content}


@router.post("", response_model=ProjectOut)
async def create_project(body: ProjectCreate, db: AsyncSession = Depends(get_db)):
    p = Project(
        name=body.name,
        description=body.description,
        repository_path=body.repository_path,
        coding_rules=body.coding_rules,
        security_rules=body.security_rules,
        tech_stack=body.tech_stack,
        excluded_paths=body.excluded_paths,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


@router.get("", response_model=list[ProjectOut])
async def list_projects(db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(Project).order_by(Project.created_at.desc()))
    return list(r.scalars().all())


async def _get_project(project_id: str, db: AsyncSession) -> Project:
    q = await db.execute(select(Project).where(Project.id == project_id))
    p = q.scalar_one_or_none()
    if not p:
        raise HTTPException(404, "project not found")
    return p


@router.get("/{project_id}", response_model=ProjectOut)
async def read_project(project_id: str, db: AsyncSession = Depends(get_db)):
    return await _get_project(project_id, db)


@router.put("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: str, body: ProjectUpdate, db: AsyncSession = Depends(get_db)
):
    p = await _get_project(project_id, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(p, field, value)
    await db.commit()
    await db.refresh(p)
    return p


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db)):
    p = await _get_project(project_id, db)
    await db.delete(p)
    await db.commit()


@router.get("/{project_id}/sessions", response_model=list[CouncilSessionOut])
async def list_sessions(project_id: str, db: AsyncSession = Depends(get_db)):
    r = await db.execute(
        select(CouncilSession)
        .where(CouncilSession.project_id == project_id)
        .options(
            selectinload(CouncilSession.agent_responses),
            selectinload(CouncilSession.consensus),
            selectinload(CouncilSession.final_prompts),
            selectinload(CouncilSession.implementation),
        )
        .order_by(CouncilSession.created_at.desc())
    )
    return list(r.scalars().unique().all())


@router.post("/{project_id}/sessions", response_model=CouncilSessionOut)
async def create_session(
    project_id: str, body: SessionCreate, db: AsyncSession = Depends(get_db)
):
    q = await db.execute(select(Project).where(Project.id == project_id))
    if not q.scalar_one_or_none():
        raise HTTPException(404, "project not found")
    s = CouncilSession(
        project_id=project_id,
        title=body.title,
        original_user_task=body.build_task() or body.original_user_task,
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return await get_session(s.id, db)


session_router = APIRouter(prefix="/sessions", tags=["sessions"])


@session_router.get("", response_model=list[CouncilSessionSummary])
async def list_all_sessions(db: AsyncSession = Depends(get_db)):
    r = await db.execute(
        select(CouncilSession)
        .options(selectinload(CouncilSession.project))
        .order_by(CouncilSession.updated_at.desc())
    )
    out: list[CouncilSessionSummary] = []
    for s in r.scalars().unique().all():
        out.append(
            CouncilSessionSummary(
                id=s.id,
                project_id=s.project_id,
                project_name=s.project.name if s.project else "",
                title=s.title,
                status=s.status,
                current_round=s.current_round,
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
        )
    return out


@session_router.post("", response_model=CouncilSessionOut)
async def create_session_global(body: SessionCreate, db: AsyncSession = Depends(get_db)):
    if not body.project_id:
        raise HTTPException(400, "project_id is required")
    q = await db.execute(select(Project).where(Project.id == body.project_id))
    if not q.scalar_one_or_none():
        raise HTTPException(404, "project not found")
    s = CouncilSession(
        project_id=body.project_id,
        title=body.title,
        original_user_task=body.build_task() or body.original_user_task,
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return await get_session(s.id, db)


async def get_session(session_id: str, db: AsyncSession) -> CouncilSessionOut:
    r = await db.execute(
        select(CouncilSession)
        .where(CouncilSession.id == session_id)
        .options(
            selectinload(CouncilSession.agent_responses),
            selectinload(CouncilSession.consensus),
            selectinload(CouncilSession.final_prompts),
            selectinload(CouncilSession.implementation),
            selectinload(CouncilSession.project),
        )
    )
    s = r.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "session not found")
    return CouncilSessionOut.model_validate(s)


@session_router.get("/{session_id}", response_model=CouncilSessionOut)
async def read_session(session_id: str, db: AsyncSession = Depends(get_db)):
    return await get_session(session_id, db)


@session_router.get("/{session_id}/export.md")
async def export_md(session_id: str, db: AsyncSession = Depends(get_db)):
    md = await session_to_markdown(db, session_id)
    if not md:
        raise HTTPException(404)
    return {"markdown": md}


@session_router.post("/{session_id}/export-markdown")
async def export_markdown_post(session_id: str, db: AsyncSession = Depends(get_db)):
    md = await session_to_markdown(db, session_id)
    if not md:
        raise HTTPException(404)
    return {"markdown": md}


# --- Clean REST surface expected by the frontend --------------------------


@session_router.post("/{session_id}/start", response_model=CouncilSessionOut)
async def session_start(session_id: str, db: AsyncSession = Depends(get_db)):
    from app.coordinator.coordinator import Coordinator

    coord = Coordinator(db, _broadcast)
    try:
        await coord.start_task(session_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    await db.commit()
    return await get_session(session_id, db)


@session_router.post("/{session_id}/run-next-round", response_model=CouncilSessionOut)
async def session_run_next(session_id: str, db: AsyncSession = Depends(get_db)):
    from app.coordinator.coordinator import Coordinator

    coord = Coordinator(db, _broadcast)
    try:
        await coord.advance_phase(session_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    await db.commit()
    return await get_session(session_id, db)


@session_router.post("/{session_id}/approve", response_model=CouncilSessionOut)
async def session_approve_consensus(session_id: str, db: AsyncSession = Depends(get_db)):
    orch = CouncilOrchestrator(db, _broadcast)
    try:
        await orch.approve_consensus(session_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    await db.commit()
    return await get_session(session_id, db)


@session_router.get("/{session_id}/responses", response_model=list[AgentResponseOut])
async def session_responses(session_id: str, db: AsyncSession = Depends(get_db)):
    r = await db.execute(
        select(AgentResponse)
        .where(AgentResponse.session_id == session_id)
        .order_by(AgentResponse.created_at)
    )
    return list(r.scalars().all())


@session_router.get("/{session_id}/consensus", response_model=ConsensusOut)
async def session_consensus(session_id: str, db: AsyncSession = Depends(get_db)):
    r = await db.execute(
        select(Consensus).where(Consensus.session_id == session_id)
    )
    c = r.scalar_one_or_none()
    if not c:
        raise HTTPException(404, "no consensus yet")
    return c


@session_router.post("/{session_id}/generate-consensus", response_model=CouncilSessionOut)
async def session_generate_consensus(session_id: str, db: AsyncSession = Depends(get_db)):
    orch = CouncilOrchestrator(db, _broadcast)
    await orch.build_consensus(session_id)
    await db.commit()
    return await get_session(session_id, db)


@session_router.get("/{session_id}/final-prompt", response_model=FinalPromptOut)
async def session_final_prompt(session_id: str, db: AsyncSession = Depends(get_db)):
    r = await db.execute(
        select(FinalPrompt)
        .where(FinalPrompt.session_id == session_id)
        .order_by(FinalPrompt.version.desc())
        .limit(1)
    )
    fp = r.scalar_one_or_none()
    if not fp:
        raise HTTPException(404, "no final prompt yet")
    return fp


@session_router.post("/{session_id}/generate-final-prompt", response_model=CouncilSessionOut)
async def session_generate_final_prompt(
    session_id: str, db: AsyncSession = Depends(get_db)
):
    orch = CouncilOrchestrator(db, _broadcast)
    try:
        await orch.regenerate_final_prompt(session_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    await db.commit()
    return await get_session(session_id, db)


@session_router.post("/{session_id}/review-final-prompt", response_model=CouncilSessionOut)
async def session_review_final_prompt(session_id: str, db: AsyncSession = Depends(get_db)):
    orch = CouncilOrchestrator(db, _broadcast)
    try:
        await orch.run_prompt_review(session_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    await db.commit()
    return await get_session(session_id, db)


@session_router.post("/{session_id}/approve-final-prompt", response_model=CouncilSessionOut)
async def session_approve_final_prompt(session_id: str, db: AsyncSession = Depends(get_db)):
    orch = CouncilOrchestrator(db, _broadcast)
    try:
        await orch.approve_final_prompt(session_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    await db.commit()
    return await get_session(session_id, db)


@session_router.post("/{session_id}/submit-to-compose2", response_model=CouncilSessionOut)
async def session_submit_compose2(session_id: str, db: AsyncSession = Depends(get_db)):
    orch = CouncilOrchestrator(db, _broadcast)
    try:
        await orch.submit_to_compose2(session_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    await db.commit()
    return await get_session(session_id, db)


@session_router.post("/{session_id}/mark-implemented", response_model=CouncilSessionOut)
async def session_mark_implemented(
    session_id: str,
    body: ImplementationManualUpdate,
    db: AsyncSession = Depends(get_db),
):
    orch = CouncilOrchestrator(db, _broadcast)
    await orch.mark_implemented(session_id, body.changed_files, body.summary)
    await db.commit()
    return await get_session(session_id, db)


@session_router.post("/{session_id}/review-implementation", response_model=CouncilSessionOut)
async def session_review_implementation(session_id: str, db: AsyncSession = Depends(get_db)):
    orch = CouncilOrchestrator(db, _broadcast)
    await orch.run_code_review(session_id)
    await db.commit()
    return await get_session(session_id, db)


@session_router.post("/{session_id}/actions/normalize")
async def action_normalize(session_id: str, db: AsyncSession = Depends(get_db)):
    orch = CouncilOrchestrator(db, _broadcast)
    await orch.normalize_task(session_id)
    await db.commit()
    return await get_session(session_id, db)


@session_router.post("/{session_id}/actions/run-round-1")
async def action_r1(session_id: str, db: AsyncSession = Depends(get_db)):
    orch = CouncilOrchestrator(db, _broadcast)
    await orch.run_initial_assessment(session_id)
    await db.commit()
    return await get_session(session_id, db)


@session_router.post("/{session_id}/actions/run-round-2")
async def action_r2(session_id: str, db: AsyncSession = Depends(get_db)):
    orch = CouncilOrchestrator(db, _broadcast)
    await orch.run_cross_review(session_id)
    await db.commit()
    return await get_session(session_id, db)


@session_router.post("/{session_id}/actions/build-consensus")
async def action_consensus(session_id: str, db: AsyncSession = Depends(get_db)):
    orch = CouncilOrchestrator(db, _broadcast)
    await orch.build_consensus(session_id)
    await db.commit()
    return await get_session(session_id, db)


@session_router.post("/{session_id}/actions/consensus-approval")
async def action_consensus_appr(session_id: str, db: AsyncSession = Depends(get_db)):
    orch = CouncilOrchestrator(db, _broadcast)
    await orch.run_consensus_approval(session_id)
    await db.commit()
    return await get_session(session_id, db)


@session_router.post("/{session_id}/actions/build-final-prompt")
async def action_fp(session_id: str, db: AsyncSession = Depends(get_db)):
    orch = CouncilOrchestrator(db, _broadcast)
    try:
        await orch.build_final_prompt(session_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    await db.commit()
    return await get_session(session_id, db)


@session_router.post("/{session_id}/actions/prompt-review")
async def action_pr(session_id: str, db: AsyncSession = Depends(get_db)):
    orch = CouncilOrchestrator(db, _broadcast)
    await orch.run_prompt_review(session_id)
    await db.commit()
    return await get_session(session_id, db)


@session_router.post("/{session_id}/actions/run-all-to-prompt")
async def action_all(session_id: str, db: AsyncSession = Depends(get_db)):
    orch = CouncilOrchestrator(db, _broadcast)
    await orch.run_through_prompt_ready(session_id)
    await db.commit()
    return await get_session(session_id, db)


@session_router.post("/{session_id}/actions/submit-compose2")
async def action_submit(session_id: str, db: AsyncSession = Depends(get_db)):
    orch = CouncilOrchestrator(db, _broadcast)
    try:
        await orch.submit_to_compose2(session_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    await db.commit()
    return await get_session(session_id, db)


@session_router.post("/{session_id}/actions/mark-implemented")
async def action_impl(
    session_id: str, body: ImplementationManualUpdate, db: AsyncSession = Depends(get_db)
):
    orch = CouncilOrchestrator(db, _broadcast)
    await orch.mark_implemented(session_id, body.changed_files, body.summary)
    await db.commit()
    return await get_session(session_id, db)


@session_router.post("/{session_id}/actions/code-review")
async def action_cr(session_id: str, db: AsyncSession = Depends(get_db)):
    orch = CouncilOrchestrator(db, _broadcast)
    await orch.run_code_review(session_id)
    await db.commit()
    return await get_session(session_id, db)


@session_router.get("/{session_id}/improvement-prompt")
async def improvement_prompt(session_id: str, db: AsyncSession = Depends(get_db)):
    s = await get_session(session_id, db)
    if not s.implementation or not s.implementation.review_result:
        raise HTTPException(400, "No code review available yet.")
    latest = max(s.final_prompts, key=lambda fp: fp.version) if s.final_prompts else None
    base = latest.prompt_text if latest else ""
    body = (
        "# Follow-up coding prompt\n\n"
        "Use this prompt to address issues raised in the council code review.\n\n"
        "## Prior final prompt (reference)\n\n"
        f"{base}\n\n"
        "## Council code review findings\n\n"
        f"{s.implementation.review_result}\n\n"
        "## Instructions\n"
        "- Fix blocking issues first.\n"
        "- Add/adjust tests called out in the review.\n"
        "- Keep changes minimal and aligned with the original task.\n"
    )
    markdown = body
    return {"markdown": markdown}


async def websocket_session(ws: WebSocket, session_id: str) -> None:
    await ws.accept()
    if ws_manager:
        await ws_manager.connect(session_id, ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if ws_manager:
            ws_manager.disconnect(session_id, ws)
