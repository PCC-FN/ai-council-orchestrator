from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkerCapabilities:
    """Reported by each worker on registration / heartbeat."""

    worker_type: str  # cursor | claude_code | continue | terminal | ...
    cursor_available: bool = False
    git_available: bool = False
    node_available: bool = False
    python_available: bool = False
    docker_available: bool = False
    powershell_available: bool = False
    claude_code_available: bool = False
    continue_available: bool = False
    installed_versions: dict[str, str] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_type": self.worker_type,
            "cursor_available": self.cursor_available,
            "git_available": self.git_available,
            "node_available": self.node_available,
            "python_available": self.python_available,
            "docker_available": self.docker_available,
            "powershell_available": self.powershell_available,
            "claude_code_available": self.claude_code_available,
            "continue_available": self.continue_available,
            "installed_versions": self.installed_versions,
            "extra": self.extra,
        }


@dataclass
class WorkerStatus:
    worker_id: str
    state: str  # idle | busy | offline | error
    current_job_id: str | None = None
    message: str = ""


class BaseWorker(ABC):
    """Abstract worker interface — remote workers implement this protocol via HTTP/WS."""

    worker_type: str = "base"

    @abstractmethod
    async def execute_task(self, job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Run an assigned job and return result metadata."""

    @abstractmethod
    async def cancel_task(self, job_id: str) -> bool:
        """Attempt to cancel a running job."""

    @abstractmethod
    async def get_status(self) -> WorkerStatus:
        """Current worker state."""

    @abstractmethod
    async def heartbeat(self) -> dict[str, Any]:
        """Health ping — returns capabilities snapshot."""

    @abstractmethod
    def capabilities(self) -> WorkerCapabilities:
        """Static/dynamic capability declaration."""


def worker_interface_doc() -> dict[str, list[str]]:
    return {
        "methods": [
            "executeTask(job_id, payload) -> result",
            "cancelTask(job_id) -> bool",
            "getStatus() -> WorkerStatus",
            "heartbeat() -> dict",
            "capabilities() -> WorkerCapabilities",
        ],
        "protocol": [
            "POST /workers/register",
            "POST /workers/{id}/heartbeat",
            "GET  /workers/{id}/jobs/poll",
            "POST /workers/{id}/jobs/{job_id}/progress",
            "POST /workers/{id}/jobs/{job_id}/complete",
            "POST /workers/{id}/jobs/{job_id}/fail",
        ],
    }
