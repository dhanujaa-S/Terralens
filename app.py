import streamlit as st

from modules.database import init_db, get_dashboard_stats
from modules.auth import create_default_admin, has_permission
from ui.styles import inject_styles
from ui.components import page_header, role_badge
from ui.login_ui import render_login_page
from ui.dashboard_ui import render_dashboard
from ui.upload_ui import render_upload_page
from ui.review_ui import render_review_page
from ui.records_ui import render_records_page
from ui.map_ui import render_map_page
from ui.analytics_ui import render_analytics_page
from ui.export_ui import render_export_page
from ui.admin_ui import render_admin_page

st.set_page_config(
    page_title="Terra Lens — AI-Powered Land Intelligence",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_styles()
init_db()
create_default_admin()

if not st.session_state.get("logged_in"):
    render_login_page()
    st.stop()

user = st.session_state["user"]

try:
    _quick_stats = get_dashboard_stats()
    _review_count = _quick_stats.get("needs_review", 0)
    _pending_count = _quick_stats.get("pending", 0)
except Exception:
    _review_count = 0
    _pending_count = 0

nav_options = ["🏠 Dashboard", "🗂️  Land Records", "🗺️  GIS Map", "📊 Analytics"]
if has_permission(user, "upload"):
    nav_options.append("📤 Upload & Process")
if has_permission(user, "verify"):
    review_label = f"✅ Human Review ({_review_count})" if _review_count > 0 else "✅ Human Review"
    nav_options.append(review_label)
if has_permission(user, "export"):
    nav_options.append("📥 Export")
if has_permission(user, "manage_users"):
    nav_options.append("⚙️  Admin")

PAGE_DESCRIPTIONS = {
    "🏠 Dashboard": "Real-time overview and key statistics",
    "🗂️  Land Records": "Search and view all digitized records",
    "🗺️  GIS Map": "Geographic view of land parcels",
    "📊 Analytics": "Statistical analysis and trends",
    "📤 Upload & Process": "Upload and digitize land record documents",
    "✅ Human Review": "Verify and approve AI-extracted records",
    "📥 Export": "Export records for government integration",
    "⚙️  Admin": "System administration and audit logs",
}

with st.sidebar:
    st.markdown(
        "<h2 style='color:#1B2A4A;margin-bottom:0;font-size:26px;'>🌍 Terra Lens</h2>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='color:#718096;font-size:13px;margin-top:0.15rem;letter-spacing:0.03em;'>"
        "AI-POWERED LAND INTELLIGENCE</p>",
        unsafe_allow_html=True,
    )
    st.divider()

    st.markdown(f"👤 **{user.get('full_name', user['username'])}**")
    st.markdown(role_badge(user["role"]), unsafe_allow_html=True)
    if user.get("district"):
        st.caption(f"📍 {user.get('district', '')}")

    st.divider()

    page = st.radio("Navigate", nav_options, label_visibility="collapsed", key="nav_radio")
    _desc = next((v for k, v in PAGE_DESCRIPTIONS.items() if k in page), "")
    st.caption(_desc)

    st.divider()

    if st.button("🚪 Logout", use_container_width=True, key="logout_btn"):
        for key in ["user", "user_id", "role", "logged_in", "just_logged_in"]:
            st.session_state.pop(key, None)
        st.rerun()

    st.sidebar.caption("Terra Lens v1.0")

if "Dashboard" in page:
    render_dashboard(user)
elif "Upload" in page:
    render_upload_page(user)
elif "Review" in page:
    render_review_page(user)
elif "Records" in page:
    render_records_page(user)
elif "GIS" in page or "Map" in page:
    render_map_page(user)
elif "Analytics" in page:
    render_analytics_page(user)
elif "Export" in page:
    render_export_page(user)
elif "Admin" in page:
    render_admin_page(user)

st.markdown("---")
st.markdown(
    "<div style='text-align:center;color:#718096;font-size:12.5px;padding:0.75rem 0;'>"
    "🌍 <b>Terra Lens</b> — Intelligent Land Record Digitization &amp; Validation Platform"
    "</div>",
    unsafe_allow_html=True,
)
