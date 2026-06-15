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

    async def _run_agent(
        self, session_id: str, agent_name: str, system: str, user: str
    ) -> ProviderResult:
        """Run one provider call and broadcast its lifecycle for the live UI."""
        await self._emit(session_id, "agent_started", {"agent": agent_name})
        try:
            res = await self.providers[agent_name].complete(system, user)
        except Exception as exc:  # surface provider failures to the UI
            await self._emit(
                session_id, "agent_failed", {"agent": agent_name, "error": str(exc)}
            )
            raise
        await self._emit(
            session_id,
            "agent_finished",
            {"agent": agent_name, "rating": res.rating},
        )
        return res

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

        u = P.user_initial_round(task, ctx)
        await self._emit(session_id, "round_started", {"round": ROUND_INITIAL})
        results = await asyncio.gather(
            self._run_agent(session_id, AGENT_CHATGPT, P.system_chatgpt_architect(), u),
            self._run_agent(session_id, AGENT_CLAUDE, P.system_claude_reviewer(), u),
            self._run_agent(session_id, AGENT_COMPOSE2, P.system_compose2_implementation(), u),
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
        await self._emit(session_id, "round_started", {"round": ROUND_CROSS})
        results = await asyncio.gather(
            self._run_agent(session_id, AGENT_CHATGPT, P.system_chatgpt_architect(), u),
            self._run_agent(session_id, AGENT_CLAUDE, P.system_claude_reviewer(), u),
            self._run_agent(session_id, AGENT_COMPOSE2, P.system_compose2_implementation(), u),
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
        await self._emit(session_id, "round_started", {"round": "consensus_build"})
        res = await self._run_agent(
            session_id,
            AGENT_CHATGPT,
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
        await self._emit(session_id, "consensus_created", {})

    async def run_consensus_approval(self, session_id: str) -> None:
        sess = await self.load_session(session_id)
        if not sess or not sess.consensus:
            return
        cons = sess.consensus
        body = _consensus_to_markdown(cons)
        u = P.user_consensus_approval(body)
        await self._emit(session_id, "round_started", {"round": ROUND_CONSENSUS_APPROVAL})
        # Compose2 reviews feasibility of consensus for implementation
        results = await asyncio.gather(
            self._run_agent(session_id, AGENT_CHATGPT, P.system_chatgpt_architect(), u),
            self._run_agent(session_id, AGENT_CLAUDE, P.system_claude_reviewer(), u),
            self._run_agent(session_id, AGENT_COMPOSE2, P.system_compose2_implementation(), u),
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
        await self._emit(session_id, "round_started", {"round": "prompt_engineering"})
        # Prompt Optimizer role runs on the architect provider stack.
        res = await self._run_agent(
            session_id,
            AGENT_CHATGPT,
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
        await self._emit(session_id, "round_started", {"round": ROUND_PROMPT_REVIEW})
        results = await asyncio.gather(
            self._run_agent(session_id, AGENT_CHATGPT, P.system_chatgpt_architect(), u),
            self._run_agent(session_id, AGENT_CLAUDE, P.system_claude_reviewer(), u),
            self._run_agent(session_id, AGENT_COMPOSE2, P.system_compose2_implementation(), u),
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
        await self._emit(session_id, "submitted_to_compose2", {})

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
        await self._emit(session_id, "round_started", {"round": ROUND_CODE_REVIEW})
        results = await asyncio.gather(
            self._run_agent(session_id, AGENT_CHATGPT, P.system_chatgpt_architect(), u),
            self._run_agent(session_id, AGENT_CLAUDE, P.system_claude_reviewer(), u),
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
        await self._emit(
            session_id, "implementation_reviewed", {"needs_revision": needs_fix}
        )

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

    # --- High-level controls used by the clean REST API -----------------

    async def start(self, session_id: str) -> str:
        """Kick off a session: normalize the task and run the first round."""
        sess = await self.load_session(session_id)
        if not sess:
            raise ValueError("session not found")
        await self._emit(session_id, "session_started", {})
        await self.normalize_task(session_id)
        await self.run_initial_assessment(session_id)
        return "initial_assessment"

    async def run_next_round(self, session_id: str) -> str:
        """Advance the session by exactly one orchestration step.

        Returns the name of the step that was executed, or a sentinel like
        ``waiting`` (manual action required) / ``done`` (nothing left to do).
        """
        sess = await self.load_session(session_id)
        if not sess:
            raise ValueError("session not found")
        status = sess.status

        if status in {"created", "", "normalized"} and not sess.normalized_task:
            await self.normalize_task(session_id)
            return "normalize"
        if status in {"created", "", "normalized"}:
            await self.run_initial_assessment(session_id)
            return "initial_assessment"
        if status == "round_1_done":
            await self.run_cross_review(session_id)
            return "cross_review"
        if status == "round_2_done":
            await self.build_consensus(session_id)
            return "build_consensus"
        if status in {"consensus_draft", "consensus_blocked"}:
            await self.run_consensus_approval(session_id)
            return "consensus_approval"
        if status == "consensus_approved":
            await self.build_final_prompt(session_id)
            return "build_final_prompt"
        if status in {"prompt_draft", "prompt_revisions"}:
            await self.run_prompt_review(session_id)
            return "prompt_review"
        if status == "implemented":
            await self.run_code_review(session_id)
            return "code_review"
        if status in {"prompt_ready", "ready_for_implementation", "needs_revision"}:
            return "waiting"  # manual action required
        return "done"

    async def approve_consensus(self, session_id: str) -> None:
        """Manually approve the consensus (skip / override agent voting)."""
        sess = await self.load_session(session_id)
        if not sess or not sess.consensus:
            raise ValueError("no consensus to approve")
        sess.consensus.approval_status = "approved"
        sess.status = "consensus_approved"
        sess.current_round = "prompt_engineering"
        sess.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self._emit(session_id, "consensus_approved", {})

    async def regenerate_final_prompt(self, session_id: str) -> None:
        """Generate a fresh final-prompt version (e.g. after revisions)."""
        sess = await self.load_session(session_id)
        if not sess or not sess.consensus:
            raise ValueError("no consensus available")
        if sess.consensus.approval_status != "approved":
            sess.consensus.approval_status = "approved"
        await self.build_final_prompt(session_id)

    async def approve_final_prompt(self, session_id: str) -> None:
        """Manual human approval of the latest final prompt."""
        sess = await self.load_session(session_id)
        if not sess:
            raise ValueError("session not found")
        fp_row = await self.db.execute(
            select(FinalPrompt)
            .where(FinalPrompt.session_id == sess.id)
            .order_by(FinalPrompt.version.desc())
            .limit(1)
        )
        fp = fp_row.scalar_one_or_none()
        if not fp:
            raise ValueError("no final prompt to approve")
        fp.approved_by_chatgpt = True
        fp.approved_by_claude = True
        fp.approved_by_compose2 = True
        sess.status = "prompt_ready"
        sess.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self._emit(session_id, "prompt_approved", {"version": fp.version})
