from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


# Columns added after the initial release. create_all() never ALTERs existing
# tables, so we add any missing columns by hand to keep old SQLite files working.
_ADDED_COLUMNS: dict[str, dict[str, str]] = {
    "projects": {
        "tech_stack": "TEXT DEFAULT ''",
        "excluded_paths": "TEXT DEFAULT ''",
    },
    "council_sessions": {
        "current_phase": "TEXT DEFAULT 'understand_problem'",
        "iteration_count": "INTEGER DEFAULT 0",
        "max_iterations": "INTEGER DEFAULT 3",
    },
}


async def _ensure_columns(conn) -> None:
    for table, columns in _ADDED_COLUMNS.items():
        rows = await conn.exec_driver_sql(f"PRAGMA table_info({table})")
        existing = {r[1] for r in rows.fetchall()}
        for name, ddl in columns.items():
            if name not in existing:
                await conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


async def init_db() -> None:
    from app.models import auth_models  # noqa: F401
    from app.models import db_models  # noqa: F401
    from app.models import vibe_models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _ensure_columns(conn)
