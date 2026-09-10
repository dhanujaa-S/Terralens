import re
import sqlite3
import logging
from datetime import datetime, date
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Optional
from pathlib import Path

from modules.field_classifier import LandRecord, LandField

logger = logging.getLogger(__name__)
DB_PATH = Path("terra_lens.db")


@dataclass
class ValidationError:
    """One validation issue found in a LandRecord."""
    field_name: str
    rule: str
    message: str
    severity: str


@dataclass
class DuplicateCandidate:
    """A potentially duplicate record found in the database."""
    record_id: int
    similarity_score: float
    matching_fields: list
    is_likely_duplicate: bool


@dataclass
class ValidationResult:
    """
    Full result returned by ValidationEngine.validate().
    is_valid is True only when there are zero errors (warnings are allowed).
    validation_score combines rule quality and extraction confidence.
    """
    is_valid: bool
    errors:               list = field(default_factory=list)
    warnings:             list = field(default_factory=list)
    duplicate_candidates: list = field(default_factory=list)
    anomalies:            list = field(default_factory=list)
    validation_score:     float = 0.0
    validated_at:         str = ""

    def __post_init__(self):
        if not self.validated_at:
            self.validated_at = datetime.now().isoformat()

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    @property
    def has_duplicates(self) -> bool:
        return any(d.is_likely_duplicate for d in self.duplicate_candidates)


class BusinessRuleValidator:
    """
    Validates a LandRecord against Indian land administration business rules.
    Returns a list of ValidationError objects — mix of errors and warnings.
    """
    VALID_STATES = {
        "andhra pradesh", "arunachal pradesh", "assam", "bihar",
        "chhattisgarh", "goa", "gujarat", "haryana", "himachal pradesh",
        "jharkhand", "karnataka", "kerala", "madhya pradesh", "maharashtra",
        "manipur", "meghalaya", "mizoram", "nagaland", "odisha", "punjab",
        "rajasthan", "sikkim", "tamil nadu", "telangana", "tripura",
        "uttar pradesh", "uttarakhand", "west bengal", "delhi",
        "jammu and kashmir", "ladakh", "puducherry", "chandigarh",
        "andaman and nicobar islands", "dadra and nagar haveli", "lakshadweep",
    }
    VALID_AREA_UNITS = {
        "acre", "hectare", "bigha", "guntha", "cent", "marla",
        "sq.ft", "sq.m", "sq.yd", "kanal", "biswa",
    }
    VALID_LAND_CLASSIFICATIONS = {
        "agricultural", "residential", "commercial", "industrial",
        "wasteland", "forest", "government", "common land", "water body",
    }
    VALID_OWNERSHIP_TYPES = {
        "single", "joint", "government", "trust", "disputed",
    }
    DATE_PATTERNS = [
        r"^\d{2}-\d{2}-\d{4}$",
        r"^\d{2}/\d{2}/\d{4}$",
        r"^\d{4}-\d{2}-\d{2}$",
    ]
    DATE_FORMATS = ["%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"]

    def validate(self, record: LandRecord) -> list:
        """Run all checks and return combined list of errors and warnings."""
        issues = []
        issues.extend(self._check_required_fields(record))
        issues.extend(self._check_formats(record))
        issues.extend(self._check_cross_fields(record))
        issues.extend(self._check_value_ranges(record))
        return issues

    def _check_required_fields(self, record: LandRecord) -> list:
        """Ensure the mandatory identity/location fields are present."""
        issues = []
        required = {
            "landowner_name": "Landowner name is mandatory for all land records",
            "village": "Village name is mandatory",
            "district": "District is mandatory",
            "state": "State is mandatory",
        }
        for field_name, message in required.items():
            val = getattr(record, field_name).value
            if val is None:
                issues.append(ValidationError(
                    field_name=field_name,
                    rule="REQUIRED_FIELD",
                    message=message,
                    severity="error",
                ))
        return issues

    def _check_formats(self, record: LandRecord) -> list:
        """Validate field formats and known-value sets."""
        issues = []

        pincode = record.pincode.value
        if pincode and not re.match(r"^\d{6}$", pincode.strip()):
            issues.append(ValidationError(
                field_name="pincode",
                rule="FORMAT_PINCODE",
                message="Pincode must be exactly 6 digits",
                severity="error",
            ))

        for field_name in ("registration_date", "mutation_date", "document_date"):
            value = getattr(record, field_name).value
            if value and not self._is_valid_date(value):
                issues.append(ValidationError(
                    field_name=field_name,
                    rule="FORMAT_DATE",
                    message=f"{field_name} must be in DD-MM-YYYY format. Got: {value}",
                    severity="warning",
                ))

        plot_area = record.plot_area.value
        if plot_area:
            try:
                area = float(plot_area.replace(",", ""))
                if area <= 0:
                    issues.append(ValidationError(
                        field_name="plot_area",
                        rule="RANGE_AREA",
                        message="Plot area must be greater than 0",
                        severity="error",
                    ))
                elif area > 10000:
                    issues.append(ValidationError(
                        field_name="plot_area",
                        rule="RANGE_AREA",
                        message="Unusually large area — please verify",
                        severity="warning",
                    ))
            except ValueError:
                issues.append(ValidationError(
                    field_name="plot_area",
                    rule="FORMAT_AREA",
                    message=f"Plot area '{plot_area}' is not a valid number",
                    severity="error",
                ))

        state = record.state.value
        if state and state.lower().strip() not in self.VALID_STATES:
            issues.append(ValidationError(
                field_name="state",
                rule="INVALID_STATE",
                message=f"'{state}' is not a recognized Indian state or UT",
                severity="warning",
            ))

        land_classification = record.land_classification.value
        if land_classification and land_classification.lower() not in self.VALID_LAND_CLASSIFICATIONS:
            issues.append(ValidationError(
                field_name="land_classification",
                rule="INVALID_CLASSIFICATION",
                message=f"'{land_classification}' is not a recognized land classification",
                severity="warning",
            ))

        area_unit = record.area_unit.value
        if area_unit and area_unit.lower() not in self.VALID_AREA_UNITS:
            issues.append(ValidationError(
                field_name="area_unit",
                rule="INVALID_AREA_UNIT",
                message=f"'{area_unit}' is not a recognized area unit",
                severity="warning",
            ))

        ownership_type = record.ownership_type.value
        if ownership_type and ownership_type.lower() not in self.VALID_OWNERSHIP_TYPES:
            issues.append(ValidationError(
                field_name="ownership_type",
                rule="INVALID_OWNERSHIP",
                message=f"'{ownership_type}' is not a recognized ownership type",
                severity="warning",
            ))

        return issues

    def _check_cross_fields(self, record: LandRecord) -> list:
        """Check logical consistency between related fields."""
        issues = []

        if record.registration_number.value and record.registration_date.value is None:
            issues.append(ValidationError(
                field_name="registration_date",
                rule="CROSS_FIELD",
                message="Registration number present but registration date is missing",
                severity="warning",
            ))

        if record.mutation_number.value and record.mutation_date.value is None:
            issues.append(ValidationError(
                field_name="mutation_date",
                rule="CROSS_FIELD",
                message="Mutation number present but mutation date is missing",
                severity="warning",
            ))

        if record.mutation_date.value and record.registration_date.value:
            mutation_dt = self._parse_date(record.mutation_date.value)
            registration_dt = self._parse_date(record.registration_date.value)
            if mutation_dt and registration_dt and mutation_dt < registration_dt:
                issues.append(ValidationError(
                    field_name="mutation_date",
                    rule="DATE_LOGIC",
                    message="Mutation date is before registration date",
                    severity="warning",
                ))

        if record.ownership_type.value and record.ownership_type.value.lower() == "joint" \
                and record.ownership_share.value is None:
            issues.append(ValidationError(
                field_name="ownership_share",
                rule="CROSS_FIELD",
                message="Joint ownership requires ownership share percentage",
                severity="warning",
            ))

        return issues

    def _check_value_ranges(self, record: LandRecord) -> list:
        """Check that field values fall within sensible real-world ranges."""
        issues = []

        registration_date = record.registration_date.value
        if registration_date:
            year_match = re.search(r"\d{4}", registration_date)
            if year_match and int(year_match.group()) > date.today().year:
                issues.append(ValidationError(
                    field_name="registration_date",
                    rule="FUTURE_DATE",
                    message="Registration date is in the future",
                    severity="error",
                ))

        return issues

    def _parse_date(self, date_str: str):
        """Parse a date string using any of the known DATE_FORMATS. Returns None on failure."""
        for fmt in self.DATE_FORMATS:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        return None

    def _is_valid_date(self, date_str: str) -> bool:
        """Return True if date_str matches any of the known DATE_PATTERNS."""
        return any(re.match(pattern, date_str) for pattern in self.DATE_PATTERNS)


class DuplicateDetector:
    """
    Checks a new LandRecord against existing records in the database.
    Uses weighted fuzzy string matching to find potential duplicates.
    Returns top 5 candidates with similarity >= 0.65.
    is_likely_duplicate is True if similarity >= 0.80.
    """
    SIMILARITY_THRESHOLD = 0.80
    CANDIDATE_THRESHOLD = 0.65
    FIELD_WEIGHTS = {
        "landowner_name": 0.30,
        "survey_number": 0.25,
        "khasra_number": 0.20,
        "village": 0.15,
        "registration_number": 0.10,
    }

    def __init__(self, db_path: Path = DB_PATH):
        """Store the path to the SQLite database used for duplicate lookups."""
        self.db_path = db_path

    def _similarity(self, a: str, b: str) -> float:
        """Compute SequenceMatcher similarity between two strings."""
        if not a or not b:
            return 0.0
        return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()

    def check(self, record: LandRecord) -> list:
        """
        Query DB for records in the same district and compute weighted similarity.
        Returns list of DuplicateCandidates sorted by score descending.
        Returns empty list on any DB error.
        """
        candidates = []
        district = record.district.value or ""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, landowner_name, survey_number, khasra_number,
                       village, district, registration_number
                FROM land_records
                WHERE district = ? OR district IS NULL
                LIMIT 500
                """,
                (district,),
            )
            rows = cur.fetchall()
            conn.close()
        except Exception as e:
            logger.warning(f"Duplicate check DB error: {e}")
            return []

        for row in rows:
            rid, db_owner, db_survey, db_khasra, db_village, db_district, db_reg = row
            db_values = {
                "landowner_name": db_owner,
                "survey_number": db_survey,
                "khasra_number": db_khasra,
                "village": db_village,
                "registration_number": db_reg,
            }
            record_values = {
                "landowner_name": record.landowner_name.value,
                "survey_number": record.survey_number.value,
                "khasra_number": record.khasra_number.value,
                "village": record.village.value,
                "registration_number": record.registration_number.value,
            }

            total_weight = 0.0
            total_score = 0.0
            matching_fields = []
            for fname, weight in self.FIELD_WEIGHTS.items():
                rv = record_values.get(fname)
                dv = db_values.get(fname)
                if rv and dv:
                    sim = self._similarity(rv, dv)
                    total_score += sim * weight
                    total_weight += weight
                    if sim > 0.85:
                        matching_fields.append(fname)

            if total_weight == 0:
                continue

            normalized = round(total_score / total_weight, 3)
            if normalized >= self.CANDIDATE_THRESHOLD:
                candidates.append(DuplicateCandidate(
                    record_id=rid,
                    similarity_score=normalized,
                    matching_fields=matching_fields,
                    is_likely_duplicate=normalized >= self.SIMILARITY_THRESHOLD,
                ))

        candidates.sort(key=lambda c: c.similarity_score, reverse=True)
        return candidates[:5]


class AnomalyDetector:
    """
    Detects suspicious patterns and logical anomalies in extracted land records.
    Returns list of human-readable anomaly description strings.
    """
    SUSPICIOUS_NAMES = {"test", "na", "n/a", "unknown", "xxx", "null", "none", ""}

    def detect(self, record: LandRecord) -> list:
        """Check record for anomalies. Returns list of anomaly description strings."""
        anomalies = []

        if record.landowner_name.value:
            if record.landowner_name.value.lower().strip() in self.SUSPICIOUS_NAMES:
                anomalies.append(
                    f"Suspicious landowner name: '{record.landowner_name.value}'"
                )

        if record.land_classification.value:
            if record.land_classification.value.lower() == "agricultural":
                boundaries = [
                    record.boundary_north.value,
                    record.boundary_south.value,
                    record.boundary_east.value,
                    record.boundary_west.value,
                ]
                if not any(boundaries):
                    anomalies.append(
                        "Agricultural land record has no boundary information — verify document"
                    )

        if record.registration_date.value:
            year_match = re.search(r"\d{4}", record.registration_date.value)
            if year_match:
                year = int(year_match.group())
                if year < 1900:
                    anomalies.append(
                        f"Registration year {year} is too old — verify document authenticity"
                    )
                elif year > date.today().year:
                    anomalies.append(
                        f"Registration year {year} is in the future"
                    )

        if record.overall_confidence < 0.4:
            anomalies.append(
                f"Very low extraction confidence ({record.overall_confidence:.1%}) "
                "— manual review is essential"
            )

        from dataclasses import fields as dc_fields
        filled = sum(
            1 for f in dc_fields(record)
            if isinstance(getattr(record, f.name), LandField)
            and getattr(record, f.name).value is not None
        )
        if filled < 3:
            anomalies.append(
                f"Only {filled} fields extracted — document may be unreadable or blank"
            )

        return anomalies


class ValidationEngine:
    """
    Master validation orchestrator for Terra Lens.
    Combines BusinessRuleValidator, DuplicateDetector, and AnomalyDetector.
    This is the ONLY class imported by other modules.
    Usage: result = ValidationEngine().validate(record)
    """

    def __init__(self, db_path: Path = DB_PATH):
        """Initialize all three sub-validators."""
        self.rule_validator = BusinessRuleValidator()
        self.duplicate_detector = DuplicateDetector(db_path)
        self.anomaly_detector = AnomalyDetector()

    def validate(self, record: LandRecord) -> ValidationResult:
        """
        Run all three validators and compute a combined validation score.
        Score formula:
          rule_score  = 1.0 - (errors*0.15) - (warnings*0.05)
                            - (duplicate_found*0.30) - (anomalies*0.10)
          final_score = rule_score * 0.6 + record.overall_confidence * 0.4
        """
        logger.info("Starting validation pipeline...")

        all_issues = self.rule_validator.validate(record)
        errors = [i for i in all_issues if i.severity == "error"]
        warnings = [i for i in all_issues if i.severity in ("warning", "info")]

        duplicates = self.duplicate_detector.check(record)
        anomalies = self.anomaly_detector.detect(record)

        error_penalty = len(errors) * 0.15
        warning_penalty = len(warnings) * 0.05
        duplicate_penalty = 0.30 if any(d.is_likely_duplicate for d in duplicates) else 0.0
        anomaly_penalty = len(anomalies) * 0.10

        rule_score = max(0.0, 1.0 - error_penalty - warning_penalty
                          - duplicate_penalty - anomaly_penalty)
        final_score = round(rule_score * 0.6 + record.overall_confidence * 0.4, 3)

        result = ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            duplicate_candidates=duplicates,
            anomalies=anomalies,
            validation_score=final_score,
        )

        logger.info(
            f"Validation complete. valid={result.is_valid} "
            f"errors={result.error_count} warnings={result.warning_count} "
            f"duplicates={len(duplicates)} score={final_score:.2f}"
        )
        return result


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    from dataclasses import fields as dc_fields
    from modules.field_classifier import LandRecord, LandField

    def mf(val, conf="high", score=0.9):
        return LandField(
            value=val, confidence=conf,
            confidence_score=score,
            needs_review=(val is None or score < 0.6)
        )

    rec = LandRecord(
        landowner_name=      mf("Ramesh Kumar Sharma"),
        father_spouse_name=  mf("Late Suresh Sharma"),
        caste_category=      mf("General"),
        survey_number=       mf("47/2"),
        khasra_number=       mf("89"),
        khata_number=        mf("125"),
        plot_number=         mf(None, "low", 0.1),
        village=             mf("Khed"),
        tehsil=              mf("Haveli"),
        district=            mf("Pune"),
        state=               mf("Maharashtra"),
        pincode=             mf("411001"),
        plot_area=           mf("2.50"),
        area_unit=           mf("acre"),
        land_classification= mf("agricultural"),
        land_use=            mf("Farming"),
        boundary_north=      mf("Road"),
        boundary_south=      mf("Plot 46"),
        boundary_east=       mf("River"),
        boundary_west=       mf("Plot 48"),
        ownership_type=      mf("Single"),
        ownership_share=     mf(None, "low", 0.0),
        registration_number= mf("REG/2019/45678"),
        registration_date=   mf("15-08-2019"),
        mutation_number=     mf("MUT/2020/1234"),
        mutation_date=       mf("22-01-2020"),
        document_date=       mf("15-08-2019"),
    )
    rec.calculate_overall_confidence()

    engine = ValidationEngine()
    result = engine.validate(rec)

    print("\n" + "=" * 60)
    print(f"Validation Score: {result.validation_score:.1%}")
    print(f"Is Valid:         {result.is_valid}")
    print(f"Errors:           {result.error_count}")
    print(f"Warnings:         {result.warning_count}")
    print(f"Duplicates found: {result.has_duplicates}")
    print(f"Anomalies:        {result.anomalies}")

    if result.errors:
        print("\nErrors:")
        for e in result.errors:
            print(f"  [{e.rule}] {e.field_name}: {e.message}")

    if result.warnings:
        print("\nWarnings:")
        for w in result.warnings:
            print(f"  [{w.rule}] {w.field_name}: {w.message}")

    print("\nModule 3 — validation_engine.py OK")
