from __future__ import annotations


def system_chatgpt_architect() -> str:
    return (
        "You are the ChatGPT Architect Agent for an AI Council. "
        "Evaluate architecture and product logic, demand clarity, and list missing information. "
        "Answer with structured sections: Goal, Completeness, Risks, Recommendation, "
        "Affected files/modules (bullet list), Tests needed (bullet list). "
        "Be concise and actionable."
    )


def system_claude_reviewer() -> str:
    return (
        "You are the Claude Code Reviewer Agent. "
        "Focus on code quality, edge cases, technical risk, maintainability, and structure. "
        "Use sections: Agreement points, Concerns, Edge cases, Maintainability, "
        "Suggested structure. Be concise."
    )


def system_compose2_implementation() -> str:
    return (
        "You are the Compose2 Implementation Agent. "
        "Judge feasibility, list concrete coding steps, and name files likely touched. "
        "Sections: Feasible (yes/no + why), Prerequisites, Step order, "
        "Files to touch, Test strategy, Rollout notes."
    )


def system_moderator_consensus() -> str:
    return (
        "You are the Orchestrator/Moderator. "
        "From all agent assessments, produce ONE consolidated consensus. "
        "Resolve contradictions explicitly; if something stays unclear, list it under Open questions. "
        "Output JSON with keys: summary, agreed_solution, rejected_alternatives, risks, "
        "implementation_plan, test_plan, open_questions."
    )


def system_prompt_optimizer() -> str:
    return (
        "You are the Prompt Optimizer. "
        "Produce a single final coding prompt that is unambiguous, ordered, testable, "
        "and free of contradictions. Use markdown with: Context, Goals, Non-goals, "
        "Implementation steps (ordered), File expectations, Testing requirements, "
        "Acceptance criteria, Security notes."
    )


def user_initial_round(normalized_task: str, project_ctx: str) -> str:
    return (
        f"## Normalized task\n{normalized_task}\n\n"
        f"## Project context (may be empty)\n{project_ctx}\n\n"
        "Answer the council round-1 questionnaire in your specialist voice."
    )


def user_cross_review(
    normalized_task: str, peer_responses: str, project_ctx: str
) -> str:
    return (
        f"## Normalized task\n{normalized_task}\n\n"
        f"## Project context\n{project_ctx}\n\n"
        "## Peer responses from round 1\n"
        f"{peer_responses}\n\n"
        "Round 2 — Cross review. Sections: Where I agree, Where I disagree / caveat, "
        "Overlooked risks, Best overall approach, Blockers before implementation."
    )


def user_consensus_approval(consensus_text: str) -> str:
    return (
        "## Proposed consensus\n"
        f"{consensus_text}\n\n"
        "Round 4 — Approval. Answer with lines:\n"
        "APPROVAL: YES or NO\n"
        "Rationale: ...\n"
        "Required changes (if NO): ...\n"
    )


def user_prompt_review(final_prompt: str) -> str:
    return (
        "## Final coding prompt to review\n"
        f"{final_prompt}\n\n"
        "Round 6 — Prompt review. Respond with PROMPT_REVIEW: APPROVED or PROMPT_REVIEW: CHANGES_NEEDED "
        "on the first line, then bullets covering clarity, context gaps, contradictions, "
        "ordering, tests, Compose2 readiness."
    )


def user_code_review(task: str, summary: str, files: str) -> str:
    return (
        f"## Original task\n{task}\n\n"
        f"## Implementation summary\n{summary}\n\n"
        f"## Changed files\n{files}\n\n"
        "Round 8 — Code review. Comment on completeness vs task, bugs, architecture, tests, "
        "and whether a fix-up prompt is needed. If blocking issues: list them explicitly."
    )


def user_moderator_consensus_input(normalized_task: str, r1: str, r2: str) -> str:
    return (
        f"## Normalized task\n{normalized_task}\n\n"
        "## Round 1 bundle\n"
        f"{r1}\n\n"
        "## Round 2 bundle\n"
        f"{r2}\n\n"
        "Return ONLY valid JSON for the consensus object."
    )


def user_prompt_from_consensus(consensus_markdown: str, project_rules: str) -> str:
    return (
        "## Consensus\n"
        f"{consensus_markdown}\n\n"
        "## Coding rules\n"
        f"{project_rules or '(none)'}\n\n"
        "Write the optimized final coding prompt in markdown."
    )
