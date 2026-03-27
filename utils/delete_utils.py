from __future__ import annotations

import re
from typing import Iterable


_SPLIT_PATTERN = re.compile(r"[,\n;\s]+")


def parse_id_list(raw: str | None) -> list[str]:
    """Parse a raw ID input into a clean, de-duplicated list."""
    if not raw:
        return []
    tokens = [token.strip() for token in _SPLIT_PATTERN.split(raw) if token.strip()]
    seen = set()
    result: list[str] = []
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        result.append(token)
    return result


def format_id_list(ids: Iterable[str]) -> str:
    return ", ".join(ids)
