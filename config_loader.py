"""
config_loader.py
────────────────
Configuration-Driven Data Access Paradigm.

Loads ``config.yaml`` at application startup and provides dictionary-based
access to all SQL queries.  This completely decouples SQL from the Python
business logic, enabling DB administrators to modify queries without
touching application code.

Usage:
    from config_loader import get_query, get_config

    sql = get_query("stock.fetch_all")
    schema = get_config("app.schema")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
import streamlit as st

from logging_config import get_logger

logger = get_logger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "config.yaml"


@st.cache_data(show_spinner=False)
def _load_config(config_mtime_ns: int) -> dict:
    """Parse config.yaml into a Python dict.

    The config file is reloaded automatically whenever its modified timestamp
    changes, which avoids stale query definitions during active development.
    """
    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {_CONFIG_PATH}. "
            "Ensure config.yaml exists in the project root."
        )

    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    logger.info("config.yaml loaded successfully (%d top-level keys).", len(config))
    return config


def get_config(dotted_key: str) -> Any:
    """Retrieve a value from config.yaml using dot-separated key notation.

    Examples:
        get_config("app.schema")       → "konghin"
        get_config("sequences.stock")  → "stk_id_seq"
        get_config("prefixes.sale")    → "SALE"
    """
    config_mtime_ns = _CONFIG_PATH.stat().st_mtime_ns
    config = _load_config(config_mtime_ns)
    keys = dotted_key.split(".")
    value = config
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            raise KeyError(f"Config key '{dotted_key}' not found (failed at '{key}').")
        value = value[key]
    return value


def get_query(dotted_key: str, schema: str | None = None) -> str:
    """Retrieve an SQL query from config.yaml and inject the schema name.

    The query string may contain ``{schema}`` placeholders which are
    replaced with the active database schema (from secrets or config).

    Parameters
    ----------
    dotted_key:
        Dot-separated path to the query, e.g. "stock.fetch_all".
    schema:
        Override schema name.  Defaults to ``st.secrets`` or config.yaml.

    Returns
    -------
    The SQL query string with schema injected, ready for parameterized execution.
    """
    query = get_config(dotted_key)
    if not isinstance(query, str):
        raise TypeError(
            f"Config key '{dotted_key}' returned {type(query).__name__}, expected str."
        )

    # Resolve schema name
    if schema is None:
        try:
            schema = st.secrets["connections"]["postgresql"]["schema"]
        except (KeyError, FileNotFoundError):
            schema = get_config("app.schema")

    return query.strip().format(schema=schema)


def get_sequence_name(table: str) -> str:
    """Return the PostgreSQL sequence name for the given table."""
    return get_config(f"sequences.{table}")


def get_prefix(table: str) -> str:
    """Return the primary key prefix for the given table."""
    return get_config(f"prefixes.{table}")
