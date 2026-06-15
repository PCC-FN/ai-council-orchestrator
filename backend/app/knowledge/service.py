from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_models import Project, ProjectKnowledge
from app.services.project_context import list_project_files


class KnowledgeService:
    """Builds and persists project knowledge for agents and workers."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_or_create(self, project_id: str) -> ProjectKnowledge:
        r = await self.db.execute(
            select(ProjectKnowledge).where(ProjectKnowledge.project_id == project_id)
        )
        row = r.scalar_one_or_none()
        if row:
            return row
        row = ProjectKnowledge(project_id=project_id)
        self.db.add(row)
        await self.db.flush()
        return row

    async def sync_from_project(self, project: Project) -> ProjectKnowledge:
        """Seed knowledge fields from the Project record and repo index."""
        k = await self.get_or_create(project.id)
        if project.tech_stack and not k.frameworks:
            k.frameworks = project.tech_stack
        if project.coding_rules and not k.code_style:
            k.code_style = project.coding_rules
        if project.repository_path:
            files = list_project_files(project.repository_path, max_files=120)
            if files and not k.file_overview:
                k.file_overview = "\n".join(f"- {f}" for f in files[:80])
                k.repo_structure = "\n".join(files[:40])
        await self.db.flush()
        return k

    async def get_context_bundle(self, project_id: str) -> dict[str, str | list]:
        """Markdown-friendly bundle injected into every agent/worker prompt."""
        r = await self.db.execute(select(Project).where(Project.id == project_id))
        project = r.scalar_one_or_none()
        if not project:
            return {}

        k = await self.get_or_create(project_id)
        await self.sync_from_project(project)

        return {
            "project_name": project.name,
            "description": project.description,
            "tech_stack": project.tech_stack or k.frameworks,
            "coding_rules": project.coding_rules,
            "security_rules": project.security_rules,
            "architecture": k.architecture,
            "design_patterns": k.design_patterns,
            "frameworks": k.frameworks,
            "naming_conventions": k.naming_conventions,
            "code_style": k.code_style,
            "adrs": k.adrs if isinstance(k.adrs, list) else [],
            "lessons_learned": k.lessons_learned,
            "key_decisions": k.key_decisions,
            "known_issues": k.known_issues,
            "best_practices": k.best_practices,
            "file_overview": k.file_overview,
            "repo_structure": k.repo_structure,
            "documentation": k.documentation,
        }

    def format_for_prompt(self, bundle: dict) -> str:
        if not bundle:
            return ""
        sections = [
            ("Projekt", bundle.get("project_name", "")),
            ("Beschreibung", bundle.get("description", "")),
            ("Technologie", bundle.get("tech_stack", "")),
            ("Architektur", bundle.get("architecture", "")),
            ("Design Patterns", bundle.get("design_patterns", "")),
            ("Frameworks", bundle.get("frameworks", "")),
            ("Namenskonventionen", bundle.get("naming_conventions", "")),
            ("Code Style", bundle.get("code_style", "")),
            ("Coding Rules", bundle.get("coding_rules", "")),
            ("Security Rules", bundle.get("security_rules", "")),
            ("Lessons Learned", bundle.get("lessons_learned", "")),
            ("Wichtige Entscheidungen", bundle.get("key_decisions", "")),
            ("Bekannte Probleme", bundle.get("known_issues", "")),
            ("Best Practices", bundle.get("best_practices", "")),
            ("Dateiübersicht", bundle.get("file_overview", "")),
            ("Repository Struktur", bundle.get("repo_structure", "")),
            ("Dokumentation", bundle.get("documentation", "")),
        ]
        lines: list[str] = ["## Projektwissen (AI Orchestra Knowledge Layer)", ""]
        for title, body in sections:
            if body and str(body).strip():
                lines.append(f"### {title}")
                lines.append(str(body).strip())
                lines.append("")
        adrs = bundle.get("adrs")
        if adrs:
            lines.append("### ADRs")
            for adr in adrs:
                lines.append(f"- {adr}")
            lines.append("")
        return "\n".join(lines).strip()
