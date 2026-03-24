"""
pages/01_🏠_Dashboard.py
──────────────────────────
Dashboard — Browse stock patterns by type with category pattern images.

Users can:
1. Select a Stock Type (RING, NECKLACE, etc.)
2. See all patterns / cpat_patterns mapped to that type
3. View the images stored in cpat_image_path
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from auth_controller import require_auth
from database_manager import DatabaseManager
from logging_config import get_logger
from utils.html_utils import escape_html
from utils.path_utils import resolve_repo_local_file

logger = get_logger(__name__)
require_auth()

st.markdown("## 🏠 Pattern Dashboard")
db = DatabaseManager.get_instance()
REPO_ROOT = Path(__file__).resolve().parent.parent

STOCK_TYPES = ["NECKLACE", "RING", "BRACELET", "BANGLE", "EARING", "PENDANT", "ANKLET"]

# ──────────────────────────────────────────────────────────
# Step 1: Select Stock Type
# ──────────────────────────────────────────────────────────
selected_type = st.selectbox("📦 Select Stock Type", STOCK_TYPES, key="dash_type")

if selected_type:
    st.markdown(f"### Patterns for **{selected_type}**")

    # Fetch patterns from category_pattern_mapping where cpat_category matches stk_type
    patterns = db.fetch_all(
        "category_pattern_mapping.fetch_distinct_patterns_by_category",
        (selected_type,),
    )

    if patterns:
        # Display in a grid
        cols_per_row = 4
        for i in range(0, len(patterns), cols_per_row):
            cols = st.columns(cols_per_row)
            for j, col in enumerate(cols):
                idx = i + j
                if idx >= len(patterns):
                    break
                p = patterns[idx]
                pattern_name = p.get("cpat_pattern", "Unknown")
                image_path = p.get("cpat_image_path", "")
                safe_pattern_name = escape_html(pattern_name)

                with col:
                    st.markdown(
                        f"""
                        <div style="background:#FFFFFF;border:1px solid #E2E8F0;box-shadow:0 4px 15px rgba(212,175,55,0.05);
                                    border-radius:12px;padding:1.4rem;text-align:center;
                                    margin-bottom:1rem;transition:all 0.4s ease;">
                            <div style="font-weight:600;font-family:'Cinzel', serif;color:#0B2545;font-size:1.1rem;
                                        margin-bottom:0.5rem;text-transform:uppercase;letter-spacing:1px;">{safe_pattern_name}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    # Try to display the image
                    if image_path:
                        img_path = resolve_repo_local_file(image_path, REPO_ROOT)
                        if img_path is not None:
                            st.image(str(img_path), caption=pattern_name, use_container_width=True)
                        elif image_path.startswith(("http://", "https://")):
                            st.image(image_path, caption=pattern_name, use_container_width=True)
                        else:
                            st.caption(f"📷 Image not found: {image_path}")
                    else:
                        st.caption("📷 No image assigned")

                    if st.button(f"🔍 View Stocks", key=f"btn_{selected_type}_{pattern_name}", use_container_width=True):
                        st.session_state["dash_filter_type"] = selected_type
                        st.session_state["dash_filter_pattern"] = pattern_name
                        st.switch_page("pages/03_Stocks.py")
    else:
        st.info(
            f"No patterns found for **{selected_type}**. "
            "Use the **Pattern Management** page to map patterns to stock types."
        )

    # Also show distinct stk_pattern values from the stock table for this type
    st.markdown("---")
    st.markdown(f"#### 📋 Stock Patterns (from inventory) for {selected_type}")
    try:
        stk_patterns = db.fetch_all("stock.fetch_distinct_patterns_by_type", (selected_type,))

        if stk_patterns:
            cols_per_row = 6
            for i in range(0, len(stk_patterns), cols_per_row):
                cols = st.columns(cols_per_row)
                for j, col in enumerate(cols):
                    idx = i + j
                    if idx >= len(stk_patterns):
                        break
                    pname = stk_patterns[idx].get("stk_pattern", "")
                    with col:
                        st.markdown(
                            f'<div style="background:#F4F6F9;border:1px solid #E2E8F0;'
                            f'border-radius:8px;padding:0.75rem;text-align:center;'
                            f'font-size:0.85rem;color:#2B2D42;font-weight:500;letter-spacing:1px;">{escape_html(pname)}</div>',
                            unsafe_allow_html=True,
                        )
        else:
            st.caption("No stock patterns found in inventory for this type.")
    except Exception as e:
        st.warning(f"Could not load stock patterns: {e}")
        logger.error("Dashboard stock pattern fetch failed", exc_info=True)
