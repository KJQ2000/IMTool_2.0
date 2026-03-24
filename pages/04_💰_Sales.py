"""
pages/04_💰_Sales.py — Sale Management

CRITICAL: 1 sale can contain MULTIPLE stock items.
Each stock gets marked SOLD with its own sell price and profit.
"""
from __future__ import annotations
from datetime import date
import pandas as pd
import streamlit as st
from auth_controller import require_auth
from config_loader import get_query
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
st.markdown("## 💰 Sales Management")
db = DatabaseManager.get_instance()

SALE_DRAFT_PREFIX = "create_sale_"
SALE_SUCCESS_KEY = "create_sale_success_message"


def sale_state_key(name: str) -> str:
    return f"{SALE_DRAFT_PREFIX}{name}"


def clear_sale_draft() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith(SALE_DRAFT_PREFIX):
            del st.session_state[key]


def format_stock_label(stock: dict) -> str:
    return (
        f"{stock['stk_id']} — {stock.get('stk_type', '?')} · "
        f"{stock.get('stk_pattern', '?')} · {stock.get('stk_weight', 0)}g"
    )

tab_view, tab_add, tab_edit = st.tabs(["📋 View Sales", "➕ Create Sale", "✏️ Edit Sale"])

# ═══════════════ VIEW ═══════════════
with tab_view:
    try:
        search_term = st.text_input(
            "Search Sales",
            key="sale_view_search",
            placeholder="Sale ID / receipt / customer ID",
        ).strip()
        search_like = f"%{search_term}%"
        total_rows = int(
            fetch_scalar_cached(
                "sale.count_filtered",
                (search_term, search_like, search_like, search_like),
            ) or 0
        )
        page_size, _, offset = render_pagination_controls(
            table_key="sale_view",
            total_rows=total_rows,
        )
        sales = fetch_rows_cached(
            "sale.fetch_page",
            (search_term, search_like, search_like, search_like, page_size, offset),
        )
        if sales:
            df_sales = pd.DataFrame(sales)
            original_df, edited_df = render_filterable_editor(
                df_sales, "sale_view", "sale_id",
                disabled_columns=["sale_id", "sale_created_at", "sale_last_update"],
            )
            if st.button("💾 Save Changes", key="btn_save_sale_table"):
                try:
                    count = save_table_changes(original_df, edited_df, "sale", "sale_id")
                    if count > 0:
                        st.success(f"✅ Saved {count} row(s).")
                        st.rerun()
                    else:
                        st.info("No changes detected.")
                except Exception as e:
                    st.error(f"Save failed: {e}")

            # Show stock items per sale
            with st.expander("🔍 View stock items for a sale"):
                lookup_sale = st.text_input("Enter Sale ID", key="lookup_sale")
                if lookup_sale:
                    stks = db.fetch_all("stock.fetch_by_sale_id", (lookup_sale,))
                    if stks:
                        st.dataframe(pd.DataFrame(stks), use_container_width=True)
                        st.caption(f"{len(stks)} item(s) in this sale")
                    else:
                        st.info("No items found for this sale.")
        else:
            st.info("No sales records found.")
    except Exception as e:
        st.error(f"Failed: {e}")

    st.markdown("---")
    st.markdown("#### 🗑️ Delete Sale")
    del_id = st.text_input("Sale ID to delete", key="del_sale")
    if st.button("Delete", key="btn_del_sale") and del_id:
        try:
            with db.transaction() as cur:
                reset_sql = get_query("stock.reset_to_in_stock_from_sale", schema=db.schema)
                stk_sql = get_query("stock.fetch_stk_ids_by_sale", schema=db.schema)
                cur.execute(stk_sql, (del_id,))
                for row in cur.fetchall():
                    sid = row["stk_id"] if isinstance(row, dict) else row[0]
                    cur.execute(reset_sql, (sid,))
                db.build_delete("sale", del_id, cur)
            clear_query_caches()
            st.success(f"Sale {del_id} deleted. Stocks reset to IN STOCK.")
            st.rerun()
        except Exception as e:
            st.error(f"Failed: {e}")

# ═══════════════ CREATE SALE (multi-stock) ═══════════════
with tab_add:
    st.markdown("#### Create New Sale")
    success_message = st.session_state.pop(SALE_SUCCESS_KEY, None)
    if success_message:
        st.success(f"✅ {success_message}")
    st.info(
        "💡 **One sale can include multiple stock items.** "
        "Nothing is marked SOLD until you click the final confirm button."
    )

    customers = fetch_rows_cached("customer.fetch_all")
    cust_map = {f"{c.get('cust_name', '?')} ({c['cust_id']})": c["cust_id"] for c in customers}

    available = fetch_rows_cached("stock.fetch_in_stock")
    available_by_id = {s["stk_id"]: s for s in available}

    receipt_key = sale_state_key("receipt")
    customer_key = sale_state_key("customer")
    date_key = sale_state_key("date")
    official_key = sale_state_key("official")
    selected_key = sale_state_key("selected_ids")

    if customer_key not in st.session_state and cust_map:
        st.session_state[customer_key] = next(iter(cust_map.keys()))
    elif customer_key in st.session_state and st.session_state[customer_key] not in cust_map:
        st.session_state[customer_key] = next(iter(cust_map.keys())) if cust_map else "No customers"

    if date_key not in st.session_state:
        st.session_state[date_key] = date.today()
    if official_key not in st.session_state:
        st.session_state[official_key] = 0
    if selected_key not in st.session_state:
        st.session_state[selected_key] = []
    else:
        removed_ids = [
            stk_id for stk_id in st.session_state[selected_key]
            if stk_id not in available_by_id
        ]
        st.session_state[selected_key] = [
            stk_id for stk_id in st.session_state[selected_key]
            if stk_id in available_by_id
        ]
        if removed_ids:
            st.warning(
                "These stock items are no longer available and were removed from the draft: "
                + ", ".join(removed_ids)
            )

    if not cust_map:
        st.warning("Create at least one customer before creating a sale.")
    if not available_by_id:
        st.info("No IN STOCK items are available for sale right now.")

    c1, c2 = st.columns(2)
    with c1:
        st.text_input("Receipt No.", key=receipt_key)
        st.selectbox(
            "Customer",
            list(cust_map.keys()) if cust_map else ["No customers"],
            key=customer_key,
            disabled=not cust_map,
        )
    with c2:
        st.date_input("Sale Date", key=date_key)
        st.selectbox("Official Receipt?", [0, 1], key=official_key)

    selected_ids = st.multiselect(
        "📦 Select Stock Items (multi-select)",
        list(available_by_id.keys()),
        key=selected_key,
        format_func=lambda stk_id: format_stock_label(available_by_id[stk_id]),
        disabled=not available_by_id,
    )

    sell_data = {}
    if selected_ids:
        st.markdown("##### 💲 Enter sell prices for each item:")
        for stk_id in selected_ids:
            stock = available_by_id[stk_id]
            weight_key = sale_state_key(f"weight_{stk_id}")
            gold_key = sale_state_key(f"gold_{stk_id}")
            labor_key = sale_state_key(f"labor_{stk_id}")

            if weight_key not in st.session_state:
                st.session_state[weight_key] = max(0.01, float(stock.get("stk_weight", 0) or 0))
            if gold_key not in st.session_state:
                st.session_state[gold_key] = max(0.01, float(stock.get("stk_gold_cost", 0) or 0))
            if labor_key not in st.session_state:
                st.session_state[labor_key] = max(0.0, float(stock.get("stk_labor_cost", 0) or 0))

            st.markdown(f"**{format_stock_label(stock)}**")
            r1, r2, r3 = st.columns(3)
            with r1:
                sw = st.number_input(
                    "Sell Weight *",
                    min_value=0.01,
                    step=0.01,
                    key=weight_key,
                )
            with r2:
                sg = st.number_input(
                    "Gold Sell Price/g *",
                    min_value=0.01,
                    step=0.01,
                    key=gold_key,
                )
            with r3:
                sl = st.number_input(
                    "Labor Sell *",
                    min_value=0.0,
                    step=0.01,
                    key=labor_key,
                )
            sell_data[stk_id] = {"weight": sw, "gold": sg, "labor": sl, "stock": stock}
            st.caption(f"Line Total: RM {sw * sg + sl:,.2f}")

        total_gold = sum(d["gold"] for d in sell_data.values())
        total_labor = sum(d["labor"] for d in sell_data.values())
        total_weight = sum(d["weight"] for d in sell_data.values())
        total_price = sum(d["gold"] * d["weight"] + d["labor"] for d in sell_data.values())

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Weight", f"{total_weight:,.2f}g")
        m2.metric("Total Gold", f"RM {total_gold:,.2f}")
        m3.metric("Total Labor", f"RM {total_labor:,.2f}")
        m4.metric("Grand Total", f"RM {total_price:,.2f}")

    action_col1, action_col2 = st.columns(2)
    with action_col1:
        submitted = st.button(
            "✅ Confirm & Create Sale",
            use_container_width=True,
            disabled=not cust_map or not available_by_id,
        )
    with action_col2:
        cancelled = st.button("Cancel Draft", use_container_width=True)

    if cancelled:
        clear_sale_draft()
        st.rerun()

    if submitted:
        sale_receipt = str(st.session_state.get(receipt_key, "") or "").strip()
        sale_cust = st.session_state.get(customer_key, "")
        sale_date = st.session_state.get(date_key, date.today())
        sale_official = st.session_state.get(official_key, 0)
        selected_ids = list(st.session_state.get(selected_key, []))

        if not selected_ids:
            st.warning("Select at least one stock item.")
        else:
            cust_id = cust_map.get(sale_cust, "")
            if not cust_id:
                st.error("Customer selection is required.")
            else:
                sell_data = {}
                validation_errors = []

                for stk_id in selected_ids:
                    stock = available_by_id.get(stk_id)
                    if not stock:
                        validation_errors.append(f"Stock {stk_id} is no longer available for sale.")
                        continue

                    weight = float(st.session_state.get(sale_state_key(f"weight_{stk_id}"), 0) or 0)
                    gold = float(st.session_state.get(sale_state_key(f"gold_{stk_id}"), 0) or 0)
                    labor = float(st.session_state.get(sale_state_key(f"labor_{stk_id}"), 0) or 0)
                    stock_weight = float(stock.get("stk_weight", 0) or 0)

                    if weight <= 0:
                        validation_errors.append(f"Sell weight for {stk_id} must be greater than 0.")
                    elif weight > stock_weight:
                        validation_errors.append(
                            f"Sell weight for {stk_id} cannot exceed stock weight ({stock_weight:.2f}g)."
                        )

                    if gold <= 0:
                        validation_errors.append(f"Gold sell price for {stk_id} must be greater than 0.")
                    if labor < 0:
                        validation_errors.append(f"Labor sell price for {stk_id} cannot be negative.")

                    sell_data[stk_id] = {
                        "weight": weight,
                        "gold": gold,
                        "labor": labor,
                        "stock": stock,
                    }

                if validation_errors:
                    for message in validation_errors:
                        st.error(message)
                else:
                    try:
                        locked_stocks = {}
                        lock_sql = get_query("stock.fetch_by_id_for_update", schema=db.schema)
                        sale_sql = get_query("sale.insert", schema=db.schema)
                        update_sql = get_query("stock.update_status_sold", schema=db.schema)

                        total_gold = sum(d["gold"] for d in sell_data.values())
                        total_labor = sum(d["labor"] for d in sell_data.values())
                        total_weight = sum(d["weight"] for d in sell_data.values())
                        total_price = sum(d["gold"] * d["weight"] + d["labor"] for d in sell_data.values())

                        with db.transaction() as cur:
                            for stk_id in selected_ids:
                                cur.execute(lock_sql, (stk_id,))
                                locked_row = cur.fetchone()
                                if not locked_row:
                                    raise ValueError(f"Stock {stk_id} no longer exists.")
                                locked_stock = dict(locked_row)
                                if locked_stock.get("stk_status") != "IN STOCK":
                                    raise ValueError(
                                        f"Stock {stk_id} is no longer available. "
                                        f"Current status: {locked_stock.get('stk_status')}."
                                    )
                                locked_stocks[stk_id] = locked_stock

                            sale_id = db.generate_pk("sale", cur=cur)
                            cur.execute(
                                sale_sql,
                                (
                                    sale_id,
                                    sale_receipt,
                                    cust_id,
                                    sale_date.isoformat(),
                                    total_labor,
                                    total_gold,
                                    total_price,
                                    total_weight,
                                    sale_official,
                                ),
                            )

                            for stk_id, details in sell_data.items():
                                stock = locked_stocks[stk_id]
                                cost_gold = float(stock.get("stk_gold_cost", 0) or 0) * float(stock.get("stk_weight", 0) or 0)
                                cost_labor = float(stock.get("stk_labor_cost", 0) or 0)
                                revenue = details["gold"] * details["weight"] + details["labor"]
                                profit = revenue - cost_gold - cost_labor

                                cur.execute(
                                    update_sql,
                                    (
                                        sale_id,
                                        details["weight"],
                                        details["labor"],
                                        details["gold"],
                                        sale_date.isoformat(),
                                        profit,
                                        stk_id,
                                    ),
                                )

                        st.session_state[SALE_SUCCESS_KEY] = (
                            f"Sale {sale_id} created. {len(selected_ids)} item(s) marked SOLD."
                        )
                        clear_sale_draft()
                        clear_query_caches()
                        logger.info("Sale %s: %d items", sale_id, len(selected_ids))
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")
                        logger.error("Sale creation failed", exc_info=True)

# ═══════════════ EDIT SALE ═══════════════
with tab_edit:
    st.markdown("#### Edit Existing Sale")
    edit_id = st.text_input("Sale ID to edit", key="edit_sale")
    if edit_id and st.button("🔍 Load", key="btn_load_sale"):
        sale = db.fetch_one("sale.fetch_by_id", (edit_id,))
        if sale:
            st.session_state["editing_sale"] = sale
        else:
            st.warning(f"Sale {edit_id} not found.")

    if "editing_sale" in st.session_state:
        sale = st.session_state["editing_sale"]
        with st.form("edit_sale"):
            e_receipt = st.text_input("Receipt No.", value=sale.get("sale_receipt_no", "") or "")
            e_gold = st.number_input("Gold Sell *", min_value=0.01, value=max(0.01, float(sale.get("sale_gold_sell", 0) or 0)), step=0.01)
            e_labor = st.number_input("Labor Sell *", min_value=0.0, value=max(0.0, float(sale.get("sale_labor_sell", 0) or 0)), step=0.01)
            e_weight = st.number_input("Weight *", min_value=0.01, value=max(0.01, float(sale.get("sale_weight", 0) or 0)), step=0.01)
            e_price = st.number_input("Total Price *", min_value=0.01, value=max(0.01, float(sale.get("sale_price", 0) or 0)), step=0.01)

            if st.form_submit_button("💾 Save", use_container_width=True):
                try:
                    cols = [
                        "sale_receipt_no",
                        "sale_cust_id",
                        "sale_sold_date",
                        "sale_labor_sell",
                        "sale_gold_sell",
                        "sale_price",
                        "sale_weight",
                        "sale_official_receipt",
                    ]
                    vals = [
                        e_receipt,
                        sale.get("sale_cust_id", ""),
                        sale.get("sale_sold_date", ""),
                        e_labor,
                        e_gold,
                        e_price,
                        e_weight,
                        sale.get("sale_official_receipt", 0),
                    ]
                    with db.transaction() as cur:
                        db.build_update(
                            "sale",
                            cols,
                            vals,
                            sale["sale_id"],
                            cur,
                            expected_last_update=sale.get("sale_last_update"),
                        )
                    clear_query_caches()
                    st.success(f"✅ Sale {sale['sale_id']} updated.")
                    del st.session_state["editing_sale"]
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")
