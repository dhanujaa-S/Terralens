import streamlit as st
import pandas as pd

from modules.database import get_all_records
from ui.components import (
    page_header, status_badge, confidence_bar,
    record_field_row, section_header, empty_state,
)


def render_records_page(user: dict) -> None:
    """Render the searchable Land Records management page with filters and a detail view."""
    page_header("Land Records", "Search and manage all digitized land records", "🗂️ ")

    with st.expander("🔍 Search & Filters", expanded=True):
        row1_c1, row1_c2, row1_c3, row1_c4 = st.columns(4)
        with row1_c1:
            owner_search = st.text_input("Owner Name", placeholder="Search owner...", key="rec_owner")
        with row1_c2:
            village_search = st.text_input("Village", placeholder="Search village...", key="rec_village")
        with row1_c3:
            district_search = st.text_input("District", placeholder="Search district...", key="rec_district")
        with row1_c4:
            state_search = st.text_input("State", placeholder="Search state...", key="rec_state")

        row2_c1, row2_c2, row2_c3, row2_c4 = st.columns(4)
        with row2_c1:
            khasra_search = st.text_input("Khasra Number", placeholder="Search khasra...", key="rec_khasra")
        with row2_c2:
            survey_search = st.text_input("Survey Number", placeholder="Search survey...", key="rec_survey")
        with row2_c3:
            status_filter = st.selectbox("Status", ["all", "pending", "verified", "rejected"], key="rec_status")
        with row2_c4:
            needs_rev = st.checkbox("Needs Review Only", value=False, key="rec_needs")

        row3_c1, row3_c2, row3_c3 = st.columns(3)
        with row3_c1:
            conf_min = st.slider("Min Confidence %", 0, 100, 0, key="rec_conf")
        with row3_c2:
            limit_val = st.selectbox("Records per page", [25, 50, 100, 200], key="rec_limit")
        with row3_c3:
            st.markdown("<br>", unsafe_allow_html=True)
            st.button("🗑️  Clear All Filters", key="rec_clear")

    status_q = None if status_filter == "all" else status_filter
    district_q = district_search.strip() or None
    records = get_all_records(status=status_q, district=district_q, limit=limit_val)

    filtered = records
    if owner_search.strip():
        filtered = [r for r in filtered if owner_search.lower() in str(r.get("landowner_name", "")).lower()]
    if village_search.strip():
        filtered = [r for r in filtered if village_search.lower() in str(r.get("village", "")).lower()]
    if state_search.strip():
        filtered = [r for r in filtered if state_search.lower() in str(r.get("state", "")).lower()]
    if khasra_search.strip():
        filtered = [r for r in filtered if khasra_search.lower() in str(r.get("khasra_number", "")).lower()]
    if survey_search.strip():
        filtered = [r for r in filtered if survey_search.lower() in str(r.get("survey_number", "")).lower()]
    if needs_rev:
        filtered = [r for r in filtered if r.get("needs_review")]
    if conf_min > 0:
        filtered = [r for r in filtered if r.get("overall_confidence", 0) >= conf_min / 100]

    st.markdown(f"**{len(filtered)} records** found")
    st.divider()

    if not filtered:
        empty_state("No records match your filters", "🗂️ ", "Try adjusting the search criteria above.")
        return

    display_rows = []
    for r in filtered:
        display_rows.append({
            "ID": r["id"],
            "Owner Name": str(r.get("landowner_name") or "")[:30],
            "Khasra No": r.get("khasra_number", ""),
            "Village": r.get("village", ""),
            "District": r.get("district", ""),
            "State": r.get("state", ""),
            "Land Type": r.get("land_classification", ""),
            "Area": f"{r.get('plot_area', '')} {r.get('area_unit', '')}".strip(),
            "Confidence": f"{r.get('overall_confidence', 0):.0%}",
            "Status": r.get("status", "").upper(),
            "Review": "⚠️  Yes" if r.get("needs_review") else "—",
        })
    df_display = pd.DataFrame(display_rows)
    st.dataframe(df_display, use_container_width=True, hide_index=True, height=480)

    st.divider()
    st.markdown("#### 📋 Detailed Record View")

    record_ids = [r["id"] for r in filtered]
    selected_id = st.selectbox("Select Record ID to View Details", record_ids, key="rec_detail_select")
    selected = next((r for r in filtered if r["id"] == selected_id), None)

    if selected:
        conf = selected.get("overall_confidence", 0)
        confidence_bar(conf, f"Extraction Confidence: {conf:.0%}")
        st.markdown(f"**Status:** {selected.get('status', '').upper()}")
        st.divider()

        col1, col2 = st.columns(2)

        with col1:
            section_header("👤 Owner Information")
            record_field_row("Landowner Name", selected.get("landowner_name"))
            record_field_row("Father / Spouse", selected.get("father_spouse_name"))
            record_field_row("Caste Category", selected.get("caste_category"))

            section_header("📍 Survey Identifiers")
            record_field_row("Survey Number", selected.get("survey_number"))
            record_field_row("Khasra Number", selected.get("khasra_number"))
            record_field_row("Khata Number", selected.get("khata_number"))
            record_field_row("Plot Number", selected.get("plot_number"))

            section_header("🗺️  Location")
            record_field_row("Village", selected.get("village"))
            record_field_row("Tehsil", selected.get("tehsil"))
            record_field_row("District", selected.get("district"))
            record_field_row("State", selected.get("state"))
            record_field_row("Pincode", selected.get("pincode"))

            section_header("🌾 Land Details")
            record_field_row("Plot Area", selected.get("plot_area"))
            record_field_row("Area Unit", selected.get("area_unit"))
            record_field_row("Classification", selected.get("land_classification"))
            record_field_row("Land Use", selected.get("land_use"))

        with col2:
            section_header("🧭 Boundaries")
            record_field_row("North", selected.get("boundary_north"))
            record_field_row("South", selected.get("boundary_south"))
            record_field_row("East", selected.get("boundary_east"))
            record_field_row("West", selected.get("boundary_west"))

            section_header("🤝 Ownership")
            record_field_row("Ownership Type", selected.get("ownership_type"))
            record_field_row("Ownership Share", selected.get("ownership_share"))

            section_header("📜 Registration")
            record_field_row("Reg. Number", selected.get("registration_number"))
            record_field_row("Reg. Date", selected.get("registration_date"))

            section_header("🔄 Mutation")
            record_field_row("Mutation Number", selected.get("mutation_number"))
            record_field_row("Mutation Date", selected.get("mutation_date"))
            record_field_row("Document Date", selected.get("document_date"))

            section_header("✅ Verification")
            record_field_row("Status", selected.get("status", "").upper())
            record_field_row("Verified By", str(selected.get("verified_by") or "—"))
            record_field_row("Verified At", selected.get("verified_at"))
            record_field_row("Reviewer Notes", selected.get("reviewer_notes"))
            record_field_row("Created At", (selected.get("created_at") or "")[:19])

            if selected.get("latitude") and selected.get("longitude"):
                section_header("📍 GPS Coordinates")
                record_field_row("Latitude", str(selected.get("latitude")))
                record_field_row("Longitude", str(selected.get("longitude")))
