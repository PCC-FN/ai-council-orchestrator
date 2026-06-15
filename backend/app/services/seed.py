from __future__ import annotations

from sqlalchemy import func, select

from app.database import SessionLocal
from app.models.db_models import AgentDefinition, CouncilSession, Project, ProjectKnowledge
from app.services import prompts as P


DEFAULT_AGENTS: list[dict] = [
    {
        "key": "chatgpt_architect",
        "display_name": "ChatGPT Architect",
        "provider": "openai",
        "role": "Architektur & Produktlogik",
        "system_prompt": P.system_chatgpt_architect(),
        "priority": 90,
    },
    {
        "key": "claude_reviewer",
        "display_name": "Claude Reviewer",
        "provider": "anthropic",
        "role": "Code-Qualität & Risiken",
        "system_prompt": P.system_claude_reviewer(),
        "priority": 85,
    },
    {
        "key": "compose2_implementation",
        "display_name": "Compose2 Implementation",
        "provider": "compose2",
        "role": "Umsetzbarkeit",
        "system_prompt": P.system_compose2_implementation(),
        "priority": 80,
    },
    {
        "key": "prompt_optimizer",
        "display_name": "Prompt Engineer",
        "provider": "openai",
        "role": "Finaler Coding-Prompt",
        "system_prompt": P.system_prompt_optimizer(),
        "priority": 75,
    },
    {
        "key": "security_expert",
        "display_name": "Security Expert",
        "provider": "mock",
        "role": "Security Review",
        "system_prompt": "You are a security expert reviewing code changes for vulnerabilities.",
        "priority": 70,
    },
    {
        "key": "testing_expert",
        "display_name": "Testing Expert",
        "provider": "mock",
        "role": "Testabdeckung",
        "system_prompt": "You are a testing expert ensuring adequate test coverage and quality.",
        "priority": 65,
    },
]


async def seed_if_empty() -> None:
    """Seed demo data and default agent definitions on first start."""
    async with SessionLocal() as db:
        agent_count = await db.scalar(select(func.count()).select_from(AgentDefinition))
        if (agent_count or 0) == 0:
            for spec in DEFAULT_AGENTS:
                db.add(AgentDefinition(**spec))
            await db.flush()

        count = await db.execute(select(func.count()).select_from(Project))
        if (count.scalar_one() or 0) > 0:
            await db.commit()
            return

        project = Project(
            name="Beispiel React App",
            description="Demo-Projekt für AI Orchestra",
            repository_path="",
            coding_rules=(
                "- TypeScript strict mode\n"
                "- Funktionale React-Komponenten + Hooks\n"
                "- Kleine, wiederverwendbare Komponenten\n"
                "- Keine Geheimnisse im Frontend"
            ),
            security_rules=(
                "- Eingaben client- und serverseitig validieren\n"
                "- Keine sensiblen Daten loggen\n"
                "- Abhängigkeiten aktuell halten"
            ),
            tech_stack="React, Vite, TypeScript, Tailwind CSS",
            excluded_paths="node_modules, dist, .env",
        )
        db.add(project)
        await db.flush()

        db.add(
            ProjectKnowledge(
                project_id=project.id,
                architecture="Single-Page-App mit React + Vite",
                design_patterns="Container/Presenter, Custom Hooks",
                frameworks="React, Vite, TypeScript, Tailwind CSS",
                naming_conventions="PascalCase für Komponenten, camelCase für Funktionen",
                code_style=project.coding_rules,
                best_practices="Kleine Komponenten, explizite Typen, keine Secrets im Frontend",
            )
        )

        session = CouncilSession(
            project_id=project.id,
            title="Login-Formular mit Validierung ergänzen",
            original_user_task=(
                "In einer React-App soll ein Login-Formular mit E-Mail- und "
                "Passwortvalidierung ergänzt werden."
            ),
            current_phase="understand_problem",
        )
        db.add(session)
        await db.commit()
