import streamlit as st
import pandas as pd
import json
from datetime import datetime

from modules.database import get_all_records
from modules.auth import has_permission
from ui.components import page_header, section_header, empty_state


def render_export_page(user: dict) -> None:
    """Render the Export & Integration page for CSV/JSON downloads and API reference info."""
    if not has_permission(user, "export"):
        st.error("🔒 Access denied. Export requires verifier or admin role.")
        return

    page_header("Export & Integration", "Export records for DILRMP and LRMS integration", "📥")

    st.info("""
🏛️  **DILRMP / LRMS Integration Ready**

Terra Lens exports in standard formats compatible with:
- Digital India Land Records Modernization Programme (DILRMP)
- Land Record Management System (LRMS)
- National Generic Document Registration System (NGDRS)
- State GIS platforms and cadastral mapping systems
""")

    with st.expander("⚙️  Export Filters", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            status_filter = st.selectbox("Status", ["verified", "all", "pending", "rejected"], key="exp_status")
        with col2:
            district_filter = st.text_input("District", placeholder="All districts", key="exp_district")
        with col3:
            limit_filter = st.selectbox("Max Records", [100, 500, 1000, 5000], key="exp_limit")

    status_q = None if status_filter == "all" else status_filter
    district_q = district_filter.strip() or None
    records = get_all_records(status=status_q, district=district_q, limit=limit_filter)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    st.markdown(f"**{len(records)} records** ready to export with current filters.")
    st.divider()

    section_header("📄 CSV Export")
    st.caption("Excel-compatible. Suitable for spreadsheet analysis and GIS import.")
    if records:
        df = pd.DataFrame(records)
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label=f"⬇️ Download CSV  ({len(records)} records)",
            data=csv_bytes,
            file_name=f"terra_lens_{timestamp}.csv",
            mime="text/csv",
            use_container_width=True,
            type="primary",
        )
    else:
        st.warning("No records found with current filters.")

    section_header("📋 JSON Export")
    st.caption("Structured JSON for API integration with government systems.")
    if records:
        payload = {
            "export_metadata": {
                "timestamp": datetime.now().isoformat(),
                "system": "Terra Lens — AI-Powered Land Intelligence",
                "record_count": len(records),
                "filters": {"status": status_filter, "district": district_q},
            },
            "records": records,
        }
        json_bytes = json.dumps(payload, indent=2, ensure_ascii=False, default=str).encode("utf-8")
        st.download_button(
            label=f"⬇️ Download JSON  ({len(records)} records)",
            data=json_bytes,
            file_name=f"terra_lens_{timestamp}.json",
            mime="application/json",
            use_container_width=True,
        )

    st.divider()
    section_header("🔌 REST API Endpoints")
    st.markdown("""
| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | System health check |
| `/api/v1/stats` | GET | Dashboard statistics |
| `/api/v1/records` | GET | List records |
| `/api/v1/records/{id}` | GET | Single record |
| `/api/v1/records/{id}/status` | PUT | Update status |
| `/api/v1/export/json` | GET | JSON export |
| `/api/v1/export/csv` | GET | CSV export |
| `/api/v1/audit` | GET | Audit trail |

Start the API server: `py -3.12 -m modules.api`

Then visit: http://localhost:8000/docs
""")
