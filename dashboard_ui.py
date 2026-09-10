import streamlit as st
import pandas as pd

from modules.database import get_dashboard_stats, get_all_records
from modules.doc_repository import get_storage_stats
from modules.auth import has_permission
from ui.components import (
    page_header, status_badge, confidence_bar,
    empty_state, section_header,
)


def render_dashboard(user: dict) -> None:
    """Render the Terra Lens dashboard with real-time stats, charts, and quick actions."""
    if st.session_state.get("just_logged_in"):
        name = user.get("full_name", user.get("username", "User"))
        role = user.get("role", "").upper()
        st.success(f"👋 Welcome back, **{name}**! You are logged in as **{role}**.")
        st.session_state["just_logged_in"] = False

    page_header("Dashboard", "Real-time land record processing overview", "🏠")

    _, col_refresh = st.columns([5, 1])
    with col_refresh:
        if st.button("🔄 Refresh", use_container_width=True, key="dash_refresh"):
            st.rerun()

    stats = get_dashboard_stats()
    storage = get_storage_stats()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📄 Total Documents", stats["total_documents"])
    col2.metric("📋 Land Records", stats["total_records"])
    col3.metric("✅ Verified", stats["verified"])
    col4.metric("⏳ Pending", stats["pending"])

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("❌ Rejected", stats["rejected"])
    col6.metric("⚠️  Needs Review", stats["needs_review"])
    col7.metric("🎯 Avg Confidence", f"{stats['avg_confidence']:.0%}")
    col8.metric("💾 Storage", f"{storage['total_size_mb']} MB")

    st.divider()

    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        section_header("📊 Verification Status")
        status_df = pd.DataFrame({
            "Status": ["Verified", "Pending", "Rejected"],
            "Records": [stats["verified"], stats["pending"], stats["rejected"]],
        })
        st.bar_chart(status_df.set_index("Status"), height=380)

    with chart_col2:
        section_header("🗺️  Top Districts")
        if stats["by_district"]:
            dist_df = pd.DataFrame(stats["by_district"])
            dist_df.columns = ["District", "Records"]
            st.bar_chart(dist_df.set_index("District").head(10), height=380)
        else:
            empty_state("No district data yet", "🗺️ ", "Upload records to see district distribution")

    records = get_all_records(limit=300)
    if records:
        st.divider()
        section_header("🎯 Confidence Distribution")
        df = pd.DataFrame(records)
        if "overall_confidence" in df.columns:
            high = len(df[df["overall_confidence"] >= 0.8])
            medium = len(df[(df["overall_confidence"] >= 0.5) & (df["overall_confidence"] < 0.8)])
            low = len(df[df["overall_confidence"] < 0.5])
            conf_df = pd.DataFrame({
                "Level": ["High ≥80%", "Medium 50-79%", "Low <50%"],
                "Records": [high, medium, low],
            })
            st.bar_chart(conf_df.set_index("Level"), height=380)

    st.divider()

    panel_col1, panel_col2 = st.columns(2)

    with panel_col1:
        section_header("⚠️  Records Needing Review")
        all_records = get_all_records(limit=100)
        review_records = [r for r in all_records if r.get("needs_review")][:5]
        if not review_records:
            st.success("✅ No records currently need review!")
        else:
            for r in review_records:
                owner = (r.get("landowner_name") or "Unknown")[:25]
                village = r.get("village", "")
                record_id = r.get("id", "")
                conf = r.get("overall_confidence", 0)
                st.markdown(
                    f"**#{record_id}** {owner} — {village} | "
                    f"Confidence: {conf:.0%}",
                )

    with panel_col2:
        section_header("🕐 Recent Records")
        recent = get_all_records(limit=5)
        for r in recent:
            owner = str(r.get("landowner_name") or "Unknown")[:20]
            status = r.get("status", "pending")
            conf = r.get("overall_confidence", 0)
            rid = r.get("id", "")
            badge = status_badge(status)
            st.markdown(
                f"**#{rid}** {owner} | {conf:.0%} | {badge}",
                unsafe_allow_html=True,
            )

    st.divider()
    section_header("⚡ Quick Actions")
    qc1, qc2, qc3 = st.columns(3)
    with qc1:
        if has_permission(user, "upload"):
            st.button("📤 Upload Document", use_container_width=True, key="dash_upload")
    with qc2:
        if has_permission(user, "verify"):
            st.button("✅ Review Queue", use_container_width=True, key="dash_review")
    with qc3:
        if has_permission(user, "export"):
            st.button("📥 Export Records", use_container_width=True, key="dash_export")
