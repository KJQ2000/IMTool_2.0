"""
pages/03_📦_Stocks.py — Stock Management (CRUD + Barcode Export)

Includes barcode export feature for Niimbot label printer:
  Filter stocks → Select → Export paired-row XLSX → Mark stk_printed=1
"""
from __future__ import annotations

import io
import math
from datetime import date, datetime

import pandas as pd
import streamlit as st

from auth_controller import require_auth
from config.config_loader import get_query
from database_manager import DatabaseManager
from config.logging_config import get_logger

from utils.editable_table import (
    render_filterable_editor,
    render_pagination_controls,
    save_table_changes,
)
from utils.query_cache import clear_query_caches, fetch_rows_cached, fetch_scalar_cached

logger = get_logger(__name__)
require_auth()
st.markdown("## 📦 Stock Management")
db = DatabaseManager.get_instance()

tab_view, tab_add, tab_edit, tab_export = st.tabs(
    ["📋 View Stocks", "➕ Add Stock", "✏️ Edit Stock", "🖨️ Barcode Export"]
)

# ═══════════════════════════════════════════════════════════
# VIEW STOCKS
# ═══════════════════════════════════════════════════════════
with tab_view:
    # Handle incoming dashboard filters
    dash_type = st.session_state.pop("dash_filter_type", None)
    dash_ptn = st.session_state.pop("dash_filter_pattern", None)
    
    if dash_type:
        st.session_state["tf"] = dash_type

    try:
        if dash_ptn:
            st.session_state["pf"] = dash_ptn

        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
        with col_f1:
            status_filter = st.selectbox(
                "Filter by Status",
                ["ALL", "IN STOCK", "SOLD", "BOOKED"],
                key="sf",
            )
        with col_f2:
            type_filter = st.selectbox(
                "Filter by Type",
                ["ALL", "NECKLACE", "RING", "BRACELET", "BANGLE", "EARING", "PENDANT", "ANKLET"],
                key="tf",
            )
        with col_f3:
            pattern_rows = (
                fetch_rows_cached("stock.fetch_distinct_patterns_by_type", (type_filter,))
                if type_filter != "ALL"
                else fetch_rows_cached("stock.fetch_distinct_patterns")
            )
            all_patterns = sorted(
                {
                    row.get("stk_pattern")
                    for row in pattern_rows
                    if row.get("stk_pattern")
                }
            )
            if dash_ptn and dash_ptn not in all_patterns:
                all_patterns.append(dash_ptn)
                all_patterns = sorted(all_patterns)
            pattern_filter = st.selectbox(
                "Filter by Pattern",
                ["ALL"] + all_patterns,
                key="pf",
            )
        with col_f4:
            search_term = st.text_input(
                "Search",
                key="stk_view_search",
                placeholder="ID / pattern / tag / remark",
            ).strip()

        search_like = f"%{search_term}%"
        filter_params = (
            status_filter,
            status_filter,
            type_filter,
            type_filter,
            pattern_filter,
            pattern_filter,
            search_term,
            search_like,
            search_like,
            search_like,
            search_like,
        )
        total_rows = int(fetch_scalar_cached("stock.count_filtered", filter_params) or 0)
        page_size, _, offset = render_pagination_controls(
            table_key="stk_view",
            total_rows=total_rows,
        )
        stocks = fetch_rows_cached("stock.fetch_page", filter_params + (page_size, offset))

        if stocks:
            df_stocks = pd.DataFrame(stocks)
            original_df, edited_df = render_filterable_editor(
                df_stocks, "stk_view", "stk_id",
                disabled_columns=["stk_id", "stk_created_at", "stk_last_update"],
            )
            if st.button("💾 Save Changes", key="btn_save_stk_table"):
                try:
                    count = save_table_changes(original_df, edited_df, "stock", "stk_id")
                    if count > 0:
                        st.success(f"✅ Saved {count} row(s).")
                        st.rerun()
                    else:
                        st.info("No changes detected.")
                except Exception as e:
                    st.error(f"Save failed: {e}")
        else:
            st.info("No stock records found.")
    except Exception as e:
        st.error(f"Failed to load stocks: {e}")
        logger.error("Stock fetch failed", exc_info=True)

    st.markdown("---")
    st.markdown("#### 🗑️ Delete Stock")
    del_id = st.text_input("Stock ID to delete", key="del_stk")
    if st.button("Delete", key="btn_del_stk") and del_id:
        try:
            with db.transaction() as cur:
                db.build_delete("stock", del_id, cur)
            clear_query_caches()
            st.success(f"Stock {del_id} deleted.")
            st.rerun()
        except Exception as e:
            st.error(f"Failed: {e}")

# ═══════════════════════════════════════════════════════════
# ADD STOCK
# ═══════════════════════════════════════════════════════════
with tab_add:
    st.markdown("#### Add New Stock Item")
    purchases = fetch_rows_cached("purchase.fetch_all")

    with st.form("add_stk", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            stk_type = st.selectbox(
                "Type *",
                ["NECKLACE", "RING", "BRACELET", "BANGLE", "EARING", "PENDANT", "ANKLET"],
            )
            stk_weight = st.number_input("Weight (g) *", min_value=0.01, step=0.01)
            stk_labor = st.number_input("Labor Cost *", min_value=0.0, step=0.01)
            stk_gtype = st.selectbox("Gold Type *", ["916", "999"])
            stk_pattern = st.text_input("Pattern *")
        with c2:
            pur_codes = {p.get("pur_code", "?"): p for p in purchases if p.get("pur_code")}
            sel_pur = st.selectbox(
                "Purchase Code *",
                list(pur_codes.keys()) if pur_codes else ["No purchases"],
            )
            stk_size = st.text_input("Size")
            stk_length = st.text_input("Length")
            stk_tag = st.text_input("Tag")
            stk_remark = st.text_input("Remark")

        submitted = st.form_submit_button("✅ Add Stock", use_container_width=True)

    if submitted:
        if not stk_pattern.strip():
            st.error("Pattern name is required.")
        elif stk_weight <= 0:
            st.error("Weight must be > 0.")
        elif sel_pur not in pur_codes:
            st.error("Select a valid purchase code.")
        else:
            try:
                pur = pur_codes[sel_pur]
                gold_cost = (
                    pur.get("pur_gold_cost_999", 0)
                    if stk_gtype == "999"
                    else pur.get("pur_gold_cost", 0)
                )
                pur_date = pur.get("pur_date")
                if pur_date and not isinstance(pur_date, str):
                    pur_date = str(pur_date)

                cols = [
                    "stk_type", "stk_weight", "stk_labor_cost", "stk_gold_type",
                    "stk_gold_cost", "stk_pur_id", "stk_pur_date", "stk_status",
                ]
                vals = [
                    stk_type, stk_weight, stk_labor, stk_gtype,
                    gold_cost, pur["pur_id"], pur_date, "IN STOCK",
                ]
                for name, val in [
                    ("stk_pattern", stk_pattern), ("stk_size", stk_size),
                    ("stk_length", stk_length), ("stk_tag", stk_tag),
                    ("stk_remark", stk_remark),
                ]:
                    if val:
                        cols.append(name)
                        vals.append(val)

                with db.transaction() as cur:
                    pk = db.generate_pk("stock", cur=cur)
                    seq_num = pk.split("_")[1]  # e.g. "101154" from "STK_101154"
                    barcode = DatabaseManager.generate_barcode_string(
                        gold_cost, stk_labor, seq_num,
                    )
                    all_cols = ["stk_id", "stk_barcode"] + cols
                    all_vals = [pk, barcode] + vals
                    db.insert_row("stock", all_cols, all_vals, cur)

                clear_query_caches()
                st.success(f"✅ {pk} added! Barcode: `{barcode}`")
                logger.info("Added stock %s barcode %s", pk, barcode)
            except Exception as e:
                st.error(f"Failed: {e}")
                logger.error("Stock insert failed", exc_info=True)

# ═══════════════════════════════════════════════════════════
# EDIT STOCK
# ═══════════════════════════════════════════════════════════
with tab_edit:
    st.markdown("#### Edit Existing Stock")
    edit_id = st.text_input("Stock ID to edit", key="edit_stk")
    if edit_id and st.button("🔍 Load", key="btn_load_stk"):
        s = db.fetch_one("stock.fetch_by_id", (edit_id,))
        if s:
            st.session_state["editing_stk"] = s
        else:
            st.warning(f"{edit_id} not found.")

    if "editing_stk" in st.session_state:
        s = st.session_state["editing_stk"]
        types = ["NECKLACE", "RING", "BRACELET", "BANGLE", "EARING", "PENDANT", "ANKLET"]
        statuses = ["IN STOCK", "SOLD", "BOOKED", "CANCELLED"]
        with st.form("edit_stk"):
            c1, c2 = st.columns(2)
            with c1:
                e_type = st.selectbox(
                    "Type", types,
                    index=types.index(s.get("stk_type", types[0]))
                    if s.get("stk_type") in types else 0,
                )
                e_weight = st.number_input(
                    "Weight *", min_value=0.01, value=max(0.01, float(s.get("stk_weight", 0) or 0)), step=0.01,
                )
                e_labor = st.number_input(
                    "Labor Cost *", min_value=0.0, value=max(0.0, float(s.get("stk_labor_cost", 0) or 0)), step=0.01,
                )
                e_gtype = st.selectbox(
                    "Gold Type *", ["916", "999"],
                    index=0 if str(s.get("stk_gold_type")) == "916" else 1,
                )
                e_pattern = st.text_input("Pattern *", value=s.get("stk_pattern", "") or "")
            with c2:
                e_size = st.text_input("Size", value=str(s.get("stk_size", "") or ""))
                e_length = st.text_input("Length", value=str(s.get("stk_length", "") or ""))
                e_status = st.selectbox(
                    "Status *", statuses,
                    index=statuses.index(s.get("stk_status", statuses[0]))
                    if s.get("stk_status") in statuses else 0,
                )
                e_tag = st.text_input("Tag", value=s.get("stk_tag", "") or "")
                e_remark = st.text_input("Remark", value=s.get("stk_remark", "") or "")

            if st.form_submit_button("💾 Save", use_container_width=True):
                if not e_pattern.strip():
                    st.error("Pattern name is required.")
                elif e_weight <= 0:
                    st.error("Weight must be > 0.")
                else:
                    try:
                        cols = [
                            "stk_type", "stk_weight", "stk_labor_cost", "stk_gold_type",
                            "stk_pattern", "stk_size", "stk_length", "stk_status",
                            "stk_tag", "stk_remark",
                        ]
                        vals = [
                            e_type, e_weight, e_labor, e_gtype,
                            e_pattern, e_size, e_length, e_status, e_tag, e_remark,
                        ]
                        with db.transaction() as cur:
                            lock_sql = get_query(
                                "stock.fetch_by_id_for_update", schema=db.schema,
                            )
                            cur.execute(lock_sql, (s["stk_id"],))
                            locked_row = cur.fetchone()
                            if not locked_row:
                                raise ValueError(f"Stock {s['stk_id']} no longer exists.")
                            db.build_update(
                                "stock",
                                cols,
                                vals,
                                s["stk_id"],
                                cur,
                                expected_last_update=s.get("stk_last_update"),
                            )
                        clear_query_caches()
                        st.success(f"✅ {s['stk_id']} updated.")
                        del st.session_state["editing_stk"]
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")
                        logger.error("Stock update failed", exc_info=True)

# ═══════════════════════════════════════════════════════════
# BARCODE EXPORT  (for Niimbot label printer)
# ═══════════════════════════════════════════════════════════
# Output: 14-column XLSX where rows are paired side-by-side.
# 7 base columns:
#   stk_barcode, stk_weight (14.00G), stk_gold_type,
#   stk_length_size ((10.0)), stk_returned, pur_code, stk_barcode_text
# Then odd-indexed rows become _2 suffix columns beside even rows.
# ═══════════════════════════════════════════════════════════

with tab_export:
    st.markdown("#### 🖨️ Export Barcodes for Label Printing")
    st.info(
        "Filter stocks below, then click **Export** to generate a formatted XLSX "
        "ready for Niimbot barcode printing. Exported stocks will be marked as printed."
    )

    # ── Filter controls ──
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        exp_status = st.selectbox(
            "Status", ["ALL", "IN STOCK", "SOLD", "BOOKED"], key="exp_sf",
        )
    with fc2:
        exp_type = st.selectbox(
            "Type",
            ["ALL", "NECKLACE", "RING", "BRACELET", "BANGLE", "EARING", "PENDANT", "ANKLET"],
            key="exp_tf",
        )
    with fc3:
        exp_date = st.date_input(
            "Created on or after", value=date.today(), key="exp_date",
        )

    exp_printed = st.selectbox(
        "Printed status", ["ALL", "Not printed only", "Printed only"], key="exp_pf",
    )

    # ── Fetch & filter ──
    try:
        printed_filter = {
            "ALL": "ALL",
            "Not printed only": "NOT_PRINTED",
            "Printed only": "PRINTED",
        }[exp_printed]
        exp_stocks = fetch_rows_cached(
            "stock.fetch_barcode_export_filtered",
            (
                exp_status,
                exp_status,
                exp_type,
                exp_type,
                exp_date.isoformat() if exp_date else None,
                exp_date.isoformat() if exp_date else None,
                printed_filter,
                printed_filter,
                printed_filter,
            ),
        )
    except Exception as e:
        exp_stocks = []
        st.error(f"Failed to load stocks: {e}")

    if exp_stocks:
        exp_df = pd.DataFrame(exp_stocks)
        st.dataframe(exp_df[["stk_id", "stk_barcode", "stk_type", "stk_weight", "stk_printed"]],
                      use_container_width=True, height=300)
        st.caption(f"{len(exp_stocks)} stock(s) match the filter")

        if st.button("🖨️ Export Barcodes to XLSX", use_container_width=True, key="btn_export"):
            try:
                stk_ids = [s["stk_id"] for s in exp_stocks]

                # Fetch barcode export data (join with purchase)
                barcode_data = db.fetch_all("stock.fetch_barcode_export", (stk_ids,))

                if not barcode_data:
                    st.warning("No barcode data found for selected stocks.")
                else:
                    # ── Format 7 columns ──
                    formatted_rows = []
                    for row in barcode_data:
                        weight_val = float(row.get("stk_weight", 0) or 0)
                        weight_str = f"{weight_val:.2f}G"

                        # stk_length_size: prefer stk_length, fallback stk_size, 1 decimal, brackets
                        length_raw = row.get("stk_length")
                        size_raw = row.get("stk_size")
                        ls_val = length_raw if length_raw is not None else size_raw
                        if ls_val is not None:
                            try:
                                ls_str = f"({float(ls_val):.1f})"
                            except (ValueError, TypeError):
                                ls_str = f"({ls_val})"
                        else:
                            ls_str = ""

                        pur_code = str(row.get("pur_code", "") or "").upper()

                        formatted_rows.append({
                            "stk_barcode": row.get("stk_barcode", ""),
                            "stk_weight": weight_str,
                            "stk_gold_type": str(row.get("stk_gold_type", "")),
                            "stk_length_size": ls_str,
                            "stk_returned": row.get("stk_returned", ""),
                            "pur_code": pur_code,
                            "stk_barcode_text": row.get("stk_barcode", ""),
                        })

                    df = pd.DataFrame(formatted_rows)

                    # ── Pair rows side-by-side (even + odd → 14 columns) ──
                    df_even = df.iloc[::2].reset_index(drop=True)     # rows 0, 2, 4, ...
                    df_odd = df.iloc[1::2].reset_index(drop=True)     # rows 1, 3, 5, ...
                    df_odd = df_odd.add_suffix("_2")

                    df_combined = pd.concat([df_even, df_odd], axis=1)

                    # ── Generate XLSX in-memory ──
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine="openpyxl") as writer:
                        df_combined.to_excel(writer, index=False, sheet_name="Barcodes")
                    output.seek(0)

                    # ── Mark as printed ──
                    try:
                        with db.transaction() as cur:
                            printed_sql = get_query("stock.update_printed", schema=db.schema)
                            cur.execute(printed_sql, (stk_ids,))
                        clear_query_caches()
                        logger.info("Marked %d stock(s) as printed", len(stk_ids))
                    except Exception as e:
                        logger.warning("Failed to mark printed: %s", e)
                        st.warning(f"Export succeeded but failed to mark as printed: {e}")

                    # ── Download button ──
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    st.download_button(
                        label="📥 Download XLSX",
                        data=output.getvalue(),
                        file_name=f"barcode_export_{ts}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )
                    st.success(
                        f"✅ Exported {len(barcode_data)} barcode(s) → "
                        f"{len(df_combined)} paired row(s). Stocks marked as printed."
                    )

            except Exception as e:
                st.error(f"Export failed: {e}")
                logger.error("Barcode export failed", exc_info=True)
    else:
        st.info("No stocks match the current filter.")
