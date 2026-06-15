from __future__ import annotations

from app.services.orchestrator import _approval_from_result  # noqa: PLC2701
from app.services.providers.base import ProviderResult


def test_approval_from_result_yes_no():
    r = ProviderResult(text="APPROVAL: YES\nok")
    assert _approval_from_result(r) == "approved"
    r2 = ProviderResult(text="APPROVAL: NO\nnope")
    assert _approval_from_result(r2) == "rejected"


def test_approval_prompt_review():
    r = ProviderResult(text="PROMPT_REVIEW: APPROVED\n")
    assert _approval_from_result(r) == "approved"
