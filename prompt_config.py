"""
prompt_config.py
----------------
Centralized prompt registry for all AI agents.

Prompts are stored in ``config/prompts.yaml`` and loaded once per process.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from logging_config import get_logger

logger = get_logger(__name__)

_PROMPTS_PATH = Path(__file__).resolve().parent / "config" / "prompts.yaml"
_TOKEN_PATTERN = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


@lru_cache(maxsize=1)
def _load_prompts() -> dict[str, Any]:
    if not _PROMPTS_PATH.exists():
        raise FileNotFoundError(f"Prompt configuration file not found: {_PROMPTS_PATH}")

    with _PROMPTS_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if not isinstance(data, dict):
        raise ValueError("prompts.yaml must contain a top-level mapping object.")

    logger.info("Prompt registry loaded from %s", _PROMPTS_PATH.name)
    return data


def get_prompt(dotted_key: str) -> str:
    """Return a prompt string by dotted key (e.g. ``summary_agent.system``)."""
    current: Any = _load_prompts()
    for key in dotted_key.split("."):
        if not isinstance(current, dict) or key not in current:
            raise KeyError(f"Prompt key not found: {dotted_key}")
        current = current[key]

    if not isinstance(current, str):
        raise TypeError(
            f"Prompt key '{dotted_key}' must resolve to string, got {type(current).__name__}."
        )
    return current.strip()


def render_prompt(dotted_key: str, values: dict[str, Any] | None = None) -> str:
    """Render a prompt with token replacements like ``{{DB_SCHEMA}}``."""
    prompt = get_prompt(dotted_key)
    values = values or {}

    for token, value in values.items():
        prompt = prompt.replace(f"{{{{{token}}}}}", str(value))

    unresolved = [m.group(1) for m in _TOKEN_PATTERN.finditer(prompt)]
    if unresolved:
        logger.warning(
            "Unresolved prompt tokens for '%s': %s",
            dotted_key,
            ", ".join(sorted(set(unresolved))),
        )

    return prompt
