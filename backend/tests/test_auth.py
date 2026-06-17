"""Tests for auth roles and permissions."""

from __future__ import annotations

from fastapi import HTTPException
import pytest

from app.auth.service import (
    ANONYMOUS_DEV,
    AuthService,
    assert_job_access,
    assert_job_write,
    should_auto_dispatch_correction,
)
from app.models.auth_models import ROLE_DEVELOPER, ROLE_VIEWER


def test_anonymous_dev_can_write_locally():
    assert ANONYMOUS_DEV.can_write is True


@pytest.mark.asyncio
async def test_create_user_and_authenticate(db_session):
    svc = AuthService(db_session)
    user, token = await svc.create_user(username="dev1", role=ROLE_DEVELOPER)
    await db_session.flush()
    found = await svc.get_by_token(token)
    assert found is not None
    assert found.username == "dev1"


@pytest.mark.asyncio
async def test_viewer_cannot_write(db_session):
    from app.auth.service import CurrentUser

    viewer = CurrentUser(id="v1", username="viewer", display_name="V", role=ROLE_VIEWER)
    with pytest.raises(HTTPException):
        await assert_job_write("other-user", viewer)


@pytest.mark.asyncio
async def test_developer_job_access(db_session):
    from app.auth.service import CurrentUser

    dev = CurrentUser(id="d1", username="dev", display_name="D", role=ROLE_DEVELOPER, is_authenticated=True)
    await assert_job_access("d1", dev)
    with pytest.raises(HTTPException):
        await assert_job_access("other", dev)


def test_auto_dispatch_modes():
    from app.models.vibe_models import CodingJob

    j = CodingJob(original_prompt="x", mode="orchestra")
    assert should_auto_dispatch_correction(j) is False
    j.mode = "direct"
    assert should_auto_dispatch_correction(j) is True
