import hashlib
import secrets
import sqlite3
import logging
from datetime import datetime
from typing import Optional

import streamlit as st

from modules.database import get_conn, log_audit

logger = logging.getLogger(__name__)

ROLE_PERMISSIONS = {
    "admin": {
        "upload", "view_records", "verify", "reject",
        "edit_fields", "view_audit", "manage_users",
        "export", "view_dashboard", "delete",
    },
    "verifier": {
        "upload", "view_records", "verify", "reject",
        "edit_fields", "export", "view_dashboard",
    },
    "uploader": {
        "upload", "view_records", "view_dashboard",
    },
    "viewer": {
        "view_records", "view_dashboard",
    },
}

EDITABLE_ROLES = ["viewer", "uploader", "verifier", "admin"]


def _hash_password(password: str, salt: str = "") -> str:
    """Hash a password with a random salt using SHA-256. Returns "salt:hash" string."""
    if salt == "":
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return f"{salt}:{hashed}"


def _verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored "salt:hash" string."""
    try:
        salt, hashed = stored_hash.split(":", 1)
        candidate = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return candidate == hashed
    except Exception:
        return False


def create_default_admin() -> None:
    """Create admin/admin123 user only if the users table is completely empty. Safe to call on every app startup."""
    with get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count == 0:
        create_user("admin", "admin123", "admin", "System Administrator")
        logger.info("Default admin user created. Login: admin / admin123")


def create_user(username: str, password: str, role: str, full_name: str,
                 state: str = "", district: str = "") -> bool:
    """Create a new user. Returns True on success, False if username already exists."""
    if role not in ROLE_PERMISSIONS:
        raise ValueError(f"Invalid role: {role}")

    password_hash = _hash_password(password)
    try:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO users (username, password_hash, role, full_name, state, district)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (username, password_hash, role, full_name, state, district),
            )
        return True
    except sqlite3.IntegrityError:
        logger.warning("Attempted to create duplicate username: %s", username)
        return False


def authenticate(username: str, password: str) -> Optional[dict]:
    """Verify credentials. Returns user dict on success, None on failure."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username=? AND is_active=1", (username,)
        ).fetchone()
        if not row:
            return None

        user = dict(row)
        if not _verify_password(password, user["password_hash"]):
            return None

        conn.execute(
            "UPDATE users SET last_login=? WHERE id=?",
            (datetime.now().isoformat(), user["id"]),
        )
        log_audit(conn, user["id"], "LOGIN", "user", user["id"], {"username": username})

        return user


def get_all_users() -> list:
    """Fetch all users with their basic profile fields, most recently created first."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, username, role, full_name, state, district,
                   is_active, created_at, last_login
            FROM users
            ORDER BY created_at DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]


def toggle_user_active(user_id: int, is_active: int) -> bool:
    """Activate or deactivate a user account."""
    with get_conn() as conn:
        conn.execute("UPDATE users SET is_active=? WHERE id=?", (is_active, user_id))
    return True


def change_user_role(user_id: int, new_role: str) -> bool:
    """Change a user's role after validating it is a known role."""
    if new_role not in ROLE_PERMISSIONS:
        raise ValueError(f"Invalid role: {new_role}")
    with get_conn() as conn:
        conn.execute("UPDATE users SET role=? WHERE id=?", (new_role, user_id))
    return True


def has_permission(user: dict, permission: str) -> bool:
    """Check if a user dict has a specific permission based on their role."""
    role = user.get("role", "viewer")
    return permission in ROLE_PERMISSIONS.get(role, set())


def login_page() -> None:
    """Render a centered login form. On success sets session_state and calls st.rerun()."""
    st.markdown("## 🌍 Terra Lens")
    st.markdown("#### Intelligent Land Record System")
    st.markdown("*Smart India Hackathon 2026 — Problem 26018*")
    st.markdown("---")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        username = st.text_input("Username", placeholder="Enter username")
        password = st.text_input("Password", type="password", placeholder="Enter password")
        login_btn = st.button("Sign in", use_container_width=True, type="primary")
        st.caption("Demo: admin / admin123")

    if login_btn:
        if not username or not password:
            st.error("Please enter both username and password.")
            return

        user = authenticate(username, password)
        if user:
            st.session_state["user"] = user
            st.session_state["user_id"] = user["id"]
            st.session_state["role"] = user["role"]
            st.rerun()
        else:
            st.error("Invalid username or password.")
            return


def logout() -> None:
    """Clear session state and rerun to return to login page."""
    for key in ["user", "user_id", "role"]:
        st.session_state.pop(key, None)
    st.rerun()


def require_auth(permission: str = None) -> dict:
    """Call at the top of every page. Stops rendering if not logged in or missing permission."""
    if "user" not in st.session_state:
        login_page()
        st.stop()

    user = st.session_state["user"]

    if permission and not has_permission(user, permission):
        st.error(f"Access denied. Your role '{user['role']}' does not have permission: {permission}")
        st.info("Contact your administrator to request access.")
        st.stop()

    return user


def show_user_badge(user: dict) -> None:
    """Display logged-in user name and role in the sidebar."""
    role_icons = {
        "admin": "🔴",
        "verifier": "🟡",
        "uploader": "🔵",
        "viewer": "⚪",
    }
    icon = role_icons.get(user.get("role", "viewer"), "⚪")
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"{icon} **{user.get('full_name', user.get('username', 'User'))}**")
    st.sidebar.caption(f"Role: {user.get('role', 'viewer').upper()}")


def render_user_management_page(user: dict) -> None:
    """Full Streamlit page for managing users. Only renders for admin role."""
    if not has_permission(user, "manage_users"):
        st.error("Access denied — admin only.")
        return

    import pandas as pd

    st.title("User Management")
    st.markdown("Manage system users and access roles.")

    users = get_all_users()
    df = pd.DataFrame(users)
    st.dataframe(df, use_container_width=True, hide_index=True)

    with st.expander("Add new user", expanded=False):
        new_username = st.text_input("Username", key="new_uname")
        new_password = st.text_input("Password", type="password", key="new_pwd")
        new_role = st.selectbox("Role", EDITABLE_ROLES, key="new_role")
        new_fullname = st.text_input("Full name", key="new_fname")
        new_state = st.text_input("State", key="new_state")
        new_district = st.text_input("District", key="new_dist")

        if st.button("Create user", key="create_user_btn"):
            if not new_username or not new_password or not new_fullname:
                st.warning("Username, password and full name are required.")
            else:
                created = create_user(
                    new_username, new_password, new_role, new_fullname,
                    new_state, new_district,
                )
                if created:
                    st.success(f"User '{new_username}' created.")
                    st.rerun()
                else:
                    st.error(f"Username '{new_username}' already exists.")

    with st.expander("Manage existing users", expanded=False):
        for u in get_all_users():
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(f"**{u['username']}** — {u['full_name'] or ''}  \n`{u['role'].upper()}`")
            with col2:
                active_label = "Deactivate" if u['is_active'] else "Activate"
                if st.button(active_label, key=f"toggle_{u['id']}"):
                    toggle_user_active(u['id'], 0 if u['is_active'] else 1)
                    st.rerun()
            with col3:
                new_role_sel = st.selectbox(
                    "Role", EDITABLE_ROLES, index=EDITABLE_ROLES.index(u['role']),
                    key=f"role_{u['id']}",
                )
                if st.button("Change", key=f"change_role_{u['id']}"):
                    change_user_role(u['id'], new_role_sel)
                    st.rerun()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from modules.database import init_db
    init_db()
    create_default_admin()
    print("Module 9 — auth.py OK")
    print("Test authenticate:")
    user = authenticate("admin", "admin123")
    print(f"  admin login: {user is not None}")
    print(f"  wrong password: {authenticate('admin', 'wrong') is None}")
    print(f"  has upload permission: {has_permission(user, 'upload')}")
    print(f"  viewer has manage_users: {has_permission({'role':'viewer'}, 'manage_users')}")
