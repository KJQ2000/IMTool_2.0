"""
utils/log_context.py
--------------------
Per-request logging context helpers using ``contextvars``.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Any, Generator
from uuid import uuid4

_TRACE_ID: ContextVar[str] = ContextVar("trace_id", default="-")
_USER_EMAIL: ContextVar[str] = ContextVar("user_email", default="-")


def new_trace_id() -> str:
    """Return a short unique trace identifier."""
    return uuid4().hex[:12]


def get_log_context() -> dict[str, str]:
    """Return active logging context fields."""
    return {
        "trace_id": _TRACE_ID.get("-"),
        "user_email": _USER_EMAIL.get("-"),
    }


def set_log_context(
    *, trace_id: str | None = None, user_email: str | None = None
) -> None:
    """Set context values for the current execution flow."""
    if trace_id is not None:
        _TRACE_ID.set(str(trace_id))
    if user_email is not None:
        _USER_EMAIL.set(str(user_email))


@contextmanager
def log_context(
    *, trace_id: str | None = None, user_email: str | None = None
) -> Generator[None, None, None]:
    """Temporarily apply logging context values for a block."""
    tokens: list[tuple[ContextVar[str], Token[str]]] = []
    try:
        if trace_id is not None:
            tokens.append((_TRACE_ID, _TRACE_ID.set(str(trace_id))))
        if user_email is not None:
            tokens.append((_USER_EMAIL, _USER_EMAIL.set(str(user_email))))
        yield
    finally:
        for var, token in reversed(tokens):
            var.reset(token)
