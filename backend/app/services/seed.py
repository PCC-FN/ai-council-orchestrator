from __future__ import annotations

from sqlalchemy import func, select

from app.database import SessionLocal
from app.models.db_models import CouncilSession, Project


async def seed_if_empty() -> None:
    """Create a demo project + session on first start so the UI is never empty."""
    async with SessionLocal() as db:
        count = await db.execute(select(func.count()).select_from(Project))
        if (count.scalar_one() or 0) > 0:
            return

        project = Project(
            name="Beispiel React App",
            description="Demo-Projekt für AI Council Coding Orchestrator",
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

        session = CouncilSession(
            project_id=project.id,
            title="Login-Formular mit Validierung ergänzen",
            original_user_task=(
                "In einer React-App soll ein Login-Formular mit E-Mail- und "
                "Passwortvalidierung ergänzt werden."
            ),
        )
        db.add(session)
        await db.commit()
