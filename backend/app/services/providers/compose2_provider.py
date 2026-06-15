from __future__ import annotations

import httpx

from app.config import get_settings
from app.services.providers.base import BaseProvider, ProviderResult


class Compose2Provider(BaseProvider):
    """
    Placeholder for a future Compose2 HTTP API.
    In `manual` mode, orchestrator skips remote calls and surfaces the prompt in the UI.
    """

    name = "compose2"

    def __init__(self) -> None:
        self._settings = get_settings()

    async def complete(self, system: str, user: str) -> ProviderResult:
        if self._settings.compose2_mode != "api" or not self._settings.compose2_base_url:
            return ProviderResult(
                text="COMPOSE2_MANUAL_MODE: No remote call executed. "
                "Review the final prompt in the UI and mark implementation when done.",
                rating=None,
                concerns="Manual mode",
                approval_status="approved",
            )
        headers = {}
        if self._settings.compose2_api_key:
            headers["Authorization"] = f"Bearer {self._settings.compose2_api_key}"
        async with httpx.AsyncClient(timeout=120.0) as client:
            # Contract is intentionally generic; adjust when an official API exists.
            r = await client.post(
                f"{self._settings.compose2_base_url.rstrip('/')}/v1/complete",
                json={"system": system, "user": user},
                headers=headers,
            )
            r.raise_for_status()
            data = r.json()
            text = data.get("text") or data.get("output") or str(data)
            return ProviderResult(text=str(text))
