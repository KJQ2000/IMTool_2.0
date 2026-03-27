"""
pages/09_📥_Batch_Import.py — Batch Import for Stocks via CSV/Excel
"""
from __future__ import annotations
import math
from datetime import datetime
from pathlib import Path
import pandas as pd
import streamlit as st
from auth_controller import require_auth
from database_manager import DatabaseManager
from config.logging_config import get_logger
from utils.path_utils import sanitize_uploaded_filename

logger = get_logger(__name__)
require_auth()
st.markdown("## 📥 Batch Import — Stock")
db = DatabaseManager.get_instance()

STAGING_DIR = Path(__file__).parent.parent / "staging"
STAGING_DIR.mkdir(exist_ok=True)

st.markdown("""
**Required columns:** `stk_type`, `stk_weight`, `stk_labor_cost`, `stk_gold_type`, `pur_code`

**Optional columns:** `stk_pattern`, `stk_size`, `stk_length`, `stk_tag`, `stk_remark`

The barcode and stk_id are auto-generated. The gold cost is sourced from the linked purchase.
""")

uploaded = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx", "xls"])

if uploaded:
    try:
        if uploaded.name.endswith(".csv"):
            df = pd.read_csv(uploaded)
        else:
            df = pd.read_excel(uploaded)

        st.markdown(f"### Preview — {len(df)} row(s)")
        st.dataframe(df.head(20), use_container_width=True)

        required = {"stk_type", "stk_weight", "stk_labor_cost", "stk_gold_type", "pur_code"}
        missing = required - set(df.columns)
        if missing:
            st.error(f"Missing required columns: {missing}")
        else:
            # Load purchase data
            purchases = db.fetch_all("purchase.fetch_all")
            pur_map = {p["pur_code"]: p for p in purchases if p.get("pur_code")}

            if st.button("🚀 Import", use_container_width=True):
                errors = []
                success_count = 0

                try:
                    with db.transaction() as cur:
                        for idx, row in df.iterrows():
                            try:
                                pur_code = str(row["pur_code"]).strip().upper()
                                if pur_code not in pur_map:
                                    errors.append(f"Row {idx + 1}: Purchase code '{pur_code}' not found")
                                    raise ValueError(f"Unknown pur_code: {pur_code}")

                                pur = pur_map[pur_code]
                                gtype = str(row["stk_gold_type"]).strip()
                                gold_cost = pur.get("pur_gold_cost_999", 0) if gtype == "999" else pur.get("pur_gold_cost", 0)
                                pur_date = pur.get("pur_date")
                                if pur_date and not isinstance(pur_date, str):
                                    pur_date = str(pur_date)

                                pk = db.generate_pk("stock", cur=cur)
                                seq_num = pk.split("_")[1]
                                labor = float(row["stk_labor_cost"])
                                barcode = DatabaseManager.generate_barcode_string(gold_cost, labor, seq_num)

                                cols = ["stk_id", "stk_barcode", "stk_type", "stk_weight",
                                        "stk_labor_cost", "stk_gold_type", "stk_gold_cost",
                                        "stk_pur_id", "stk_pur_date", "stk_status"]
                                vals = [pk, barcode, str(row["stk_type"]).strip().upper(),
                                        float(row["stk_weight"]), labor, gtype, gold_cost,
                                        pur["pur_id"], pur_date, "IN STOCK"]

                                for opt in ["stk_pattern", "stk_size", "stk_length", "stk_tag", "stk_remark"]:
                                    if opt in row and pd.notna(row[opt]) and str(row[opt]).strip():
                                        cols.append(opt)
                                        vals.append(str(row[opt]).strip())

                                db.insert_row("stock", cols, vals, cur)
                                success_count += 1
                                logger.info("Batch: inserted %s barcode %s", pk, barcode)

                            except Exception as e:
                                errors.append(f"Row {idx + 1}: {e}")
                                raise  # Rollback entire batch

                    st.success(f"✅ {success_count} stock item(s) imported!")
                    # Archive
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    archive_dir = STAGING_DIR / "SUCCESS"
                    archive_dir.mkdir(exist_ok=True)
                    archive_name = sanitize_uploaded_filename(uploaded.name, fallback_stem="batch_import")
                    (archive_dir / f"{ts}_{archive_name}").write_bytes(uploaded.getvalue())

                except Exception:
                    st.error(f"❌ Batch import ROLLED BACK. Errors:")
                    for err in errors:
                        st.markdown(f"- {err}")
                    archive_dir = STAGING_DIR / "FAILED"
                    archive_dir.mkdir(exist_ok=True)
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    archive_name = sanitize_uploaded_filename(uploaded.name, fallback_stem="batch_import")
                    (archive_dir / f"{ts}_{archive_name}").write_bytes(uploaded.getvalue())

    except Exception as e:
        st.error(f"Failed to parse file: {e}")
        logger.error("Batch import parse failed", exc_info=True)
