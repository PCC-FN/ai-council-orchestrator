"""Authentication and authorization for Vibe Coding and admin APIs."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.auth_models import (
    ROLE_ADMIN,
    ROLE_DEVELOPER,
    ROLE_VIEWER,
    OrchestraUser,
)


@dataclass
class CurrentUser:
    id: str
    username: str
    display_name: str
    role: str
    is_authenticated: bool = True

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN

    @property
    def can_write(self) -> bool:
        return self.role in {ROLE_ADMIN, ROLE_DEVELOPER}

    @property
    def can_view(self) -> bool:
        return self.role in {ROLE_ADMIN, ROLE_DEVELOPER, ROLE_VIEWER}


ANONYMOUS_DEV = CurrentUser(
    id="anonymous",
    username="anonymous",
    display_name="Entwickler (lokal)",
    role=ROLE_DEVELOPER,
    is_authenticated=False,
)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def generate_token() -> str:
    return secrets.token_urlsafe(32)


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_token(self, token: str) -> OrchestraUser | None:
        token_hash = hash_token(token)
        r = await self.db.execute(
            select(OrchestraUser).where(
                OrchestraUser.token_hash == token_hash,
                OrchestraUser.is_active.is_(True),
            )
        )
        return r.scalar_one_or_none()

    async def create_user(
        self, *, username: str, role: str, display_name: str = ""
    ) -> tuple[OrchestraUser, str]:
        token = generate_token()
        user = OrchestraUser(
            username=username,
            display_name=display_name or username,
            role=role,
            token_hash=hash_token(token),
        )
        self.db.add(user)
        await self.db.flush()
        return user, token

    async def list_users(self) -> list[OrchestraUser]:
        r = await self.db.execute(select(OrchestraUser).order_by(OrchestraUser.created_at))
        return list(r.scalars().all())

    def to_current(self, user: OrchestraUser) -> CurrentUser:
        return CurrentUser(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            role=user.role,
        )


def _extract_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.headers.get("X-Orchestra-Token") or request.headers.get("X-API-Token")


async def get_current_user(
    request: Request, db: AsyncSession = Depends(get_db)
) -> CurrentUser:
    settings = get_settings()
    if not settings.auth_required:
        token = _extract_token(request)
        if token:
            user = await AuthService(db).get_by_token(token)
            if user:
                return AuthService(db).to_current(user)
        return ANONYMOUS_DEV

    token = _extract_token(request)
    if not token:
        raise HTTPException(401, "Authentifizierung erforderlich — Token fehlt")
    user = await AuthService(db).get_by_token(token)
    if not user:
        raise HTTPException(401, "Ungültiger Token")
    return AuthService(db).to_current(user)


def require_roles(*roles: str):
    async def _dep(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role == ROLE_ADMIN:
            return user
        if user.role not in roles:
            raise HTTPException(403, f"Rolle '{user.role}' nicht berechtigt")
        return user

    return _dep


require_viewer = require_roles(ROLE_VIEWER, ROLE_DEVELOPER, ROLE_ADMIN)
require_developer = require_roles(ROLE_DEVELOPER, ROLE_ADMIN)
require_admin = require_roles(ROLE_ADMIN)


async def assert_job_access(job_user_id: str, user: CurrentUser) -> None:
    if user.is_admin or user.role == ROLE_VIEWER:
        return
    if not user.is_authenticated:
        return
    if user.can_write and job_user_id in (user.id, "default", "anonymous"):
        return
    if user.is_authenticated:
        raise HTTPException(403, "Kein Zugriff auf diese Aufgabe")


async def assert_job_write(job_user_id: str, user: CurrentUser) -> None:
    if user.is_admin:
        return
    if not user.can_write:
        raise HTTPException(403, "Schreibzugriff verweigert")
    if user.is_authenticated and job_user_id not in (user.id, "default", "anonymous"):
        raise HTTPException(403, "Nur eigene Aufgaben bearbeitbar")
