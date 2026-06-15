from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.settings_schemas import SettingsOut, SettingsUpdate
from app.services.settings_service import SettingsService

router = APIRouter(tags=["settings"])
_svc = SettingsService()


@router.get("/settings", response_model=SettingsOut)
async def get_settings(db: AsyncSession = Depends(get_db)):
    """Non-secret runtime info plus masked provider key status."""
    return await _svc.get_public(db)


@router.put("/settings", response_model=SettingsOut)
async def update_settings(body: SettingsUpdate, db: AsyncSession = Depends(get_db)):
    """Persist provider keys and runtime options (keys never returned in full)."""
    config = body.model_dump(
        include={
            "compose2_mode",
            "use_mock_providers",
            "default_openai_model",
            "default_anthropic_model",
            "compose2_base_url",
        },
        exclude_none=True,
    )
    secrets = body.model_dump(
        include={
            "openai_api_key",
            "anthropic_api_key",
            "compose2_api_key",
            "gemini_api_key",
            "github_token",
        },
        exclude_none=True,
    )
    return await _svc.update(db, config=config or None, secrets=secrets or None)
