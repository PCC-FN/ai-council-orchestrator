"""Tests for Vibe Coding core components."""

from __future__ import annotations

import pytest

from app.vibe.path_security import discover_projects, is_path_within_root, resolve_project_path
from app.vibe.secret_mask import mask_secrets


class TestSecretMasking:
    def test_masks_api_key(self):
        text = "OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz"
        assert "sk-********" in mask_secrets(text)
        assert "abcdefghijklmnopqrst" not in mask_secrets(text)

    def test_masks_password(self):
        assert "********" in mask_secrets("DATABASE_PASSWORD=supersecret123")

    def test_masks_bearer_token(self):
        result = mask_secrets("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9")
        assert "Bearer ********" in result


class TestPathSecurity:
    def test_blocks_directory_traversal(self):
        root = r"C:\Development"
        assert not is_path_within_root(r"C:\Development\..\Windows", root)

    def test_allows_nested_project(self):
        root = r"C:\Development"
        assert is_path_within_root(r"C:\Development\my-app\src", root)

    def test_resolve_project_path(self):
        root = r"C:\Development"
        resolved = resolve_project_path(r"C:\Development\app", [root])
        assert resolved is not None
        assert resolve_project_path(r"C:\Other\app", [root]) is None


@pytest.mark.asyncio
async def test_create_coding_job(db_session):
    from app.models.db_models import WorkerRegistration
    from app.models.vibe_models import WorkerProject
    from app.vibe.service import VibeCodingService

    w = WorkerRegistration(name="test-worker", worker_type="vibe", capabilities={})
    db_session.add(w)
    await db_session.flush()
    p = WorkerProject(worker_id=w.id, name="demo", local_path=r"C:\dev\demo")
    db_session.add(p)
    await db_session.flush()

    svc = VibeCodingService(db_session)
    job = await svc.create_job(
        worker_id=w.id,
        project_id=p.id,
        prompt="Add feature X",
        mode="direct",
    )
    assert job.status == "draft"
    assert job.original_prompt == "Add feature X"


@pytest.mark.asyncio
async def test_job_status_transitions(db_session):
    from app.models.db_models import WorkerRegistration
    from app.models.vibe_models import WorkerProject
    from app.vibe.service import VibeCodingService

    w = WorkerRegistration(name="w", worker_type="vibe", capabilities={})
    db_session.add(w)
    await db_session.flush()
    p = WorkerProject(worker_id=w.id, name="p", local_path=r"C:\dev\p")
    db_session.add(p)
    await db_session.flush()

    svc = VibeCodingService(db_session)
    job = await svc.create_job(worker_id=w.id, project_id=p.id, prompt="task", mode="ai_review")
    job = await svc.analyze_job(job.id)
    assert job.status == "awaiting_approval"
    job = await svc.approve_plan(job.id)
    assert job.status in ("queued", "preparing")


@pytest.mark.asyncio
async def test_worker_token_auth(db_session):
    from app.vibe.service import VibeCodingService

    svc = VibeCodingService(db_session)
    token, _ = svc.generate_worker_token()
    w = await svc.register_worker_with_token(name="auth-test", token=token)
    assert await svc.authenticate_worker_token(token) is not None
    assert await svc.authenticate_worker_token("wrong-token") is None
    assert w.name == "auth-test"
