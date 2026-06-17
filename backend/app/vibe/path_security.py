"""Secure path validation for worker project roots."""

from __future__ import annotations

import os
from pathlib import Path


def normalize_path(path: str) -> Path:
    return Path(os.path.normpath(os.path.abspath(path)))


def is_path_within_root(candidate: str, root: str) -> bool:
    """Return True if candidate is inside root (prevents directory traversal)."""
    try:
        cand = normalize_path(candidate)
        root_path = normalize_path(root)
        cand.relative_to(root_path)
        return True
    except (ValueError, OSError):
        return False


def resolve_project_path(project_path: str, allowed_roots: list[str]) -> str | None:
    """Resolve project path if it lies within any allowed root."""
    normalized = normalize_path(project_path)
    for root in allowed_roots:
        if is_path_within_root(str(normalized), root):
            return str(normalized)
    return None


def discover_projects(roots: list[str]) -> list[dict[str, str]]:
    """Discover git projects under configured roots."""
    projects: list[dict[str, str]] = []
    seen: set[str] = set()
    for root in roots:
        root_path = normalize_path(root)
        if not root_path.is_dir():
            continue
        candidates = [root_path]
        try:
            for child in root_path.iterdir():
                if child.is_dir() and not child.name.startswith("."):
                    candidates.append(child)
        except OSError:
            continue
        for path in candidates:
            key = str(path)
            if key in seen:
                continue
            seen.add(key)
            is_git = (path / ".git").exists()
            projects.append(
                {
                    "name": path.name,
                    "local_path": key,
                    "is_git": str(is_git).lower(),
                }
            )
    return projects
