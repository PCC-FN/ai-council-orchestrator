from __future__ import annotations

from app.config import get_settings
from app.services.providers.anthropic_provider import AnthropicProvider
from app.services.providers.base import BaseProvider
from app.services.providers.compose2_provider import Compose2Provider
from app.services.providers.mock_provider import MockProvider
from app.services.providers.openai_provider import OpenAIProvider

AGENT_CHATGPT = "chatgpt_architect"
AGENT_CLAUDE = "claude_reviewer"
AGENT_COMPOSE2 = "compose2_implementation"


def build_providers() -> dict[str, BaseProvider]:
    s = get_settings()
    if s.use_mock_providers:
        mock = MockProvider()
        return {
            AGENT_CHATGPT: mock,
            AGENT_CLAUDE: mock,
            AGENT_COMPOSE2: mock,
        }
    chat = (
        OpenAIProvider()
        if s.openai_api_key.strip()
        else MockProvider()
    )
    claude = (
        AnthropicProvider()
        if s.anthropic_api_key.strip()
        else MockProvider()
    )
    compose = Compose2Provider()
    if s.compose2_mode == "api" and s.compose2_base_url.strip():
        pass  # use real HTTP provider
    elif not s.compose2_api_key.strip() and s.compose2_mode != "api":
        pass  # Compose2Provider already handles manual
    return {
        AGENT_CHATGPT: chat,
        AGENT_CLAUDE: claude,
        AGENT_COMPOSE2: compose,
    }
