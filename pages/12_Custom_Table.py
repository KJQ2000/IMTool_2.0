"""
pages/12_🧩_Custom_Stock_Table.py — Custom stock-centric reporting page

Lets users choose visible columns and filter stock rows by semicolon-delimited
``stk_tag`` values while keeping related purchase, salesman, sale, booking,
and customer context in a single table.
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd
import streamlit as st

from auth_controller import require_auth
from database_manager import DatabaseManager
from logging_config import get_logger
from utils.html_utils import escape_html

logger = get_logger(__name__)
require_auth()

st.markdown("## 🧩 Custom Stock Table")
st.caption(
    "Build your own stock-centric view with purchase, salesman, sale, booking, "
    "and customer details in one table."
)

db = DatabaseManager.get_instance()

PREFIX_LABELS = [
    ("sale_cust_", "Sale Customer "),
    ("book_cust_", "Booking Customer "),
    ("linked_cust_", "Linked Customer "),
    ("stk_", "Stock "),
    ("pur_", "Purchase "),
    ("slm_", "Salesman "),
    ("sale_", "Sale "),
    ("book_", "Booking "),
]

GROUP_ORDER = [
    ("Stock", ("stk_",)),
    ("Purchase", ("pur_",)),
    ("Salesman", ("slm_",)),
    ("Sale Customer", ("sale_cust_",)),
    ("Sale", ("sale_",)),
    ("Booking Customer", ("book_cust_",)),
    ("Booking", ("book_",)),
    ("Linked Customer", ("linked_cust_",)),
]

DEFAULT_COLUMNS = [
    "stk_id",
    "stk_status",
    "stk_type",
    "stk_pattern",
    "stk_weight",
    "stk_tag",
    "pur_code",
    "slm_name",
    "linked_cust_name",
    "sale_id",
    "book_id",
]


@st.cache_data(show_spinner=False, ttl=60)
def load_custom_rows() -> list[dict[str, Any]]:
    return DatabaseManager.get_instance().fetch_all("stock.fetch_custom_table")


def split_tags(value: Any) -> list[str]:
    if value is None:
        return []
    return [tag.strip() for tag in str(value).split(";") if tag and tag.strip()]


def prettify_text(value: str) -> str:
    return (
        value.replace("_", " ")
        .title()
        .replace(" Id", " ID")
        .replace(" Tin", " TIN")
        .replace(" Sst", " SST")
        .replace(" Msic", " MSIC")
        .replace(" Rm", " RM")
    )


def prettify_column(column_name: str) -> str:
    for prefix, label in PREFIX_LABELS:
        if column_name.startswith(prefix):
            suffix = column_name[len(prefix):]
            return f"{label}{prettify_text(suffix)}"
    return prettify_text(column_name)


def get_column_group(column_name: str) -> str:
    for group_name, prefixes in GROUP_ORDER:
        if any(column_name.startswith(prefix) for prefix in prefixes):
            return group_name
    return "Other"


def get_grouped_columns(columns: list[str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for group_name, _prefixes in GROUP_ORDER:
        matching = sorted(
            [column for column in columns if get_column_group(column) == group_name],
            key=prettify_column,
        )
        if matching:
            grouped[group_name] = matching

    other_columns = sorted(
        [column for column in columns if get_column_group(column) == "Other"],
        key=prettify_column,
    )
    if other_columns:
        grouped["Other"] = other_columns

    return grouped


def initialize_column_state(columns: list[str]) -> None:
    available_defaults = {column for column in DEFAULT_COLUMNS if column in columns}
    for column in columns:
        state_key = f"custom_table_col_{column}"
        if state_key not in st.session_state:
            st.session_state[state_key] = column in available_defaults


def set_all_columns(columns: list[str], selected: bool) -> None:
    for column in columns:
        st.session_state[f"custom_table_col_{column}"] = selected


def reset_default_columns(columns: list[str]) -> None:
    available_defaults = {column for column in DEFAULT_COLUMNS if column in columns}
    for column in columns:
        st.session_state[f"custom_table_col_{column}"] = column in available_defaults


def get_selected_columns(columns: list[str]) -> list[str]:
    return [
        column for column in columns
        if st.session_state.get(f"custom_table_col_{column}", False)
    ]


def get_distinct_tags(rows: list[dict[str, Any]]) -> list[str]:
    distinct_tags: set[str] = set()
    for row in rows:
        distinct_tags.update(split_tags(row.get("stk_tag")))
    return sorted(distinct_tags, key=str.casefold)


def apply_tag_filter(df: pd.DataFrame, selected_tags: list[str], mode: str) -> pd.DataFrame:
    if not selected_tags or "stk_tag" not in df.columns:
        return df

    selected_set = set(selected_tags)
    tag_sets = df["stk_tag"].apply(lambda value: set(split_tags(value)))

    if mode == "ALL":
        mask = tag_sets.apply(lambda tags: selected_set.issubset(tags))
    else:
        mask = tag_sets.apply(lambda tags: bool(tags & selected_set))

    return df[mask]


def apply_search_filter(df: pd.DataFrame, search_text: str) -> pd.DataFrame:
    query = search_text.strip()
    if not query:
        return df

    searchable = (
        df.fillna("")
        .astype(str)
        .apply(lambda row: " ".join(row.values), axis=1)
    )
    return df[searchable.str.contains(query, case=False, na=False)]


def apply_sort(df: pd.DataFrame, sort_column: str, ascending: bool) -> pd.DataFrame:
    if not sort_column or sort_column not in df.columns:
        return df

    try:
        return df.sort_values(
            by=sort_column,
            ascending=ascending,
            na_position="last",
            kind="stable",
        )
    except TypeError:
        sortable = df.copy()
        sortable[sort_column] = sortable[sort_column].astype(str)
        return sortable.sort_values(
            by=sort_column,
            ascending=ascending,
            na_position="last",
            kind="stable",
        )


try:
    rows = load_custom_rows()
except Exception as exc:
    st.error(f"Failed to load custom stock data: {exc}")
    logger.error("Custom stock table load failed", exc_info=True)
    st.stop()

if not rows:
    st.info("No stock records found.")
    st.stop()

df = pd.DataFrame(rows)
all_columns = list(df.columns)
grouped_columns = get_grouped_columns(all_columns)
distinct_tags = get_distinct_tags(rows)
initialize_column_state(all_columns)

selector_col, content_col = st.columns([2.0, 3.0], gap="large")

with selector_col:
    st.markdown("### Visible Columns")
    st.caption(f"{len(all_columns)} available columns")

    action_col1, action_col2, action_col3 = st.columns(3)
    with action_col1:
        if st.button("All", help="Select All Columns", use_container_width=True):
            set_all_columns(all_columns, True)
            st.rerun()
    with action_col2:
        if st.button("Clear", help="Clear All Columns", use_container_width=True):
            set_all_columns(all_columns, False)
            st.rerun()
    with action_col3:
        if st.button("Reset", help="Reset Defaults", use_container_width=True):
            reset_default_columns(all_columns)
            st.rerun()

    for group_name, group_columns in grouped_columns.items():
        with st.expander(f"{group_name} ({len(group_columns)})", expanded=group_name == "Stock"):
            for column in group_columns:
                st.checkbox(
                    prettify_column(column),
                    key=f"custom_table_col_{column}",
                )

selected_columns = get_selected_columns(all_columns)
filtered_df = df.copy()

with content_col:
    top_left, top_right = st.columns([1.4, 2.6], gap="large")

    with top_left:
        search_text = st.text_input(
            "Search",
            placeholder="Search across all loaded fields...",
        )

        sort_candidates = selected_columns if selected_columns else all_columns
        default_sort = "stk_created_at" if "stk_created_at" in sort_candidates else sort_candidates[0]
        sort_column = st.selectbox(
            "Sort By",
            sort_candidates,
            index=sort_candidates.index(default_sort),
            format_func=prettify_column,
        )
        sort_order = st.selectbox("Order", ["Descending", "Ascending"], index=0)

    with top_right:
        st.markdown("**Filter by stk_tag**")
        tag_mode_label = st.radio(
            "Match condition",
            ["Any selected tags", "All selected tags"],
            horizontal=True,
            label_visibility="collapsed",
        )
        selected_tags = st.multiselect(
            "Select tags",
            options=distinct_tags,
            default=[],
            label_visibility="collapsed",
        )

    with st.expander("🎯 Column Dropdown Filters", expanded=False):
        st.caption("Filter data further by selecting specific values for any visible column.")
        filter_cols = st.columns(4)
        column_filters = {}
        for i, col in enumerate(selected_columns):
            unique_vals = df[col].dropna().unique().tolist()
            if not unique_vals:
                continue
            
            try:
                unique_vals = sorted(unique_vals)
            except TypeError:
                unique_vals = sorted(unique_vals, key=lambda x: str(x).lower())

            with filter_cols[i % 4]:
                selected_vals = st.multiselect(
                    prettify_column(col),
                    options=unique_vals,
                    default=[],
                    format_func=str,
                    placeholder="All...",
                )
                if selected_vals:
                    column_filters[col] = selected_vals

    filtered_df = apply_tag_filter(
        filtered_df,
        selected_tags,
        "ALL" if tag_mode_label == "All selected tags" else "ANY",
    )
    filtered_df = apply_search_filter(filtered_df, search_text)
    
    for col, vals in column_filters.items():
        filtered_df = filtered_df[filtered_df[col].isin(vals)]

    filtered_df = apply_sort(filtered_df, sort_column, sort_order == "Ascending")

    metrics_col1, metrics_col2, metrics_col3 = st.columns(3)
    with metrics_col1:
        st.metric("Filtered Rows", len(filtered_df))
    with metrics_col2:
        st.metric("Total Rows", len(df))
    with metrics_col3:
        st.metric("Selected Columns", len(selected_columns))

    if not selected_columns:
        st.info("Please select at least one column.")
        st.stop()

    page_size = st.selectbox("Rows Per Page", [25, 50, 100, "All"], index=0)
    display_df = filtered_df[selected_columns].copy()

    if page_size == "All":
        paged_df = display_df
        st.caption(f"Showing all {len(display_df)} filtered row(s).")
    else:
        total_pages = max(1, math.ceil(len(display_df) / int(page_size)))
        page_number = st.number_input(
            "Page",
            min_value=1,
            max_value=total_pages,
            value=1,
            step=1,
        )
        start_idx = (page_number - 1) * int(page_size)
        end_idx = start_idx + int(page_size)
        paged_df = display_df.iloc[start_idx:end_idx]
        if display_df.empty:
            st.caption("No rows match the current filters.")
        else:
            st.caption(
                f"Showing rows {start_idx + 1} to {min(end_idx, len(display_df))} "
                f"of {len(display_df)} filtered row(s) across {total_pages} page(s)."
            )

    st.dataframe(
        paged_df,
        use_container_width=True,
        height=650,
        hide_index=True,
    )
