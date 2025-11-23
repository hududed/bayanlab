#!/usr/bin/env python3
"""
Enrich masajid (mosques) data using Google Places API (New) with OSM fallback.

Uses the shared PlacesEnricher utility (backend/services/common/places_enricher.py).

For each masjid, validates/enriches:
- Address (street, city, state, zip)
- Phone number
- Website
- Coordinates (lat/lng)
- Google Place ID (for deduplication)
- Google rating (optional)

Input: seed/masajid_colorado.csv
Output: seed/masajid_colorado_enriched.csv

Usage:
    uv run python scripts/enrich_masajid.py
    uv run python scripts/enrich_masajid.py --limit 5
    uv run python scripts/enrich_masajid.py --osm-only   # Skip Google, use OSM only
    uv run python scripts/enrich_masajid.py --dry-run

Requirements:
    GOOGLE_PLACES_API_KEY in .env (optional if using --osm-only)
"""

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.common.places_enricher import PlacesEnricher, EnrichmentResult
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Paths
INPUT_CSV = Path("seed/masajid_colorado.csv")
OUTPUT_CSV = Path("seed/masajid_colorado_enriched.csv")


def enrich_masajid(
    input_csv: Path,
    output_csv: Path,
    limit: int | None = None,
    dry_run: bool = False,
    osm_only: bool = False,
):
    """
    Read masajid CSV, enrich via Google Places (New) + OSM, save results.
    """
    enricher = PlacesEnricher(use_osm_fallback=True)

    if dry_run:
        print("🔍 DRY RUN - No API calls will be made\n")

    if osm_only:
        print("🗺️  OSM ONLY mode - Using OpenStreetMap (free, geocoding only)\n")
    elif not enricher.api_key:
        print("⚠️  No GOOGLE_PLACES_API_KEY found, falling back to OSM only\n")
        osm_only = True

    # Read input CSV
    with open(input_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if limit:
        rows = rows[:limit]

    print(f"🕌 Enriching {len(rows)} masajid...\n")

    # Stats
    total = 0
    success = 0
    failed = 0
    google_count = 0
    osm_count = 0

    enriched_rows = []

    for idx, row in enumerate(rows, start=1):
        total += 1
        name = row.get("name", "").strip()
        city = row.get("address_city", "").strip()
        state = row.get("address_state", "CO").strip()

        if not name:
            print(f"[{idx}/{len(rows)}] ⏭️  Skipping: No name")
            failed += 1
            continue

        print(f"[{idx}/{len(rows)}] {name} ({city}, {state})")
        print(f"  Original: {row.get('address_street', 'N/A')}")

        if dry_run:
            enriched_row = row.copy()
            enriched_row["enrichment_status"] = "dry_run"
            enriched_row["enrichment_source"] = ""
        else:
            # Use shared enricher with "mosque" suffix for better search
            result = enricher.enrich(name, city, state, query_suffix="mosque", osm_only=osm_only)

            enriched_row = row.copy()

            if result.status == "success":
                success += 1

                # Update address fields (only if Google found something)
                if result.address.street:
                    enriched_row["address_street"] = result.address.street
                if result.address.city:
                    enriched_row["address_city"] = result.address.city
                if result.address.state:
                    enriched_row["address_state"] = result.address.state
                if result.address.zip:
                    enriched_row["address_zip"] = result.address.zip

                # Update lat/lng
                if result.latitude:
                    enriched_row["latitude"] = str(result.latitude)
                if result.longitude:
                    enriched_row["longitude"] = str(result.longitude)

                # Update contact (only if enriched data is present, don't overwrite existing)
                if result.phone and not row.get("phone"):
                    enriched_row["phone"] = result.phone
                if result.website and not row.get("website"):
                    enriched_row["website"] = result.website

                # Google-specific fields
                enriched_row["google_place_id"] = result.google_place_id or ""
                enriched_row["google_rating"] = str(result.google_rating) if result.google_rating else ""
                enriched_row["google_review_count"] = str(result.google_review_count) if result.google_review_count else ""

                # Track source
                enriched_row["enrichment_status"] = "success"
                enriched_row["enrichment_source"] = result.source

                if result.source == "google_places_new":
                    google_count += 1
                else:
                    osm_count += 1

                print(f"  ✅ {result.source}: {result.address.street or 'No street'}")
                if result.address.full:
                    print(f"     Full: {result.address.full}")
            else:
                enriched_row["enrichment_status"] = result.status
                enriched_row["enrichment_source"] = result.source
                enriched_row["google_place_id"] = ""
                failed += 1

                if result.error:
                    print(f"  ❌ {result.source}: {result.error}")
                else:
                    print(f"  ❌ Not found")

        enriched_row["enrichment_date"] = datetime.now().isoformat()
        enriched_rows.append(enriched_row)

    # Output columns - preserve original + add enrichment fields
    original_columns = list(rows[0].keys()) if rows else []
    enrichment_columns = [
        "google_place_id",
        "google_rating",
        "google_review_count",
        "enrichment_status",
        "enrichment_source",
        "enrichment_date",
    ]

    # Merge columns, avoiding duplicates
    output_columns = original_columns.copy()
    for col in enrichment_columns:
        if col not in output_columns:
            output_columns.append(col)

    with open(output_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=output_columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(enriched_rows)

    # Summary
    print(f"\n{'='*50}")
    print("📊 Enrichment Summary")
    print(f"{'='*50}")
    print(f"Total:        {total}")
    print(f"Success:      {success} ({success/total*100:.1f}%)" if total > 0 else "Success: 0")
    print(f"  - Google:   {google_count}")
    print(f"  - OSM:      {osm_count}")
    print(f"Failed:       {failed}")
    print(f"\n📁 Output: {output_csv}")


def main():
    parser = argparse.ArgumentParser(description="Enrich masajid via Google Places (New) + OSM")
    parser.add_argument("--input", type=Path, default=INPUT_CSV, help="Input CSV path")
    parser.add_argument("--output", type=Path, default=OUTPUT_CSV, help="Output CSV path")
    parser.add_argument("--limit", type=int, help="Limit number of records to process")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making API calls")
    parser.add_argument("--osm-only", action="store_true", help="Use OSM only (free, no Google API)")

    args = parser.parse_args()

    if not args.input.exists():
        print(f"❌ Input file not found: {args.input}")
        exit(1)

    enrich_masajid(args.input, args.output, args.limit, args.dry_run, args.osm_only)


if __name__ == "__main__":
    main()
