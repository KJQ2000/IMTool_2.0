"""
pages/06_📖_Bookings.py — Booking Management (multi-stock + payments + close booking)

CRITICAL: 1 booking can contain MULTIPLE stock items.
Each stock gets its own gold/labor/weight booking prices.
Close Booking = finalize payment + atomically create a Sale with booked stock data.
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
st.markdown("## 📖 Booking Management")
db = DatabaseManager.get_instance()

BOOK_DRAFT_PREFIX = "create_book_"
BOOK_SUCCESS_KEY = "create_book_success_message"


def book_state_key(name: str) -> str:
    return f"{BOOK_DRAFT_PREFIX}{name}"


def clear_book_draft() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith(BOOK_DRAFT_PREFIX):
            del st.session_state[key]


def format_stock_label(stock: dict) -> str:
    return (
        f"{stock['stk_id']} — {stock.get('stk_type', '?')} · "
        f"{stock.get('stk_pattern', '?')} · {stock.get('stk_weight', 0)}g"
    )


tab_view, tab_add, tab_edit, tab_pay, tab_close = st.tabs(
    ["📋 View Bookings", "➕ Create Booking", "✏️ Edit Booking", "💳 Add Payment", "📦 Close Booking"]
)

# ═══════════════ VIEW ═══════════════
with tab_view:
    try:
        search_term = st.text_input(
            "Search Bookings",
            key="book_view_search",
            placeholder="Booking ID / receipt / customer ID / status",
        ).strip()
        search_like = f"%{search_term}%"
        total_rows = int(
            fetch_scalar_cached(
                "booking.count_filtered",
                (search_term, search_like, search_like, search_like, search_like),
            ) or 0
        )
        page_size, _, offset = render_pagination_controls(
            table_key="book_view",
            total_rows=total_rows,
        )
        bookings = fetch_rows_cached(
            "booking.fetch_page",
            (search_term, search_like, search_like, search_like, search_like, page_size, offset),
        )
        if bookings:
            df_book = pd.DataFrame(bookings)
            original_df, edited_df = render_filterable_editor(
                df_book, "book_view", "book_id",
                disabled_columns=["book_id", "book_created_at", "book_last_update"],
            )
            if st.button("💾 Save Changes", key="btn_save_book_table"):
                try:
                    count = save_table_changes(original_df, edited_df, "booking", "book_id")
                    if count > 0:
                        st.success(f"✅ Saved {count} row(s).")
                        st.rerun()
                    else:
                        st.info("No changes detected.")
                except Exception as e:
                    st.error(f"Save failed: {e}")

            with st.expander("🔍 View stock items for a booking"):
                lookup_book = st.text_input("Enter Booking ID", key="lookup_book")
                if lookup_book:
                    stks = db.fetch_all("stock.fetch_by_book_id", (lookup_book,))
                    if stks:
                        st.dataframe(pd.DataFrame(stks), use_container_width=True)
                    else:
                        st.info("No items found for this booking.")
        else:
            st.info("No booking records found.")
    except Exception as e:
        st.error(f"Failed: {e}")

    st.markdown("---")
    del_id = st.text_input("Booking ID to delete", key="del_book")
    if st.button("Delete", key="btn_del_book") and del_id:
        try:
            with db.transaction() as cur:
                reset_sql = get_query("stock.reset_to_in_stock_from_booking", schema=db.schema)
                stk_sql = get_query("stock.fetch_stk_ids_by_booking", schema=db.schema)
                delete_payments_sql = get_query("book_payment.delete_by_booking", schema=db.schema)
                cur.execute(stk_sql, (del_id,))
                for row in cur.fetchall():
                    sid = row["stk_id"] if isinstance(row, dict) else row[0]
                    cur.execute(reset_sql, (sid,))
                cur.execute(delete_payments_sql, (del_id,))
                db.build_delete("booking", del_id, cur)
            clear_query_caches()
            st.success(f"Booking {del_id} deleted. Stocks reset.")
            st.rerun()
        except Exception as e:
            st.error(f"Failed: {e}")

# ═══════════════ CREATE BOOKING (multi-stock, per-stock pricing) ═══════════════
with tab_add:
    st.markdown("#### Create New Booking")
    success_message = st.session_state.pop(BOOK_SUCCESS_KEY, None)
    if success_message:
        st.success(f"✅ {success_message}")
    st.info("💡 **One booking can include multiple stock items.** Enter pricing per item below.")

    customers = fetch_rows_cached("customer.fetch_all")
    cust_map = {f"{c.get('cust_name', '?')} ({c['cust_id']})": c["cust_id"] for c in customers}

    available = fetch_rows_cached("stock.fetch_in_stock")
    available_by_id = {s["stk_id"]: s for s in available}

    receipt_key = book_state_key("receipt")
    customer_key = book_state_key("customer")
    date_key = book_state_key("date")
    selected_key = book_state_key("selected_ids")

    if customer_key not in st.session_state and cust_map:
        st.session_state[customer_key] = next(iter(cust_map.keys()))
    elif customer_key in st.session_state and st.session_state[customer_key] not in cust_map:
        st.session_state[customer_key] = next(iter(cust_map.keys())) if cust_map else "No customers"

    if date_key not in st.session_state:
        st.session_state[date_key] = date.today()
    if selected_key not in st.session_state:
        st.session_state[selected_key] = []
    else:
        st.session_state[selected_key] = [
            stk_id for stk_id in st.session_state[selected_key]
            if stk_id in available_by_id
        ]

    if not cust_map:
        st.warning("Create at least one customer before creating a booking.")
    if not available_by_id:
        st.info("No IN STOCK items are available for booking right now.")

    c1, c2 = st.columns(2)
    with c1:
        st.text_input("Receipt No.", key=receipt_key)
        st.selectbox(
            "Customer *",
            list(cust_map.keys()) if cust_map else ["No customers"],
            key=customer_key,
            disabled=not cust_map,
        )
    with c2:
        st.date_input("Booking Date", key=date_key)

    selected_ids = st.multiselect(
        "📦 Select Stock Items (multi-select)",
        list(available_by_id.keys()),
        key=selected_key,
        format_func=lambda stk_id: format_stock_label(available_by_id[stk_id]),
        disabled=not available_by_id,
    )

    book_data: dict = {}
    if selected_ids:
        st.markdown("##### 💲 Enter booking prices for each item:")
        for stk_id in selected_ids:
            stock = available_by_id[stk_id]
            weight_key = book_state_key(f"weight_{stk_id}")
            gold_key = book_state_key(f"gold_{stk_id}")
            labor_key = book_state_key(f"labor_{stk_id}")

            if weight_key not in st.session_state:
                st.session_state[weight_key] = max(0.01, float(stock.get("stk_weight", 0) or 0))
            if gold_key not in st.session_state:
                st.session_state[gold_key] = max(0.01, float(stock.get("stk_gold_cost", 0) or 0))
            if labor_key not in st.session_state:
                st.session_state[labor_key] = max(0.0, float(stock.get("stk_labor_cost", 0) or 0))

            st.markdown(f"**{format_stock_label(stock)}**")
            r1, r2, r3 = st.columns(3)
            with r1:
                bw = st.number_input("Book Weight *", min_value=0.01, step=0.01, key=weight_key)
            with r2:
                bg = st.number_input("Gold Book Price/g *", min_value=0.01, step=0.01, key=gold_key)
            with r3:
                bl = st.number_input("Labor Book *", min_value=0.0, step=0.01, key=labor_key)
            book_data[stk_id] = {"weight": bw, "gold": bg, "labor": bl, "stock": stock}
            st.caption(f"Line Total: RM {bw * bg + bl:,.2f}")

        total_gold = sum(d["gold"] for d in book_data.values())
        total_labor = sum(d["labor"] for d in book_data.values())
        total_weight = sum(d["weight"] for d in book_data.values())
        total_price = sum(d["gold"] * d["weight"] + d["labor"] for d in book_data.values())

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Weight", f"{total_weight:,.2f}g")
        m2.metric("Total Gold", f"RM {total_gold:,.2f}")
        m3.metric("Total Labor", f"RM {total_labor:,.2f}")
        m4.metric("Grand Total", f"RM {total_price:,.2f}")

    book_deposit = st.number_input("Initial Deposit (RM)", min_value=0.0, step=0.01, key=book_state_key("deposit"))

    action_col1, action_col2 = st.columns(2)
    with action_col1:
        submitted = st.button(
            "✅ Confirm & Create Booking",
            use_container_width=True,
            disabled=not cust_map or not available_by_id,
        )
    with action_col2:
        cancelled = st.button("Cancel Draft", use_container_width=True, key="cancel_book_draft")

    if cancelled:
        clear_book_draft()
        st.rerun()

    if submitted:
        book_receipt = str(st.session_state.get(receipt_key, "") or "").strip()
        book_cust = st.session_state.get(customer_key, "")
        book_date_val = st.session_state.get(date_key, date.today())
        selected_ids = list(st.session_state.get(selected_key, []))

        if not selected_ids:
            st.warning("Select at least one stock item.")
        else:
            cust_id = cust_map.get(book_cust, "")
            if not cust_id:
                st.error("Customer selection is required.")
            else:
                # Re-read book_data from session state
                book_data = {}
                for stk_id in selected_ids:
                    stock = available_by_id.get(stk_id)
                    if not stock:
                        continue
                    weight = float(st.session_state.get(book_state_key(f"weight_{stk_id}"), 0) or 0)
                    gold = float(st.session_state.get(book_state_key(f"gold_{stk_id}"), 0) or 0)
                    labor = float(st.session_state.get(book_state_key(f"labor_{stk_id}"), 0) or 0)
                    book_data[stk_id] = {"weight": weight, "gold": gold, "labor": labor, "stock": stock}

                total_gold = sum(d["gold"] for d in book_data.values())
                total_labor = sum(d["labor"] for d in book_data.values())
                total_weight = sum(d["weight"] for d in book_data.values())
                total_price = sum(d["gold"] * d["weight"] + d["labor"] for d in book_data.values())
                remaining = total_price - book_deposit

                try:
                    lock_sql = get_query("stock.fetch_by_id_for_update", schema=db.schema)
                    update_sql = get_query("stock.update_status_booked", schema=db.schema)
                    with db.transaction() as cur:
                        locked_stocks = {}
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

                        book_id = db.generate_pk("booking", cur=cur)
                        book_sql = get_query("booking.insert", schema=db.schema)
                        cur.execute(book_sql, (
                            book_id, cust_id, book_receipt, book_date_val.isoformat(),
                            total_gold, total_labor, total_weight, total_price, remaining, "BOOKED",
                        ))

                        if book_deposit > 0:
                            bp_id = db.generate_pk("book_payment", cur=cur)
                            bp_sql = get_query("book_payment.insert", schema=db.schema)
                            cur.execute(bp_sql, (bp_id, book_deposit, book_date_val.isoformat(), book_id, "PAID"))

                        for stk_id, details in book_data.items():
                            stk_book_price = details["weight"] * details["gold"] + details["labor"]
                            cur.execute(update_sql, (
                                book_id, details["weight"], details["labor"],
                                details["gold"], stk_book_price, stk_id,
                            ))

                    st.session_state[BOOK_SUCCESS_KEY] = (
                        f"Booking {book_id} created! {len(book_data)} item(s) marked BOOKED."
                    )
                    clear_book_draft()
                    clear_query_caches()
                    logger.info("Booking %s: %d items", book_id, len(book_data))
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")
                    logger.error("Booking creation failed", exc_info=True)

# ═══════════════ EDIT BOOKING (per-stock) ═══════════════
with tab_edit:
    st.markdown("#### Edit Existing Booking")
    edit_id = st.text_input("Booking ID to edit", key="edit_book")
    if edit_id and st.button("🔍 Load", key="btn_load_book"):
        b = db.fetch_one("booking.fetch_by_id", (edit_id,))
        if b:
            st.session_state["editing_book"] = b
            st.session_state["editing_book_stocks"] = db.fetch_all("stock.fetch_by_book_id", (edit_id,))
        else:
            st.warning(f"Booking {edit_id} not found.")

    if "editing_book" in st.session_state:
        bk = st.session_state["editing_book"]
        booked_stocks = st.session_state.get("editing_book_stocks", [])

        with st.form("edit_book"):
            e_receipt = st.text_input("Receipt", value=bk.get("book_receipt_no", "") or "")
            statuses = ["BOOKED", "COMPLETED", "CANCELLED"]
            e_status = st.selectbox("Status", statuses,
                index=statuses.index(bk.get("book_status", "BOOKED")) if bk.get("book_status") in statuses else 0)

            st.markdown("##### 💲 Per-stock booking prices:")
            edit_stock_data = {}
            for stk in booked_stocks:
                stk_id = stk["stk_id"]
                st.markdown(f"**{stk_id} — {stk.get('stk_type', '?')} · {stk.get('stk_pattern', '?')} · {stk.get('stk_weight', 0)}g**")
                r1, r2, r3 = st.columns(3)
                with r1:
                    ew = st.number_input(
                        "Weight", min_value=0.01,
                        value=max(0.01, float(stk.get("stk_weight_book", 0) or stk.get("stk_weight", 0) or 0)),
                        step=0.01, key=f"edit_bw_{stk_id}"
                    )
                with r2:
                    eg = st.number_input(
                        "Gold Price/g", min_value=0.01,
                        value=max(0.01, float(stk.get("stk_gold_book", 0) or stk.get("stk_gold_cost", 0) or 0)),
                        step=0.01, key=f"edit_bg_{stk_id}"
                    )
                with r3:
                    el = st.number_input(
                        "Labor", min_value=0.0,
                        value=max(0.0, float(stk.get("stk_labor_book", 0) or stk.get("stk_labor_cost", 0) or 0)),
                        step=0.01, key=f"edit_bl_{stk_id}"
                    )
                edit_stock_data[stk_id] = {"weight": ew, "gold": eg, "labor": el}
                st.caption(f"Line Total: RM {ew * eg + el:,.2f}")

            if st.form_submit_button("💾 Save", use_container_width=True):
                try:
                    total_gold = sum(d["gold"] for d in edit_stock_data.values())
                    total_labor = sum(d["labor"] for d in edit_stock_data.values())
                    total_weight = sum(d["weight"] for d in edit_stock_data.values())
                    total_price = sum(d["gold"] * d["weight"] + d["labor"] for d in edit_stock_data.values())
                    total_paid = db.fetch_scalar("book_payment.sum_payments", (bk["book_id"],)) or 0
                    e_remaining = total_price - float(total_paid)

                    with db.transaction() as cur:
                        db.build_update(
                            "booking",
                            [
                                "book_gold_price",
                                "book_labor_price",
                                "book_weight",
                                "book_price",
                                "book_cust_id",
                                "book_receipt_no",
                                "book_remaining",
                                "book_status",
                            ],
                            [
                                total_gold,
                                total_labor,
                                total_weight,
                                total_price,
                                bk.get("book_cust_id"),
                                e_receipt,
                                e_remaining,
                                e_status,
                            ],
                            bk["book_id"],
                            cur,
                            expected_last_update=bk.get("book_last_update"),
                        )

                        update_stk_sql = get_query("stock.update_status_booked", schema=db.schema)
                        for stk_id, details in edit_stock_data.items():
                            stk_book_price = details["weight"] * details["gold"] + details["labor"]
                            cur.execute(update_stk_sql, (
                                bk["book_id"], details["weight"], details["labor"],
                                details["gold"], stk_book_price, stk_id,
                            ))

                    clear_query_caches()
                    st.success(f"✅ Booking {bk['book_id']} updated.")
                    del st.session_state["editing_book"]
                    if "editing_book_stocks" in st.session_state:
                        del st.session_state["editing_book_stocks"]
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")

# ═══════════════ ADD PAYMENT ═══════════════
with tab_pay:
    st.markdown("#### Add Payment to Booking")
    pay_book_id = st.text_input("Booking ID", key="pay_book")

    if pay_book_id:
        booking = db.fetch_one("booking.fetch_by_id", (pay_book_id,))
        if booking:
            st.info(f"**{pay_book_id}** — Total: RM {booking.get('book_price', 0)} · Remaining: RM {booking.get('book_remaining', 0)}")

            payments = db.fetch_all("book_payment.fetch_by_booking", (pay_book_id,))
            if payments:
                st.dataframe(pd.DataFrame(payments), use_container_width=True)

            with st.form("add_payment"):
                p_amt = st.number_input("Payment Amount (RM)", min_value=0.0, step=0.01)
                p_date = st.date_input("Payment Date", value=date.today())

                submitted_payment = st.form_submit_button("💳 Add Payment", use_container_width=True)

                if submitted_payment:
                    if p_amt <= 0:
                        st.error("Payment amount must be greater than 0.")
                    else:
                        try:
                            with db.transaction() as cur:
                                lock_booking_sql = get_query("booking.fetch_by_id_for_update", schema=db.schema)
                                cur.execute(lock_booking_sql, (pay_book_id,))
                                locked_booking = cur.fetchone()
                                if not locked_booking:
                                    raise ValueError(f"Booking {pay_book_id} not found.")
                                locked_booking = dict(locked_booking)
                                if locked_booking.get("book_status") in {"COMPLETED", "CANCELLED"}:
                                    raise ValueError(
                                        f"Booking {pay_book_id} cannot accept payment in status "
                                        f"{locked_booking.get('book_status')}."
                                    )
                                current_remaining = float(locked_booking.get("book_remaining", 0) or 0)
                                if p_amt > current_remaining:
                                    raise ValueError(
                                        f"Payment RM {p_amt:,.2f} exceeds remaining balance "
                                        f"RM {current_remaining:,.2f}."
                                    )
                                bp_id = db.generate_pk("book_payment", cur=cur)
                                bp_sql = get_query("book_payment.insert", schema=db.schema)
                                update_remaining_sql = get_query("booking.update_remaining", schema=db.schema)
                                cur.execute(bp_sql, (bp_id, p_amt, p_date.isoformat(), pay_book_id, "PAID"))
                                new_rem = current_remaining - p_amt
                                cur.execute(update_remaining_sql, (new_rem, pay_book_id))
                            clear_query_caches()
                            st.success(f"✅ Payment {bp_id}: RM {p_amt}. Remaining: RM {new_rem}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed: {e}")
                            logger.error("Payment insert failed", exc_info=True)
        else:
            st.warning(f"Booking {pay_book_id} not found.")

# ═══════════════ CLOSE BOOKING (atomic: final payment + create sale) ═══════════════
with tab_close:
    st.markdown("#### 📦 Close Booking & Create Sale")
    st.info(
        "💡 **Close a booking** to finalize payment and automatically create a sale. "
        "All booked stock items will be moved to SOLD with booking prices prefilled. "
        "This is fully atomic — nothing changes until you confirm."
    )

    close_book_id = st.text_input("Booking ID to close", key="close_book")

    if close_book_id:
        close_booking = db.fetch_one("booking.fetch_by_id", (close_book_id,))
        if close_booking:
            if close_booking.get("book_status") == "COMPLETED":
                st.warning("This booking is already completed.")
            elif close_booking.get("book_status") == "CANCELLED":
                st.warning("This booking has been cancelled.")
            else:
                booked_stocks = db.fetch_all("stock.fetch_by_book_id", (close_book_id,))
                total_paid = db.fetch_scalar("book_payment.sum_payments", (close_book_id,)) or 0
                remaining = float(close_booking.get("book_remaining", 0) or 0)

                st.markdown("##### Booking Summary")
                mc1, mc2, mc3 = st.columns(3)
                mc1.metric("Total Price", f"RM {close_booking.get('book_price', 0):,.2f}")
                mc2.metric("Total Paid", f"RM {float(total_paid):,.2f}")
                mc3.metric("Remaining", f"RM {remaining:,.2f}")

                if booked_stocks:
                    st.markdown("##### Booked Stock Items → Will become SOLD")
                    stk_display = []
                    for stk in booked_stocks:
                        line_price = (
                            float(stk.get("stk_weight_book", 0) or 0) *
                            float(stk.get("stk_gold_book", 0) or 0) +
                            float(stk.get("stk_labor_book", 0) or 0)
                        )
                        stk_display.append({
                            "Stock ID": stk["stk_id"],
                            "Type": stk.get("stk_type", ""),
                            "Pattern": stk.get("stk_pattern", ""),
                            "Book Weight": stk.get("stk_weight_book", 0),
                            "Gold Book": stk.get("stk_gold_book", 0),
                            "Labor Book": stk.get("stk_labor_book", 0),
                            "Line Total": f"RM {line_price:,.2f}",
                        })
                    st.dataframe(pd.DataFrame(stk_display), use_container_width=True, hide_index=True)

                # Sale details
                with st.form("close_booking_form"):
                    st.markdown("##### Sale Details")
                    cb_c1, cb_c2 = st.columns(2)
                    with cb_c1:
                        sale_receipt = st.text_input("Sale Receipt No.", value=close_booking.get("book_receipt_no", "") or "")
                        sale_date = st.date_input("Sale Date", value=date.today())
                    with cb_c2:
                        sale_official = st.selectbox("Official Receipt?", [0, 1])

                    confirm_close = st.form_submit_button(
                        "🔒 Close Booking & Create Sale",
                        use_container_width=True,
                    )

                if confirm_close:
                    if not booked_stocks:
                        st.error("No stocks found for this booking.")
                    else:
                        try:
                            with db.transaction() as cur:
                                lock_booking_sql = get_query("booking.fetch_by_id_for_update", schema=db.schema)
                                cur.execute(lock_booking_sql, (close_book_id,))
                                locked_booking_row = cur.fetchone()
                                if not locked_booking_row:
                                    raise ValueError(f"Booking {close_book_id} no longer exists.")
                                locked_booking = dict(locked_booking_row)
                                if locked_booking.get("book_status") == "COMPLETED":
                                    raise ValueError("This booking is already completed.")
                                if locked_booking.get("book_status") == "CANCELLED":
                                    raise ValueError("This booking has been cancelled.")

                                locked_stocks_sql = get_query("stock.fetch_by_book_id_for_update", schema=db.schema)
                                cur.execute(locked_stocks_sql, (close_book_id,))
                                locked_stock_rows = [dict(row) for row in cur.fetchall()]
                                if not locked_stock_rows:
                                    raise ValueError("No stocks found for this booking.")

                                # 1. Add final payment for remaining amount
                                locked_remaining = float(locked_booking.get("book_remaining", 0) or 0)
                                if locked_remaining > 0:
                                    bp_id = db.generate_pk("book_payment", cur=cur)
                                    bp_sql = get_query("book_payment.insert", schema=db.schema)
                                    cur.execute(bp_sql, (
                                        bp_id, locked_remaining, date.today().isoformat(),
                                        close_book_id, "PAID",
                                    ))

                                # 2. Update booking status to COMPLETED
                                complete_sql = get_query("booking.update_status_completed", schema=db.schema)
                                cur.execute(complete_sql, (close_book_id,))

                                # 3. Create sale record with booking data
                                sale_id = db.generate_pk("sale", cur=cur)
                                cust_id = locked_booking.get("book_cust_id", "")

                                total_labor_sell = sum(float(s.get("stk_labor_book", 0) or 0) for s in locked_stock_rows)
                                total_gold_sell = sum(float(s.get("stk_gold_book", 0) or 0) for s in locked_stock_rows)
                                total_weight_sell = sum(float(s.get("stk_weight_book", 0) or 0) for s in locked_stock_rows)
                                total_price_sell = sum(
                                    float(s.get("stk_weight_book", 0) or 0) * float(s.get("stk_gold_book", 0) or 0)
                                    + float(s.get("stk_labor_book", 0) or 0)
                                    for s in locked_stock_rows
                                )

                                sale_sql = get_query("sale.insert", schema=db.schema)
                                cur.execute(sale_sql, (
                                    sale_id, sale_receipt, cust_id,
                                    sale_date.isoformat(),
                                    total_labor_sell, total_gold_sell,
                                    total_price_sell, total_weight_sell,
                                    sale_official,
                                ))

                                # 4. Update each stock: BOOKED → SOLD, copy book prices to sell prices
                                update_sold_sql = get_query("stock.update_status_sold", schema=db.schema)
                                for stk in locked_stock_rows:
                                    stk_weight_sell = float(stk.get("stk_weight_book", 0) or 0)
                                    stk_gold_sell = float(stk.get("stk_gold_book", 0) or 0)
                                    stk_labor_sell = float(stk.get("stk_labor_book", 0) or 0)

                                    # Calculate profit: revenue - cost
                                    revenue = stk_weight_sell * stk_gold_sell + stk_labor_sell
                                    cost_gold = float(stk.get("stk_weight", 0) or 0) * float(stk.get("stk_gold_cost", 0) or 0)
                                    cost_labor = float(stk.get("stk_labor_cost", 0) or 0)
                                    profit = revenue - cost_gold - cost_labor

                                    cur.execute(update_sold_sql, (
                                        sale_id,
                                        stk_weight_sell,
                                        stk_labor_sell,
                                        stk_gold_sell,
                                        sale_date.isoformat(),
                                        profit,
                                        stk["stk_id"],
                                    ))

                            clear_query_caches()
                            st.success(
                                f"✅ Booking {close_book_id} closed! "
                                f"Sale {sale_id} created with {len(locked_stock_rows)} item(s)."
                            )
                            logger.info("Closed booking %s → sale %s", close_book_id, sale_id)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed: {e}")
                            logger.error("Close booking failed", exc_info=True)
        else:
            st.warning(f"Booking {close_book_id} not found.")
