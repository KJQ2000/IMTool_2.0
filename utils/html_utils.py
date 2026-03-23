"""
HTML safety helpers for Streamlit pages that use ``unsafe_allow_html=True``.
"""

from __future__ import annotations

from html import escape


def escape_html(value: object) -> str:
    """Return an HTML-escaped string representation of ``value``."""
    return escape("" if value is None else str(value), quote=True)


def format_multiline_html(value: object) -> str:
    """Escape HTML-sensitive characters and preserve newlines with ``<br>``."""
    return escape_html(value).replace("\n", "<br>")
