from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SettingKind = Literal["secret", "config"]


@dataclass(frozen=True)
class SettingDefinition:
    key: str
    label: str
    description: str
    kind: SettingKind
    env_var: str
    placeholder: str = ""


SECRET_KEYS: tuple[SettingDefinition, ...] = (
    SettingDefinition(
        key="openai_api_key",
        label="OpenAI",
        description="ChatGPT Architect & Prompt Engineer",
        kind="secret",
        env_var="OPENAI_API_KEY",
        placeholder="sk-…",
    ),
    SettingDefinition(
        key="anthropic_api_key",
        label="Anthropic",
        description="Claude Reviewer",
        kind="secret",
        env_var="ANTHROPIC_API_KEY",
        placeholder="sk-ant-…",
    ),
    SettingDefinition(
        key="compose2_api_key",
        label="Compose2",
        description="Compose2 Implementation (nur bei API-Modus)",
        kind="secret",
        env_var="COMPOSE2_API_KEY",
        placeholder="Bearer-Token",
    ),
    SettingDefinition(
        key="gemini_api_key",
        label="Google Gemini",
        description="Geplant — noch kein Provider aktiv",
        kind="secret",
        env_var="GEMINI_API_KEY",
        placeholder="AIza…",
    ),
    SettingDefinition(
        key="github_token",
        label="GitHub",
        description="Geplant — Pull-Request-Integration",
        kind="secret",
        env_var="GITHUB_TOKEN",
        placeholder="ghp_…",
    ),
)

CONFIG_KEYS: tuple[str, ...] = (
    "default_openai_model",
    "default_anthropic_model",
    "compose2_mode",
    "compose2_base_url",
    "use_mock_providers",
)

ALL_PERSISTED_KEYS: frozenset[str] = frozenset(
    [d.key for d in SECRET_KEYS] + list(CONFIG_KEYS)
)
