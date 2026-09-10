import sqlite3
import json
import logging
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)
DB_PATH = Path("terra_lens.db")

EDITABLE_FIELDS = {
    "landowner_name", "survey_number", "khasra_number", "khata_number",
    "village", "tehsil", "district", "state", "pincode", "plot_area",
    "area_unit", "land_classification", "registration_number",
    "registration_date", "mutation_number", "mutation_date",
}


@contextmanager
def get_conn():
    """
    Yields a SQLite connection with WAL mode and foreign keys enabled.
    Auto-commits on success, rolls back on exception, always closes.
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """
    Creates all database tables (documents, land_records, validation_results,
    users, audit_log) and their indexes if they do not already exist.
    """
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_size_bytes INTEGER,
                storage_path TEXT,
                uploaded_by INTEGER,
                uploaded_at TEXT DEFAULT (datetime('now')),
                status TEXT DEFAULT 'pending',
                page_count INTEGER DEFAULT 1,
                ocr_method TEXT,
                ocr_confidence REAL,
                image_quality REAL,
                raw_ocr_text TEXT
            );

            CREATE TABLE IF NOT EXISTS land_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER REFERENCES documents(id),
                landowner_name TEXT,
                landowner_name_conf REAL DEFAULT 0.0,
                father_spouse_name TEXT,
                caste_category TEXT,
                survey_number TEXT,
                survey_number_conf REAL DEFAULT 0.0,
                khasra_number TEXT,
                khasra_number_conf REAL DEFAULT 0.0,
                khata_number TEXT,
                plot_number TEXT,
                village TEXT,
                village_conf REAL DEFAULT 0.0,
                tehsil TEXT,
                district TEXT,
                district_conf REAL DEFAULT 0.0,
                state TEXT,
                pincode TEXT,
                plot_area TEXT,
                area_unit TEXT,
                land_classification TEXT,
                land_use TEXT,
                boundary_north TEXT,
                boundary_south TEXT,
                boundary_east TEXT,
                boundary_west TEXT,
                ownership_type TEXT,
                ownership_share TEXT,
                registration_number TEXT,
                registration_date TEXT,
                mutation_number TEXT,
                mutation_date TEXT,
                document_date TEXT,
                latitude REAL,
                longitude REAL,
                overall_confidence REAL DEFAULT 0.0,
                flagged_fields TEXT,
                needs_review INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                verified_by INTEGER,
                verified_at TEXT,
                reviewer_notes TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS validation_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id INTEGER REFERENCES land_records(id),
                is_valid INTEGER DEFAULT 0,
                validation_score REAL DEFAULT 0.0,
                errors_json TEXT,
                warnings_json TEXT,
                anomalies_json TEXT,
                duplicate_ids TEXT,
                validated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'viewer',
                full_name TEXT,
                state TEXT,
                district TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now')),
                last_login TEXT
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                entity_type TEXT,
                entity_id INTEGER,
                details TEXT,
                ip_address TEXT,
                timestamp TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_records_district ON land_records(district);
            CREATE INDEX IF NOT EXISTS idx_records_village ON land_records(village);
            CREATE INDEX IF NOT EXISTS idx_records_status ON land_records(status);
            CREATE INDEX IF NOT EXISTS idx_records_khasra ON land_records(khasra_number);
            CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id);
            CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_log(timestamp);
        """)
    logger.info("Database initialized at %s", DB_PATH)


def log_audit(conn, user_id: int, action: str, entity_type: str,
              entity_id: int, details: dict) -> None:
    """
    Insert one audit log row using an EXISTING open connection.
    Must be called inside the same with get_conn() block as the main operation
    so both writes are in the same transaction.
    """
    conn.execute(
        """
        INSERT INTO audit_log (user_id, action, entity_type, entity_id, details)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, action, entity_type, entity_id, json.dumps(details)),
    )


def insert_document(filename: str, file_type: str, file_size: int,
                     storage_path: str, uploaded_by: int, page_count: int,
                     ocr_method: str, ocr_confidence: float,
                     image_quality: float, raw_ocr_text: str) -> int:
    """
    Insert a new row into documents and log the upload action.
    Returns the new document's row id.
    """
    with get_conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO documents (
                filename, file_type, file_size_bytes, storage_path,
                uploaded_by, page_count, ocr_method, ocr_confidence,
                image_quality, raw_ocr_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (filename, file_type, file_size, storage_path, uploaded_by,
             page_count, ocr_method, ocr_confidence, image_quality,
             raw_ocr_text),
        )
        doc_id = cursor.lastrowid
        log_audit(conn, uploaded_by, "UPLOAD", "document", doc_id,
                   {"filename": filename, "pages": page_count})
        return int(doc_id)


def insert_land_record(document_id: int, record, user_id: int) -> int:
    """
    Insert a new land record extracted from a document, along with per-field
    confidence scores, and log the creation action.
    Returns the new record's row id.
    """
    def v(f):
        return getattr(getattr(record, f, None), 'value', None)

    def c(f):
        return getattr(getattr(record, f, None), 'confidence_score', 0.0)

    with get_conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO land_records (
                document_id, landowner_name, landowner_name_conf,
                father_spouse_name, caste_category,
                survey_number, survey_number_conf,
                khasra_number, khasra_number_conf,
                khata_number, plot_number,
                village, village_conf,
                tehsil, district, district_conf,
                state, pincode,
                plot_area, area_unit,
                land_classification, land_use,
                boundary_north, boundary_south, boundary_east, boundary_west,
                ownership_type, ownership_share,
                registration_number, registration_date,
                mutation_number, mutation_date,
                document_date, latitude, longitude,
                overall_confidence, flagged_fields, needs_review
            ) VALUES (
                ?, ?, ?,
                ?, ?,
                ?, ?,
                ?, ?,
                ?, ?,
                ?, ?,
                ?, ?, ?,
                ?, ?,
                ?, ?,
                ?, ?,
                ?, ?, ?, ?,
                ?, ?,
                ?, ?,
                ?, ?,
                ?, ?, ?,
                ?, ?, ?
            )
            """,
            (
                document_id, v('landowner_name'), c('landowner_name'),
                v('father_spouse_name'), v('caste_category'),
                v('survey_number'), c('survey_number'),
                v('khasra_number'), c('khasra_number'),
                v('khata_number'), v('plot_number'),
                v('village'), c('village'),
                v('tehsil'), v('district'), c('district'),
                v('state'), v('pincode'),
                v('plot_area'), v('area_unit'),
                v('land_classification'), v('land_use'),
                v('boundary_north'), v('boundary_south'),
                v('boundary_east'), v('boundary_west'),
                v('ownership_type'), v('ownership_share'),
                v('registration_number'), v('registration_date'),
                v('mutation_number'), v('mutation_date'),
                v('document_date'), v('latitude'), v('longitude'),
                record.overall_confidence,
                json.dumps(record.flagged_fields),
                1 if record.flagged_fields else 0,
            ),
        )
        record_id = cursor.lastrowid
        log_audit(conn, user_id, "CREATE_RECORD", "record", record_id,
                   {"document_id": document_id,
                    "confidence": record.overall_confidence})
        return int(record_id)


def save_validation(record_id: int, result) -> int:
    """
    Persist a validation result for a land record, serializing errors,
    warnings, anomalies, and duplicate candidate ids as JSON.
    Returns the new validation_results row id.
    """
    errors_json = json.dumps([
        {"field": e.field_name, "rule": e.rule, "msg": e.message}
        for e in result.errors
    ])
    warnings_json = json.dumps([
        {"field": w.field_name, "rule": w.rule, "msg": w.message}
        for w in result.warnings
    ])
    anomalies_json = json.dumps(result.anomalies)
    duplicate_ids = json.dumps([
        d.record_id for d in result.duplicate_candidates
        if d.is_likely_duplicate
    ])

    with get_conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO validation_results (
                record_id, is_valid, validation_score,
                errors_json, warnings_json, anomalies_json, duplicate_ids
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (record_id, 1 if result.is_valid else 0, result.validation_score,
             errors_json, warnings_json, anomalies_json, duplicate_ids),
        )
        return int(cursor.lastrowid)


def update_record_status(record_id: int, status: str, verified_by: int,
                          notes: str = "") -> bool:
    """
    Update a land record's status, verifier, verification timestamp, and
    reviewer notes, then log the status change action.
    Returns True on success.
    """
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE land_records
            SET status=?, verified_by=?, verified_at=datetime('now'),
                reviewer_notes=?, updated_at=datetime('now')
            WHERE id=?
            """,
            (status, verified_by, notes, record_id),
        )
        log_audit(conn, verified_by, f"STATUS_{status.upper()}", "record",
                   record_id, {"notes": notes})
    return True


def update_record_field(record_id: int, field_name: str, new_value: str,
                         user_id: int) -> bool:
    """
    Update a single editable field on a land record and log the edit action.
    Raises ValueError if field_name is not in the allowed editable set.
    Returns True on success.
    """
    if field_name not in EDITABLE_FIELDS:
        raise ValueError(f"Field '{field_name}' cannot be edited")

    with get_conn() as conn:
        conn.execute(
            f"UPDATE land_records SET {field_name}=?, updated_at=datetime('now') WHERE id=?",
            (new_value, record_id),
        )
        log_audit(conn, user_id, "EDIT_FIELD", "record", record_id,
                   {"field": field_name, "new_value": new_value})
    return True


def get_record(record_id: int) -> Optional[dict]:
    """
    Fetch a single land record by id.
    Returns a dict of the row, or None if no matching record exists.
    """
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM land_records WHERE id=?", (record_id,)
        ).fetchone()
        return dict(row) if row else None


def get_all_records(status: Optional[str] = None,
                     district: Optional[str] = None,
                     limit: int = 100, offset: int = 0) -> list:
    """
    Fetch land records, optionally filtered by status and/or district,
    ordered by most recently created, with pagination.
    Returns a list of dicts, or an empty list on error.
    """
    try:
        query = "SELECT * FROM land_records WHERE 1=1"
        params = []
        if status:
            query += " AND status=?"
            params.append(status)
        if district:
            query += " AND district=?"
            params.append(district)
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]
    except Exception:
        logger.exception("Failed to fetch records")
        return []


def get_dashboard_stats() -> dict:
    """
    Compute aggregate statistics for the dashboard: document and record
    counts, status breakdowns, average confidence, and top districts by
    record count.
    Returns a dict of stats.
    """
    with get_conn() as conn:
        total_documents = conn.execute(
            "SELECT COUNT(*) FROM documents"
        ).fetchone()[0]
        total_records = conn.execute(
            "SELECT COUNT(*) FROM land_records"
        ).fetchone()[0]
        pending = conn.execute(
            "SELECT COUNT(*) FROM land_records WHERE status='pending'"
        ).fetchone()[0]
        verified = conn.execute(
            "SELECT COUNT(*) FROM land_records WHERE status='verified'"
        ).fetchone()[0]
        rejected = conn.execute(
            "SELECT COUNT(*) FROM land_records WHERE status='rejected'"
        ).fetchone()[0]
        needs_review = conn.execute(
            "SELECT COUNT(*) FROM land_records WHERE needs_review=1"
        ).fetchone()[0]
        avg_confidence_row = conn.execute(
            "SELECT AVG(overall_confidence) FROM land_records"
        ).fetchone()[0]
        avg_confidence = round(avg_confidence_row, 3) if avg_confidence_row is not None else 0.0
        by_district_rows = conn.execute(
            """
            SELECT district, COUNT(*) as count
            FROM land_records
            WHERE district IS NOT NULL
            GROUP BY district
            ORDER BY count DESC
            LIMIT 10
            """
        ).fetchall()
        by_district = [
            {"district": row["district"], "count": row["count"]}
            for row in by_district_rows
        ]

        return {
            "total_documents": total_documents,
            "total_records": total_records,
            "pending": pending,
            "verified": verified,
            "rejected": rejected,
            "needs_review": needs_review,
            "avg_confidence": avg_confidence,
            "by_district": by_district,
        }


def get_audit_log(limit: int = 50) -> list:
    """
    Fetch the most recent audit log entries, joined with the acting user's
    username and role.
    Returns a list of dicts, or an empty list on error.
    """
    try:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT al.*, u.username, u.role
                FROM audit_log al
                LEFT JOIN users u ON al.user_id = u.id
                ORDER BY al.timestamp DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]
    except Exception:
        logger.exception("Failed to fetch audit log")
        return []


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
    print(f"Database initialized at: {DB_PATH}")
    stats = get_dashboard_stats()
    print(f"Stats: {stats}")
    print("Module 8 — database.py OK")
