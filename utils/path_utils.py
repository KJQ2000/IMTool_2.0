"""
Filesystem helpers for safe repo-local uploads and archived files.
"""

from __future__ import annotations

import re
from pathlib import Path

_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1F]')


def sanitize_filename_component(value: str, fallback: str) -> str:
    """Return a Windows-safe filename component."""
    cleaned = _INVALID_FILENAME_CHARS.sub("", str(value).strip().replace(" ", "_"))
    cleaned = cleaned.rstrip(" .")
    return cleaned or fallback


def sanitize_uploaded_filename(filename: str, fallback_stem: str = "upload") -> str:
    """Return a safe archive filename preserving the original extension."""
    original = Path(str(filename or ""))
    stem = sanitize_filename_component(original.stem or fallback_stem, fallback_stem)
    suffix = sanitize_filename_component(original.suffix.lower(), "")
    return f"{stem}{suffix}" if suffix.startswith(".") else stem


def resolve_repo_local_file(path_value: str | Path, repo_root: str | Path) -> Path | None:
    """Resolve a file path and ensure it stays within the repository root."""
    try:
        root = Path(repo_root).resolve()
        candidate = Path(path_value)
        if not candidate.is_absolute():
            candidate = root / candidate
        resolved = candidate.resolve()
    except (OSError, RuntimeError, TypeError):
        return None

    if resolved != root and root not in resolved.parents:
        return None
    if not resolved.exists() or not resolved.is_file():
        return None
    return resolved
