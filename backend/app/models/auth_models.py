"""User accounts and role-based access for AI Orchestra."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

ROLE_ADMIN = "admin"
ROLE_DEVELOPER = "developer"
ROLE_VIEWER = "viewer"

ALL_ROLES = frozenset({ROLE_ADMIN, ROLE_DEVELOPER, ROLE_VIEWER})


def _uuid() -> str:
    return str(uuid.uuid4())


class OrchestraUser(Base):
    __tablename__ = "orchestra_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), default="")
    role: Mapped[str] = mapped_column(String(32), default=ROLE_DEVELOPER)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC)
    )
