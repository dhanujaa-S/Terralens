import random
import json
import logging
from datetime import datetime, timedelta

from modules.database import init_db, get_conn
from modules.auth import _hash_password, create_default_admin

logger = logging.getLogger(__name__)

OWNERS = [
    "Ramesh Kumar Sharma", "Sunita Devi",
    "Mohan Lal Verma", "Priya Singh",
    "Abdul Rashid Khan", "Lakshmi Narayanan",
    "Kavitha Reddy", "Meena Kumari",
    "Fatima Begum",
]

FATHER_NAMES = [
    "S/o Suresh Sharma", "S/o Lal Khan",
    "Suresh Patil", "Rajender Singh Yadav",
    "Gopal Das", "D/o Ramesh Verma",
    "S/o Narayanan Pillai", "D/o Patil Krishnaiah",
    "S/o Das Gupta",
]

VILLAGES = [
    ("Khed", "Haveli", "Pune", "Maharashtra", 18.5204, 73.8567),
    ("Devanahalli", "Devanahalli", "Bengaluru Rural", "Karnataka", 13.2467, 77.7120),
    ("Kumbakonam", "Kumbakonam", "Thanjavur", "Tamil Nadu", 10.9617, 79.3788),
    ("Khurja", "Khurja", "Bulandshahr", "Uttar Pradesh", 28.2526, 77.8556),
    ("Anand", "Anand", "Anand", "Gujarat", 22.5645, 72.9289),
    ("Amravati", "Amravati", "Amravati", "Maharashtra", 20.9374, 77.7796),
    ("Nellore", "Nellore", "Nellore", "Andhra Pradesh", 14.4426, 79.9865),
    ("Muzaffarpur", "Muzaffarpur", "Muzaffarpur", "Bihar", 26.1197, 85.3910),
]

LAND_TYPES = ["Agricultural", "Residential", "Commercial", "Wasteland"]
LAND_USES = ["Farming", "Residential", "Shop", "Unused"]
AREA_UNITS = ["Acre", "Hectare", "Bigha", "Guntha"]
OWNERSHIP_TYPES = ["Single", "Joint", "Government"]
BOUNDARIES = ["Road", "River", "Canal", "Plot 12", "Forest land",
              "Railway line", "NH-48", "Nala", "Plot 45", "Stream"]
CASTES = ["General", "OBC", "SC", "ST"]

STATUS_POOL = (
    ["verified"] * 6 +
    ["pending"] * 3 +
    ["rejected"] * 1
)


def _random_date(start_year: int = 2000, end_year: int = 2024) -> str:
    """Return a random date as DD-MM-YYYY string between the two years."""
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)
    delta = end - start
    rand = start + timedelta(days=random.randint(0, delta.days))
    return rand.strftime("%d-%m-%Y")


def _random_confidence() -> float:
    """
    Return a weighted random confidence score.
    60% high (0.85-1.0), 30% medium (0.60-0.85), 10% low (0.30-0.60).
    """
    bucket = random.choices(
        ["high", "medium", "low"],
        weights=[60, 30, 10],
    )[0]
    if bucket == "high":
        return round(random.uniform(0.85, 1.0), 3)
    elif bucket == "medium":
        return round(random.uniform(0.60, 0.85), 3)
    else:
        return round(random.uniform(0.30, 0.60), 3)


def generate_sample_records(count: int = 25) -> list:
    """
    Generate a list of realistic Indian land record dicts.
    Each dict has column names matching the land_records table exactly.
    Includes realistic GPS coordinates near each village.
    """
    records = []
    for i in range(count):
        owner = random.choice(OWNERS)
        father = random.choice(FATHER_NAMES)
        village, tehsil, district, state, base_lat, base_lng = random.choice(VILLAGES)
        land_type = random.choice(LAND_TYPES)
        area = round(random.uniform(0.5, 15.0), 2)
        unit = random.choice(AREA_UNITS)
        conf = _random_confidence()
        status = random.choice(STATUS_POOL)
        reg_year = random.randint(2005, 2023)
        mut_year = random.randint(reg_year, 2024)

        lat = round(base_lat + random.uniform(-0.05, 0.05), 6)
        lng = round(base_lng + random.uniform(-0.05, 0.05), 6)

        flagged = (
            json.dumps([]) if conf > 0.70
            else json.dumps(["pincode", "plot_area"])
        )

        record = {
            "document_id": i + 1,
            "landowner_name": owner,
            "landowner_name_conf": conf,
            "father_spouse_name": father,
            "caste_category": random.choice(CASTES),
            "survey_number": f"{random.randint(1,999)}/{random.randint(1,9)}",
            "survey_number_conf": conf,
            "khasra_number": str(random.randint(100, 9999)),
            "khasra_number_conf": conf,
            "khata_number": str(random.randint(1, 500)),
            "plot_number": str(random.randint(1, 200)) if random.random() > 0.3 else None,
            "village": village,
            "village_conf": conf,
            "tehsil": tehsil,
            "district": district,
            "district_conf": conf,
            "state": state,
            "pincode": f"{random.randint(400000, 799999)}",
            "plot_area": str(area),
            "area_unit": unit,
            "land_classification": land_type,
            "land_use": LAND_USES[LAND_TYPES.index(land_type)],
            "boundary_north": random.choice(BOUNDARIES),
            "boundary_south": random.choice(BOUNDARIES),
            "boundary_east": random.choice(BOUNDARIES),
            "boundary_west": random.choice(BOUNDARIES),
            "ownership_type": random.choice(OWNERSHIP_TYPES),
            "ownership_share": "50%" if random.random() > 0.7 else None,
            "registration_number": f"REG/{reg_year}/{random.randint(10000,99999)}",
            "registration_date": _random_date(reg_year, reg_year),
            "mutation_number": f"MUT/{mut_year}/{random.randint(1000,9999)}",
            "mutation_date": _random_date(mut_year, mut_year),
            "document_date": _random_date(reg_year, reg_year),
            "latitude": lat,
            "longitude": lng,
            "overall_confidence": conf,
            "flagged_fields": flagged,
            "needs_review": 0 if conf > 0.70 else 1,
            "status": status,
        }
        records.append(record)
    return records


def seed_database(record_count: int = 25) -> None:
    """
    Seed the database with sample documents, land records, and demo users.
    Safe to re-run — uses INSERT OR IGNORE on all inserts.
    Run this once before demo day:
      py -3.12 -m modules.test_data
    Creates these demo login accounts:
      admin    / admin123   (full access)
      verifier1/ verify123  (verify and reject records)
      uploader1/ upload123  (upload documents)
      viewer1  / view123    (read-only)
    """
    init_db()
    logger.info(f"Seeding database with {record_count} sample records...")

    with get_conn() as conn:
        for i in range(record_count):
            conn.execute(
                """
                INSERT OR IGNORE INTO documents
                (id, filename, file_type, file_size_bytes, status,
                 page_count, ocr_confidence, image_quality)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    i + 1,
                    f"sample_land_record_{i+1:03d}.pdf",
                    ".pdf",
                    random.randint(80_000, 2_000_000),
                    "processed",
                    random.randint(1, 4),
                    round(random.uniform(0.70, 0.99), 2),
                    round(random.uniform(0.60, 0.99), 2),
                ),
            )

        records = generate_sample_records(record_count)
        for r in records:
            conn.execute(
                """
                INSERT OR IGNORE INTO land_records (
                    document_id,
                    landowner_name,       landowner_name_conf,
                    father_spouse_name,   caste_category,
                    survey_number,        survey_number_conf,
                    khasra_number,        khasra_number_conf,
                    khata_number,         plot_number,
                    village,              village_conf,
                    tehsil,               district,
                    district_conf,        state,
                    pincode,              plot_area,
                    area_unit,            land_classification,
                    land_use,             boundary_north,
                    boundary_south,       boundary_east,
                    boundary_west,        ownership_type,
                    ownership_share,      registration_number,
                    registration_date,    mutation_number,
                    mutation_date,        document_date,
                    latitude,             longitude,
                    overall_confidence,   flagged_fields,
                    needs_review,         status
                ) VALUES (
                    :document_id,
                    :landowner_name,       :landowner_name_conf,
                    :father_spouse_name,   :caste_category,
                    :survey_number,        :survey_number_conf,
                    :khasra_number,        :khasra_number_conf,
                    :khata_number,         :plot_number,
                    :village,              :village_conf,
                    :tehsil,               :district,
                    :district_conf,        :state,
                    :pincode,              :plot_area,
                    :area_unit,            :land_classification,
                    :land_use,             :boundary_north,
                    :boundary_south,       :boundary_east,
                    :boundary_west,        :ownership_type,
                    :ownership_share,      :registration_number,
                    :registration_date,    :mutation_number,
                    :mutation_date,        :document_date,
                    :latitude,             :longitude,
                    :overall_confidence,   :flagged_fields,
                    :needs_review,         :status
                )
                """,
                r,
            )

        create_default_admin()

        demo_users = [
            ("verifier1", "verify123", "verifier", "Anita Reddy", "Tamil Nadu", "Chennai"),
            ("uploader1", "upload123", "uploader", "Suresh Kumar", "Maharashtra", "Pune"),
            ("viewer1", "view123", "viewer", "Priya Singh", "Karnataka", "Bengaluru"),
        ]
        for uname, pwd, role, name, state, dist in demo_users:
            conn.execute(
                """
                INSERT OR IGNORE INTO users
                (username, password_hash, role, full_name, state, district)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (uname, _hash_password(pwd), role, name, state, dist),
            )

    logger.info("Database seeding complete.")


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    count = 25
    if len(sys.argv) > 1:
        try:
            count = int(sys.argv[1])
        except ValueError:
            pass

    print("=" * 60)
    print("Terra Lens — Database Seeder")
    print("Smart India Hackathon 2026 — Problem 26018")
    print("=" * 60)

    seed_database(count)

    print(f"\nSeeded {count} land records")
    print(f"Seeded {count} documents")
    print("\nDemo login credentials:")
    print("  admin     / admin123   (full access)")
    print("  verifier1 / verify123  (verify records)")
    print("  uploader1 / upload123  (upload documents)")
    print("  viewer1   / view123    (read only)")
    print("\nRun the app:")
    print("  py -3.12 -m streamlit run app.py")
    print("\nModule 13 — test_data.py OK")
