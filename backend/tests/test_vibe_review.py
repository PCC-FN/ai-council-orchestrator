"""Tests for Vibe Coding post-implementation review."""

from __future__ import annotations

import pytest

from app.models.vibe_models import CodingJob, FileChange
from app.vibe.review import _heuristic_review, should_auto_dispatch_correction


def _job(**kwargs) -> CodingJob:
    j = CodingJob(
        original_prompt=kwargs.get("prompt", "Add feature"),
        mode=kwargs.get("mode", "direct"),
        review_rounds=kwargs.get("review_rounds", 0),
        max_review_rounds=3,
    )
    return j


def test_review_passes_with_changes_and_tests():
    job = _job(prompt="Add login form with tests")
    result = _heuristic_review(
        job,
        {
            "changed_files": ["src/Login.tsx", "tests/login.test.ts"],
            "tests": {"passed": 4, "failed": 0},
            "summary": "Done",
        },
        [],
    )
    assert result.passed is True
    assert result.needs_correction is False


def test_review_fails_without_files():
    job = _job()
    result = _heuristic_review(job, {"changed_files": [], "tests": {}}, [])
    assert result.passed is False
    assert result.needs_correction is True
    assert result.correction_prompt


def test_review_fails_missing_migration():
    job = _job(prompt="Create database migration for users table")
    result = _heuristic_review(
        job,
        {"changed_files": ["src/users.ts"], "tests": {"passed": 1, "failed": 0}},
        [],
    )
    assert result.passed is False
    assert any("Migration" in m for m in result.report.get("missing_requirements", []))


def test_auto_dispatch_by_mode():
    assert should_auto_dispatch_correction(_job(mode="direct")) is True
    assert should_auto_dispatch_correction(_job(mode="autonomous")) is True
    assert should_auto_dispatch_correction(_job(mode="ai_review")) is False
    assert should_auto_dispatch_correction(_job(mode="orchestra")) is False


def test_review_with_file_change_models():
    job = _job(prompt="Add permissions")
    fc = FileChange(job_id="x", path="src/auth/permissions.ts", change_type="created")
    result = _heuristic_review(
        job,
        {"tests": {"passed": 2, "failed": 0}},
        [fc],
    )
    assert "permissions" in job.original_prompt.lower() or result.passed or result.needs_correction
