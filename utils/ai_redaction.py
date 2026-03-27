from __future__ import annotations

import os
import re
from typing import Iterable, Mapping


def _env_true(name: str, default: str = "true") -> bool:
    value = os.getenv(name, default).strip().lower()
    return value in {"1", "true", "yes", "y", "on"}


REDACT_ENABLED = _env_true("AI_REDACT_PII", "true")

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"\b(?:\+?\d[\d\s\-]{6,}\d)\b")
_ID_RE = re.compile(r"\b(?:IC|NRIC|TIN|SST|GST|VAT)\s*[:#]?\s*\w+\b", re.IGNORECASE)

# Column-based redaction keeps LLM from seeing PII in results.
_SENSITIVE_COLUMN_PATTERNS = [
    r"^cust_",
    r"^slm_",
    r"^usr_",
    r"_email",
    r"_phone",
    r"_address",
    r"_tin",
    r"_password",
    r"_receipt",
    r"_invoice",
    r"_buyer_id",
    r"_sst_reg_no",
    r"_reg_no",
]


def _is_sensitive_column(col: str) -> bool:
    lc = col.lower()
    return any(re.search(pat, lc) for pat in _SENSITIVE_COLUMN_PATTERNS)


def redact_text(text: str) -> str:
    if not REDACT_ENABLED or not text:
        return text
    redacted = _EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    redacted = _PHONE_RE.sub("[REDACTED_PHONE]", redacted)
    redacted = _ID_RE.sub("[REDACTED_ID]", redacted)
    return redacted


def redact_rows(rows: list[Mapping[str, object]], columns: Iterable[str]) -> list[dict[str, object]]:
    if not REDACT_ENABLED or not rows:
        return [dict(r) for r in rows]
    cols = list(columns)
    sensitive = {c for c in cols if _is_sensitive_column(c)}
    redacted_rows: list[dict[str, object]] = []
    for row in rows:
        new_row: dict[str, object] = {}
        for c in cols:
            value = row.get(c, "")
            if c in sensitive:
                new_row[c] = "[REDACTED]"
            elif isinstance(value, str):
                new_row[c] = redact_text(value)
            else:
                new_row[c] = value
        redacted_rows.append(new_row)
    return redacted_rows


def redact_columns(columns: Iterable[str]) -> list[str]:
    if not REDACT_ENABLED:
        return list(columns)
    return ["[REDACTED]" if _is_sensitive_column(c) else c for c in columns]
