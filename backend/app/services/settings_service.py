from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_env_settings, set_db_settings_overrides
from app.core.settings_keys import ALL_PERSISTED_KEYS, CONFIG_KEYS, SECRET_KEYS
from app.models.db_models import AppSetting


def _mask_secret(value: str) -> str | None:
    stripped = value.strip()
    if not stripped:
        return None
    if len(stripped) <= 4:
        return "••••"
    return f"…{stripped[-4:]}"


def _resolve(settings, db_values: dict[str, str], key: str) -> str:
    if key in db_values:
        return db_values[key]
    return str(getattr(settings, key, ""))


def _resolve_bool(settings, db_values: dict[str, str], key: str) -> bool:
    raw = _resolve(settings, db_values, key)
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class SettingsService:
    """Load and persist provider credentials plus runtime options."""

    async def load_db_values(self, db: AsyncSession) -> dict[str, str]:
        r = await db.execute(select(AppSetting))
        return {row.key: row.value for row in r.scalars().all()}

    async def sync_runtime_from_db(self, db: AsyncSession) -> None:
        db_values = await self.load_db_values(db)
        env = get_env_settings()
        overrides: dict[str, Any] = {}
        for key in ALL_PERSISTED_KEYS:
            if key in db_values:
                if key == "use_mock_providers":
                    overrides[key] = db_values[key].strip().lower() in {"1", "true", "yes", "on"}
                else:
                    overrides[key] = db_values[key]
        set_db_settings_overrides(overrides)

    def build_public_view(self, db_values: dict[str, str]) -> dict[str, Any]:
        env = get_env_settings()
        effective_fields: dict[str, Any] = {}
        for key in ALL_PERSISTED_KEYS:
            if key in db_values:
                if key == "use_mock_providers":
                    effective_fields[key] = _resolve_bool(env, db_values, key)
                else:
                    effective_fields[key] = db_values[key]
            else:
                effective_fields[key] = getattr(env, key)
        effective = env.model_copy(update=effective_fields)

        openai_ok = bool(effective.openai_api_key.strip())
        anthropic_ok = bool(effective.anthropic_api_key.strip())
        using_mock = effective.use_mock_providers or not (openai_ok and anthropic_ok)

        provider_keys = []
        for definition in SECRET_KEYS:
            value = getattr(effective, definition.key, "")
            configured = bool(str(value).strip())
            source = "none"
            if configured:
                source = "database" if definition.key in db_values else "env"
            provider_keys.append(
                {
                    "key": definition.key,
                    "label": definition.label,
                    "description": definition.description,
                    "env_var": definition.env_var,
                    "placeholder": definition.placeholder,
                    "configured": configured,
                    "source": source,
                    "masked_hint": _mask_secret(value),
                    "available": definition.key
                    in {"openai_api_key", "anthropic_api_key", "compose2_api_key"},
                }
            )

        return {
            "product": "AI Orchestra",
            "compose2_mode": effective.compose2_mode,
            "use_mock_providers": effective.use_mock_providers,
            "mock_active": using_mock,
            "default_openai_model": effective.default_openai_model,
            "default_anthropic_model": effective.default_anthropic_model,
            "compose2_base_url": effective.compose2_base_url,
            "openai_configured": openai_ok,
            "anthropic_configured": anthropic_ok,
            "compose2_configured": bool(effective.compose2_api_key.strip()),
            "provider_keys": provider_keys,
        }

    async def get_public(self, db: AsyncSession) -> dict[str, Any]:
        db_values = await self.load_db_values(db)
        return self.build_public_view(db_values)

    async def update(
        self,
        db: AsyncSession,
        *,
        config: dict[str, Any] | None = None,
        secrets: dict[str, str | None] | None = None,
    ) -> dict[str, Any]:
        db_values = await self.load_db_values(db)

        if config:
            for key, value in config.items():
                if key not in CONFIG_KEYS or value is None:
                    continue
                if key == "use_mock_providers":
                    stored = "true" if value else "false"
                else:
                    stored = str(value)
                await self._upsert(db, db_values, key, stored)

        if secrets:
            for key, value in secrets.items():
                if key not in {d.key for d in SECRET_KEYS}:
                    continue
                if value is None:
                    continue
                await self._upsert(db, db_values, key, value)

        await db.commit()
        await self.sync_runtime_from_db(db)
        return await self.get_public(db)

    async def _upsert(
        self,
        db: AsyncSession,
        db_values: dict[str, str],
        key: str,
        value: str,
    ) -> None:
        row = await db.get(AppSetting, key)
        if row is None:
            row = AppSetting(key=key, value=value)
            db.add(row)
        else:
            row.value = value
        db_values[key] = value
