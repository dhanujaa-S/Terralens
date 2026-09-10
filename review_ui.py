import streamlit as st
import json

from modules.database import get_all_records, update_record_field, update_record_status
from modules.doc_repository import retrieve_document
from modules.auth import has_permission
from ui.components import (
    page_header, status_badge, confidence_bar,
    record_field_row, section_header,
    empty_state, error_panel, warning_panel,
)

EDITABLE_FIELDS = [
    "landowner_name", "survey_number", "khasra_number", "khata_number",
    "village", "tehsil", "district", "state", "pincode", "plot_area", "area_unit",
    "land_classification", "registration_number", "registration_date",
    "mutation_number", "mutation_date",
]

FIELD_LABELS = {
    "landowner_name": "Landowner Name", "survey_number": "Survey Number",
    "khasra_number": "Khasra Number", "khata_number": "Khata Number",
    "village": "Village", "tehsil": "Tehsil", "district": "District",
    "state": "State", "pincode": "Pincode", "plot_area": "Plot Area",
    "area_unit": "Area Unit", "land_classification": "Land Classification",
    "registration_number": "Registration Number", "registration_date": "Registration Date",
    "mutation_number": "Mutation Number", "mutation_date": "Mutation Date",
}

ALL_DISPLAY_GROUPS = {
    "👤 Owner": ["landowner_name", "father_spouse_name", "caste_category"],
    "📍 Survey": ["survey_number", "khasra_number", "khata_number", "plot_number"],
    "🗺️  Location": ["village", "tehsil", "district", "state", "pincode"],
    "🌾 Land Details": ["plot_area", "area_unit", "land_classification", "land_use"],
    "🧭 Boundaries": ["boundary_north", "boundary_south", "boundary_east", "boundary_west"],
    "🤝 Ownership": ["ownership_type", "ownership_share"],
    "📜 Registration": ["registration_number", "registration_date"],
    "🔄 Mutation": ["mutation_number", "mutation_date", "document_date"],
}


def render_review_page(user: dict) -> None:
    """Render the Human Review split-screen workflow for verifying extracted land records."""
    page_header("Human Review", "Verify and approve AI-extracted land records", "✅")

    can_verify = has_permission(user, "verify")
    if not can_verify:
        st.info("👁️  You are in read-only mode. Contact your administrator to get verification access.")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        status_filter = st.selectbox("Status", ["pending", "all", "verified", "rejected"], key="rev_status")
    with col2:
        district_filter = st.text_input("District", placeholder="All districts...", key="rev_district")
    with col3:
        only_flagged = st.checkbox("Flagged Only", value=True, key="rev_flagged")
    with col4:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Refresh", use_container_width=True, key="rev_refresh"):
            st.rerun()

    status_q = None if status_filter == "all" else status_filter
    district_q = district_filter.strip() or None
    records = get_all_records(status=status_q, district=district_q, limit=100)
    if only_flagged:
        records = [r for r in records if r.get("needs_review")]

    if not records:
        empty_state("No records in the review queue", "✅", "All done! Adjust filters to see other records.")
        return

    st.markdown(f"**{len(records)} record(s)** in queue")
    st.divider()

    for r in records:
        conf = r.get("overall_confidence", 0.0)
        status = r.get("status", "pending")
        owner = r.get("landowner_name", "Unknown")
        village = r.get("village", "")
        district = r.get("district", "")
        record_id = r.get("id")
        conf_pct = f"{conf:.0%}"
        sicon = {"verified": "✅", "rejected": "❌", "pending": "⏳"}.get(status, "⏳")
        cicon = "🟢" if conf >= 0.8 else "🟡" if conf >= 0.5 else "🔴"

        try:
            flagged_list = json.loads(r.get("flagged_fields") or "[]")
        except Exception:
            flagged_list = []

        expander_label = (
            f"{sicon} Record #{record_id} — {owner} | "
            f"{village}, {district} | {cicon} {conf_pct}"
        )

        with st.expander(expander_label, expanded=(r.get("needs_review") == 1)):
            col_left, col_right = st.columns([45, 55])

            with col_left:
                st.markdown("#### 🖼️  Original Document")
                storage_path = r.get("storage_path", "")
                if storage_path:
                    doc_bytes = retrieve_document(storage_path)
                    if doc_bytes:
                        ext = storage_path.lower().rsplit(".", 1)[-1] if "." in storage_path else ""
                        if ext in ["jpg", "jpeg", "png", "bmp", "tiff", "tif"]:
                            st.image(
                                doc_bytes, use_container_width=True,
                                caption=f"Document #{r.get('document_id', '')}",
                            )
                        elif ext == "pdf":
                            st.info("📄 PDF stored. Download to view.")
                            st.download_button(
                                "⬇️ Download PDF", data=doc_bytes,
                                file_name=f"record_{record_id}.pdf",
                                mime="application/pdf",
                                key=f"dl_{record_id}",
                            )
                        else:
                            st.info("Document stored but preview not supported.")
                    else:
                        st.info("📁 Document preview unavailable.")
                else:
                    st.info("📁 No document attached.")

                st.markdown("---")
                st.markdown("#### 📊 Extraction Summary")
                confidence_bar(conf, f"Overall Confidence: {conf_pct}")
                st.caption(f"Flagged fields: {len(flagged_list)}")
                if flagged_list:
                    st.warning(f"⚠️  Attention needed: {', '.join(flagged_list)}")

            with col_right:
                st.markdown("#### 📋 Extracted Record")

                if can_verify:
                    st.caption("✏️  Edit fields below to correct extraction errors before approving.")
                    edited = {}
                    for fname in EDITABLE_FIELDS:
                        current = r.get(fname, "") or ""
                        is_flag = fname in flagged_list
                        label = FIELD_LABELS.get(fname, fname.replace("_", " ").title())
                        disp_lbl = f"⚠️  {label}" if is_flag else label
                        new_val = st.text_input(
                            disp_lbl, value=current,
                            key=f"edit_{record_id}_{fname}",
                            help="AI flagged this field as uncertain" if is_flag else "",
                        )
                        if new_val != current:
                            edited[fname] = new_val

                    st.markdown("---")
                    st.markdown("#### ✅ Review Decision")
                    notes = st.text_area(
                        "Reviewer Notes",
                        placeholder="Add notes about this decision...",
                        key=f"notes_{record_id}",
                        height=80,
                    )

                    ac1, ac2 = st.columns(2)
                    with ac1:
                        if st.button(
                            "✅ Approve", key=f"approve_{record_id}",
                            use_container_width=True, type="primary",
                        ):
                            for fname, val in edited.items():
                                update_record_field(record_id, fname, val, user["id"])
                            update_record_status(record_id, "verified", user["id"], notes)
                            st.success("✅ Record approved!")
                            st.rerun()
                    with ac2:
                        if st.button(
                            "❌ Reject", key=f"reject_{record_id}",
                            use_container_width=True,
                        ):
                            update_record_status(record_id, "rejected", user["id"], notes)
                            st.error("❌ Record rejected.")
                            st.rerun()
                else:
                    st.caption("👁️  Read-only view.")
                    for group_name, field_names in ALL_DISPLAY_GROUPS.items():
                        section_header(group_name)
                        for fname in field_names:
                            record_field_row(
                                label=fname.replace("_", " ").title(),
                                value=r.get(fname),
                                flagged=fname in flagged_list,
                            )

                st.caption(f"Status: {status.upper()} | Record #{record_id} | {(r.get('created_at') or '')[:10]}")
