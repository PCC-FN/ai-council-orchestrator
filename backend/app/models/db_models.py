from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
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
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC)
    )

    sessions: Mapped[list[CouncilSession]] = relationship(
        "CouncilSession", back_populates="project", cascade="all, delete-orphan"
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
    )  # created, running, paused, consensus, prompt_ready, implementing, reviewing, completed, needs_revision
    current_round: Mapped[str] = mapped_column(String(64), default="pending")
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
