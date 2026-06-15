from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ProviderKeyOut(BaseModel):
    key: str
    label: str
    description: str
    env_var: str
    placeholder: str = ""
    configured: bool
    source: Literal["env", "database", "none"]
    masked_hint: str | None = None
    available: bool = True


class SettingsOut(BaseModel):
    product: str = "AI Orchestra"
    compose2_mode: Literal["manual", "api"]
    use_mock_providers: bool
    mock_active: bool
    default_openai_model: str
    default_anthropic_model: str
    compose2_base_url: str
    openai_configured: bool
    anthropic_configured: bool
    compose2_configured: bool
    provider_keys: list[ProviderKeyOut]


class SettingsUpdate(BaseModel):
    """Partial update — omit fields to leave unchanged; empty string clears secrets."""

    compose2_mode: Literal["manual", "api"] | None = None
    use_mock_providers: bool | None = None
    default_openai_model: str | None = None
    default_anthropic_model: str | None = None
    compose2_base_url: str | None = None
    openai_api_key: str | None = Field(default=None, description="Empty string removes stored key")
    anthropic_api_key: str | None = None
    compose2_api_key: str | None = None
    gemini_api_key: str | None = None
    github_token: str | None = None
