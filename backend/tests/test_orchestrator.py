from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.db_models import CouncilSession
from app.services.orchestrator import CouncilOrchestrator


async def test_run_through_prompt_ready_mock(db_session, sample_session):
    orch = CouncilOrchestrator(db_session, broadcast=None)
    await orch.run_through_prompt_ready(sample_session.id)
    await db_session.commit()

    r2 = await db_session.execute(
        select(CouncilSession)
        .where(CouncilSession.id == sample_session.id)
        .options(
            selectinload(CouncilSession.agent_responses),
            selectinload(CouncilSession.consensus),
            selectinload(CouncilSession.final_prompts),
        )
    )
    s2 = r2.unique().scalar_one()
    assert s2.normalized_task
    assert len(s2.agent_responses) >= 3
    assert s2.consensus is not None
    assert s2.consensus.approval_status == "approved"
    assert s2.final_prompts
    fp = max(s2.final_prompts, key=lambda x: x.version)
    assert fp.prompt_text
    assert fp.approved_by_chatgpt and fp.approved_by_claude and fp.approved_by_compose2
