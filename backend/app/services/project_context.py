from __future__ import annotations

import os
import re
from pathlib import Path

from app.config import get_settings

_SENSITIVE_PART = re.compile(
    r"(\.env$|\.key$|\.pem$|credentials|id_rsa|\.git[/\\]|node_modules|vendor|[/\\]dist[/\\]|[/\\]build[/\\])",
    re.I,
)


def resolve_safe_path(repository_path: str, relative: str) -> Path | None:
    if not repository_path:
        return None
    root = Path(repository_path).resolve()
    if not root.exists() or not root.is_dir():
        return None
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    if _SENSITIVE_PART.search(str(candidate)):
        return None
    return candidate


def list_project_files(repository_path: str, max_files: int = 200) -> list[str]:
    root = Path(repository_path).resolve()
    if not root.is_dir():
        return []
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        pruned = []
        for d in list(dirnames):
            low = d.lower()
            if low in {"node_modules", "vendor", "dist", "build", ".git"}:
                pruned.append(d)
            elif _SENSITIVE_PART.search(low):
                pruned.append(d)
        for d in pruned:
            dirnames.remove(d)
        for fn in filenames:
            p = Path(dirpath) / fn
            rel = p.relative_to(root).as_posix()
            if _SENSITIVE_PART.search(rel):
                continue
            if len(out) >= max_files:
                return out
            out.append(rel)
    return sorted(out)


def read_safe_file_sync(repository_path: str, relative: str) -> str | None:
    path = resolve_safe_path(repository_path, relative)
    if not path or not path.is_file():
        return None
    max_b = get_settings().max_project_file_bytes
    try:
        sz = path.stat().st_size
    except OSError:
        return None
    if sz > max_b:
        return f"[FILE TOO LARGE: {path.name} > {max_b} bytes]"
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def build_context_snippet_sync(repository_path: str, max_chars: int = 6000) -> str:
    files = list_project_files(repository_path, max_files=80)
    if not files:
        return ""
    lines = ["### Indexed files (sample)", ""]
    lines.extend(f"- {f}" for f in files[:50])
    text = "\n".join(lines)
    return text[:max_chars]
