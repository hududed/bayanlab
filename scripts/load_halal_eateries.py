#!/usr/bin/env python3
"""
Load enriched halal eateries CSV into database.

Input: exports/halal_eateries/colorado_halal_eateries_enriched.csv
Output: Rows in halal_eateries table

Usage:
    uv run python scripts/load_halal_eateries.py
    uv run python scripts/load_halal_eateries.py --dry-run
    uv run python scripts/load_halal_eateries.py --clear  # Clear table first
"""

import argparse
import csv
import os
from decimal import Decimal
from pathlib import Path
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

INPUT_CSV = Path("exports/halal_eateries/colorado_halal_eateries_enriched.csv")

# Use sync DB URL for direct psycopg2 connection
DATABASE_URL = os.getenv('DATABASE_URL_SYNC', 'postgresql://bayan:bayan@localhost:5433/bayan_backbone')


def parse_tags(tags_str: str) -> dict:
    """Parse semicolon-separated tags into boolean flags."""
    flags = {
        'is_favorite': False,
        'is_new_listed': False,
        'is_food_truck': False,
        'is_carry_out_only': False,
        'is_cafe_bakery': False,
        'has_many_locations': False,
    }

    if not tags_str:
        return flags

    tags = [t.strip().lower() for t in tags_str.split(';')]

    if 'favorite' in tags:
        flags['is_favorite'] = True
    if 'new_listed' in tags:
        flags['is_new_listed'] = True
    if 'food_truck' in tags:
        flags['is_food_truck'] = True
    if 'carry_out' in tags:
        flags['is_carry_out_only'] = True
    if 'cafe_bakery' in tags:
        flags['is_cafe_bakery'] = True
    if 'many_locations' in tags:
        flags['has_many_locations'] = True

    return flags


def map_halal_status(status_str: str) -> str:
    """Map CSV halal_status to enum value."""
    status_map = {
        'validated': 'validated',
        'likely_halal': 'likely_halal',
        'unverified': 'unverified',
    }
    return status_map.get(status_str.lower(), 'unverified')


def load_eateries(input_csv: Path, dry_run: bool = False, clear: bool = False):
    """Load CSV into halal_eateries table."""

    with open(input_csv, 'r', encoding='utf-8') as f:
        reader = list(csv.DictReader(f))

    print(f"📂 Loading {len(reader)} eateries from {input_csv}")

    if dry_run:
        print("🔍 DRY RUN - No database changes\n")
        for i, row in enumerate(reader[:5], 1):
            print(f"{i}. {row['name']} - {row.get('address_street', 'N/A')}, {row.get('address_city', 'N/A')}")
        print(f"... and {len(reader) - 5} more")
        return

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    try:
        if clear:
            print("🗑️  Clearing existing data...")
            cur.execute("DELETE FROM halal_eateries")
            print(f"   Deleted {cur.rowcount} rows")

        # Prepare data for bulk insert
        rows_to_insert = []

        for row in reader:
            tags = parse_tags(row.get('tags', ''))

            # Use enriched address fields, fallback to original
            city = row.get('address_city') or row.get('city', '')
            state = row.get('address_state') or row.get('state', 'CO')

            # Parse numeric fields
            lat = row.get('latitude')
            lng = row.get('longitude')
            rating = row.get('google_rating')

            rows_to_insert.append((
                row.get('name', ''),
                row.get('cuisine_style', ''),
                row.get('address_street', ''),
                city,
                state,
                row.get('address_zip', ''),
                Decimal(lat) if lat else None,
                Decimal(lng) if lng else None,
                row.get('phone', ''),
                row.get('website', ''),
                row.get('hours_raw', ''),
                Decimal(rating) if rating else None,
                map_halal_status(row.get('halal_status', 'unverified')),
                tags['is_favorite'],
                tags['is_new_listed'],
                tags['is_food_truck'],
                tags['is_carry_out_only'],
                tags['is_cafe_bakery'],
                tags['has_many_locations'],
                row.get('source', 'colorado_halal'),
                row.get('source_ref', ''),
                row.get('google_place_id', ''),
                row.get('tags', ''),
            ))

        # Bulk upsert - use name + city as unique key to avoid duplicates
        # ON CONFLICT updates existing records, inserts new ones
        insert_query = """
            INSERT INTO halal_eateries (
                name, cuisine_style, address_street, address_city, address_state, address_zip,
                latitude, longitude, phone, website, hours_raw, google_rating, halal_status,
                is_favorite, is_new_listed, is_food_truck, is_carry_out_only, is_cafe_bakery,
                has_many_locations, source, source_ref, google_place_id, tags
            ) VALUES %s
            ON CONFLICT (LOWER(name), LOWER(address_street)) DO UPDATE SET
                name = EXCLUDED.name,
                cuisine_style = EXCLUDED.cuisine_style,
                address_street = EXCLUDED.address_street,
                address_city = EXCLUDED.address_city,
                address_state = EXCLUDED.address_state,
                address_zip = EXCLUDED.address_zip,
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                phone = EXCLUDED.phone,
                website = EXCLUDED.website,
                hours_raw = EXCLUDED.hours_raw,
                google_rating = EXCLUDED.google_rating,
                halal_status = EXCLUDED.halal_status,
                is_favorite = EXCLUDED.is_favorite,
                is_new_listed = EXCLUDED.is_new_listed,
                is_food_truck = EXCLUDED.is_food_truck,
                is_carry_out_only = EXCLUDED.is_carry_out_only,
                is_cafe_bakery = EXCLUDED.is_cafe_bakery,
                has_many_locations = EXCLUDED.has_many_locations,
                source = EXCLUDED.source,
                source_ref = EXCLUDED.source_ref,
                tags = EXCLUDED.tags,
                updated_at = NOW()
        """

        execute_values(cur, insert_query, rows_to_insert)

        conn.commit()

        # Get count
        cur.execute("SELECT COUNT(*) FROM halal_eateries")
        count = cur.fetchone()[0]

        print(f"\n✅ Loaded {len(rows_to_insert)} eateries")
        print(f"📊 Total in table: {count}")

    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Load halal eateries CSV into database')
    parser.add_argument('--input', type=Path, default=INPUT_CSV, help='Input CSV path')
    parser.add_argument('--dry-run', action='store_true', help='Preview without loading')
    parser.add_argument('--clear', action='store_true', help='Clear table before loading')

    args = parser.parse_args()

    if not args.input.exists():
        print(f"❌ Input file not found: {args.input}")
        exit(1)

    load_eateries(args.input, args.dry_run, args.clear)


if __name__ == "__main__":
    main()
