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

    # ── Search / Filter ──
    search_query = st.text_input(
        "🔍 Search patterns by name",
        key="dash_pattern_search",
        placeholder="Type to filter pattern names...",
    )

    if patterns:
        # Apply search filter
        if search_query.strip():
            q = search_query.strip().lower()
            patterns = [
                p for p in patterns
                if q in (p.get("cpat_pattern", "") or "").lower()
            ]

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
            st.info(f"No patterns matching **\"{search_query}\"** found.")
    else:
        st.info(
            f"No patterns found for **{selected_type}**. "
            "Use the **Pattern Management** page to map patterns to stock types."
        )

    # ── Missing Patterns (no photo yet) ──
    st.markdown("---")
    st.markdown(f"#### 📋 Missing Patterns (no photo yet) for {selected_type}")
    st.caption("Patterns that exist in stock inventory but have no entry in Pattern Management.")
    try:
        stk_patterns = db.fetch_all("stock.fetch_distinct_patterns_by_type", (selected_type,))
        stk_pattern_names = {
            (row.get("stk_pattern", "") or "").strip()
            for row in (stk_patterns or [])
            if (row.get("stk_pattern", "") or "").strip()
        }

        # Re-fetch full cpat_patterns list (not search-filtered)
        all_cpat = db.fetch_all(
            "category_pattern_mapping.fetch_distinct_patterns_by_category",
            (selected_type,),
        )
        cpat_pattern_names = {
            (row.get("cpat_pattern", "") or "").strip()
            for row in (all_cpat or [])
            if (row.get("cpat_pattern", "") or "").strip()
        }

        missing = sorted(stk_pattern_names - cpat_pattern_names)

        if missing:
            st.warning(f"**{len(missing)}** pattern(s) in inventory still need a photo.")
            cols_per_row = 6
            for i in range(0, len(missing), cols_per_row):
                cols = st.columns(cols_per_row)
                for j, col in enumerate(cols):
                    idx = i + j
                    if idx >= len(missing):
                        break
                    pname = missing[idx]
                    with col:
                        st.markdown(
                            f'<div style="background:#FFF8E1;border:1px solid #FFB300;'
                            f'border-radius:8px;padding:0.75rem;text-align:center;'
                            f'font-size:0.85rem;color:#E65100;font-weight:600;letter-spacing:1px;">'
                            f'📷 {escape_html(pname)}</div>',
                            unsafe_allow_html=True,
                        )
        else:
            st.success("✅ All stock patterns have photos in Pattern Management!")
    except Exception as e:
        st.warning(f"Could not load stock patterns: {e}")
        logger.error("Dashboard missing pattern fetch failed", exc_info=True)

