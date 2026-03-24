"""
app.py
──────
Chop Kong Hin — Enterprise Inventory Management System

Streamlit multi-page application entry point.
Configures page layout, applies premium CSS theme, enforces authentication,
and sets up sidebar navigation with logout capability.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from logging_config import configure_logging, get_logger
from utils.html_utils import escape_html
from utils.log_context import set_log_context

# Configure logging BEFORE any other imports that use it
configure_logging()

from auth_controller import login_form, logout, get_current_user
from database_manager import DatabaseManager

logger = get_logger(__name__)

# ──────────────────────────────────────────────────────────
# Page Configuration
# ──────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Chop Kong Hin — Inventory Management",
    page_icon="💍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────────────────
# Premium CSS — Dark/Gold Jewellery-Shop Aesthetic
# ──────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Cinzel:wght@600&display=swap');

    :root {
        --bg-main: #F4F6F9;
        --bg-card: #FFFFFF;
        --border-color: #E2E8F0;
        --text-main: #2B2D42;
        --text-muted: #8D99AE;
        --gold: #D4AF37;
        --red-accent: #D62828;
        --primary-navy: #0B2545;
    }

    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
        background-color: var(--bg-main) !important;
        color: var(--text-main) !important;
    }

    .stApp {
        background-color: var(--bg-main) !important;
    }

    /* Premium Header */
    .main-header {
        background: rgba(255, 255, 255, 0.9);
        backdrop-filter: blur(15px);
        -webkit-backdrop-filter: blur(15px);
        border-bottom: 2px solid var(--gold);
        padding: 2.5rem 3rem 2rem;
        margin-bottom: 2.5rem;
        border-radius: 0 0 24px 24px;
        box-shadow: 0 4px 30px rgba(212, 175, 55, 0.1);
        text-align: center;
        animation: fadeInDown 0.8s ease-out;
    }
    .main-title {
        font-family: 'Cinzel', serif;
        font-size: 2.4rem;
        font-weight: 600;
        color: var(--primary-navy);
        margin: 0;
        letter-spacing: 2px;
    }
    .main-subtitle {
        color: var(--gold);
        font-size: 0.9rem;
        margin-top: 0.5rem;
        font-weight: 600;
        letter-spacing: 4px;
        text-transform: uppercase;
        opacity: 0.9;
    }

    /* Luxury Metric Cards */
    .metric-card {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 16px;
        padding: 2rem;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.03);
        transition: all 0.4s ease;
        position: relative;
        overflow: hidden;
    }
    .metric-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; width: 100%; height: 3px;
        background: linear-gradient(90deg, transparent, var(--gold), transparent);
        opacity: 0;
        transition: opacity 0.4s ease;
    }
    .metric-card:hover::before {
        opacity: 1;
    }
    .metric-card:hover {
        border-color: rgba(212, 175, 55, 0.4);
        transform: translateY(-5px);
        box-shadow: 0 15px 30px rgba(212, 175, 55, 0.15);
    }
    .metric-value {
        font-size: 2.8rem;
        font-weight: 700;
        color: var(--primary-navy);
        margin-bottom: 0.5rem;
        font-family: 'Cinzel', serif;
    }
    .metric-label {
        font-size: 0.85rem;
        color: var(--text-muted);
        text-transform: uppercase;
        font-weight: 600;
        letter-spacing: 2px;
    }

    /* Status chips */
    .status-chip {
        display: inline-block;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.05em;
        background: #F4F6F9;
    }
    .chip-green  { color: #2A9D8F; border: 1px solid #2A9D8F; }
    .chip-red    { color: var(--red-accent); border: 1px solid var(--red-accent); }
    .chip-gold   { color: var(--gold); border: 1px solid var(--gold); }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, var(--primary-navy) 0%, #06152B 100%) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
        font-size: 0.95rem !important;
        padding: 0.6rem 2rem !important;
        transition: all 0.3s ease !important;
        letter-spacing: 1px;
        box-shadow: 0 4px 10px rgba(11, 37, 69, 0.2) !important;
    }
    .stButton > button:hover { 
        background: linear-gradient(135deg, var(--gold) 0%, #B8922A 100%) !important;
        color: #FFFFFF !important;
        box-shadow: 0 6px 15px rgba(212, 175, 55, 0.4) !important; 
        transform: translateY(-2px) !important;
    }
    .stButton > button:active {
        transform: translateY(1px) !important;
    }

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background: #FFFFFF !important;
        border-right: 1px solid var(--border-color) !important;
        box-shadow: 5px 0 25px rgba(0,0,0,0.03) !important;
    }
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p, 
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1,
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2,
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3,
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h4 {
        color: var(--primary-navy) !important;
    }
    .sidebar-user {
        color: var(--text-muted) !important;
        font-size: 0.85rem;
        font-weight: 400;
        letter-spacing: 1px;
    }

    /* Forms & Inputs */
    .stTextInput input, .stSelectbox select, .stDateInput input,
    .stNumberInput input, .stTextArea textarea {
        background: #FFFFFF !important;
        border: 1px solid var(--border-color) !important;
        color: var(--text-main) !important;
        border-radius: 8px !important;
        transition: all 0.3s ease !important;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: var(--gold) !important;
        box-shadow: 0 0 0 1px rgba(212,175,55,0.4) !important;
    }

    /* Dataframes */
    .stDataFrame {
        border: 1px solid var(--border-color);
        border-radius: 12px;
        overflow: hidden;
    }

    /* Expander */
    .streamlit-expanderHeader {
        background: #FFFFFF !important;
        color: var(--primary-navy) !important;
        border-radius: 8px !important;
        border: 1px solid var(--border-color) !important;
        font-weight: 500 !important;
        transition: all 0.3s ease !important;
    }
    .streamlit-expanderHeader:hover {
        border-color: var(--gold) !important;
        box-shadow: 0 0 8px rgba(212,175,55,0.1) !important;
    }

    /* Divider */
    hr {
        border-top-color: var(--border-color) !important;
        margin: 2em 0 !important;
    }

    /* Animations */
    @keyframes fadeInDown {
        from { opacity: 0; transform: translateY(-15px); }
        to   { opacity: 1; transform: translateY(0); }
    }

    /* Hide Streamlit chrome */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ──────────────────────────────────────────────────────────
# Authentication Gate
# ──────────────────────────────────────────────────────────
if not login_form():
    st.stop()
set_log_context(user_email=get_current_user())

# ──────────────────────────────────────────────────────────
# Sidebar (shown only when authenticated)
# ──────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://chopkonghin.com/cdn/shop/files/logo.png?v=1759327714&width=3840", use_container_width=True)
    st.markdown("<br>", unsafe_allow_html=True)
    current_user = get_current_user()
    st.markdown(
        f"<p class='sidebar-user'>Logged in as: <b>{escape_html(current_user)}</b></p>",
        unsafe_allow_html=True,
    )
    st.divider()

    # Database connection status
    st.markdown("#### 🔌 System Status")
    try:
        db = DatabaseManager.get_instance()
        if db.test_connection():
            st.markdown(
                '<span class="status-chip chip-green">● Database Connected</span>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<span class="status-chip chip-red">● Database Disconnected</span>',
                unsafe_allow_html=True,
            )
    except Exception:
        st.markdown(
            '<span class="status-chip chip-red">● Database Error</span>',
            unsafe_allow_html=True,
        )

    st.divider()

    if st.button("🚪 Logout", use_container_width=True):
        logout()

    st.divider()
    st.markdown(
        "<p style='color:#555;font-size:0.7rem;text-align:center;'>© 2025 Chop Kong Hin<br>Enterprise v2.0</p>",
        unsafe_allow_html=True,
    )

# ──────────────────────────────────────────────────────────
# Application Routing
# ──────────────────────────────────────────────────────────
pages = {
    "Dashboards": [
        st.Page("pages/00_Home.py", title="Home", icon="🏠"),
        st.Page("pages/01_Dashboard.py", title="Pattern Dashboard", icon="🏠"),
    ],
    "Inventory & Sales": [
        st.Page("pages/03_Stocks.py", title="Stocks", icon="📦"),
        st.Page("pages/04_Sales.py", title="Sales", icon="💰"),
        st.Page("pages/06_Bookings.py", title="Bookings", icon="📖"),
        st.Page("pages/05_Purchases.py", title="Purchases", icon="📋"),
    ],
    "Relations": [
        st.Page("pages/07_Customers.py", title="Customers", icon="👥"),
        st.Page("pages/08_Salesmen.py", title="Salesmen", icon="🤝"),
    ],
    "Tools": [
         st.Page("pages/02_Pattern_Management.py", title="Pattern Management", icon="🎨"),
         st.Page("pages/09_Batch_Import.py", title="Batch Import", icon="📥"),
         st.Page("pages/10_Barcode.py", title="Barcode", icon="🏷️"),
         st.Page("pages/11_Agentic_Intelligence.py", title="Agentic Intelligence", icon="🤖"),
         st.Page("pages/12_Custom_Table.py", title="Custom Stock Table", icon="🧩"),
    ]
}

pg = st.navigation(pages)
pg.run()
