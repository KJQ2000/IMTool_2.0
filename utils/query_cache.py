from __future__ import annotations

from typing import Any

import streamlit as st

from database_manager import DatabaseManager


@st.cache_data(show_spinner=False, ttl=60)
def fetch_rows_cached(
    query_key: str,
    params: tuple[Any, ...] | None = None,
) -> list[dict[str, Any]]:
    return DatabaseManager.get_instance().fetch_all(query_key, params)


@st.cache_data(show_spinner=False, ttl=60)
def fetch_scalar_cached(
    query_key: str,
    params: tuple[Any, ...] | None = None,
) -> Any:
    return DatabaseManager.get_instance().fetch_scalar(query_key, params)


def clear_query_caches() -> None:
    fetch_rows_cached.clear()
    fetch_scalar_cached.clear()
