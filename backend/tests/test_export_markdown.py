from __future__ import annotations

from app.services.export_markdown import session_to_markdown
from app.services.orchestrator import CouncilOrchestrator


async def test_markdown_export_contains_sections(db_session, sample_session):
    orch = CouncilOrchestrator(db_session, None)
    await orch.run_through_prompt_ready(sample_session.id)
    await db_session.commit()

    md = await session_to_markdown(db_session, sample_session.id)
    assert "Council Session Export" in md
    assert "Original task" in md
    assert "Consensus" in md
    assert "Final prompts" in md
