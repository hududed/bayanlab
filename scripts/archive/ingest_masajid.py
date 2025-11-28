#!/usr/bin/env python3
"""
Ingest Colorado mosques (masajid) from CSV into the database.

Supports both raw and enriched CSV files. Enriched files include:
- google_place_id, google_rating, google_review_count
- verification_status (from enrichment)

Usage:
    python scripts/ingest_masajid.py                              # Uses enriched CSV
    python scripts/ingest_masajid.py seed/masajid_colorado.csv    # Specific file
    python scripts/ingest_masajid.py --dry-run

Or with uv:
    uv run python scripts/ingest_masajid.py
"""
import csv
import os
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

# Load .env file
load_dotenv()


def get_db_connection():
    """Get database connection from environment."""
    # Try sync URL first (for scripts)
    db_url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL or DATABASE_URL_SYNC environment variable required")

    # Convert asyncpg URL to psycopg2 format
    if "postgresql+asyncpg" in db_url:
        db_url = db_url.replace("postgresql+asyncpg", "postgresql")

    # Handle ssl parameter
    if "sslmode=" not in db_url and "ssl=" not in db_url:
        db_url += ("&" if "?" in db_url else "?") + "sslmode=require"
    elif "ssl=require" in db_url:
        db_url = db_url.replace("ssl=require", "sslmode=require")

    return psycopg2.connect(db_url)


def parse_bool(value: str) -> bool | None:
    """Parse boolean from CSV string."""
    if not value:
        return None
    return value.upper() in ("TRUE", "1", "YES", "T")


def ingest_masajid(csv_path: Path, dry_run: bool = False):
    """Ingest masajid from CSV file."""
    print(f"Reading from {csv_path}")

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Found {len(rows)} mosques to ingest")

    if dry_run:
        print("DRY RUN - not inserting into database")
        for row in rows:
            print(f"  - {row['name']} ({row['address_city']}, {row['address_state']})")
        return

    conn = get_db_connection()
    cur = conn.cursor()

    # Prepare data for insertion
    insert_data = []
    for row in rows:
        # Parse google rating if present
        google_rating = None
        if row.get("google_rating"):
            try:
                google_rating = float(row["google_rating"])
            except ValueError:
                pass

        # Parse google review count if present
        google_review_count = None
        if row.get("google_review_count"):
            try:
                google_review_count = int(row["google_review_count"])
            except ValueError:
                pass

        # Determine verification status from enrichment
        verification_status = "unverified"
        if row.get("enrichment_status") == "success":
            verification_status = "verified"

        insert_data.append((
            row["name"],
            row.get("address_street") or None,
            row["address_city"],
            row["address_state"],
            row.get("address_zip") or None,
            float(row["latitude"]) if row.get("latitude") else None,
            float(row["longitude"]) if row.get("longitude") else None,
            row.get("phone") or None,
            row.get("website") or None,
            row.get("email") or None,
            row.get("languages") or None,
            parse_bool(row.get("has_womens_section")),
            parse_bool(row.get("has_parking")),
            parse_bool(row.get("has_wudu_facilities")),
            parse_bool(row.get("offers_jumah")),
            parse_bool(row.get("offers_daily_prayers")),
            parse_bool(row.get("offers_quran_classes")),
            parse_bool(row.get("offers_weekend_school")),
            row.get("region", "CO"),
            row["source"],
            row.get("notes") or None,
            row.get("google_place_id") or None,
            google_rating,
            google_review_count,
            verification_status,
        ))

    # Upsert query (insert or update on conflict)
    insert_sql = """
        INSERT INTO masajid (
            name, address_street, address_city, address_state, address_zip,
            latitude, longitude, phone, website, email, languages,
            has_womens_section, has_parking, has_wudu_facilities,
            offers_jumah, offers_daily_prayers, offers_quran_classes, offers_weekend_school,
            region, source, notes,
            google_place_id, google_rating, google_review_count, verification_status
        ) VALUES %s
        ON CONFLICT (LOWER(name), LOWER(address_city)) DO UPDATE SET
            address_street = EXCLUDED.address_street,
            address_state = EXCLUDED.address_state,
            address_zip = EXCLUDED.address_zip,
            latitude = COALESCE(EXCLUDED.latitude, masajid.latitude),
            longitude = COALESCE(EXCLUDED.longitude, masajid.longitude),
            phone = COALESCE(EXCLUDED.phone, masajid.phone),
            website = COALESCE(EXCLUDED.website, masajid.website),
            email = COALESCE(EXCLUDED.email, masajid.email),
            languages = COALESCE(EXCLUDED.languages, masajid.languages),
            has_womens_section = COALESCE(EXCLUDED.has_womens_section, masajid.has_womens_section),
            has_parking = COALESCE(EXCLUDED.has_parking, masajid.has_parking),
            has_wudu_facilities = COALESCE(EXCLUDED.has_wudu_facilities, masajid.has_wudu_facilities),
            offers_jumah = COALESCE(EXCLUDED.offers_jumah, masajid.offers_jumah),
            offers_daily_prayers = COALESCE(EXCLUDED.offers_daily_prayers, masajid.offers_daily_prayers),
            offers_quran_classes = COALESCE(EXCLUDED.offers_quran_classes, masajid.offers_quran_classes),
            offers_weekend_school = COALESCE(EXCLUDED.offers_weekend_school, masajid.offers_weekend_school),
            notes = COALESCE(EXCLUDED.notes, masajid.notes),
            google_place_id = COALESCE(EXCLUDED.google_place_id, masajid.google_place_id),
            google_rating = COALESCE(EXCLUDED.google_rating, masajid.google_rating),
            google_review_count = COALESCE(EXCLUDED.google_review_count, masajid.google_review_count),
            verification_status = EXCLUDED.verification_status,
            updated_at = NOW()
    """

    try:
        execute_values(cur, insert_sql, insert_data)
        conn.commit()
        print(f"Successfully ingested {len(insert_data)} mosques")
    except Exception as e:
        conn.rollback()
        print(f"Error inserting data: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    import sys

    # Default CSV path - prefer enriched file if it exists
    enriched_path = Path(__file__).parent.parent / "seed" / "masajid_colorado_enriched.csv"
    raw_path = Path(__file__).parent.parent / "seed" / "masajid_colorado.csv"
    csv_path = enriched_path if enriched_path.exists() else raw_path

    # Check for command line argument
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        csv_path = Path(sys.argv[1])

    # Check for dry run flag
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv

    if not csv_path.exists():
        print(f"Error: CSV file not found at {csv_path}")
        sys.exit(1)

    ingest_masajid(csv_path, dry_run=dry_run)
