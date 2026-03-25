"""
utils/editable_table.py — Reusable editable table with column filtering and save.

Provides:
  - render_filterable_editor(): Shows column filters + st.data_editor + Save button
  - save_table_changes(): Diffs edited vs original DataFrame and persists changes
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd
import streamlit as st

from database_manager import DatabaseManager
from logging_config import get_logger
from utils.query_cache import clear_query_caches

logger = get_logger(__name__)


def _coerce_value(value: Any) -> Any:
    """Coerce pandas/numpy types to Python-native types for DB insert."""
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if hasattr(value, "item"):  # numpy scalar
        return value.item()
    return value


def render_pagination_controls(
    *,
    table_key: str,
    total_rows: int,
    default_page_size: int = 50,
    page_size_options: tuple[int, ...] = (25, 50, 100),
) -> tuple[int, int, int]:
    """Render pagination controls and return (page_size, page_number, offset)."""
    size_key = f"{table_key}_page_size"
    page_key = f"{table_key}_page"
    is_expanded = st.session_state.get(f"{table_key}_is_expanded", False)

    # Determine current page size without conflicting with widget key
    current_size = st.session_state.get(size_key, default_page_size)
    if current_size not in page_size_options:
        current_size = default_page_size

    if page_key not in st.session_state:
        st.session_state[page_key] = 1

    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        page_size_val = st.selectbox(
            "Rows per page",
            list(page_size_options),
            index=list(page_size_options).index(current_size),
            key=size_key,
        )
    total_pages = max(1, (total_rows + page_size_val - 1) // page_size_val)
    st.session_state[page_key] = min(max(1, int(st.session_state[page_key])), total_pages)
    with c2:
        page_number = st.number_input(
            "Page",
            min_value=1,
            max_value=total_pages,
            value=min(st.session_state[page_key], total_pages),
            step=1,
            key=page_key,
        )
    with c3:
        start_row = 0 if total_rows == 0 else (page_number - 1) * page_size_val + 1
        end_row = min(total_rows, page_number * page_size_val)
        st.caption(f"Showing database rows {start_row}-{end_row} of {total_rows}")

    offset_val = (page_number - 1) * page_size_val
    if is_expanded:
        return max(1, total_rows), 1, 0
    return int(page_size_val), int(page_number), int(offset_val)


def render_filterable_editor(
    df: pd.DataFrame,
    table_key: str,
    id_column: str,
    *,
    height: int = 500,
    disabled_columns: list[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Render column filters + editable table. Returns (original_df, edited_df).

    Parameters
    ----------
    df : Original DataFrame from database.
    table_key : Unique key prefix for Streamlit widgets.
    id_column : Primary key column name (e.g. 'stk_id').
    height : Table height in pixels.
    disabled_columns : Columns that should not be editable.
    """
    if df.empty:
        st.info("No records found.")
        return df, df

    if disabled_columns is None:
        disabled_columns = [id_column]
    elif id_column not in disabled_columns:
        disabled_columns = [id_column] + list(disabled_columns)

    # ── Column Filters ──
    with st.expander("🔎 Column Filters", expanded=False):
        filter_cols = st.columns(min(4, len(df.columns)))
        filters: dict[str, Any] = {}

        for i, col in enumerate(df.columns):
            col_container = filter_cols[i % len(filter_cols)]
            with col_container:
                unique_vals = df[col].dropna().unique()

                # Categorical: <= 20 unique values → multiselect
                if len(unique_vals) <= 20 and df[col].dtype == object:
                    selected = st.multiselect(
                        col,
                        options=sorted(str(v) for v in unique_vals),
                        key=f"{table_key}_filter_{col}",
                    )
                    if selected:
                        filters[col] = selected
                else:
                    # Text/numeric search
                    search = st.text_input(
                        col,
                        key=f"{table_key}_filter_{col}",
                        placeholder=f"Filter {col}...",
                    )
                    if search.strip():
                        filters[col] = search.strip()

    # Set index to id_column so edits track rows regardless of dataset pagination
    df_indexed = df.set_index(id_column, drop=False)
    filtered_df = df_indexed.copy()
    for col, filter_val in filters.items():
        if isinstance(filter_val, list):
            filtered_df = filtered_df[filtered_df[col].astype(str).isin(filter_val)]
        else:
            filtered_df = filtered_df[
                filtered_df[col].astype(str).str.contains(str(filter_val), case=False, na=False)
            ]

    st.caption(f"Showing {len(filtered_df)} of {len(df_indexed)} record(s)")

    # ── Editable Table Setup ──
    is_expanded_key = f"{table_key}_is_expanded"
    global_edits_key = f"{table_key}_global_edits"
    full_df_key = f"{table_key}_full_df"

    if global_edits_key not in st.session_state:
        st.session_state[global_edits_key] = {}
    global_edits = st.session_state[global_edits_key]

    is_expanded = st.session_state.get(is_expanded_key, False)

    # 1. Prepare UI dataframe by baking global edits into the true original filtered rows
    df_for_editor = filtered_df.copy()
    for row_pk, changes in global_edits.items():
        if row_pk in df_for_editor.index:
            for col, val in changes.items():
                if col in df_for_editor.columns:
                    df_for_editor.loc[row_pk, col] = val

    # Stable editor key — only ONE editor is rendered at a time (if/else)
    editor_key = f"{table_key}_editor"

    # Expand / Collapse buttons
    col_btn, _ = st.columns([1, 5])
    with col_btn:
        if is_expanded:
            if st.button("↙️ Collapse Table", key=f"{table_key}_collapse_btn"):
                st.session_state[is_expanded_key] = False
                st.rerun()
        else:
            if st.button("↗️ Expand Table (All Data)", key=f"{table_key}_expand_btn"):
                st.session_state[is_expanded_key] = True
                st.rerun()

    def process_edits(edited_df: pd.DataFrame):
        """Extract user edits by diffing against the true base dataset."""
        for idx in edited_df.index:
            for col in edited_df.columns:
                try:
                    orig_val = filtered_df.loc[idx, col]
                    edit_val = edited_df.loc[idx, col]
                except KeyError:
                    continue
                if pd.isna(orig_val) and pd.isna(edit_val):
                    continue
                if str(orig_val) != str(edit_val):
                    global_edits.setdefault(idx, {})[col] = edit_val
                else:
                    # Value was reverted to original — clean up
                    if idx in global_edits and col in global_edits[idx]:
                        del global_edits[idx][col]
                        if not global_edits[idx]:
                            del global_edits[idx]

    if is_expanded:
        # Cache full dataset for safely restoring edited hidden rows later
        st.session_state[full_df_key] = filtered_df

        # In-page expanded view — shows full dataset in a tall editor
        edited_ui_df = st.data_editor(
            df_for_editor,
            use_container_width=True,
            height=min(800, max(400, len(df_for_editor) * 36 + 40)),
            num_rows="fixed",
            disabled=disabled_columns,
            key=f"{editor_key}_exp",
        )
        process_edits(edited_ui_df)
    else:
        # Normal main table view — paginated
        edited_ui_df = st.data_editor(
            df_for_editor,
            use_container_width=True,
            height=height,
            num_rows="fixed",
            disabled=disabled_columns,
            key=f"{editor_key}_main",
        )
        process_edits(edited_ui_df)

    # 3. Stitch hidden edited rows from total set back so DB saves them
    final_original_df = filtered_df.copy()
    final_edited_df = edited_ui_df.copy()

    if global_edits and not is_expanded and full_df_key in st.session_state:
        full_df = st.session_state[full_df_key]
        missing_ids = [rid for rid in global_edits if rid not in final_edited_df.index and rid in full_df.index]

        if missing_ids:
            missing_orig = full_df.loc[missing_ids]
            final_original_df = pd.concat([final_original_df, missing_orig])

            missing_edited = missing_orig.copy()
            for rid in missing_ids:
                if rid in global_edits and global_edits[rid]:
                    for col, val in global_edits[rid].items():
                        if col in missing_edited.columns:
                            missing_edited.loc[rid, col] = val
            final_edited_df = pd.concat([final_edited_df, missing_edited])

    if global_edits:
        has_active_edits = any(changes for changes in global_edits.values())

        if has_active_edits:
            st.markdown("---")
            with st.expander("📝 Unsaved Changes Preview", expanded=True):
                for row_id, changes in global_edits.items():
                    if not changes:
                        continue
                    try:
                        for col, new_val in changes.items():
                            orig_val = "?"
                            if row_id in final_original_df.index:
                                orig_val = final_original_df.loc[row_id, col]
                            st.markdown(f"- **Row ID {row_id}** &nbsp;👉&nbsp; `{col}` changed from `{orig_val}` to `{new_val}`")
                    except Exception:
                        pass

    return final_original_df, final_edited_df


def save_table_changes(
    original_df: pd.DataFrame,
    edited_df: pd.DataFrame,
    table_name: str,
    id_column: str,
    *,
    exclude_columns: list[str] | None = None,
) -> int:
    """Compare original and edited DataFrames, persist changes to DB.

    Returns the number of rows updated.
    """
    db = DatabaseManager.get_instance()
    exclude = set(exclude_columns or [])
    last_update_column = next(
        (col for col in original_df.columns if col.endswith("last_update")),
        None,
    )
    # Always exclude timestamp columns
    for col in original_df.columns:
        if "created_at" in col or "last_update" in col:
            exclude.add(col)

    updated_count = 0
    changed_rows: list[tuple[str, list[str], list[Any], Any | None]] = []

    for idx in edited_df.index:
        if idx not in original_df.index:
            continue

        row_id = edited_df.at[idx, id_column]
        orig_row = original_df.loc[idx]
        edit_row = edited_df.loc[idx]

        changed_cols = []
        changed_vals = []
        for col in edited_df.columns:
            if col == id_column or col in exclude:
                continue
            orig_val = _coerce_value(orig_row[col])
            edit_val = _coerce_value(edit_row[col])

            # Normalize for comparison
            if orig_val is None and edit_val is None:
                continue
            if str(orig_val) != str(edit_val):
                changed_cols.append(col)
                changed_vals.append(edit_val)

        if changed_cols:
            expected_last_update = _coerce_value(orig_row[last_update_column]) if last_update_column else None
            changed_rows.append(
                (_coerce_value(row_id), changed_cols, changed_vals, expected_last_update)
            )

    if not changed_rows:
        return 0

    try:
        with db.transaction() as cur:
            for row_id, cols, vals, expected_last_update in changed_rows:
                db.build_update(
                    table_name,
                    cols,
                    vals,
                    row_id,
                    cur,
                    expected_last_update=expected_last_update,
                )
                updated_count += 1
        logger.info("Saved %d row(s) to %s", updated_count, table_name)
        clear_query_caches()
    except Exception as e:
        logger.error("Failed to save table changes: %s", e, exc_info=True)
        raise

    return updated_count
