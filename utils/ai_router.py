from __future__ import annotations

import os
import re


def _env_true(name: str, default: str = "true") -> bool:
    value = os.getenv(name, default).strip().lower()
    return value in {"1", "true", "yes", "y", "on"}


DB_ROUTER_ENABLED = _env_true("AI_FORCE_DB_ROUTER", "true")

_DB_PATTERNS = [
    r"\bhow many\b",
    r"\bcount\b",
    r"\btotal\b",
    r"\bsum\b",
    r"\baverage\b",
    r"\bavg\b",
    r"\blist\b",
    r"\bshow\b",
    r"\btop\b",
    r"\bhighest\b",
    r"\blowest\b",
    r"\bmost\b",
    r"\bstock\b",
    r"\binventory\b",
    r"\bsales\b",
    r"\bbookings?\b",
    r"\bcustomers?\b",
    r"\bpurchases?\b",
    r"\bsalesmen?\b",
    r"\brevenue\b",
    r"\bprofit\b",
    r"\bbooked\b",
    r"\bsold\b",
    r"\bin stock\b",
    r"\bthis year\b",
    r"\bthis month\b",
    r"\btoday\b",
    r"\byesterday\b",
]


def should_force_database(question: str) -> bool:
    if not DB_ROUTER_ENABLED:
        return False
    q = question.strip().lower()
    if not q:
        return False
    return any(re.search(pat, q) for pat in _DB_PATTERNS)
