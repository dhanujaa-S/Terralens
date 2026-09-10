import streamlit as st
import pandas as pd

from modules.database import get_dashboard_stats, get_audit_log
from modules.doc_repository import get_storage_stats
from modules.auth import get_all_users, has_permission
from ui.components import page_header, section_header, empty_state


def render_admin_page(user: dict) -> None:
    """Render the System Administration page: health, users, audit trail, and DB summary."""
    if not has_permission(user, "manage_users"):
        st.error("🔒 Access denied. Admin role required.")
        return

    page_header("System Administration", "Database, users, storage and audit management", "⚙️ ")

    section_header("🖥️  System Status")
    stats = get_dashboard_stats()
    storage = get_storage_stats()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Land Records", stats["total_records"])
    m2.metric("Documents", stats["total_documents"])
    m3.metric("Storage Used", f"{storage['total_size_mb']} MB")
    m4.metric("Thumbnails", storage.get("thumbnail_count", 0))

    st.success("✅ Database: Online")
    st.success("✅ Storage: Online")

    st.divider()
    section_header("👥 User Management")
    users = get_all_users()
    if users:
        udf = pd.DataFrame(users)
        show_cols = [c for c in ["id", "username", "role", "full_name", "state", "district", "is_active", "last_login"] if c in udf.columns]
        display_df = udf[show_cols].copy()
        if "is_active" in display_df.columns:
            display_df["is_active"] = display_df["is_active"].map({1: "✅ Active", 0: "❌ Inactive"})
        st.dataframe(display_df, use_container_width=True, hide_index=True, height=250)
        st.caption(f"Total users: {len(users)}")
    else:
        empty_state("No users found", "👥")

    st.divider()
    section_header("📋 Audit Trail")
    col_lim, col_ref = st.columns([4, 1])
    with col_lim:
        audit_limit = st.selectbox("Show last", [50, 100, 200, 500], key="admin_audit_lim")
    with col_ref:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄", key="admin_ref"):
            st.rerun()

    audit_log = get_audit_log(limit=audit_limit)
    if audit_log:
        adf = pd.DataFrame(audit_log)
        show_cols = [c for c in ["timestamp", "username", "role", "action", "entity_type", "entity_id", "details"] if c in adf.columns]
        st.dataframe(adf[show_cols], use_container_width=True, hide_index=True, height=420)
        st.download_button(
            "⬇️ Download Audit Log CSV",
            data=adf.to_csv(index=False).encode("utf-8"),
            file_name="terra_lens_audit.csv",
            mime="text/csv",
        )
    else:
        empty_state("No audit records yet", "📋", "Actions will be logged here as the system is used.")

    st.divider()
    section_header("📊 Database Summary")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Documents", stats["total_documents"])
        st.metric("Records", stats["total_records"])
    with c2:
        st.metric("Verified", stats["verified"])
        st.metric("Pending", stats["pending"])
        st.metric("Rejected", stats["rejected"])
    with c3:
        st.metric("Needs Review", stats["needs_review"])
        st.metric("Avg Confidence", f"{stats['avg_confidence']:.0%}")
