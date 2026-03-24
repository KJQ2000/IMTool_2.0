"""
pages/10_🏷️_Barcode.py — Barcode Lookup & Manual Generation

Barcodes are auto-generated on stock creation/batch import.
This page is for:
  1. Looking up a stock's barcode
  2. Manually testing the barcode algorithm
  3. Future: scanning barcodes for invoice creation
"""
from __future__ import annotations
import streamlit as st
from auth_controller import require_auth
from database_manager import DatabaseManager
from logging_config import get_logger
from utils.html_utils import escape_html

logger = get_logger(__name__)
require_auth()
st.markdown("## 🏷️ Barcode Lookup & Generator")
db = DatabaseManager.get_instance()

tab_lookup, tab_manual = st.tabs(["🔍 Lookup by Stock ID", "🧪 Manual Generator"])

# ═══════════════ LOOKUP ═══════════════
with tab_lookup:
    st.markdown("Enter a Stock ID to retrieve its barcode and details.")
    stk_id = st.text_input("Stock ID", placeholder="e.g. STK_101154", key="bc_lookup")

    if stk_id and st.button("🔍 Lookup", key="btn_bc_lookup"):
        stk = db.fetch_one("stock.fetch_by_id", (stk_id,))
        if stk:
            barcode = stk.get("stk_barcode", "N/A")
            safe_barcode = escape_html(barcode)
            safe_stock_id = escape_html(stk_id)
            safe_stock_type = escape_html(stk.get("stk_type", "?"))
            safe_pattern = escape_html(stk.get("stk_pattern", "?"))
            st.markdown(
                f"""
                <div style="background:#FFFFFF;border:1px solid #E2E8F0;box-shadow:0 4px 20px rgba(212,175,55,0.1);
                            border-radius:16px;padding:3rem;text-align:center;margin:1.5rem 0;">
                    <div style="font-size:3.2rem;font-family:'Courier New', monospace;font-weight:800;
                                color:#0B2545;letter-spacing:8px;text-shadow: 0 0 10px rgba(212,175,55,0.2);">{safe_barcode}</div>
                    <div style="color:#D4AF37;font-size:0.95rem;margin-top:1.2rem;font-weight:600;text-transform:uppercase;letter-spacing:2px;">
                        {safe_stock_id} · {safe_stock_type} · {safe_pattern}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Decode breakdown
            try:
                bc = str(barcode)
                if len(bc) >= 8:
                    prefix_val = ord(bc[0]) - 64
                    suffix = bc[-4:]
                    gp_letter = bc[1]
                    gp_val = str(ord(gp_letter) - 64) + bc[2:4]
                    labor_code = bc[4:-4]

                    st.markdown("##### 🔬 Barcode Breakdown")
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Prefix", f"{bc[0]} = {prefix_val}")
                    with col2:
                        st.metric("Gold Cost", gp_val)
                    with col3:
                        st.metric("Labor", labor_code.lstrip("0") or "0")
                    with col4:
                        st.metric("Suffix", suffix)
            except Exception:
                pass

            # Stock details
            with st.expander("📋 Full Stock Details"):
                for k, v in stk.items():
                    st.markdown(f"**{k}:** {v}")

            # Future: barcode image rendering (scalable for scanner integration)
            st.caption("💡 Future: barcode scanner will decode this for invoice creation.")
        else:
            st.warning(f"Stock {stk_id} not found.")

# ═══════════════ MANUAL GENERATOR ═══════════════
with tab_manual:
    st.markdown("Test the barcode algorithm manually.")
    st.caption("This generates a barcode string without saving anything.")

    c1, c2, c3 = st.columns(3)
    with c1:
        m_gold = st.number_input("Gold Cost", min_value=0.0, step=0.01, key="m_gold")
    with c2:
        m_labor = st.number_input("Labor Cost", min_value=0.0, step=0.01, key="m_labor")
    with c3:
        m_stk_num = st.text_input("STK ID Number (digits only)", placeholder="e.g. 101154", key="m_stknum")

    if st.button("⚡ Generate", key="btn_gen_bc") and m_stk_num:
        try:
            barcode = DatabaseManager.generate_barcode_string(m_gold, m_labor, m_stk_num)
            st.markdown(
                f"""
                <div style="background:#FFFFFF;border:1px solid #E2E8F0;box-shadow:0 4px 20px rgba(212,175,55,0.1);
                            border-radius:16px;padding:3rem;text-align:center;margin:1.5rem 0;">
                    <div style="font-size:3.2rem;font-family:'Courier New', monospace;font-weight:800;
                                color:#0B2545;letter-spacing:8px;text-shadow: 0 0 10px rgba(212,175,55,0.2);">{escape_html(barcode)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        except Exception as e:
            st.error(f"Error: {e}")
