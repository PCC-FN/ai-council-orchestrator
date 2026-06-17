"""AI Orchestra post-implementation review for Vibe Coding jobs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.config import get_settings
from app.models.vibe_models import CodingJob, FileChange
from app.services.providers.registry import AGENT_CLAUDE, build_providers


@dataclass
class ReviewResult:
    passed: bool
    needs_correction: bool
    correction_prompt: str = ""
    report: dict[str, Any] = field(default_factory=dict)
    auto_dispatch: bool = False


REVIEW_SYSTEM = """You are AI Orchestra's implementation reviewer.
Analyze whether the coding task was fulfilled based on the original request,
worker result, changed files, and test outcomes.

Respond with ONLY valid JSON (no markdown fences):
{
  "passed": boolean,
  "score": number (0-100),
  "fulfilled_requirements": ["..."],
  "missing_requirements": ["..."],
  "issues": ["..."],
  "security_concerns": ["..."],
  "test_assessment": "string",
  "maintainability": "string",
  "needs_correction": boolean,
  "correction_prompt": "precise instructions for Cursor if needs_correction else empty string",
  "summary": "short German summary"
}
"""


def _heuristic_review(
    job: CodingJob,
    worker_result: dict[str, Any],
    file_changes: list[FileChange],
) -> ReviewResult:
    """Offline review for mock mode and tests."""
    original = job.original_prompt.lower()
    changed = worker_result.get("changed_files") or [f.path for f in file_changes]
    tests = worker_result.get("tests") or {}
    failed = int(tests.get("failed") or 0)
    passed_count = int(tests.get("passed") or 0)

    issues: list[str] = []
    missing: list[str] = []
    fulfilled: list[str] = []

    if not changed:
        issues.append("Keine Dateiänderungen erkannt")
    else:
        fulfilled.append(f"{len(changed)} Datei(en) geändert")

    if failed > 0:
        issues.append(f"{failed} Test(s) fehlgeschlagen")

    if "migration" in original and not any("migration" in p.lower() for p in changed):
        missing.append("Datenbankmigration fehlt")
        issues.append("Aufgabe erwähnt Migration, aber keine Migrationsdatei gefunden")

    if "test" in original and passed_count == 0 and failed == 0:
        missing.append("Keine Tests ausgeführt oder ergänzt")
        issues.append("Tests wurden angefordert, aber keine Testergebnisse vorliegen")

    if "berechtigung" in original or "permission" in original:
        if not any("auth" in p.lower() or "permission" in p.lower() for p in changed):
            missing.append("Berechtigungslogik nicht erkennbar in geänderten Dateien")

    passed = len(issues) == 0 and len(missing) == 0 and bool(changed)
    needs_correction = not passed and bool(issues or missing)

    correction = ""
    if needs_correction:
        parts = ["Bitte folgende Probleme beheben:\n"]
        for i, issue in enumerate(issues + missing, 1):
            parts.append(f"{i}. {issue}")
        parts.append("\nUrsprüngliche Aufgabe:\n" + job.original_prompt)
        correction = "\n".join(parts)

    report = {
        "passed": passed,
        "score": 90 if passed else max(20, 60 - len(issues) * 15 - len(missing) * 10),
        "fulfilled_requirements": fulfilled,
        "missing_requirements": missing,
        "issues": issues,
        "security_concerns": [],
        "test_assessment": f"{passed_count} OK, {failed} fehlgeschlagen",
        "maintainability": "OK" if passed else "Nachbesserung empfohlen",
        "needs_correction": needs_correction,
        "review_round": job.review_rounds,
        "summary": "Ergebnis erfüllt die Anforderungen." if passed else "Nachbesserung erforderlich.",
        "engine": "heuristic",
    }
    return ReviewResult(
        passed=passed,
        needs_correction=needs_correction,
        correction_prompt=correction,
        report=report,
    )


def _parse_ai_review(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                return None
    return None


async def run_implementation_review(
    job: CodingJob,
    worker_result: dict[str, Any],
    file_changes: list[FileChange],
) -> ReviewResult:
    settings = get_settings()
    providers = build_providers()
    provider = providers.get(AGENT_CLAUDE)

    use_heuristic = settings.use_mock_providers or not (
        settings.openai_api_key.strip() or settings.anthropic_api_key.strip()
    )

    if use_heuristic or provider is None:
        return _heuristic_review(job, worker_result, file_changes)

    changed = worker_result.get("changed_files") or [f.path for f in file_changes]
    user_prompt = (
        f"## Original task\n{job.original_prompt}\n\n"
        f"## Implementation plan\n{json.dumps(job.implementation_plan or {}, ensure_ascii=False)[:2000]}\n\n"
        f"## Worker summary\n{worker_result.get('summary', '')}\n\n"
        f"## Changed files\n{json.dumps(changed, ensure_ascii=False)}\n\n"
        f"## Test results\n{json.dumps(worker_result.get('tests', {}), ensure_ascii=False)}\n\n"
        f"## Build/Lint\nbuild: {worker_result.get('build_status')}, lint: {worker_result.get('lint_status')}\n"
    )

    try:
        result = await provider.complete(REVIEW_SYSTEM, user_prompt)
        parsed = _parse_ai_review(result.text)
        if not parsed:
            fallback = _heuristic_review(job, worker_result, file_changes)
            fallback.report["ai_parse_failed"] = True
            return fallback

        passed = bool(parsed.get("passed"))
        needs = bool(parsed.get("needs_correction", not passed))
        return ReviewResult(
            passed=passed,
            needs_correction=needs and not passed,
            correction_prompt=str(parsed.get("correction_prompt") or ""),
            report={**parsed, "engine": "ai", "agent_concerns": result.concerns},
        )
    except Exception as exc:
        fallback = _heuristic_review(job, worker_result, file_changes)
        fallback.report["ai_error"] = str(exc)
        return fallback


def should_auto_dispatch_correction(job: CodingJob) -> bool:
    """Autonomous/direct modes may auto-send corrections; others need user approval."""
    return job.mode in ("direct", "autonomous")


def format_review_markdown(review: ReviewResult, job: CodingJob) -> str:
    r = review.report
    lines = [
        "## AI-Nachprüfung",
        "",
        f"**Ergebnis:** {'Bestanden' if review.passed else 'Nachbesserung nötig'}",
        f"**Score:** {r.get('score', '—')}/100",
        f"**Runde:** {job.review_rounds}/{job.max_review_rounds}",
        "",
    ]
    if r.get("fulfilled_requirements"):
        lines.append("### Erfüllt")
        lines.extend(f"- {x}" for x in r["fulfilled_requirements"])
        lines.append("")
    if r.get("missing_requirements"):
        lines.append("### Fehlende Anforderungen")
        lines.extend(f"- {x}" for x in r["missing_requirements"])
        lines.append("")
    if r.get("issues"):
        lines.append("### Probleme")
        lines.extend(f"- {x}" for x in r["issues"])
        lines.append("")
    if r.get("security_concerns"):
        lines.append("### Sicherheit")
        lines.extend(f"- {x}" for x in r["security_concerns"])
        lines.append("")
    lines.append(f"**Zusammenfassung:** {r.get('summary', '')}")
    if review.needs_correction and review.correction_prompt:
        lines.extend(["", "### Korrekturauftrag", "", review.correction_prompt])
    return "\n".join(lines)
