"""
pages/07_👥_Customers.py — Customer Management
"""
from __future__ import annotations
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
st.markdown("## 👥 Customer Management")
db = DatabaseManager.get_instance()

tab_view, tab_add, tab_edit = st.tabs(["📋 View", "➕ Add", "✏️ Edit"])

with tab_view:
    try:
        search_term = st.text_input(
            "Search Customers",
            key="cust_view_search",
            placeholder="Customer ID / name / phone / email",
        ).strip()
        search_like = f"%{search_term}%"
        total_rows = int(
            fetch_scalar_cached(
                "customer.count_filtered",
                (search_term, search_like, search_like, search_like, search_like),
            ) or 0
        )
        page_size, _, offset = render_pagination_controls(
            table_key="cust_view",
            total_rows=total_rows,
        )
        customers = fetch_rows_cached(
            "customer.fetch_page",
            (search_term, search_like, search_like, search_like, search_like, page_size, offset),
        )
        if customers:
            df_cust = pd.DataFrame(customers)
            original_df, edited_df = render_filterable_editor(
                df_cust, "cust_view", "cust_id",
                disabled_columns=["cust_id", "cust_created_at", "cust_last_update"],
            )
            if st.button("💾 Save Changes", key="btn_save_cust_table"):
                try:
                    count = save_table_changes(original_df, edited_df, "customer", "cust_id")
                    if count > 0:
                        st.success(f"✅ Saved {count} row(s).")
                        st.rerun()
                    else:
                        st.info("No changes detected.")
                except Exception as e:
                    st.error(f"Save failed: {e}")
        else:
            st.info("No customers found.")
    except Exception as e:
        st.error(f"Failed: {e}")

    st.markdown("---")
    del_id = st.text_input("Customer ID to delete", key="del_cust")
    if st.button("Delete", key="btn_del_cust") and del_id:
        try:
            with db.transaction() as cur:
                db.build_delete("customer", del_id, cur)
            clear_query_caches()
            st.success(f"Deleted {del_id}")
            st.rerun()
        except Exception as e:
            st.error(f"Failed: {e}")

with tab_add:
    with st.form("add_cust", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            c_name = st.text_input("Name *")
            c_email = st.text_input("Email")
            c_phone = st.text_input("Phone")
            c_address = st.text_area("Address")
        with c2:
            c_buyer = st.text_input("Buyer ID (e-invoice)")
            c_sst = st.text_input("SST Reg No.")
            c_tin = st.text_input("TIN")
        submitted = st.form_submit_button("✅ Add", use_container_width=True)

    if submitted:
        if not c_name.strip():
            st.error("Name is required.")
        else:
            try:
                cols, vals = ["cust_name"], [c_name.strip()]
                for cn, cv in [("cust_email_address", c_email), ("cust_phone_number", c_phone),
                               ("cust_address", c_address), ("cust_buyer_id", c_buyer),
                               ("cust_sst_reg_no", c_sst), ("cust_tin", c_tin)]:
                    if cv:
                        cols.append(cn)
                        vals.append(cv.strip())
                with db.transaction() as cur:
                    pk = db.build_insert("customer", cols, vals, cur)
                clear_query_caches()
                st.success(f"✅ Customer {pk} added!")
            except Exception as e:
                st.error(f"Failed: {e}")

with tab_edit:
    edit_id = st.text_input("Customer ID to edit", key="edit_cust")
    if edit_id and st.button("🔍 Load", key="btn_load_cust"):
        c = db.fetch_one("customer.fetch_by_id", (edit_id,))
        if c:
            st.session_state["editing_cust"] = c
        else:
            st.warning(f"Not found: {edit_id}")

    if "editing_cust" in st.session_state:
        c = st.session_state["editing_cust"]
        with st.form("edit_cust"):
            c1, c2 = st.columns(2)
            with c1:
                e_name = st.text_input("Name *", value=c.get("cust_name", "") or "")
                e_email = st.text_input("Email", value=c.get("cust_email_address", "") or "")
                e_phone = st.text_input("Phone", value=c.get("cust_phone_number", "") or "")
                e_addr = st.text_area("Address", value=c.get("cust_address", "") or "")
            with c2:
                e_buyer = st.text_input("Buyer ID", value=c.get("cust_buyer_id", "") or "")
                e_sst = st.text_input("SST", value=c.get("cust_sst_reg_no", "") or "")
                e_tin = st.text_input("TIN", value=c.get("cust_tin", "") or "")
            if st.form_submit_button("💾 Save", use_container_width=True):
                if not e_name.strip():
                    st.error("Name is required.")
                else:
                    try:
                        cols = ["cust_name", "cust_email_address", "cust_phone_number",
                                "cust_address", "cust_buyer_id", "cust_sst_reg_no", "cust_tin"]
                        vals = [e_name, e_email, e_phone, e_addr, e_buyer, e_sst, e_tin]
                        with db.transaction() as cur:
                            db.build_update(
                                "customer",
                                cols,
                                vals,
                                c["cust_id"],
                                cur,
                                expected_last_update=c.get("cust_last_update"),
                            )
                        clear_query_caches()
                        st.success(f"✅ Updated {c['cust_id']}")
                        del st.session_state["editing_cust"]
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")
