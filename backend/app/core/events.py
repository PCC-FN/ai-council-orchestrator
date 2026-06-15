from __future__ import annotations

# Persistent event types emitted across AI Orchestra.
# Stored in orchestra_events and broadcast via WebSocket where applicable.

EVENT_AGENT_STARTED = "agent_started"
EVENT_AGENT_FINISHED = "agent_finished"
EVENT_AGENT_FAILED = "agent_failed"

EVENT_WORKER_REGISTERED = "worker_registered"
EVENT_WORKER_HEARTBEAT = "worker_heartbeat"
EVENT_WORKER_OFFLINE = "worker_offline"

EVENT_JOB_CREATED = "job_created"
EVENT_JOB_ASSIGNED = "job_assigned"
EVENT_JOB_STARTED = "job_started"
EVENT_JOB_PROGRESS = "job_progress"
EVENT_JOB_COMPLETED = "job_completed"
EVENT_JOB_FAILED = "job_failed"
EVENT_JOB_CANCELLED = "job_cancelled"

EVENT_PHASE_STARTED = "phase_started"
EVENT_PHASE_COMPLETED = "phase_completed"
EVENT_PHASE_FAILED = "phase_failed"

EVENT_TASK_STARTED = "task_started"
EVENT_TASK_COMPLETED = "task_completed"

EVENT_CONSENSUS_CREATED = "consensus_created"
EVENT_PROMPT_CREATED = "prompt_created"
EVENT_PROMPT_APPROVED = "prompt_approved"

EVENT_REVIEW_PASSED = "review_passed"
EVENT_REVIEW_FAILED = "review_failed"

EVENT_COMMIT_CREATED = "commit_created"
EVENT_PULL_REQUEST_CREATED = "pull_request_created"

# Legacy session events (still emitted for backward-compatible UIs)
LEGACY_SESSION_EVENTS = frozenset(
    {
        "session_started",
        "round_started",
        "normalized",
        "round_complete",
        "consensus_ready",
        "consensus_created",
        "consensus_approved",
        "final_prompt_created",
        "prompt_review_done",
        "prompt_approved",
        "submitted_to_compose2",
        "implemented",
        "implementation_reviewed",
        "code_review_done",
    }
)
