from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    repository_path: Mapped[str] = mapped_column(String(1024), default="")
    coding_rules: Mapped[str] = mapped_column(Text, default="")
    security_rules: Mapped[str] = mapped_column(Text, default="")
    tech_stack: Mapped[str] = mapped_column(Text, default="")
    excluded_paths: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC)
    )

    sessions: Mapped[list[CouncilSession]] = relationship(
        "CouncilSession", back_populates="project", cascade="all, delete-orphan"
    )
    knowledge: Mapped[ProjectKnowledge | None] = relationship(
        "ProjectKnowledge",
        back_populates="project",
        uselist=False,
        cascade="all, delete-orphan",
    )


class CouncilSession(Base):
    __tablename__ = "council_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    original_user_task: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_task: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(
        String(64), default="created"
    )
    current_round: Mapped[str] = mapped_column(String(64), default="pending")
    # AI Orchestra 12-phase workflow (Coordinator tracks this separately too).
    current_phase: Mapped[str] = mapped_column(String(64), default="understand_problem")
    iteration_count: Mapped[int] = mapped_column(Integer, default=0)
    max_iterations: Mapped[int] = mapped_column(Integer, default=3)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC)
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        onupdate=lambda: dt.datetime.now(dt.UTC),
    )

    project: Mapped[Project] = relationship("Project", back_populates="sessions")
    agent_responses: Mapped[list[AgentResponse]] = relationship(
        "AgentResponse", back_populates="session", cascade="all, delete-orphan"
    )
    consensus: Mapped[Consensus | None] = relationship(
        "Consensus",
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan",
    )
    final_prompts: Mapped[list[FinalPrompt]] = relationship(
        "FinalPrompt", back_populates="session", cascade="all, delete-orphan"
    )
    implementation: Mapped[ImplementationResult | None] = relationship(
        "ImplementationResult",
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan",
    )
    phase_executions: Mapped[list[PhaseExecution]] = relationship(
        "PhaseExecution", back_populates="task", cascade="all, delete-orphan"
    )
    jobs: Mapped[list[OrchestraJob]] = relationship(
        "OrchestraJob", back_populates="task", cascade="all, delete-orphan"
    )


# Alias for the new product name (table name stays for migration compatibility).
OrchestraTask = CouncilSession


class AgentResponse(Base):
    __tablename__ = "agent_responses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("council_sessions.id"), nullable=False
    )
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False)
    round_name: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    concerns: Mapped[str] = mapped_column(Text, default="")
    approval_status: Mapped[str] = mapped_column(
        String(32), default="pending"
    )  # pending, approved, rejected
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC)
    )

    session: Mapped[CouncilSession] = relationship("CouncilSession", back_populates="agent_responses")


class Consensus(Base):
    __tablename__ = "consensus"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("council_sessions.id"), unique=True, nullable=False
    )
    summary: Mapped[str] = mapped_column(Text, default="")
    agreed_solution: Mapped[str] = mapped_column(Text, default="")
    rejected_alternatives: Mapped[str] = mapped_column(Text, default="")
    risks: Mapped[str] = mapped_column(Text, default="")
    implementation_plan: Mapped[str] = mapped_column(Text, default="")
    test_plan: Mapped[str] = mapped_column(Text, default="")
    open_questions: Mapped[str] = mapped_column(Text, default="")
    approval_status: Mapped[str] = mapped_column(String(32), default="pending")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC)
    )

    session: Mapped[CouncilSession] = relationship("CouncilSession", back_populates="consensus")


class FinalPrompt(Base):
    __tablename__ = "final_prompts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("council_sessions.id"), nullable=False
    )
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    approved_by_chatgpt: Mapped[bool] = mapped_column(default=False)
    approved_by_claude: Mapped[bool] = mapped_column(default=False)
    approved_by_compose2: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC)
    )

    session: Mapped[CouncilSession] = relationship("CouncilSession", back_populates="final_prompts")


def _empty_json_dict() -> dict:
    return {}


def _empty_json_list() -> list:
    return []


class ImplementationResult(Base):
    __tablename__ = "implementation_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("council_sessions.id"), unique=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(64), default="pending")  # pending, implemented, failed
    changed_files: Mapped[list | dict] = mapped_column(JSON, default=_empty_json_list)
    summary: Mapped[str] = mapped_column(Text, default="")
    review_result: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC)
    )

    session: Mapped[CouncilSession] = relationship(
        "CouncilSession", back_populates="implementation"
    )


class ProjectKnowledge(Base):
    """Persistent project knowledge injected into every agent/worker context."""

    __tablename__ = "project_knowledge"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), unique=True, nullable=False
    )
    architecture: Mapped[str] = mapped_column(Text, default="")
    design_patterns: Mapped[str] = mapped_column(Text, default="")
    frameworks: Mapped[str] = mapped_column(Text, default="")
    naming_conventions: Mapped[str] = mapped_column(Text, default="")
    code_style: Mapped[str] = mapped_column(Text, default="")
    adrs: Mapped[list | dict] = mapped_column(JSON, default=_empty_json_list)
    lessons_learned: Mapped[str] = mapped_column(Text, default="")
    key_decisions: Mapped[str] = mapped_column(Text, default="")
    known_issues: Mapped[str] = mapped_column(Text, default="")
    best_practices: Mapped[str] = mapped_column(Text, default="")
    prompt_history: Mapped[list | dict] = mapped_column(JSON, default=_empty_json_list)
    review_history: Mapped[list | dict] = mapped_column(JSON, default=_empty_json_list)
    file_overview: Mapped[str] = mapped_column(Text, default="")
    repo_structure: Mapped[str] = mapped_column(Text, default="")
    documentation: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        onupdate=lambda: dt.datetime.now(dt.UTC),
    )

    project: Mapped[Project] = relationship("Project", back_populates="knowledge")


class AgentDefinition(Base):
    """Configurable AI agent — provider, model, role, system prompt."""

    __tablename__ = "agent_definitions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), default="mock")
    model: Mapped[str] = mapped_column(String(128), default="")
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    role: Mapped[str] = mapped_column(String(128), default="")
    temperature: Mapped[float] = mapped_column(Float, default=0.7)
    priority: Mapped[int] = mapped_column(Integer, default=50)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC)
    )


class WorkerRegistration(Base):
    """Remote coding worker registered with AI Orchestra."""

    __tablename__ = "worker_registrations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    worker_type: Mapped[str] = mapped_column(String(64), default="generic")
    hostname: Mapped[str] = mapped_column(String(256), default="")
    status: Mapped[str] = mapped_column(String(32), default="idle")  # idle|busy|offline|error
    capabilities: Mapped[dict | list] = mapped_column(JSON, default=_empty_json_dict)
    current_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    last_heartbeat_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    registered_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC)
    )


class OrchestraJob(Base):
    """Implementation job dispatched to a worker."""

    __tablename__ = "orchestra_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("council_sessions.id"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    worker_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("worker_registrations.id"), nullable=True
    )
    job_type: Mapped[str] = mapped_column(String(64), default="implementation")
    branch: Mapped[str] = mapped_column(String(256), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    final_prompt: Mapped[str] = mapped_column(Text, default="")
    affected_files: Mapped[list | dict] = mapped_column(JSON, default=_empty_json_list)
    priority: Mapped[int] = mapped_column(Integer, default=50)
    required_capabilities: Mapped[list | dict] = mapped_column(JSON, default=_empty_json_list)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=3600)
    status: Mapped[str] = mapped_column(
        String(32), default="pending"
    )  # pending|assigned|running|completed|failed|cancelled
    progress_message: Mapped[str] = mapped_column(Text, default="")
    result: Mapped[dict | list] = mapped_column(JSON, default=_empty_json_dict)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC)
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        onupdate=lambda: dt.datetime.now(dt.UTC),
    )

    task: Mapped[CouncilSession] = relationship("CouncilSession", back_populates="jobs")
    worker: Mapped[WorkerRegistration | None] = relationship("WorkerRegistration")


class PhaseExecution(Base):
    """Audit record for each workflow phase on a task."""

    __tablename__ = "phase_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("council_sessions.id"), nullable=False
    )
    phase_key: Mapped[str] = mapped_column(String(64), nullable=False)
    phase_number: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(
        String(32), default="pending"
    )  # pending|running|completed|failed|skipped
    summary: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict | list] = mapped_column(JSON, default=_empty_json_dict)
    started_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    task: Mapped[CouncilSession] = relationship("CouncilSession", back_populates="phase_executions")


class OrchestraEvent(Base):
    """Persistent event log — all actions are reproducible and auditable."""

    __tablename__ = "orchestra_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    agent_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict | list] = mapped_column(JSON, default=_empty_json_dict)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC)
    )
