"""
pages/06_📖_Bookings.py — Booking Management (multi-stock + payments)

CRITICAL: 1 booking can contain MULTIPLE stock items.
"""
from __future__ import annotations
from datetime import date
import pandas as pd
import streamlit as st
from auth_controller import require_auth
from config_loader import get_query
from database_manager import DatabaseManager
from logging_config import get_logger

logger = get_logger(__name__)
require_auth()
st.markdown("## 📖 Booking Management")
db = DatabaseManager.get_instance()

tab_view, tab_add, tab_edit, tab_pay = st.tabs(
    ["📋 View Bookings", "➕ Create Booking", "✏️ Edit Booking", "💳 Add Payment"]
)

# ═══════════════ VIEW ═══════════════
with tab_view:
    try:
        bookings = db.fetch_all("booking.fetch_all")
        if bookings:
            st.dataframe(pd.DataFrame(bookings), use_container_width=True, height=400)

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
            st.success(f"Booking {del_id} deleted. Stocks reset.")
            st.rerun()
        except Exception as e:
            st.error(f"Failed: {e}")

# ═══════════════ CREATE BOOKING (multi-stock) ═══════════════
with tab_add:
    st.markdown("#### Create New Booking")
    st.info("💡 **One booking can include multiple stock items.**")

    customers = db.fetch_all("customer.fetch_all")
    cust_map = {f"{c.get('cust_name', '?')} ({c['cust_id']})": c["cust_id"] for c in customers}

    available = db.fetch_all("stock.fetch_in_stock")
    stk_map = {f"{s['stk_id']} — {s.get('stk_type', '?')} · {s.get('stk_pattern', '?')} · {s.get('stk_weight', 0)}g": s for s in available}

    with st.form("create_book"):
        c1, c2 = st.columns(2)
        with c1:
            book_receipt = st.text_input("Receipt No.")
            book_cust = st.selectbox("Customer *", list(cust_map.keys()) if cust_map else ["No customers"])
            book_date = st.date_input("Date", value=date.today())
        with c2:
            book_gold = st.number_input("Gold Price", min_value=0.0, step=0.01)
            book_labor = st.number_input("Labor Price", min_value=0.0, step=0.01)
            book_weight = st.number_input("Weight (g)", min_value=0.0, step=0.01)

        selected = st.multiselect("📦 Select Stock Items (multi-select)", list(stk_map.keys()))
        book_deposit = st.number_input("Initial Deposit (RM)", min_value=0.0, step=0.01)

        submitted = st.form_submit_button("✅ Create Booking", use_container_width=True)

    if submitted and selected:
        if not cust_map or book_cust not in cust_map:
            st.error("Customer selection is required.")
        else:
            try:
                cust_id = cust_map.get(book_cust, "")
                total_price = book_gold + book_labor
                remaining = total_price - book_deposit

                with db.transaction() as cur:
                    book_id = db.generate_pk("booking", cur=cur)
                    book_sql = get_query("booking.insert", schema=db.schema)
                    cur.execute(book_sql, (
                        book_id, cust_id, book_receipt, book_date.isoformat(),
                        book_gold, book_labor, book_weight, total_price, remaining, "BOOKED",
                    ))

                    if book_deposit > 0:
                        bp_id = db.generate_pk("book_payment", cur=cur)
                        bp_sql = get_query("book_payment.insert", schema=db.schema)
                        cur.execute(
                            bp_sql,
                            (bp_id, book_deposit, book_date.isoformat(), book_id, "PAID"),
                        )

                    update_sql = get_query("stock.update_status_booked", schema=db.schema)
                    for stk_label in selected:
                        s = stk_map[stk_label]
                        cur.execute(
                            update_sql,
                            (book_id, book_weight, book_labor, book_gold, total_price, s["stk_id"]),
                        )

                st.success(f"✅ Booking {book_id} created! {len(selected)} item(s) marked BOOKED.")
            except Exception as e:
                st.error(f"Failed: {e}")
                logger.error("Booking creation failed", exc_info=True)
    elif submitted:
        st.warning("Select at least one stock item.")

# ═══════════════ EDIT ═══════════════
with tab_edit:
    edit_id = st.text_input("Booking ID to edit", key="edit_book")
    if edit_id and st.button("🔍 Load", key="btn_load_book"):
        b = db.fetch_one("booking.fetch_by_id", (edit_id,))
        if b:
            st.session_state["editing_book"] = b
        else:
            st.warning(f"Booking {edit_id} not found.")

    if "editing_book" in st.session_state:
        bk = st.session_state["editing_book"]
        with st.form("edit_book"):
            e_receipt = st.text_input("Receipt", value=bk.get("book_receipt_no", "") or "")
            e_gold = st.number_input("Gold Price", min_value=0.0, value=max(0.0, float(bk.get("book_gold_price", 0) or 0)), step=0.01)
            e_labor = st.number_input("Labor Price", min_value=0.0, value=max(0.0, float(bk.get("book_labor_price", 0) or 0)), step=0.01)
            e_weight = st.number_input("Weight", min_value=0.0, value=max(0.0, float(bk.get("book_weight", 0) or 0)), step=0.01)
            statuses = ["BOOKED", "COMPLETED", "CANCELLED"]
            e_status = st.selectbox("Status", statuses,
                index=statuses.index(bk.get("book_status", "BOOKED")) if bk.get("book_status") in statuses else 0)

            if st.form_submit_button("💾 Save", use_container_width=True):
                try:
                    e_price = e_gold + e_labor
                    total_paid = db.fetch_scalar("book_payment.sum_payments", (bk["book_id"],)) or 0
                    e_remaining = e_price - float(total_paid)
                    update_sql = get_query("booking.update_by_id", schema=db.schema)
                    with db.transaction() as cur:
                        cur.execute(update_sql, (
                            e_gold, e_labor, e_weight, e_price,
                            bk.get("book_cust_id"), e_receipt, e_remaining, bk["book_id"],
                        ))
                    st.success(f"✅ Booking {bk['book_id']} updated.")
                    del st.session_state["editing_book"]
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
                                bp_id = db.generate_pk("book_payment", cur=cur)
                                bp_sql = get_query("book_payment.insert", schema=db.schema)
                                update_remaining_sql = get_query("booking.update_remaining", schema=db.schema)
                                cur.execute(bp_sql, (bp_id, p_amt, p_date.isoformat(), pay_book_id, "PAID"))
                                new_rem = float(booking.get("book_remaining", 0)) - p_amt
                                cur.execute(update_remaining_sql, (new_rem, pay_book_id))
                            st.success(f"✅ Payment {bp_id}: RM {p_amt}. Remaining: RM {new_rem}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed: {e}")
                            logger.error("Payment insert failed", exc_info=True)
        else:
            st.warning(f"Booking {pay_book_id} not found.")
