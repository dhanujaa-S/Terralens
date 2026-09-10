import streamlit as st
import pandas as pd

from modules.database import get_all_records, get_dashboard_stats
from ui.components import page_header, empty_state, section_header


def render_analytics_page(user: dict) -> None:
    """Render the Analytics page with real-data charts and attention-needed tables."""
    page_header("Analytics", "Statistical analysis of digitization progress", "📊")

    stats = get_dashboard_stats()
    records = get_all_records(limit=500)

    if not records:
        empty_state("No data available", "📊", "Upload land records first to see analytics.")
        return

    df = pd.DataFrame(records)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Records", stats["total_records"])
    m2.metric("Verified", stats["verified"])
    m3.metric("Avg Confidence", f"{stats['avg_confidence']:.0%}")
    m4.metric("Needs Review", stats["needs_review"])

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        section_header("📊 Verification Status")
        sdf = pd.DataFrame({
            "Status": ["Verified", "Pending", "Rejected"],
            "Records": [stats["verified"], stats["pending"], stats["rejected"]],
        })
        st.bar_chart(sdf.set_index("Status"), height=420)

    with col2:
        section_header("🌾 Land Classification")
        if "land_classification" in df.columns:
            cc = df["land_classification"].dropna().value_counts().reset_index()
            cc.columns = ["Classification", "Count"]
            if not cc.empty:
                st.bar_chart(cc.set_index("Classification"), height=420)
            else:
                empty_state("No classification data", "🌾")

    col3, col4 = st.columns(2)
    with col3:
        section_header("🎯 Confidence Distribution")
        if "overall_confidence" in df.columns:
            high = len(df[df["overall_confidence"] >= 0.8])
            medium = len(df[(df["overall_confidence"] >= 0.5) & (df["overall_confidence"] < 0.8)])
            low = len(df[df["overall_confidence"] < 0.5])
            cdf = pd.DataFrame({
                "Level": ["High ≥80%", "Medium 50-79%", "Low <50%"],
                "Records": [high, medium, low],
            })
            st.bar_chart(cdf.set_index("Level"), height=420)

    with col4:
        section_header("🗺️  Records by District")
        if stats["by_district"]:
            ddf = pd.DataFrame(stats["by_district"])
            ddf.columns = ["District", "Records"]
            st.bar_chart(ddf.set_index("District"), height=420)
        else:
            empty_state("No district data", "🗺️ ")

    st.divider()
    section_header("⚠️  Records Requiring Attention")

    col_a, col_b = st.columns(2)
    with col_a:
        flagged = df[df.get("needs_review", pd.Series(dtype=int)) == 1] if "needs_review" in df.columns else pd.DataFrame()
        st.markdown(f"**Flagged Records: {len(flagged)}**")
        if not flagged.empty:
            show_cols = [c for c in ["id", "landowner_name", "village", "overall_confidence", "status"] if c in flagged.columns]
            st.dataframe(flagged[show_cols].head(10), use_container_width=True, hide_index=True, height=350)
        else:
            st.success("No flagged records!")

    with col_b:
        low_conf = df[df.get("overall_confidence", pd.Series(dtype=float)) < 0.5] if "overall_confidence" in df.columns else pd.DataFrame()
        st.markdown(f"**Low Confidence Records: {len(low_conf)}**")
        if not low_conf.empty:
            show_cols = [c for c in ["id", "landowner_name", "village", "overall_confidence", "status"] if c in low_conf.columns]
            st.dataframe(low_conf[show_cols].head(10), use_container_width=True, hide_index=True, height=350)
        else:
            st.success("No low-confidence records!")
