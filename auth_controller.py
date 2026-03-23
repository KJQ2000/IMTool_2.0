"""
auth_controller.py
──────────────────
Enterprise Authentication Module with Role-Based Access Control.

Security Architecture:
  • Passwords verified against bcrypt-salted hashes stored in PostgreSQL
  • Session state managed via Streamlit's st.session_state
  • NO self-service registration — user provisioning is IT-admin only
  • Every page must call require_auth() to enforce session gating

ARCHITECTURAL WARNING:
  Self-service account creation (register/sign-up) has been deliberately
  removed from this application per enterprise security policy. User accounts
  MUST be provisioned exclusively by authorized IT administrators via direct
  database interaction or the admin CLI.
"""

from __future__ import annotations

import bcrypt
import streamlit as st

from config_loader import get_query
from logging_config import get_logger
from utils.log_context import set_log_context

logger = get_logger(__name__)


def _get_db():
    """Lazy import to avoid circular dependency."""
    from database_manager import DatabaseManager
    return DatabaseManager.get_instance()


def hash_password(plain_password: str) -> str:
    """Hash a plain-text password using bcrypt.

    Intended for IT admin use when provisioning accounts.

    Parameters
    ----------
    plain_password:
        The plain-text password to hash.

    Returns
    -------
    The bcrypt hash string (safe to store in the database).
    """
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def _is_bcrypt_hash(value: str) -> bool:
    return value.startswith(("$2a$", "$2b$", "$2y$"))


def _migrate_legacy_password(user_id: str, email: str, plain_password: str) -> None:
    """Upgrade a legacy plain-text password to bcrypt after a successful login."""
    try:
        db = _get_db()
        password_hash = hash_password(plain_password)
        update_sql = get_query("auth.update_password_hash", schema=db.schema)
        with db.transaction() as cur:
            cur.execute(update_sql, (password_hash, user_id))
        logger.info("Migrated legacy plain-text password to bcrypt for %s", email)
    except Exception:
        logger.error(
            "Failed to migrate legacy plain-text password for %s",
            email,
            exc_info=True,
        )


def verify_password(email: str, plain_password: str) -> bool:
    """Verify a user's credentials against the database.

    Fetches the stored password hash for the given email and compares
    it with the provided plain-text password using bcrypt.

    Parameters
    ----------
    email:
        The user's email address.
    plain_password:
        The plain-text password to verify.

    Returns
    -------
    True if credentials are valid, False otherwise.
    """
    try:
        email = email.strip()
        db = _get_db()
        user = db.fetch_one("auth.verify_credentials", (email,))

        if not user:
            logger.warning("Login attempt with non-existent email: %s", email)
            return False

        stored_password = user.get("usr_password", "")

        # Support both bcrypt hashes and legacy plain-text passwords
        # bcrypt hashes start with $2b$ or $2a$
        if _is_bcrypt_hash(stored_password):
            is_valid = bcrypt.checkpw(
                plain_password.encode("utf-8"),
                stored_password.encode("utf-8"),
            )
        else:
            # Legacy plain-text comparison (for migration period)
            is_valid = plain_password == stored_password
            if is_valid:
                logger.warning(
                    "User %s authenticated with legacy plain-text password. "
                    "Please migrate to bcrypt hash.",
                    email,
                )
                user_id = user.get("usr_id")
                if user_id:
                    _migrate_legacy_password(str(user_id), email, plain_password)

        if is_valid:
            logger.info("User %s authenticated successfully.", email)
        else:
            logger.warning("Failed login attempt for email: %s", email)

        return is_valid

    except Exception as e:
        logger.error("Authentication error for %s: %s", email, e, exc_info=True)
        return False


def login_form() -> bool:
    """Render the Streamlit login form and handle authentication.

    Returns True if the user is authenticated (either just logged in
    or was already logged in from a previous session).
    """
    # Already authenticated
    if st.session_state.get("authenticated"):
        set_log_context(user_email=st.session_state.get("user_email", "-"))
        return True

    st.markdown(
        """
        <div style="text-align: center; padding: 2rem 0;">
            <div style="font-size: 3.5rem; margin-bottom: 0.5rem;">💍</div>
            <h1 style="font-family: 'Playfair Display', serif; color: #C9A84C;
                        font-size: 2.2rem; margin-bottom: 0.2rem;">
                Chop Kong Hin
            </h1>
            <p style="color: #9A9A8A; font-size: 0.9rem;">
                Enterprise Inventory Management System
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("login_form", clear_on_submit=False):
        st.markdown("#### 🔐 Staff Login")
        email = st.text_input("Email", placeholder="Enter your email address")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        submitted = st.form_submit_button("Sign In", use_container_width=True)

        if submitted:
            email = email.strip()
            if not email or not password:
                st.error("Please enter both email and password.")
                return False

            if verify_password(email, password):
                st.session_state["authenticated"] = True
                st.session_state["user_email"] = email
                set_log_context(user_email=email)
                logger.info("Session established for %s", email)
                st.rerun()
            else:
                st.error("❌ Incorrect email or password.")
                return False

    # ──────────────────────────────────────────────────────────
    # ARCHITECTURAL WARNING:
    # Self-service registration has been deliberately REMOVED.
    # User accounts MUST be provisioned exclusively by IT admins
    # via direct database interaction.
    # DO NOT add a "Create Account" or "Sign Up" button here.
    # ──────────────────────────────────────────────────────────

    st.markdown(
        """
        <div style="text-align: center; padding: 1rem; color: #555; font-size: 0.75rem;">
            Contact your IT administrator for account provisioning.
        </div>
        """,
        unsafe_allow_html=True,
    )

    return False


def require_auth() -> bool:
    """Guard function to enforce authentication on every page.

    Call this at the top of every Streamlit page. If the user is not
    authenticated, it displays the login form and stops page execution.

    Returns True if authenticated, halts execution otherwise.
    """
    if not st.session_state.get("authenticated"):
        login_form()
        st.stop()
    set_log_context(user_email=st.session_state.get("user_email", "-"))
    return True


def logout() -> None:
    """Clear the user's session and redirect to the login page."""
    email = st.session_state.get("user_email", "unknown")
    logger.info("User %s logged out.", email)

    st.session_state["authenticated"] = False
    st.session_state.pop("user_email", None)
    set_log_context(user_email="-")
    st.rerun()


def get_current_user() -> str:
    """Return the email of the currently logged-in user."""
    return st.session_state.get("user_email", "")
