import streamlit as st

from modules.gis_module import render_map
from modules.database import get_all_records
from ui.components import page_header, empty_state


def render_map_page(user: dict) -> None:
    """Render the GIS Map page showing all geo-tagged land records on a Leaflet map."""
    page_header("GIS Map", "Geographic view of all digitized land parcels", "🗺️ ")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        state_filter = st.text_input("State", placeholder="All states...", key="map_state")
    with col2:
        district_filter = st.text_input("District", placeholder="All districts...", key="map_district")
    with col3:
        status_filter = st.selectbox("Status", ["all", "verified", "pending", "rejected"], key="map_status")
    with col4:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Apply", use_container_width=True, key="map_apply"):
            st.rerun()

    status_q = None if status_filter == "all" else status_filter
    district_q = district_filter.strip() or None
    all_records = get_all_records(status=status_q, district=district_q, limit=1000)

    if state_filter.strip():
        all_records = [r for r in all_records if state_filter.lower() in str(r.get("state", "")).lower()]

    geo_records = [r for r in all_records if r.get("latitude") and r.get("longitude")]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Records", len(all_records))
    m2.metric("Geo-Tagged", len(geo_records))
    m3.metric("Verified on Map", sum(1 for r in geo_records if r.get("status") == "verified"))
    m4.metric("Pending on Map", sum(1 for r in geo_records if r.get("status") == "pending"))

    st.divider()
    if geo_records:
        render_map(geo_records)
    else:
        empty_state(
            "No geo-tagged records to display",
            "🗺️ ",
            "Upload land records to automatically geo-tag them using village/district names.",
        )

    st.markdown("**Map Legend:** 🟢 Green = Verified &nbsp;&nbsp; 🟠 Orange = Pending &nbsp;&nbsp; 🔴 Red = Rejected")

    untagged = len(all_records) - len(geo_records)
    if untagged > 0:
        st.warning(f"⚠️  {untagged} record(s) have no GPS coordinates — village/district could not be geocoded.")
