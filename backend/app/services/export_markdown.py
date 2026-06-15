from __future__ import annotations

from collections import defaultdict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.db_models import AgentResponse, Consensus, CouncilSession, FinalPrompt


async def session_to_markdown(db: AsyncSession, session_id: str) -> str:
    q = await db.execute(
        select(CouncilSession)
        .where(CouncilSession.id == session_id)
        .options(
            selectinload(CouncilSession.agent_responses),
            selectinload(CouncilSession.consensus),
            selectinload(CouncilSession.final_prompts),
            selectinload(CouncilSession.implementation),
            selectinload(CouncilSession.project),
        )
    )
    sess = q.scalar_one_or_none()
    if not sess:
        return ""

    lines: list[str] = [
        f"# Council Session Export: {sess.title}",
        "",
        "## Metadata",
        f"- Session ID: `{sess.id}`",
        f"- Project: {sess.project.name if sess.project else 'n/a'}",
        f"- Status: {sess.status}",
        f"- Current round: {sess.current_round}",
        "",
        "## Original task",
        sess.original_user_task,
        "",
        "## Normalized task",
        sess.normalized_task or "_pending_",
        "",
    ]

    by_round: dict[str, list[AgentResponse]] = defaultdict(list)
    for ar in sorted(sess.agent_responses, key=lambda x: x.created_at):
        by_round[ar.round_name].append(ar)

    order = [
        "initial_assessment",
        "cross_review",
        "consensus_approval",
        "prompt_review",
        "code_review",
    ]
    for rnd in order:
        if rnd not in by_round:
            continue
        lines.append(f"## Agent responses — {rnd}")
        lines.append("")
        for ar in by_round[rnd]:
            lines.append(f"### {ar.agent_name}")
            lines.append(f"- approval_status: {ar.approval_status}")
            if ar.rating is not None:
                lines.append(f"- rating: {ar.rating}")
            if ar.concerns:
                lines.append(f"- concerns: {ar.concerns}")
            lines.append("")
            lines.append(ar.content)
            lines.append("")
    # Any extra rounds
    for rnd, items in by_round.items():
        if rnd in order:
            continue
        lines.append(f"## Agent responses — {rnd}")
        for ar in items:
            lines.append(f"### {ar.agent_name}")
            lines.append(ar.content)
            lines.append("")

    if sess.consensus:
        c = sess.consensus
        lines.extend(
            [
                "## Consensus",
                f"**Approval status:** {c.approval_status}",
                "",
                "### Summary",
                c.summary or "",
                "",
                "### Agreed solution",
                c.agreed_solution or "",
                "",
                "### Rejected alternatives",
                c.rejected_alternatives or "",
                "",
                "### Risks",
                c.risks or "",
                "",
                "### Implementation plan",
                c.implementation_plan or "",
                "",
                "### Test plan",
                c.test_plan or "",
                "",
                "### Open questions",
                c.open_questions or "",
                "",
            ]
        )

    if sess.final_prompts:
        lines.append("## Final prompts (versions)")
        for fp in sorted(sess.final_prompts, key=lambda x: (x.version, x.created_at)):
            lines.append(f"### v{fp.version} — `{fp.id}`")
            lines.append(
                f"- Approved ChatGPT: {fp.approved_by_chatgpt} | "
                f"Claude: {fp.approved_by_claude} | Compose2: {fp.approved_by_compose2}"
            )
            lines.append("")
            lines.append(fp.prompt_text)
            lines.append("")

    if sess.implementation:
        imp = sess.implementation
        lines.extend(
            [
                "## Implementation result",
                f"- status: {imp.status}",
                f"- changed_files: {imp.changed_files}",
                "",
                "### Summary",
                imp.summary or "",
                "",
                "### Review result",
                imp.review_result or "",
                "",
            ]
        )

    return "\n".join(lines).strip() + "\n"


def render_final_prompt_for_download(prompt: FinalPrompt) -> str:
    return prompt.prompt_text
