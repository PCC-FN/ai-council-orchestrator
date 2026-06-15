from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    repository_path: str = ""
    coding_rules: str = ""
    security_rules: str = ""


class ProjectOut(BaseModel):
    id: str
    name: str
    description: str
    repository_path: str
    coding_rules: str
    security_rules: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionCreate(BaseModel):
    title: str
    original_user_task: str


class FinalPromptOut(BaseModel):
    id: str
    session_id: str
    prompt_text: str
    version: int
    approved_by_chatgpt: bool
    approved_by_claude: bool
    approved_by_compose2: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentResponseOut(BaseModel):
    id: str
    session_id: str
    agent_name: str
    round_name: str
    content: str
    rating: int | None
    concerns: str
    approval_status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConsensusOut(BaseModel):
    id: str
    session_id: str
    summary: str
    agreed_solution: str
    rejected_alternatives: str
    risks: str
    implementation_plan: str
    test_plan: str
    open_questions: str
    approval_status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ImplementationResultOut(BaseModel):
    id: str
    session_id: str
    status: str
    changed_files: list[Any] | dict[str, Any]
    summary: str
    review_result: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CouncilSessionOut(BaseModel):
    id: str
    project_id: str
    title: str
    original_user_task: str
    normalized_task: str
    status: str
    current_round: str
    created_at: datetime
    updated_at: datetime
    agent_responses: list[AgentResponseOut] = Field(default_factory=list)
    consensus: ConsensusOut | None = None
    final_prompts: list[FinalPromptOut] = Field(default_factory=list)
    implementation: ImplementationResultOut | None = None

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def _sort_nested(self) -> CouncilSessionOut:
        self.agent_responses = sorted(self.agent_responses, key=lambda x: x.created_at)
        self.final_prompts = sorted(self.final_prompts, key=lambda x: (x.version, x.created_at))
        return self


class ImplementationManualUpdate(BaseModel):
    status: str = "implemented"
    changed_files: list[str] = []
    summary: str = ""
