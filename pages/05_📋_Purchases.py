"""
pages/05_📋_Purchases.py — Purchase Management (CRUD)
"""
from __future__ import annotations
from datetime import date
import pandas as pd
import streamlit as st
from auth_controller import require_auth
from database_manager import DatabaseManager
from logging_config import get_logger

from utils.editable_table import (
    render_filterable_editor,
    render_pagination_controls,
    save_table_changes,
)
from utils.query_cache import clear_query_caches, fetch_rows_cached, fetch_scalar_cached

logger = get_logger(__name__)
require_auth()
st.markdown("## 📋 Purchase Management")
db = DatabaseManager.get_instance()

tab_view, tab_add, tab_edit = st.tabs(["📋 View Purchases", "➕ Add Purchase", "✏️ Edit Purchase"])

with tab_view:
    try:
        search_term = st.text_input(
            "Search Purchases",
            key="pur_view_search",
            placeholder="Purchase ID / code / invoice / status",
        ).strip()
        search_like = f"%{search_term}%"
        total_rows = int(
            fetch_scalar_cached(
                "purchase.count_filtered",
                (search_term, search_like, search_like, search_like, search_like),
            ) or 0
        )
        page_size, _, offset = render_pagination_controls(
            table_key="pur_view",
            total_rows=total_rows,
        )
        purchases = fetch_rows_cached(
            "purchase.fetch_page",
            (search_term, search_like, search_like, search_like, search_like, page_size, offset),
        )
        if purchases:
            df_pur = pd.DataFrame(purchases)
            original_df, edited_df = render_filterable_editor(
                df_pur, "pur_view", "pur_id",
                disabled_columns=["pur_id", "pur_created_at", "pur_last_update"],
            )
            if st.button("💾 Save Changes", key="btn_save_pur_table"):
                try:
                    count = save_table_changes(original_df, edited_df, "purchase", "pur_id")
                    if count > 0:
                        st.success(f"✅ Saved {count} row(s).")
                        st.rerun()
                    else:
                        st.info("No changes detected.")
                except Exception as e:
                    st.error(f"Save failed: {e}")
        else:
            st.info("No purchase records found.")
    except Exception as e:
        st.error(f"Failed: {e}")

    st.markdown("---")
    del_id = st.text_input("Purchase ID to delete", key="del_pur")
    if st.button("Delete", key="btn_del_pur") and del_id:
        try:
            with db.transaction() as cur:
                db.build_delete("purchase", del_id, cur)
            clear_query_caches()
            st.success(f"Purchase {del_id} deleted.")
            st.rerun()
        except Exception as e:
            st.error(f"Failed: {e}")

with tab_add:
    st.markdown("#### Add New Purchase")
    salesmen = fetch_rows_cached("salesman.fetch_all")
    slm_map = {f"{s.get('slm_name', '?')} ({s['slm_id']})": s["slm_id"] for s in salesmen}

    with st.form("add_pur", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            pur_code = st.text_input("Purchase Code *")
            pur_slm = st.selectbox("Salesman", list(slm_map.keys()) if slm_map else ["None"])
            pur_date = st.date_input("Date", value=date.today())
            pur_method = st.selectbox("Method", ["CASH", "TRADE-IN"])
        with c2:
            pur_gc = st.number_input("Gold Cost (916)", min_value=0.0, step=0.01)
            pur_gc999 = st.number_input("Gold Cost (999)", min_value=0.0, step=0.01)
            pur_labor = st.number_input("Labor Cost", min_value=0.0, step=0.01)
            pur_weight = st.number_input("Weight (g)", min_value=0.0, step=0.01)

        c3, c4 = st.columns(2)
        with c3:
            pur_invoice = st.text_input("Invoice No.")
            pur_official = st.selectbox("Official Invoice?", [0, 1])
        with c4:
            pur_total = st.number_input("Total Amount", min_value=0.0, step=0.01)
            pur_status = st.selectbox("Payment Status", ["NOT_PAID", "IN_PAYMENT", "PAID", "CANCELLED"])

        submitted = st.form_submit_button("✅ Add", use_container_width=True)

    if submitted:
        if not pur_code.strip():
            st.error("Purchase Code is required.")
        else:
            try:
                cols = ["pur_code", "pur_slm_id", "pur_date", "pur_method",
                        "pur_gold_cost", "pur_labor_cost", "pur_weight",
                        "pur_official_invoice", "pur_invoice_no", "pur_payment_status", "pur_total_amt"]
                vals = [pur_code.upper(), slm_map.get(pur_slm, ""), pur_date.isoformat(), pur_method,
                        pur_gc, pur_labor, pur_weight, pur_official, pur_invoice, pur_status, pur_total]
                if pur_gc999 > 0:
                    cols.append("pur_gold_cost_999")
                    vals.append(pur_gc999)
                with db.transaction() as cur:
                    pk = db.build_insert("purchase", cols, vals, cur)
                clear_query_caches()
                st.success(f"✅ Purchase {pk} added!")
            except Exception as e:
                st.error(f"Failed: {e}")
                logger.error("Purchase insert failed", exc_info=True)

with tab_edit:
    st.markdown("#### Edit Existing Purchase")
    edit_id = st.text_input("Purchase ID to edit", key="edit_pur")
    if edit_id and st.button("🔍 Load", key="btn_load_pur"):
        p = db.fetch_one("purchase.fetch_by_id", (edit_id,))
        if p:
            st.session_state["editing_pur"] = p
        else:
            st.warning(f"Purchase {edit_id} not found.")

    if "editing_pur" in st.session_state:
        p = st.session_state["editing_pur"]
        with st.form("edit_pur"):
            c1, c2 = st.columns(2)
            with c1:
                e_code = st.text_input("Code *", value=p.get("pur_code", "") or "")
                e_gc = st.number_input("Gold Cost 916", value=float(p.get("pur_gold_cost", 0) or 0), step=0.01)
                e_labor = st.number_input("Labor", value=float(p.get("pur_labor_cost", 0) or 0), step=0.01)
                e_weight = st.number_input("Weight", value=float(p.get("pur_weight", 0) or 0), step=0.01)
            with c2:
                e_invoice = st.text_input("Invoice", value=p.get("pur_invoice_no", "") or "")
                e_total = st.number_input("Total", min_value=0.0, value=max(0.0, float(p.get("pur_total_amt", 0) or 0)), step=0.01)
                e_status = st.selectbox("Payment Status", ["NOT_PAID", "IN_PAYMENT", "PAID", "CANCELLED"],
                    index=["NOT_PAID", "IN_PAYMENT", "PAID", "CANCELLED"].index(p.get("pur_payment_status", "NOT_PAID"))
                    if p.get("pur_payment_status") in ["NOT_PAID", "IN_PAYMENT", "PAID", "CANCELLED"] else 0)

            if st.form_submit_button("💾 Save", use_container_width=True):
                if not e_code.strip():
                    st.error("Purchase Code is required.")
                else:
                    try:
                        cols = ["pur_code", "pur_gold_cost", "pur_labor_cost", "pur_weight",
                                "pur_invoice_no", "pur_total_amt", "pur_payment_status"]
                        vals = [e_code.upper(), e_gc, e_labor, e_weight, e_invoice, e_total, e_status]
                        with db.transaction() as cur:
                            db.build_update(
                                "purchase",
                                cols,
                                vals,
                                p["pur_id"],
                                cur,
                                expected_last_update=p.get("pur_last_update"),
                            )
                        clear_query_caches()
                        st.success(f"✅ Purchase {p['pur_id']} updated.")
                        del st.session_state["editing_pur"]
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")
