from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WorkerProjectOut(BaseModel):
    id: str
    worker_id: str
    name: str
    local_path: str = Field(serialization_alias="localPath")
    repository_url: str = ""
    default_branch: str = "main"
    is_enabled: bool = True
    last_used_at: datetime | None = None

    model_config = {"from_attributes": True, "populate_by_name": True}


class VibeWorkerOut(BaseModel):
    id: str
    name: str
    hostname: str = ""
    status: str
    version: str = "1.0.0"
    operating_system: str = ""
    capabilities: dict[str, Any] = Field(default_factory=dict)
    last_heartbeat_at: datetime | None = None
    online: bool = False
    project_count: int = 0

    model_config = {"from_attributes": True}


class ChatMessageOut(BaseModel):
    id: str
    job_id: str
    sender_type: str
    sender_name: str
    content: str
    message_type: str = "text"
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class FileChangeOut(BaseModel):
    id: str
    job_id: str
    path: str
    change_type: str
    diff: str = ""
    content_after: str = ""
    is_approved: bool | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class VibeJobEventOut(BaseModel):
    id: str
    job_id: str
    worker_id: str | None = None
    session_id: str | None = None
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class CodingJobOut(BaseModel):
    id: str
    user_id: str = "default"
    worker_id: str | None = None
    project_id: str | None = None
    mode: str
    title: str
    original_prompt: str
    optimized_prompt: str = ""
    implementation_plan: dict[str, Any] = Field(default_factory=dict)
    status: str
    branch_name: str = ""
    current_step: str = ""
    progress_percent: int = 0
    adapter_type: str = "mock"
    orchestra_task_id: str | None = None
    review_rounds: int = 0
    max_review_rounds: int = 3
    started_at: datetime | None = None
    finished_at: datetime | None = None
    completion_report: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessageOut] = Field(default_factory=list)
    file_changes: list[FileChangeOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class CodingJobCreate(BaseModel):
    worker_id: str
    project_id: str
    prompt: str
    mode: str = "direct"
    title: str = ""
    adapter_type: str = "mock"


class CodingJobMessageIn(BaseModel):
    message: str


class CodingJobApproveIn(BaseModel):
    edited_plan: dict[str, Any] | None = None


class CodingJobRejectIn(BaseModel):
    reason: str = ""


class CodingJobCommitIn(BaseModel):
    message: str = "orchestra: implement changes"


class CodingJobPushIn(BaseModel):
    allow_dangerous: bool = False


class WorkerTokenOut(BaseModel):
    worker_id: str
    token: str
    message: str = "Token nur einmal sichtbar — sicher speichern."


class WorkerRegisterVibeIn(BaseModel):
    name: str
    token: str
    hostname: str = ""
    operating_system: str = ""
    version: str = "1.0.0"
    capabilities: dict[str, Any] = Field(default_factory=dict)
    projects: list[dict[str, str]] = Field(default_factory=list)
