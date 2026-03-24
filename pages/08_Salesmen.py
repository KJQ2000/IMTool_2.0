"""
pages/08_🤝_Salesmen.py — Salesman Management
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
st.markdown("## 🤝 Salesman Management")
db = DatabaseManager.get_instance()

tab_view, tab_add, tab_edit = st.tabs(["📋 View", "➕ Add", "✏️ Edit"])

with tab_view:
    try:
        search_term = st.text_input(
            "Search Salesmen",
            key="slm_view_search",
            placeholder="Salesman ID / name / company / phone / email",
        ).strip()
        search_like = f"%{search_term}%"
        total_rows = int(
            fetch_scalar_cached(
                "salesman.count_filtered",
                (search_term, search_like, search_like, search_like, search_like, search_like),
            ) or 0
        )
        page_size, _, offset = render_pagination_controls(
            table_key="slm_view",
            total_rows=total_rows,
        )
        salesmen = fetch_rows_cached(
            "salesman.fetch_page",
            (
                search_term,
                search_like,
                search_like,
                search_like,
                search_like,
                search_like,
                page_size,
                offset,
            ),
        )
        if salesmen:
            df_slm = pd.DataFrame(salesmen)
            original_df, edited_df = render_filterable_editor(
                df_slm, "slm_view", "slm_id",
                disabled_columns=["slm_id", "slm_created_at", "slm_last_update"],
            )
            if st.button("💾 Save Changes", key="btn_save_slm_table"):
                try:
                    count = save_table_changes(original_df, edited_df, "salesman", "slm_id")
                    if count > 0:
                        st.success(f"✅ Saved {count} row(s).")
                        st.rerun()
                    else:
                        st.info("No changes detected.")
                except Exception as e:
                    st.error(f"Save failed: {e}")
        else:
            st.info("No salesmen found.")
    except Exception as e:
        st.error(f"Failed: {e}")

    st.markdown("---")
    del_id = st.text_input("Salesman ID to delete", key="del_slm")
    if st.button("Delete", key="btn_del_slm") and del_id:
        try:
            with db.transaction() as cur:
                db.build_delete("salesman", del_id, cur)
            clear_query_caches()
            st.success(f"Deleted {del_id}")
            st.rerun()
        except Exception as e:
            st.error(f"Failed: {e}")

with tab_add:
    with st.form("add_slm", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            s_name = st.text_input("Name *")
            s_company = st.text_input("Company Name")
            s_email = st.text_input("Email")
            s_phone = st.text_input("Phone")
            s_address = st.text_area("Address")
        with c2:
            s_desc = st.text_input("Description")
            s_supplier = st.text_input("Supplier ID (e-invoice)")
            s_tin = st.text_input("TIN")
            s_reg = st.text_input("Reg No.")
            s_msic = st.text_input("MSIC Code")
        submitted = st.form_submit_button("✅ Add", use_container_width=True)

    if submitted:
        if not s_name.strip():
            st.error("Name is required.")
        else:
            try:
                cols, vals = ["slm_name"], [s_name.strip()]
                for cn, cv in [("slm_company_name", s_company), ("slm_email_address", s_email),
                               ("slm_phone_number", s_phone), ("slm_address", s_address),
                               ("slm_desc", s_desc), ("slm_supplier_id", s_supplier),
                               ("slm_tin", s_tin), ("slm_reg_no", s_reg), ("slm_msic", s_msic)]:
                    if cv:
                        cols.append(cn)
                        vals.append(cv.strip())
                with db.transaction() as cur:
                    pk = db.build_insert("salesman", cols, vals, cur)
                clear_query_caches()
                st.success(f"✅ Salesman {pk} added!")
            except Exception as e:
                st.error(f"Failed: {e}")

with tab_edit:
    edit_id = st.text_input("Salesman ID to edit", key="edit_slm")
    if edit_id and st.button("🔍 Load", key="btn_load_slm"):
        s = db.fetch_one("salesman.fetch_by_id", (edit_id,))
        if s:
            st.session_state["editing_slm"] = s
        else:
            st.warning(f"Not found: {edit_id}")

    if "editing_slm" in st.session_state:
        s = st.session_state["editing_slm"]
        with st.form("edit_slm"):
            c1, c2 = st.columns(2)
            with c1:
                e_name = st.text_input("Name *", value=s.get("slm_name", "") or "")
                e_company = st.text_input("Company", value=s.get("slm_company_name", "") or "")
                e_email = st.text_input("Email", value=s.get("slm_email_address", "") or "")
                e_phone = st.text_input("Phone", value=s.get("slm_phone_number", "") or "")
                e_addr = st.text_area("Address", value=s.get("slm_address", "") or "")
            with c2:
                e_desc = st.text_input("Desc", value=s.get("slm_desc", "") or "")
                e_supplier = st.text_input("Supplier ID", value=s.get("slm_supplier_id", "") or "")
                e_tin = st.text_input("TIN", value=s.get("slm_tin", "") or "")
                e_reg = st.text_input("Reg No.", value=s.get("slm_reg_no", "") or "")
                e_msic = st.text_input("MSIC", value=s.get("slm_msic", "") or "")
            if st.form_submit_button("💾 Save", use_container_width=True):
                if not e_name.strip():
                    st.error("Name is required.")
                else:
                    try:
                        cols = ["slm_name", "slm_company_name", "slm_email_address",
                                "slm_phone_number", "slm_address", "slm_desc",
                                "slm_supplier_id", "slm_tin", "slm_reg_no", "slm_msic"]
                        vals = [e_name, e_company, e_email, e_phone, e_addr,
                                e_desc, e_supplier, e_tin, e_reg, e_msic]
                        with db.transaction() as cur:
                            db.build_update(
                                "salesman",
                                cols,
                                vals,
                                s["slm_id"],
                                cur,
                                expected_last_update=s.get("slm_last_update"),
                            )
                        clear_query_caches()
                        st.success(f"✅ Updated {s['slm_id']}")
                        del st.session_state["editing_slm"]
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")
