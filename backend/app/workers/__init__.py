"""Worker abstractions — coding workers are NOT AI agents."""

from app.workers.base import WorkerCapabilities, WorkerStatus, worker_interface_doc

__all__ = ["WorkerCapabilities", "WorkerStatus", "worker_interface_doc"]
