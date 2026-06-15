from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class PluginEntry:
    kind: str  # agent | worker | provider | exporter | importer | tool
    name: str
    version: str = "1.0.0"
    description: str = ""
    factory: Callable[..., Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class PluginRegistry:
    """Central registry — new plugins register here without core changes."""

    def __init__(self) -> None:
        self._entries: dict[str, PluginEntry] = {}

    def register(self, entry: PluginEntry) -> None:
        key = f"{entry.kind}:{entry.name}"
        self._entries[key] = entry

    def get(self, kind: str, name: str) -> PluginEntry | None:
        return self._entries.get(f"{kind}:{name}")

    def list(self, kind: str | None = None) -> list[PluginEntry]:
        if kind is None:
            return list(self._entries.values())
        return [e for k, e in self._entries.items() if e.kind == kind]

    def create(self, kind: str, name: str, **kwargs: Any) -> Any:
        entry = self.get(kind, name)
        if not entry or not entry.factory:
            raise KeyError(f"No plugin factory: {kind}:{name}")
        return entry.factory(**kwargs)


plugin_registry = PluginRegistry()
