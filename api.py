import csv
import io
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from modules.database import (
    get_all_records,
    get_record,
    update_record_status,
    get_dashboard_stats,
    get_audit_log,
    init_db,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Terra Lens API",
    description=(
        "Intelligent Land Record Digitization and Validation System — "
        "Smart India Hackathon 2026 — Problem Statement 26018"
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    """Initialize database tables on API startup."""
    init_db()
    logger.info("Terra Lens API started. Database initialized.")


class StatusUpdate(BaseModel):
    """Request body for updating a record's verification status."""
    status: str
    verified_by: int
    notes: Optional[str] = ""


@app.get("/health", tags=["System"])
def health_check() -> dict:
    """
    Health check endpoint.
    Returns system status and current timestamp.
    Used by monitoring tools and government portals to verify API is live.
    """
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "system": "Terra Lens",
        "version": "1.0.0",
        "hackathon": "Smart India Hackathon 2026",
        "problem": "26018",
    }


@app.get("/api/v1/stats", tags=["Dashboard"])
def get_stats() -> dict:
    """
    Returns processing statistics for the analytics dashboard.
    Includes total documents, records, verification status breakdown,
    average confidence, and top 10 districts.
    """
    return get_dashboard_stats()


@app.get("/api/v1/records", tags=["Records"])
def list_records(
    status: Optional[str] = Query(None, description="Filter: pending | verified | rejected"),
    district: Optional[str] = Query(None, description="Filter by district name"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    """
    List land records with optional filters.
    Supports pagination via limit and offset.
    Returns total count and list of record dicts.
    """
    records = get_all_records(
        status=status,
        district=district,
        limit=limit,
        offset=offset,
    )
    return {
        "count": len(records),
        "offset": offset,
        "limit": limit,
        "filters": {"status": status, "district": district},
        "records": records,
    }


@app.get("/api/v1/records/{record_id}", tags=["Records"])
def get_one_record(record_id: int) -> dict:
    """
    Get a single land record by its database ID.
    Returns 404 if record does not exist.
    """
    record = get_record(record_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Record {record_id} not found",
        )
    return record


@app.put("/api/v1/records/{record_id}/status", tags=["Records"])
def update_status(record_id: int, body: StatusUpdate) -> dict:
    """
    Update the verification status of a land record.
    Used by human reviewers to approve or reject records.
    Valid status values: verified | rejected | pending
    """
    valid_statuses = {"verified", "rejected", "pending"}
    if body.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{body.status}'. Must be one of: {valid_statuses}",
        )

    success = update_record_status(
        record_id=record_id,
        status=body.status,
        verified_by=body.verified_by,
        notes=body.notes or "",
    )
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Record {record_id} not found or update failed",
        )

    return {
        "success": True,
        "record_id": record_id,
        "new_status": body.status,
        "updated_at": datetime.now().isoformat(),
    }


@app.get("/api/v1/export/json", tags=["Export"])
def export_json(
    status: Optional[str] = Query("verified", description="Filter by status"),
    district: Optional[str] = Query(None, description="Filter by district"),
) -> StreamingResponse:
    """
    Export land records as a downloadable JSON file.
    Designed for integration with LRMS and DILRMP government systems.
    Default exports only verified records.
    """
    records = get_all_records(status=status, district=district, limit=10000)
    export_data = {
        "export_timestamp": datetime.now().isoformat(),
        "system": "Terra Lens — SIH 2026",
        "problem_id": "26018",
        "record_count": len(records),
        "filters": {"status": status, "district": district},
        "records": records,
    }
    json_str = json.dumps(export_data, indent=2, ensure_ascii=False)
    filename = f"land_records_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    return StreamingResponse(
        io.BytesIO(json_str.encode("utf-8")),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/api/v1/export/csv", tags=["Export"])
def export_csv(
    status: Optional[str] = Query("verified", description="Filter by status"),
    district: Optional[str] = Query(None, description="Filter by district"),
) -> StreamingResponse:
    """
    Export land records as a downloadable CSV file.
    Compatible with Excel and government GIS systems.
    Default exports only verified records.
    """
    records = get_all_records(status=status, district=district, limit=10000)
    if not records:
        raise HTTPException(
            status_code=404,
            detail="No records found with the given filters",
        )

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=records[0].keys())
    writer.writeheader()
    writer.writerows(records)
    output.seek(0)

    filename = f"land_records_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/api/v1/audit", tags=["Audit"])
def get_audit(
    limit: int = Query(50, ge=1, le=500),
) -> dict:
    """
    Returns the audit trail of all system actions.
    Used for compliance, transparency, and governance reporting.
    """
    log = get_audit_log(limit=limit)
    return {
        "count": len(log),
        "log": log,
    }


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.INFO)
    print("Starting Terra Lens API server...")
    print("Docs available at: http://localhost:8000/docs")
    print("Health check at:   http://localhost:8000/health")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
