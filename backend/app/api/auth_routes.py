from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import AuthService, CurrentUser, get_current_user, require_admin, require_developer
from app.database import get_db
from app.models.auth_models import ROLE_ADMIN, ROLE_DEVELOPER, ROLE_VIEWER

auth_router = APIRouter(prefix="/auth", tags=["auth"])


class UserOut(BaseModel):
    id: str
    username: str
    display_name: str
    role: str

    model_config = {"from_attributes": True}


class UserCreateIn(BaseModel):
    username: str
    display_name: str = ""
    role: str = Field(default=ROLE_DEVELOPER, pattern="^(admin|developer|viewer)$")


class UserCreateOut(BaseModel):
    user: UserOut
    token: str
    message: str = "Token nur einmal sichtbar — sicher speichern."


@auth_router.get("/me", response_model=UserOut)
async def auth_me(user: CurrentUser = Depends(get_current_user)):
    return UserOut(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
    )


@auth_router.get("/me/permissions")
async def auth_permissions(user: CurrentUser = Depends(get_current_user)):
    return {
        "role": user.role,
        "can_write": user.can_write,
        "can_view": user.can_view,
        "is_admin": user.is_admin,
        "is_authenticated": user.is_authenticated,
    }


@auth_router.get("/users", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db), _admin: CurrentUser = Depends(require_admin)):
    rows = await AuthService(db).list_users()
    return [UserOut.model_validate(u) for u in rows]


@auth_router.post("/users", response_model=UserCreateOut)
async def create_user(
    body: UserCreateIn,
    db: AsyncSession = Depends(get_db),
    _admin: CurrentUser = Depends(require_admin),
):
    if body.role not in {ROLE_ADMIN, ROLE_DEVELOPER, ROLE_VIEWER}:
        raise HTTPException(400, "invalid role")
    svc = AuthService(db)
    user, token = await svc.create_user(
        username=body.username,
        role=body.role,
        display_name=body.display_name,
    )
    await db.commit()
    return UserCreateOut(user=UserOut.model_validate(user), token=token)
