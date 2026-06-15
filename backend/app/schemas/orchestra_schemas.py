from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# --- Agents ---


class AgentDefinitionOut(BaseModel):
    id: str
    key: str
    display_name: str
    provider: str
    model: str
    system_prompt: str
    role: str
    temperature: float
    priority: int
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentDefinitionCreate(BaseModel):
    key: str
    display_name: str
    provider: str = "mock"
    model: str = ""
    system_prompt: str = ""
    role: str = ""
    temperature: float = 0.7
    priority: int = 50
    active: bool = True


# --- Workers ---


class WorkerRegisterIn(BaseModel):
    name: str
    worker_type: str = "generic"
    hostname: str = ""
    capabilities: dict[str, Any] = Field(default_factory=dict)


class WorkerOut(BaseModel):
    id: str
    name: str
    worker_type: str
    hostname: str
    status: str
    capabilities: dict[str, Any] | list[Any]
    current_job_id: str | None
    last_heartbeat_at: datetime | None
    registered_at: datetime

    model_config = {"from_attributes": True}


class WorkerHeartbeatIn(BaseModel):
    status: str = "idle"
    capabilities: dict[str, Any] | None = None


# --- Jobs ---


class JobOut(BaseModel):
    id: str
    task_id: str
    project_id: str
    worker_id: str | None
    job_type: str
    branch: str
    description: str
    final_prompt: str
    affected_files: list[Any] | dict[str, Any]
    priority: int
    status: str
    progress_message: str
    result: dict[str, Any] | list[Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobProgressIn(BaseModel):
    message: str


class JobCompleteIn(BaseModel):
    summary: str = ""
    changed_files: list[str] = Field(default_factory=list)
    commit_hash: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)


class JobFailIn(BaseModel):
    error: str


# --- Events ---


class EventOut(BaseModel):
    id: str
    event_type: str
    task_id: str | None
    project_id: str | None
    worker_id: str | None
    job_id: str | None
    agent_key: str | None
    payload: dict[str, Any] | list[Any]
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Phases ---


class PhaseExecutionOut(BaseModel):
    id: str
    task_id: str
    phase_key: str
    phase_number: int
    status: str
    summary: str
    metadata_json: dict[str, Any] | list[Any]
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class PhaseDefinitionOut(BaseModel):
    key: str
    number: int
    label: str
    description: str


# --- Knowledge ---


class ProjectKnowledgeOut(BaseModel):
    id: str
    project_id: str
    architecture: str
    design_patterns: str
    frameworks: str
    naming_conventions: str
    code_style: str
    adrs: list[Any] | dict[str, Any]
    lessons_learned: str
    key_decisions: str
    known_issues: str
    best_practices: str
    prompt_history: list[Any] | dict[str, Any]
    review_history: list[Any] | dict[str, Any]
    file_overview: str
    repo_structure: str
    documentation: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectKnowledgeUpdate(BaseModel):
    architecture: str | None = None
    design_patterns: str | None = None
    frameworks: str | None = None
    naming_conventions: str | None = None
    code_style: str | None = None
    lessons_learned: str | None = None
    key_decisions: str | None = None
    known_issues: str | None = None
    best_practices: str | None = None
    documentation: str | None = None


# --- Dashboard ---


class OrchestraDashboardOut(BaseModel):
    product: str = "AI Orchestra"
    active_tasks: int
    completed_tasks: int
    active_workers: int
    pending_jobs: int
    running_jobs: int
    recent_events: list[EventOut]
    agents: list[AgentDefinitionOut]
    workers: list[WorkerOut]


# --- Task (Orchestra naming) ---


class TaskCreate(BaseModel):
    project_id: str
    title: str
    feature_description: str
    affected_files: str = ""
    desired_outcome: str = ""
    constraints: str = ""

    def build_task(self) -> str:
        parts: list[str] = [self.feature_description.strip()]
        if self.affected_files.strip():
            parts.append(f"## Betroffene Dateien\n{self.affected_files.strip()}")
        if self.desired_outcome.strip():
            parts.append(f"## Gewünschtes Ergebnis\n{self.desired_outcome.strip()}")
        if self.constraints.strip():
            parts.append(f"## Einschränkungen\n{self.constraints.strip()}")
        return "\n\n".join(p for p in parts if p)
