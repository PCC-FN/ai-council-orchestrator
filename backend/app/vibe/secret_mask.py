"""Mask secrets before logging or sending to clients."""

from __future__ import annotations

import re

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)([^\s'\"]+)"), r"\1********"),
    (re.compile(r"(?i)(bearer\s+)([a-zA-Z0-9._\-]+)"), r"\1********"),
    (re.compile(r"(?i)(password\s*[=:]\s*)([^\s'\"]+)"), r"\1********"),
    (re.compile(r"(?i)(secret\s*[=:]\s*)([^\s'\"]+)"), r"\1********"),
    (re.compile(r"(?i)(token\s*[=:]\s*)([^\s'\"]+)"), r"\1********"),
    (re.compile(r"(?i)(database_url\s*[=:]\s*)([^\s'\"]+)"), r"\1********"),
    (re.compile(r"sk-[a-zA-Z0-9]{8,}"), "sk-********"),
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END"), "[PRIVATE KEY REDACTED]"),
]


def mask_secrets(text: str) -> str:
    if not text:
        return text
    out = text
    for pattern, repl in _PATTERNS:
        out = pattern.sub(repl, out)
    return out


def mask_dict(data: dict | list | str | int | float | bool | None) -> dict | list | str | int | float | bool | None:
    if isinstance(data, str):
        return mask_secrets(data)
    if isinstance(data, list):
        return [mask_dict(x) for x in data]
    if isinstance(data, dict):
        return {k: mask_dict(v) for k, v in data.items()}
    return data
