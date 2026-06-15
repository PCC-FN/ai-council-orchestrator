from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./council.db"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    openai_api_key: str = ""
    anthropic_api_key: str = ""
    compose2_api_key: str = ""

    default_openai_model: str = "gpt-4o-mini"
    default_anthropic_model: str = "claude-3-5-sonnet-20241022"

    compose2_mode: Literal["manual", "api"] = "manual"
    compose2_base_url: str = ""

    max_project_file_bytes: int = 512_000

    use_mock_providers: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
