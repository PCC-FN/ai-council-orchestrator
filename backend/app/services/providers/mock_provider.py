from __future__ import annotations

import json

from app.services.providers.base import BaseProvider, ProviderResult


class MockProvider(BaseProvider):
    """Deterministic, offline responses for demos and tests."""

    name = "mock"

    async def complete(self, system: str, user: str) -> ProviderResult:
        agent_hint = "agent"
        if "ChatGPT Architect" in system or "architect" in system.lower():
            agent_hint = "chatgpt_architect"
        elif "Claude Code Reviewer" in system or "reviewer" in system.lower():
            agent_hint = "claude_reviewer"
        elif "Compose2" in system or "compose2" in system.lower():
            agent_hint = "compose2"

        if "Prompt Optimizer" in system or "final coding prompt" in system.lower():
            md = (
                "# Context\nDerived from council consensus.\n\n"
                "## Goals\nShip the agreed minimal change.\n\n"
                "## Non-goals\nOut-of-scope refactors.\n\n"
                "## Implementation steps\n"
                "1. Locate integration points.\n"
                "2. Implement core logic.\n"
                "3. Add/adjust tests.\n"
                "4. Run formatter/linter.\n\n"
                "## Testing requirements\n"
                "- Unit tests for core branches\n"
                "- One integration test for happy path\n\n"
                "## Acceptance criteria\n"
                "- Tests pass\n"
                "- No new secrets\n"
            )
            return ProviderResult(text=md, rating=5)

        lower = user.lower()

        if "Return ONLY valid JSON" in user or "consensus object" in user:
            cons = {
                "summary": "Align on minimal implementation with tests.",
                "agreed_solution": "Implement with clear modules and cover edge cases.",
                "rejected_alternatives": "Big-bang rewrite without tests.",
                "risks": "Ambiguous API contracts.",
                "implementation_plan": "1) Discover 2) Implement 3) Test 4) Document",
                "test_plan": "Unit + one integration path.",
                "open_questions": "Deployment target if any.",
            }
            return ProviderResult(text=json.dumps(cons, indent=2), rating=5)

        if "approval" in lower and ("consensus" in lower or "konsens" in lower):
            return ProviderResult(
                text="APPROVAL: YES\n"
                "The consensus is complete enough for implementation planning.\n"
                "Minor follow-up: confirm error handling for empty input.",
                rating=4,
                concerns="Empty input edge case should be explicit.",
                approval_status="approved",
            )
        if "prompt" in lower and ("review" in lower or "prüfen" in lower):
            approved = "widerspruch" not in lower and "contradiction" not in lower
            return ProviderResult(
                text=(
                    "PROMPT_REVIEW: APPROVED\n"
                    if approved
                    else "PROMPT_REVIEW: CHANGES_NEEDED\nClarify conflicting constraints.\n"
                ),
                rating=5 if approved else 3,
                concerns="" if approved else "Ordering of steps vs. tests.",
                approval_status="approved" if approved else "rejected",
            )
        if "code review" in lower or "implementation summary" in lower:
            return ProviderResult(
                text="CODE_REVIEW: LOOKS_GOOD\n"
                "Task appears addressed; add one negative-path test.\n"
                "No blocking issues.",
                rating=4,
                concerns="Missing explicit test for validation failure branch.",
                approval_status="approved",
            )

        if agent_hint == "claude_reviewer":
            text = (
                "## Zustimmungspunkte\n"
                "- Der Ansatz ist grundsätzlich tragfähig und klein gehalten.\n"
                "- Eine klare Trennung von UI und Validierungslogik ist sinnvoll.\n\n"
                "## Bedenken\n"
                "- Fehlerzustände (leere Felder, ungültige E-Mail) müssen explizit behandelt werden.\n"
                "- Eingaben sollten clientseitig **und** serverseitig validiert werden.\n\n"
                "## Edge Cases\n"
                "- Leere Eingaben und reine Leerzeichen\n"
                "- Sehr lange Eingaben / fehlerhaftes E-Mail-Format\n"
                "- Mehrfaches schnelles Absenden (Double-Submit)\n\n"
                "## Wartbarkeit\n"
                "Reine, testbare Funktionen für die Validierung bevorzugen; "
                "Komponenten klein und wiederverwendbar halten.\n\n"
                "## Vorgeschlagene Struktur\n"
                "- `LoginForm`-Komponente\n"
                "- `useLoginValidation`-Hook\n"
                "- `validators.ts` für reine Prüflogik"
            )
            return ProviderResult(
                text=text,
                rating=4,
                concerns="Validierung muss auch serverseitig erfolgen.",
            )

        if agent_hint == "compose2":
            text = (
                "## Umsetzbar\n"
                "Ja — der Umfang ist klar und in wenigen Schritten implementierbar.\n\n"
                "## Voraussetzungen\n"
                "- Vorhandenes Formular-/Routing-Setup\n"
                "- Test-Runner konfiguriert\n\n"
                "## Schrittreihenfolge\n"
                "1. Formularfelder und State anlegen\n"
                "2. Validierungslogik als reine Funktionen ergänzen\n"
                "3. Fehleranzeige und Loading-State einbauen\n"
                "4. Tests für gültige/ungültige Eingaben schreiben\n"
                "5. Linter/Formatter ausführen\n\n"
                "## Betroffene Dateien\n"
                "- `src/components/LoginForm.tsx`\n"
                "- `src/utils/validators.ts`\n"
                "- `tests/login_form.test.tsx`\n\n"
                "## Teststrategie\n"
                "Unit-Tests für Validatoren + ein Happy-Path-Integrationstest.\n\n"
                "## Rollout\n"
                "Keine Migrationen nötig; rein additive Änderung."
            )
            return ProviderResult(
                text=text, rating=5, concerns="Mock-Antwort — echtes Modell ersetzt dies."
            )

        text = (
            "## Ziel\n"
            "Eine minimale, getestete Änderung passend zur Aufgabe liefern.\n\n"
            "## Vollständigkeit\n"
            "Weitgehend klar; Zielumgebung/Deployment ggf. noch bestätigen.\n\n"
            "## Risiken\n"
            "- Scope Creep\n"
            "- Fehlende nicht-funktionale Anforderungen (z. B. A11y, i18n)\n\n"
            "## Empfehlung\n"
            "Hinter einer kleinen, klar abgegrenzten Schnittstelle implementieren "
            "und mit Unit-Tests absichern.\n\n"
            "## Betroffene Dateien / Module\n"
            "- `src/components/LoginForm.tsx`\n"
            "- `tests/login_form.test.tsx`\n\n"
            "## Benötigte Tests\n"
            "- Unit: Kern-Validierung\n"
            "- Integration: erfolgreicher Login-Flow"
        )
        return ProviderResult(
            text=text, rating=4, concerns="Mock-Antwort — echtes Modell ersetzt dies."
        )
