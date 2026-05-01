"""
pages/00_Home.py
──────────────────────────
Enterprise Dashboard Landing Page
"""

from __future__ import annotations

import streamlit as st
from database_manager import DatabaseManager
from auth_controller import get_current_user
from config.logging_config import get_logger

logger = get_logger(__name__)

st.markdown(
    """
    <div class="main-header">
        <img src="https://chopkonghin.com/cdn/shop/files/logo.png?v=1759327714&width=3840" style="max-height: 100px; margin-bottom: 1.5rem;">
        <div class="main-title">ENTERPRISE INVENTORY</div>
        <div class="main-subtitle">Management System</div>
    </div>
    """,
    unsafe_allow_html=True,
)

logger.info("Dashboard loaded for user: %s", get_current_user())

# Dashboard metrics
try:
    db = DatabaseManager.get_instance()

    col1, col2, col3, col4 = st.columns(4)

    # Stock count
    in_stock = db.fetch_scalar("stock.count_by_status", ("IN STOCK",)) or 0
    with col1:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-value">{int(in_stock)}</div>
                <div class="metric-label">📦 Items In Stock</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Sold items
    sold_items = db.fetch_scalar("stock.count_by_status", ("SOLD",)) or 0
    with col2:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-value">{int(sold_items)}</div>
                <div class="metric-label">💰 Items Sold</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Booked items
    booked_items = db.fetch_scalar("stock.count_by_status", ("BOOKED",)) or 0
    with col3:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-value">{int(booked_items)}</div>
                <div class="metric-label">📖 Items Booked</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Customers
    customers = db.fetch_scalar("customer.count_all") or 0
    with col4:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-value">{int(customers)}</div>
                <div class="metric-label">👥 Customers</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)
    st.info("👈 Use the sidebar to navigate between modules.")

except Exception as e:
    st.warning("⚠️ Unable to load dashboard metrics. Please check your database connection.")
    logger.error("Dashboard metrics failed: %s", e, exc_info=True)
