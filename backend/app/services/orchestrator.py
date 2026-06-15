from __future__ import annotations

import asyncio
import json
import re
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.db_models import (
    AgentResponse,
    Consensus,
    CouncilSession,
    FinalPrompt,
    ImplementationResult,
    Project,
)
from app.services import prompts as P
from app.services.project_context import build_context_snippet_sync
from app.services.providers.base import BaseProvider, ProviderResult
from app.services.providers.registry import (
    AGENT_CHATGPT,
    AGENT_CLAUDE,
    AGENT_COMPOSE2,
    build_providers,
)

ROUND_INITIAL = "initial_assessment"
ROUND_CROSS = "cross_review"
ROUND_CONSENSUS_APPROVAL = "consensus_approval"
ROUND_PROMPT_REVIEW = "prompt_review"
ROUND_CODE_REVIEW = "code_review"


def _consensus_to_markdown(c: Consensus) -> str:
    return "\n".join(
        [
            f"**Summary:** {c.summary}",
            f"**Agreed solution:** {c.agreed_solution}",
            f"**Risks:** {c.risks}",
            f"**Implementation plan:** {c.implementation_plan}",
            f"**Test plan:** {c.test_plan}",
            f"**Open questions:** {c.open_questions}",
        ]
    )


def _parse_consensus_json(text: str) -> dict[str, str]:
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return {k: str(v) for k, v in data.items()}
    except json.JSONDecodeError:
        pass
    return {
        "summary": text[:2000],
        "agreed_solution": text,
        "rejected_alternatives": "",
        "risks": "",
        "implementation_plan": "",
        "test_plan": "",
        "open_questions": "",
    }


def _approval_from_result(r: ProviderResult) -> str:
    if r.approval_status in {"approved", "rejected"}:
        return r.approval_status
    t = r.text.upper()
    if "APPROVAL: YES" in t or "PROMPT_REVIEW: APPROVED" in t:
        return "approved"
    if "APPROVAL: NO" in t or "PROMPT_REVIEW: CHANGES_NEEDED" in t:
        return "rejected"
    return "pending"


class CouncilOrchestrator:
    def __init__(self, db: AsyncSession, broadcast=None) -> None:
        self.db = db
        self.broadcast = broadcast
        self.providers: dict[str, BaseProvider] = build_providers()

    async def _emit(self, session_id: str, event: str, payload: dict) -> None:
        if self.broadcast:
            await self.broadcast(session_id, {"event": event, **payload})

    async def load_session(self, session_id: str) -> CouncilSession | None:
        q = await self.db.execute(
            select(CouncilSession)
            .where(CouncilSession.id == session_id)
            .options(
                selectinload(CouncilSession.project),
                selectinload(CouncilSession.agent_responses),
                selectinload(CouncilSession.consensus),
                selectinload(CouncilSession.final_prompts),
                selectinload(CouncilSession.implementation),
            )
        )
        return q.scalar_one_or_none()

    async def normalize_task(self, session_id: str) -> None:
        sess = await self.load_session(session_id)
        if not sess:
            return
        proj = sess.project
        ctx = build_context_snippet_sync(proj.repository_path if proj else "", 4000)
        prompt = (
            "Normalize and structure the user task for a coding council. "
            "Output markdown with: Objective, Scope, Constraints, Deliverables, Unknowns.\n\n"
            f"## User task\n{sess.original_user_task}\n\n## Context\n{ctx}"
        )
        provider = self.providers[AGENT_CHATGPT]
        res = await provider.complete(
            "You are the Orchestrator normalizing tasks.", prompt
        )
        sess.normalized_task = res.text or sess.original_user_task
        sess.current_round = ROUND_INITIAL
        sess.status = "normalized"
        sess.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self._emit(session_id, "normalized", {"preview": sess.normalized_task[:500]})

    async def run_initial_assessment(self, session_id: str) -> None:
        sess = await self.load_session(session_id)
        if not sess or not sess.project:
            return
        proj: Project = sess.project
        ctx = build_context_snippet_sync(proj.repository_path, 4000)
        task = sess.normalized_task or sess.original_user_task

        async def one(name: str, system_fn, user: str) -> ProviderResult:
            p = self.providers[name]
            return await p.complete(system_fn(), user)

        u = P.user_initial_round(task, ctx)
        results = await asyncio.gather(
            one(AGENT_CHATGPT, P.system_chatgpt_architect, u),
            one(AGENT_CLAUDE, P.system_claude_reviewer, u),
            one(AGENT_COMPOSE2, P.system_compose2_implementation, u),
        )
        agents = [AGENT_CHATGPT, AGENT_CLAUDE, AGENT_COMPOSE2]
        for agent, r in zip(agents, results, strict=True):
            self.db.add(
                AgentResponse(
                    session_id=sess.id,
                    agent_name=agent,
                    round_name=ROUND_INITIAL,
                    content=r.text,
                    rating=r.rating,
                    concerns=r.concerns or "",
                    approval_status="pending",
                )
            )
        sess.current_round = ROUND_CROSS
        sess.status = "round_1_done"
        sess.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self._emit(session_id, "round_complete", {"round": ROUND_INITIAL})

    async def run_cross_review(self, session_id: str) -> None:
        sess = await self.load_session(session_id)
        if not sess or not sess.project:
            return
        proj = sess.project
        ctx = build_context_snippet_sync(proj.repository_path, 4000)
        task = sess.normalized_task or sess.original_user_task
        peers = "\n\n".join(
            f"### {ar.agent_name}\n{ar.content}"
            for ar in sess.agent_responses
            if ar.round_name == ROUND_INITIAL
        )
        u = P.user_cross_review(task, peers, ctx)

        async def one(name: str, system_fn) -> ProviderResult:
            return await self.providers[name].complete(system_fn(), u)

        results = await asyncio.gather(
            one(AGENT_CHATGPT, P.system_chatgpt_architect),
            one(AGENT_CLAUDE, P.system_claude_reviewer),
            one(AGENT_COMPOSE2, P.system_compose2_implementation),
        )
        agents = [AGENT_CHATGPT, AGENT_CLAUDE, AGENT_COMPOSE2]
        for agent, r in zip(agents, results, strict=True):
            self.db.add(
                AgentResponse(
                    session_id=sess.id,
                    agent_name=agent,
                    round_name=ROUND_CROSS,
                    content=r.text,
                    rating=r.rating,
                    concerns=r.concerns or "",
                    approval_status="pending",
                )
            )
        sess.current_round = "consensus_build"
        sess.status = "round_2_done"
        sess.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self._emit(session_id, "round_complete", {"round": ROUND_CROSS})

    async def build_consensus(self, session_id: str) -> None:
        sess = await self.load_session(session_id)
        if not sess:
            return
        r1 = "\n".join(
            f"{ar.agent_name}: {ar.content}"
            for ar in sess.agent_responses
            if ar.round_name == ROUND_INITIAL
        )
        r2 = "\n".join(
            f"{ar.agent_name}: {ar.content}"
            for ar in sess.agent_responses
            if ar.round_name == ROUND_CROSS
        )
        task = sess.normalized_task or sess.original_user_task
        moderator = self.providers[AGENT_CHATGPT]
        res = await moderator.complete(
            P.system_moderator_consensus(),
            P.user_moderator_consensus_input(task, r1, r2),
        )
        fields = _parse_consensus_json(res.text)
        if sess.consensus:
            cons = sess.consensus
            cons.summary = fields.get("summary", "")
            cons.agreed_solution = fields.get("agreed_solution", "")
            cons.rejected_alternatives = fields.get("rejected_alternatives", "")
            cons.risks = fields.get("risks", "")
            cons.implementation_plan = fields.get("implementation_plan", "")
            cons.test_plan = fields.get("test_plan", "")
            cons.open_questions = fields.get("open_questions", "")
            cons.approval_status = "pending"
        else:
            cons = Consensus(
                session_id=sess.id,
                summary=fields.get("summary", ""),
                agreed_solution=fields.get("agreed_solution", ""),
                rejected_alternatives=fields.get("rejected_alternatives", ""),
                risks=fields.get("risks", ""),
                implementation_plan=fields.get("implementation_plan", ""),
                test_plan=fields.get("test_plan", ""),
                open_questions=fields.get("open_questions", ""),
                approval_status="pending",
            )
            self.db.add(cons)
        sess.current_round = ROUND_CONSENSUS_APPROVAL
        sess.status = "consensus_draft"
        sess.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self._emit(session_id, "consensus_ready", {})

    async def run_consensus_approval(self, session_id: str) -> None:
        sess = await self.load_session(session_id)
        if not sess or not sess.consensus:
            return
        cons = sess.consensus
        body = _consensus_to_markdown(cons)
        u = P.user_consensus_approval(body)

        async def one(name: str, system_fn) -> ProviderResult:
            return await self.providers[name].complete(system_fn(), u)

        # Compose2 reviews feasibility of consensus for implementation
        results = await asyncio.gather(
            one(AGENT_CHATGPT, P.system_chatgpt_architect),
            one(AGENT_CLAUDE, P.system_claude_reviewer),
            one(AGENT_COMPOSE2, P.system_compose2_implementation),
        )
        agents = [AGENT_CHATGPT, AGENT_CLAUDE, AGENT_COMPOSE2]
        for agent, r in zip(agents, results, strict=True):
            self.db.add(
                AgentResponse(
                    session_id=sess.id,
                    agent_name=agent,
                    round_name=ROUND_CONSENSUS_APPROVAL,
                    content=r.text,
                    rating=r.rating,
                    concerns=r.concerns or "",
                    approval_status=_approval_from_result(r),
                )
            )
        approvals = [_approval_from_result(r) for r in results]
        if all(a == "approved" for a in approvals):
            cons.approval_status = "approved"
            sess.status = "consensus_approved"
        else:
            cons.approval_status = "revisions_requested"
            sess.status = "consensus_blocked"
        sess.current_round = "prompt_engineering"
        sess.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self._emit(session_id, "consensus_approval_done", {"approvals": approvals})

    async def build_final_prompt(self, session_id: str) -> None:
        sess = await self.load_session(session_id)
        if not sess or not sess.consensus:
            return
        if sess.consensus.approval_status != "approved":
            raise ValueError("Consensus must be approved before prompt engineering.")
        proj = sess.project
        rules = ""
        if proj:
            rules = (proj.coding_rules or "") + "\n\n" + (proj.security_rules or "")
        cons_md = _consensus_to_markdown(sess.consensus)
        optimizer = self.providers[AGENT_CHATGPT]  # Prompt Optimizer role on same provider stack
        res = await optimizer.complete(
            P.system_prompt_optimizer(),
            P.user_prompt_from_consensus(cons_md, rules),
        )
        vr = await self.db.execute(
            select(func.coalesce(func.max(FinalPrompt.version), 0)).where(
                FinalPrompt.session_id == sess.id
            )
        )
        version = int(vr.scalar_one() or 0) + 1
        fp = FinalPrompt(
            session_id=sess.id,
            prompt_text=res.text,
            version=version,
            approved_by_chatgpt=False,
            approved_by_claude=False,
            approved_by_compose2=False,
        )
        self.db.add(fp)
        sess.current_round = ROUND_PROMPT_REVIEW
        sess.status = "prompt_draft"
        sess.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self._emit(session_id, "final_prompt_created", {"version": version})

    async def run_prompt_review(self, session_id: str) -> None:
        sess = await self.load_session(session_id)
        if not sess:
            return
        fp_row = await self.db.execute(
            select(FinalPrompt)
            .where(FinalPrompt.session_id == sess.id)
            .order_by(FinalPrompt.version.desc())
            .limit(1)
        )
        fp = fp_row.scalar_one_or_none()
        if not fp:
            raise ValueError("No final prompt found for review.")
        u = P.user_prompt_review(fp.prompt_text)

        async def one(name: str, system_fn) -> ProviderResult:
            return await self.providers[name].complete(system_fn(), u)

        results = await asyncio.gather(
            one(AGENT_CHATGPT, P.system_chatgpt_architect),
            one(AGENT_CLAUDE, P.system_claude_reviewer),
            one(AGENT_COMPOSE2, P.system_compose2_implementation),
        )
        agents = [AGENT_CHATGPT, AGENT_CLAUDE, AGENT_COMPOSE2]
        for agent, r in zip(agents, results, strict=True):
            self.db.add(
                AgentResponse(
                    session_id=sess.id,
                    agent_name=agent,
                    round_name=ROUND_PROMPT_REVIEW,
                    content=r.text,
                    rating=r.rating,
                    concerns=r.concerns or "",
                    approval_status=_approval_from_result(r),
                )
            )
        fp.approved_by_chatgpt = _approval_from_result(results[0]) == "approved"
        fp.approved_by_claude = _approval_from_result(results[1]) == "approved"
        fp.approved_by_compose2 = _approval_from_result(results[2]) == "approved"
        if fp.approved_by_chatgpt and fp.approved_by_claude and fp.approved_by_compose2:
            sess.status = "prompt_ready"
        else:
            sess.status = "prompt_revisions"
        sess.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self._emit(session_id, "prompt_review_done", {})

    async def submit_to_compose2(self, session_id: str) -> None:
        sess = await self.load_session(session_id)
        if not sess:
            return
        fp_row = await self.db.execute(
            select(FinalPrompt)
            .where(FinalPrompt.session_id == sess.id)
            .order_by(FinalPrompt.version.desc())
            .limit(1)
        )
        fp = fp_row.scalar_one_or_none()
        if not fp:
            raise ValueError("No final prompt to hand off.")
        if not (fp.approved_by_chatgpt and fp.approved_by_claude and fp.approved_by_compose2):
            raise ValueError("All reviewers must approve the final prompt first.")
        if not sess.implementation:
            self.db.add(
                ImplementationResult(session_id=sess.id, status="pending", changed_files=[])
            )
        else:
            sess.implementation.status = "pending"
        sess.status = "ready_for_implementation"
        sess.current_round = "implementation"
        sess.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self._emit(session_id, "compose2_handoff", {})

    async def mark_implemented(
        self, session_id: str, changed_files: list[str], summary: str
    ) -> None:
        sess = await self.load_session(session_id)
        if not sess:
            return
        if not sess.implementation:
            self.db.add(
                ImplementationResult(
                    session_id=sess.id,
                    status="implemented",
                    changed_files=changed_files,
                    summary=summary,
                )
            )
        else:
            sess.implementation.changed_files = changed_files
            sess.implementation.summary = summary
            sess.implementation.status = "implemented"
        sess.status = "implemented"
        sess.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self._emit(session_id, "implemented", {})

    async def run_code_review(self, session_id: str) -> None:
        sess = await self.load_session(session_id)
        if not sess or not sess.implementation:
            return
        imp = sess.implementation
        files = imp.changed_files if isinstance(imp.changed_files, list) else str(imp.changed_files)
        u = P.user_code_review(sess.original_user_task, imp.summary or "", str(files))

        async def one(name: str, system_fn) -> ProviderResult:
            return await self.providers[name].complete(system_fn(), u)

        results = await asyncio.gather(
            one(AGENT_CHATGPT, P.system_chatgpt_architect),
            one(AGENT_CLAUDE, P.system_claude_reviewer),
        )
        text = "\n\n".join(
            f"### {agent}\n{r.text}" for agent, r in zip([AGENT_CHATGPT, AGENT_CLAUDE], results, strict=True)
        )
        imp.review_result = text
        needs_fix = any(
            re.search(r"blocking|must fix|CHANGES_NEEDED", r.text, re.I) for r in results
        )
        sess.status = "needs_revision" if needs_fix else "completed"
        for agent, r in zip([AGENT_CHATGPT, AGENT_CLAUDE], results, strict=True):
            self.db.add(
                AgentResponse(
                    session_id=sess.id,
                    agent_name=agent,
                    round_name=ROUND_CODE_REVIEW,
                    content=r.text,
                    rating=r.rating,
                    concerns=r.concerns or "",
                    approval_status="rejected" if needs_fix else "approved",
                )
            )
        sess.current_round = "code_review"
        sess.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self._emit(session_id, "code_review_done", {"needs_revision": needs_fix})

    async def run_through_prompt_ready(self, session_id: str) -> None:
        """Convenience: normalize → round1 → round2 → consensus → approvals → prompt → prompt review."""

        await self.normalize_task(session_id)
        await self.run_initial_assessment(session_id)
        await self.run_cross_review(session_id)
        await self.build_consensus(session_id)
        await self.run_consensus_approval(session_id)
        loaded = await self.load_session(session_id)
        if (
            loaded
            and loaded.consensus
            and loaded.consensus.approval_status != "approved"
        ):
            return
        await self.build_final_prompt(session_id)
        await self.run_prompt_review(session_id)
