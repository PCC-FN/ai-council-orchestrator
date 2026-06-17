"""Versioned Vibe Coding WebSocket event protocol (v1)."""

VIBE_PROTOCOL_VERSION = 1

# Worker lifecycle
EVENT_WORKER_CONNECTED = "worker.connected"
EVENT_WORKER_DISCONNECTED = "worker.disconnected"
EVENT_WORKER_HEARTBEAT = "worker.heartbeat"

# Job lifecycle
EVENT_JOB_CREATED = "job.created"
EVENT_JOB_QUEUED = "job.queued"
EVENT_JOB_STARTED = "job.started"
EVENT_JOB_PAUSED = "job.paused"
EVENT_JOB_RESUMED = "job.resumed"
EVENT_JOB_CANCELLED = "job.cancelled"
EVENT_JOB_FAILED = "job.failed"
EVENT_JOB_COMPLETED = "job.completed"

# Agent / Cursor
EVENT_AGENT_STARTED = "agent.started"
EVENT_AGENT_MESSAGE = "agent.message"
EVENT_AGENT_QUESTION = "agent.question"
EVENT_AGENT_OUTPUT = "agent.output"
EVENT_AGENT_ERROR = "agent.error"

# Files & Git
EVENT_FILE_CREATED = "file.created"
EVENT_FILE_CHANGED = "file.changed"
EVENT_FILE_DELETED = "file.deleted"
EVENT_GIT_DIFF_UPDATED = "git.diff.updated"

# Commands & tests
EVENT_COMMAND_STARTED = "command.started"
EVENT_COMMAND_OUTPUT = "command.output"
EVENT_COMMAND_COMPLETED = "command.completed"
EVENT_TEST_STARTED = "test.started"
EVENT_TEST_COMPLETED = "test.completed"

# Approvals
EVENT_APPROVAL_REQUIRED = "approval.required"
EVENT_APPROVAL_RECEIVED = "approval.received"

# Analysis
EVENT_ANALYSIS_STARTED = "analysis.started"
EVENT_PLAN_CREATED = "plan.created"

# Post-implementation review
EVENT_REVIEW_STARTED = "review.started"
EVENT_REVIEW_COMPLETED = "review.completed"
EVENT_CORRECTION_QUEUED = "correction.queued"

CODING_JOB_STATUSES = frozenset(
    {
        "draft",
        "analyzing",
        "awaiting_approval",
        "queued",
        "preparing",
        "running",
        "awaiting_user_input",
        "testing",
        "reviewing",
        "completed",
        "failed",
        "cancelled",
    }
)

CODING_MODES = frozenset({"direct", "ai_review", "orchestra", "autonomous"})

SENDER_TYPES = frozenset({"user", "orchestra", "agent", "worker", "cursor", "system"})
