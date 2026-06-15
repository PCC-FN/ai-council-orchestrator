from __future__ import annotations

import re

from openai import AsyncOpenAI

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


class OpenAIProvider(BaseProvider):
    name = "openai_chatgpt"

    def __init__(self) -> None:
        s = get_settings()
        self._client = AsyncOpenAI(api_key=s.openai_api_key or "invalid")
        self._model = s.default_openai_model

    async def complete(self, system: str, user: str) -> ProviderResult:
        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
        )
        text = resp.choices[0].message.content or ""
        return _parse_trailer(ProviderResult(text=text.strip()))
