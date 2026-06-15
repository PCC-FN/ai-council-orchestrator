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
    tech_stack: str = ""
    excluded_paths: str = ""


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    repository_path: str | None = None
    coding_rules: str | None = None
    security_rules: str | None = None
    tech_stack: str | None = None
    excluded_paths: str | None = None


class ProjectOut(BaseModel):
    id: str
    name: str
    description: str
    repository_path: str
    coding_rules: str
    security_rules: str
    tech_stack: str = ""
    excluded_paths: str = ""
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionCreate(BaseModel):
    title: str
    original_user_task: str = ""
    project_id: str | None = None
    affected_files: str = ""
    desired_outcome: str = ""
    constraints: str = ""

    def build_task(self) -> str:
        """Compose the structured task text from optional fields."""
        parts: list[str] = []
        if self.original_user_task.strip():
            parts.append(self.original_user_task.strip())
        if self.affected_files.strip():
            parts.append(f"## Betroffene Dateien / Module\n{self.affected_files.strip()}")
        if self.desired_outcome.strip():
            parts.append(f"## Gewünschtes Ergebnis\n{self.desired_outcome.strip()}")
        if self.constraints.strip():
            parts.append(f"## Einschränkungen\n{self.constraints.strip()}")
        return "\n\n".join(parts).strip()


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
    current_phase: str = "understand_problem"
    iteration_count: int = 0
    max_iterations: int = 3
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


class CouncilSessionSummary(BaseModel):
    id: str
    project_id: str
    project_name: str = ""
    title: str
    status: str
    current_round: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
