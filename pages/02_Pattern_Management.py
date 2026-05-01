"""
pages/02_🎨_Pattern_Management.py
──────────────────────────────────
Pattern Management — Upload and map images to stock patterns/categories.

Maps stk_pattern/cpat_pattern to stk_type/cpat_category with images.
Uses the category_pattern_mapping table.
"""

from __future__ import annotations

import shutil
import hashlib
from pathlib import Path

import pandas as pd
import streamlit as st

from auth_controller import require_auth
from database_manager import DatabaseManager
from config.logging_config import get_logger
from utils.html_utils import escape_html
from utils.image_processing import process_pattern_image
from utils.path_utils import resolve_repo_local_file, sanitize_filename_component

logger = get_logger(__name__)
require_auth()

st.markdown("## 🎨 Pattern Management")
db = DatabaseManager.get_instance()

# Image storage directory
BASE_DIR = Path(__file__).resolve().parent.parent
IMAGE_DIR = BASE_DIR / "system_files" / "pattern_images"
IMAGE_DIR.mkdir(parents=True, exist_ok=True)

STOCK_TYPES = ["NECKLACE", "RING", "BRACELET", "BANGLE", "EARING", "PENDANT", "ANKLET"]


def _sanitize_filename_stem(stem: str) -> str:
    """Keep Unicode (including emoji) while removing Windows-forbidden chars."""
    return sanitize_filename_component(stem, "PATTERN_IMAGE")


def _build_upload_filename(pattern_text: str, original_name: str) -> str:
    original = Path(original_name)
    # Prefer uploaded stem so existing emoji filenames remain visible.
    candidate_stem = original.stem or pattern_text
    ext = original.suffix.lower() or ".jpg"
    return f"{_sanitize_filename_stem(candidate_stem)}{ext}"


def _get_original_extension(uploaded_file) -> str:
    ext = Path(uploaded_file.name).suffix.lower()
    return ext or ".jpg"


def _reset_preview_state(prefix: str) -> None:
    for suffix in ("sig", "orig", "proc", "choice"):
        st.session_state.pop(f"{prefix}_{suffix}", None)


def _ensure_preview_bytes(uploaded_file, auto_enhance: bool, key_prefix: str) -> tuple[bytes, bytes | None]:
    image_bytes = uploaded_file.getvalue()
    signature = hashlib.sha256(image_bytes).hexdigest()

    if st.session_state.get(f"{key_prefix}_sig") != signature:
        st.session_state[f"{key_prefix}_sig"] = signature
        st.session_state[f"{key_prefix}_orig"] = image_bytes
        st.session_state[f"{key_prefix}_proc"] = None
        st.session_state[f"{key_prefix}_choice"] = "Original"

    original_bytes = st.session_state[f"{key_prefix}_orig"]
    processed_bytes = st.session_state.get(f"{key_prefix}_proc")

    if auto_enhance and processed_bytes is None:
        with st.spinner("✨ Generating AI enhancement preview..."):
            st.session_state[f"{key_prefix}_proc"] = process_pattern_image(original_bytes)
        processed_bytes = st.session_state[f"{key_prefix}_proc"]

    return original_bytes, processed_bytes


def _render_image_preview(uploaded_file, auto_enhance: bool, key_prefix: str) -> tuple[bytes | None, str | None]:
    if uploaded_file is None:
        _reset_preview_state(key_prefix)
        return None, None

    original_bytes, processed_bytes = _ensure_preview_bytes(uploaded_file, auto_enhance, key_prefix)

    st.markdown("##### 🔍 Preview")
    if auto_enhance:
        col_orig, col_proc = st.columns(2)
        with col_orig:
            st.image(original_bytes, caption="Original", use_container_width=True)
        with col_proc:
            st.image(processed_bytes or original_bytes, caption="AI Enhanced", use_container_width=True)

        choice = st.radio(
            "Which image should be saved?",
            ["AI Enhanced", "Original"],
            key=f"{key_prefix}_choice",
            index=0,
        )
    else:
        st.image(original_bytes, caption="Original", use_container_width=True)
        choice = "Original"
        st.session_state[f"{key_prefix}_choice"] = choice

    if choice == "AI Enhanced" and auto_enhance:
        return processed_bytes or original_bytes, ".jpg"

    return original_bytes, _get_original_extension(uploaded_file)


tab_view, tab_add, tab_edit = st.tabs(["📋 View Mappings", "➕ Add Mapping", "✏️ Edit Mapping"])

# ══════════════════════════════════════════════════════════
# VIEW MAPPINGS
# ══════════════════════════════════════════════════════════
with tab_view:
    # Filter by category
    filter_cat = st.selectbox("Filter by Category", ["ALL"] + STOCK_TYPES, key="cpat_filter")

    try:
        if filter_cat == "ALL":
            mappings = db.fetch_all("category_pattern_mapping.fetch_all")
        else:
            mappings = db.fetch_all("category_pattern_mapping.fetch_by_category", (filter_cat,))

        if mappings:
            st.dataframe(pd.DataFrame(mappings), width="stretch", height=400)
            st.caption(f"Showing {len(mappings)} mapping(s)")

            # Image gallery
            st.markdown("### 📷 Image Gallery")
            cols_per_row = 4
            for i in range(0, len(mappings), cols_per_row):
                cols = st.columns(cols_per_row)
                for j, col in enumerate(cols):
                    idx = i + j
                    if idx >= len(mappings):
                        break
                    m = mappings[idx]
                    with col:
                        img_path = m.get("cpat_image_path", "")
                        label = f"{m.get('cpat_category', '?')} / {m.get('cpat_pattern', '?')}"
                        resolved_path = resolve_repo_local_file(img_path, BASE_DIR) if img_path else None
                        if resolved_path is not None:
                            st.image(str(resolved_path), caption=label, width="stretch")
                        elif img_path and img_path.startswith(("http://", "https://")):
                            st.image(img_path, caption=label, width="stretch")
                        else:
                            st.markdown(
                                f'<div style="background:#FFFFFF;border:1px solid #E2E8F0;'
                                f'border-radius:12px;padding:3rem;text-align:center;color:#8D99AE;box-shadow:0 4px 15px rgba(212,175,55,0.05);">'
                                f'<span style="font-size:1.5rem">📷</span><br><br><small style="letter-spacing:1px;text-transform:uppercase;color:#0B2545;font-weight:500;">{escape_html(label)}</small></div>',
                                unsafe_allow_html=True,
                            )
        else:
            st.info("No pattern mappings found. Use the '➕ Add Mapping' tab to create one.")
    except Exception as e:
        st.error(f"Failed to load mappings: {e}")
        logger.error("Pattern mapping fetch failed", exc_info=True)

    st.markdown("---")
    st.markdown("#### 🗑️ Delete Mapping")
    del_cpat_id = st.text_input("Enter CPAT ID to delete", key="del_cpat_id")
    if st.button("Delete Mapping", key="btn_del_cpat"):
        if del_cpat_id:
            try:
                with db.transaction() as cur:
                    db.build_delete("category_pattern_mapping", del_cpat_id, cur)
                st.success(f"Mapping {del_cpat_id} deleted.")
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")
        else:
            st.warning("Please enter a CPAT ID.")

# ══════════════════════════════════════════════════════════
# ADD MAPPING
# ══════════════════════════════════════════════════════════
with tab_add:
    st.markdown("#### Map a Pattern to a Category")

    col1, col2 = st.columns(2)

    with col1:
        cpat_category = st.selectbox("Category (stk_type) *", STOCK_TYPES, key="add_cpat_cat")
        cpat_pattern = st.text_input("Pattern Name *", placeholder="e.g. BUTTERFLY, DRAGON", key="add_cpat_pattern")

    with col2:
        st.markdown("##### 📷 Upload Pattern Image")
        uploaded_file = st.file_uploader(
            "Choose image file",
            type=["jpg", "jpeg", "png", "webp"],
            key="cpat_image_upload",
        )
        if uploaded_file is not None:
            st.caption(f"Selected filename: {uploaded_file.name}")

    st.markdown("---")
    auto_enhance = st.checkbox(
        "✨ Apply Enterprise AI Enhancement (Crop, Zoom & Sharpen)",
        value=True,
        key="add_auto_enhance",
        help="Uses YOLO-World to detect the jewellery, removes background, and enhances contrast.",
    )

    selected_image_bytes = None
    selected_image_ext = None
    if uploaded_file is not None:
        selected_image_bytes, selected_image_ext = _render_image_preview(
            uploaded_file, auto_enhance, "add_cpat"
        )

    if st.button("✅ Add Pattern Mapping", use_container_width=True):
        if not cpat_pattern:
            st.error("Pattern name is required.")
        else:
            try:
                # Save image file
                image_path = ""
                if uploaded_file is not None:
                    # Create category subdirectory
                    cat_dir = IMAGE_DIR / cpat_category.lower()
                    cat_dir.mkdir(parents=True, exist_ok=True)

                    filename = _build_upload_filename(cpat_pattern, uploaded_file.name)
                    chosen_ext = selected_image_ext or _get_original_extension(uploaded_file)
                    filename = str(Path(filename).with_suffix(chosen_ext))

                    save_path = cat_dir / filename

                    image_data = selected_image_bytes or uploaded_file.getvalue()

                    with open(save_path, "wb") as f:
                        f.write(image_data)

                    image_path = save_path.relative_to(BASE_DIR).as_posix()
                    logger.info("Saved pattern image: %s", image_path)

                columns = ["cpat_category", "cpat_pattern"]
                values = [cpat_category, cpat_pattern.strip().upper()]

                if image_path:
                    columns.append("cpat_image_path")
                    values.append(image_path)

                with db.transaction() as cur:
                    pk = db.build_insert("category_pattern_mapping", columns, values, cur)

                st.success(f"✅ Pattern mapping {pk} created!")
                logger.info("Added pattern mapping %s: %s -> %s", pk, cpat_category, cpat_pattern)
                _reset_preview_state("add_cpat")
                st.session_state["cpat_image_upload"] = None
                st.session_state["add_cpat_pattern"] = ""
                st.session_state["add_auto_enhance"] = True
                st.session_state["add_cpat_cat"] = STOCK_TYPES[0]

            except Exception as e:
                st.error(f"Failed to add mapping: {e}")
                logger.error("Pattern mapping insert failed", exc_info=True)

# ══════════════════════════════════════════════════════════
# EDIT MAPPING
# ══════════════════════════════════════════════════════════
with tab_edit:
    st.markdown("#### Edit Existing Pattern Mapping")

    edit_cpat_id = st.text_input("Enter CPAT ID to edit", key="edit_cpat_id")

    if edit_cpat_id and st.button("🔍 Load Mapping", key="btn_load_cpat"):
        mapping = db.fetch_one("category_pattern_mapping.fetch_by_id", (edit_cpat_id,))
        if mapping:
            st.session_state["editing_cpat"] = mapping
        else:
            st.warning(f"Mapping {edit_cpat_id} not found.")

    if "editing_cpat" in st.session_state:
        m = st.session_state["editing_cpat"]

        # Show current image
        current_img = m.get("cpat_image_path", "")
        resolved_current_img = resolve_repo_local_file(current_img, BASE_DIR) if current_img else None
        if resolved_current_img is not None:
            st.image(str(resolved_current_img), caption="Current image", width=200)

        e_category = st.selectbox(
            "Category",
            STOCK_TYPES,
            index=STOCK_TYPES.index(m.get("cpat_category", STOCK_TYPES[0]))
            if m.get("cpat_category", "") in STOCK_TYPES else 0,
            key="edit_cpat_category",
        )
        e_pattern = st.text_input(
            "Pattern",
            value=m.get("cpat_pattern", "") or "",
            key="edit_cpat_pattern",
        )

        st.markdown("##### 📷 Replace Image (optional)")
        replacement_file = st.file_uploader(
            "Upload new image",
            type=["jpg", "jpeg", "png", "webp"],
            key="cpat_replace_img",
        )
        if replacement_file is not None:
            st.caption(f"Selected filename: {replacement_file.name}")

        st.markdown("---")
        edit_auto_enhance = st.checkbox(
            "✨ Apply Enterprise AI Enhancement (Crop, Zoom & Sharpen)",
            value=True,
            key="edit_auto_enhance",
            help="Uses YOLO-World to detect the jewellery, removes background, and enhances contrast.",
        )

        selected_edit_bytes = None
        selected_edit_ext = None
        if replacement_file is not None:
            selected_edit_bytes, selected_edit_ext = _render_image_preview(
                replacement_file, edit_auto_enhance, "edit_cpat"
            )

        if st.button("💾 Save", use_container_width=True):
            try:
                new_image_path = current_img
                if replacement_file is not None:
                    cat_dir = IMAGE_DIR / e_category.lower()
                    cat_dir.mkdir(parents=True, exist_ok=True)
                    filename = _build_upload_filename(e_pattern, replacement_file.name)
                    chosen_ext = selected_edit_ext or _get_original_extension(replacement_file)
                    filename = str(Path(filename).with_suffix(chosen_ext))

                    save_path = cat_dir / filename

                    image_data = selected_edit_bytes or replacement_file.getvalue()
                    with open(save_path, "wb") as f:
                        f.write(image_data)
                    new_image_path = save_path.relative_to(BASE_DIR).as_posix()

                columns = ["cpat_category", "cpat_pattern", "cpat_image_path"]
                values = [e_category, e_pattern.strip().upper(), new_image_path]

                with db.transaction() as cur:
                    db.build_update(
                        "category_pattern_mapping",
                        columns,
                        values,
                        m["cpat_id"],
                        cur,
                        expected_last_update=m.get("cpat_last_update"),
                    )

                st.success(f"✅ Mapping {m['cpat_id']} updated.")
                _reset_preview_state("edit_cpat")
                st.session_state["cpat_replace_img"] = None
                del st.session_state["editing_cpat"]
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")
                logger.error("Pattern mapping update failed", exc_info=True)
