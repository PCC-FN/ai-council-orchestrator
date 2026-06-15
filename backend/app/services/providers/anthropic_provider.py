from __future__ import annotations

import re

from anthropic import AsyncAnthropic

from app.config import get_settings
from app.services.providers.base import BaseProvider, ProviderResult


def _parse_trailer(result: ProviderResult) -> ProviderResult:
    text = result.text
    m = re.search(r"APPROVAL:\s*(YES|NO)", text, re.I)
    if m:
        result.approval_status = "approved" if m.group(1).upper() == "YES" else "rejected"
    m2 = re.search(r"PROMPT_REVIEW:\s*(APPROVED|CHANGES_NEEDED)", text, re.I)
    if m2:
        result.approval_status = (
            "approved" if m2.group(1).upper() == "APPROVED" else "rejected"
        )
    return result


class AnthropicProvider(BaseProvider):
    name = "anthropic_claude"

    def __init__(self) -> None:
        s = get_settings()
        self._client = AsyncAnthropic(api_key=s.anthropic_api_key or "invalid")
        self._model = s.default_anthropic_model

    async def complete(self, system: str, user: str) -> ProviderResult:
        msg = await self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        parts: list[str] = []
        for block in msg.content:
            if hasattr(block, "text"):
                parts.append(block.text)
        text = "\n".join(parts).strip()
        return _parse_trailer(ProviderResult(text=text))
