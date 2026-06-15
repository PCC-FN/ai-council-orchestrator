from __future__ import annotations

import os

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("USE_MOCK_PROVIDERS", "true")

from app.database import Base
from app.models import db_models  # noqa: F401
from app.models.db_models import CouncilSession, Project


@pytest.fixture
async def db_session(tmp_path):
    db_path = tmp_path / "test.db"
    url = f"sqlite+aiosqlite:///{db_path}"
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def sample_project(db_session: AsyncSession):
    p = Project(
        name="Demo",
        description="Example",
        repository_path="",
        coding_rules="Follow PEP8.",
        security_rules="No secrets in repo.",
    )
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    return p


@pytest.fixture
async def sample_session(db_session: AsyncSession, sample_project: Project):
    s = CouncilSession(
        project_id=sample_project.id,
        title="Add feature X",
        original_user_task="Implement feature X with tests.",
    )
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    return s
