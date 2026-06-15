from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ProviderResult:
    """Structured output from an LLM turn. Parsing is best-effort in orchestrator."""

    text: str
    rating: int | None = None
    concerns: str = ""
    approval_status: str | None = None  # approved | rejected | None (not applicable)


class BaseProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def complete(self, system: str, user: str) -> ProviderResult:
        raise NotImplementedError
