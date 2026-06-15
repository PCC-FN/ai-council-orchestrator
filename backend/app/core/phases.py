from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PhaseDefinition:
    """One workflow phase in the 12-step AI Orchestra pipeline."""

    key: str
    number: int
    label: str
    description: str


# Canonical 12-phase workflow. Each phase is stored individually (PhaseExecution).
PHASES: tuple[PhaseDefinition, ...] = (
    PhaseDefinition("understand_problem", 1, "Problem verstehen", "Aufgabe normalisieren und Kontext sammeln"),
    PhaseDefinition("develop_architecture", 2, "Architektur entwickeln", "Initial Assessment durch Architektur-Agenten"),
    PhaseDefinition("agent_discussion", 3, "Agenten-Diskussion", "Cross-Review zwischen allen Agenten"),
    PhaseDefinition("find_consensus", 4, "Konsens finden", "Moderator konsolidiert Positionen"),
    PhaseDefinition("prompt_engineering", 5, "Prompt Engineering", "Finaler Implementierungs-Prompt"),
    PhaseDefinition("prompt_review", 6, "Prompt Review", "Agenten prüfen den finalen Prompt"),
    PhaseDefinition("handoff_worker", 7, "Worker-Übergabe", "Job für Coding-Worker erstellen"),
    PhaseDefinition("implementation", 8, "Implementierung", "Worker setzt den Prompt um"),
    PhaseDefinition("code_review", 9, "Code Review", "Agenten prüfen die Umsetzung"),
    PhaseDefinition("improvement_rounds", 10, "Verbesserungsrunden", "Bei Problemen erneut implementieren"),
    PhaseDefinition("git_commit", 11, "Git Commit", "Änderungen committen"),
    PhaseDefinition("pull_request", 12, "Pull Request", "PR erstellen und abschließen"),
)

PHASE_BY_KEY: dict[str, PhaseDefinition] = {p.key: p for p in PHASES}
PHASE_KEYS: tuple[str, ...] = tuple(p.key for p in PHASES)


def phase_after(key: str) -> str | None:
    """Return the next phase key, or None if this is the last phase."""
    try:
        idx = PHASE_KEYS.index(key)
    except ValueError:
        return None
    if idx + 1 >= len(PHASE_KEYS):
        return None
    return PHASE_KEYS[idx + 1]


def phase_number(key: str) -> int:
    p = PHASE_BY_KEY.get(key)
    return p.number if p else 0
