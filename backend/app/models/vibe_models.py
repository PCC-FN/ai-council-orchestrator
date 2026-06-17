"""Vibe Coding data model — extends AI Orchestra with browser-driven coding jobs."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _empty_json_dict() -> dict:
    return {}


def _empty_json_list() -> list:
    return []


class WorkerProject(Base):
    """Project discovered on a remote worker within allowed PROJECT_ROOTS."""

    __tablename__ = "worker_projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    worker_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("worker_registrations.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    local_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    repository_url: Mapped[str] = mapped_column(String(1024), default="")
    default_branch: Mapped[str] = mapped_column(String(128), default="main")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_used_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC)
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        onupdate=lambda: dt.datetime.now(dt.UTC),
    )


class CodingJob(Base):
    """Browser-initiated vibe coding task."""

    __tablename__ = "coding_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    orchestra_task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    user_id: Mapped[str] = mapped_column(String(64), default="default")
    worker_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("worker_registrations.id"), nullable=True
    )
    project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("worker_projects.id"), nullable=True
    )
    mode: Mapped[str] = mapped_column(String(32), default="direct")
    title: Mapped[str] = mapped_column(String(512), default="")
    original_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    optimized_prompt: Mapped[str] = mapped_column(Text, default="")
    implementation_plan: Mapped[dict | list] = mapped_column(JSON, default=_empty_json_dict)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    branch_name: Mapped[str] = mapped_column(String(256), default="")
    current_step: Mapped[str] = mapped_column(String(256), default="")
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    adapter_type: Mapped[str] = mapped_column(String(64), default="mock")
    review_rounds: Mapped[int] = mapped_column(Integer, default=0)
    max_review_rounds: Mapped[int] = mapped_column(Integer, default=3)
    started_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completion_report: Mapped[dict | list] = mapped_column(JSON, default=_empty_json_dict)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC)
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        onupdate=lambda: dt.datetime.now(dt.UTC),
    )

    sessions: Mapped[list[CodingSession]] = relationship(
        "CodingSession", back_populates="job", cascade="all, delete-orphan"
    )
    messages: Mapped[list[ChatMessage]] = relationship(
        "ChatMessage", back_populates="job", cascade="all, delete-orphan"
    )
    events: Mapped[list[VibeJobEvent]] = relationship(
        "VibeJobEvent", back_populates="job", cascade="all, delete-orphan"
    )
    file_changes: Mapped[list[FileChange]] = relationship(
        "FileChange", back_populates="job", cascade="all, delete-orphan"
    )
    approvals: Mapped[list[Approval]] = relationship(
        "Approval", back_populates="job", cascade="all, delete-orphan"
    )


class CodingSession(Base):
    """Active coding agent session for a job."""

    __tablename__ = "coding_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("coding_jobs.id"), nullable=False
    )
    adapter_type: Mapped[str] = mapped_column(String(64), default="mock")
    external_session_id: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[str] = mapped_column(String(32), default="pending")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC)
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        onupdate=lambda: dt.datetime.now(dt.UTC),
    )

    job: Mapped[CodingJob] = relationship("CodingJob", back_populates="sessions")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("coding_jobs.id"), nullable=False
    )
    sender_type: Mapped[str] = mapped_column(String(32), nullable=False)
    sender_name: Mapped[str] = mapped_column(String(128), default="")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(String(64), default="text")
    metadata_json: Mapped[dict | list] = mapped_column(JSON, default=_empty_json_dict)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC)
    )

    job: Mapped[CodingJob] = relationship("CodingJob", back_populates="messages")


class VibeJobEvent(Base):
    """Persistent vibe coding event log."""

    __tablename__ = "vibe_job_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("coding_jobs.id"), nullable=False
    )
    worker_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict | list] = mapped_column(JSON, default=_empty_json_dict)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC)
    )

    job: Mapped[CodingJob] = relationship("CodingJob", back_populates="events")


class FileChange(Base):
    __tablename__ = "file_changes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("coding_jobs.id"), nullable=False
    )
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    change_type: Mapped[str] = mapped_column(String(32), default="modified")
    diff: Mapped[str] = mapped_column(Text, default="")
    content_after: Mapped[str] = mapped_column(Text, default="")
    is_approved: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC)
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        onupdate=lambda: dt.datetime.now(dt.UTC),
    )

    job: Mapped[CodingJob] = relationship("CodingJob", back_populates="file_changes")


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("coding_jobs.id"), nullable=False
    )
    approval_type: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="pending")
    requested_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC)
    )
    answered_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    answered_by: Mapped[str | None] = mapped_column(String(64), nullable=True)

    job: Mapped[CodingJob] = relationship("CodingJob", back_populates="approvals")
