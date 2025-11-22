#!/usr/bin/env python3
"""
Enrich halal eateries data using Google Places API (New) with OSM fallback.

For each eatery, searches and extracts:
- Address (street, city, state, zip)
- Phone number (Google only)
- Website (Google only)
- Google Maps rating (Google only)
- Coordinates (lat/lng)

Enrichment Strategy:
1. Try Google Places API (New) first - full data
2. Fallback to OSM Nominatim - geocoding only (free, no API key)

Input: exports/halal_eateries/colorado_halal_eateries_raw.csv
Output: exports/halal_eateries/colorado_halal_eateries_enriched.csv

Usage:
    uv run python scripts/enrich_halal_eateries.py
    uv run python scripts/enrich_halal_eateries.py --limit 10
    uv run python scripts/enrich_halal_eateries.py --osm-only   # Skip Google, use OSM only
    uv run python scripts/enrich_halal_eateries.py --dry-run

Requirements:
    GOOGLE_PLACES_API_KEY in .env (optional if using --osm-only)
"""

import argparse
import csv
import os
import time
import httpx
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Paths
INPUT_CSV = Path("exports/halal_eateries/colorado_halal_eateries_raw.csv")
OUTPUT_CSV = Path("exports/halal_eateries/colorado_halal_eateries_enriched.csv")

# API keys
GOOGLE_API_KEY = os.getenv('GOOGLE_PLACES_API_KEY')

# Google Places API (New) endpoints
GOOGLE_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
GOOGLE_PLACE_DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"

# OSM Nominatim endpoint
OSM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"


def search_google_places_new(name: str, city: str, state: str = "CO") -> Optional[Dict]:
    """
    Search using Google Places API (New).
    https://developers.google.com/maps/documentation/places/web-service/text-search
    """
    if not GOOGLE_API_KEY:
        return None

    query = f"{name} {city} {state}"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.addressComponents,places.location,places.nationalPhoneNumber,places.websiteUri,places.rating"
    }

    payload = {
        "textQuery": query,
        "maxResultCount": 1,
        "locationBias": {
            "rectangle": {
                "low": {"latitude": 36.9, "longitude": -109.1},   # SW Colorado
                "high": {"latitude": 41.1, "longitude": -102.0}   # NE Colorado
            }
        }
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(GOOGLE_TEXT_SEARCH_URL, headers=headers, json=payload)

            if response.status_code != 200:
                print(f"  ⚠️  Google API error: {response.status_code} - {response.text[:100]}")
                return None

            data = response.json()

            if not data.get('places'):
                return None

            place = data['places'][0]

            # Parse address components
            address_parts = parse_google_address_components(place.get('addressComponents', []))

            location = place.get('location', {})

            return {
                'google_place_id': place.get('id'),
                'google_name': place.get('displayName', {}).get('text'),
                'address_full': place.get('formattedAddress'),
                'address_street': address_parts.get('street'),
                'address_city': address_parts.get('city'),
                'address_state': address_parts.get('state'),
                'address_zip': address_parts.get('zip'),
                'phone': place.get('nationalPhoneNumber'),
                'website': place.get('websiteUri'),
                'google_rating': place.get('rating'),
                'latitude': location.get('latitude'),
                'longitude': location.get('longitude'),
                'enrichment_status': 'success',
                'enrichment_source': 'google_places_new'
            }

    except Exception as e:
        print(f"  ❌ Google error: {e}")
        return None


def parse_google_address_components(components: list) -> Dict:
    """Parse Google address_components (new API format)."""
    result = {'street': None, 'city': None, 'state': None, 'zip': None}

    street_number = None
    route = None

    for comp in components:
        types = comp.get('types', [])
        text = comp.get('longText', '')
        short_text = comp.get('shortText', '')

        if 'street_number' in types:
            street_number = text
        elif 'route' in types:
            route = text
        elif 'locality' in types:
            result['city'] = text
        elif 'administrative_area_level_1' in types:
            result['state'] = short_text  # CO not Colorado
        elif 'postal_code' in types:
            result['zip'] = text

    if street_number and route:
        result['street'] = f"{street_number} {route}"
    elif route:
        result['street'] = route

    return result


def search_osm(name: str, city: str, state: str = "CO") -> Optional[Dict]:
    """
    Search using OpenStreetMap Nominatim (free, no API key).
    Returns geocoding data only (lat/lng, address).
    """
    query = f"{name}, {city}, {state}, USA"

    params = {
        "q": query,
        "format": "json",
        "limit": 1,
        "addressdetails": 1
    }

    headers = {
        "User-Agent": "BayanLab/1.0 (halal-eateries-enrichment)"
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(OSM_SEARCH_URL, params=params, headers=headers)

            if response.status_code != 200:
                return None

            data = response.json()

            if not data:
                return None

            result = data[0]
            address = result.get('address', {})

            # Build street address
            house_number = address.get('house_number', '')
            road = address.get('road', '')
            street = f"{house_number} {road}".strip() if house_number or road else None

            return {
                'google_place_id': None,
                'google_name': result.get('display_name', '').split(',')[0],
                'address_full': result.get('display_name'),
                'address_street': street,
                'address_city': address.get('city') or address.get('town') or address.get('village'),
                'address_state': address.get('state'),
                'address_zip': address.get('postcode'),
                'phone': None,  # OSM doesn't have phone
                'website': None,  # OSM doesn't have website
                'google_rating': None,
                'latitude': float(result.get('lat')),
                'longitude': float(result.get('lon')),
                'enrichment_status': 'success',
                'enrichment_source': 'osm'
            }

    except Exception as e:
        print(f"  ❌ OSM error: {e}")
        return None


def search_eatery(name: str, city: str, state: str = "CO", osm_only: bool = False) -> Optional[Dict]:
    """
    Search for eatery using Google Places (New) with OSM fallback.
    """

    # Try Google first (unless osm_only)
    if not osm_only and GOOGLE_API_KEY:
        print(f"  🔍 Trying Google Places (New)...")
        result = search_google_places_new(name, city, state)
        if result:
            return result
        print(f"  ⚠️  Google: No results, trying OSM...")

    # Fallback to OSM
    print(f"  🗺️  Trying OSM...")
    result = search_osm(name, city, state)
    if result:
        return result

    return None


def enrich_eateries(input_csv: Path, output_csv: Path, limit: Optional[int] = None,
                   dry_run: bool = False, osm_only: bool = False):
    """
    Read halal eateries CSV, enrich via Google Places (New) + OSM, save results.
    """

    if dry_run:
        print("🔍 DRY RUN - No API calls will be made\n")

    if osm_only:
        print("🗺️  OSM ONLY mode - Using OpenStreetMap (free, geocoding only)\n")
    elif not GOOGLE_API_KEY:
        print("⚠️  No GOOGLE_PLACES_API_KEY found, falling back to OSM only\n")
        osm_only = True

    enriched_rows = []
    total = 0
    success = 0
    failed = 0
    google_count = 0
    osm_count = 0

    with open(input_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

        if limit:
            rows = rows[:limit]

        print(f"🍽️  Enriching {len(rows)} halal eateries...\n")

        for idx, row in enumerate(rows, start=1):
            total += 1
            name = row.get('name', '').strip()
            city = row.get('city', '').strip()
            state = row.get('state', 'CO').strip()

            if not name:
                print(f"[{idx}/{len(rows)}] ⏭️  Skipping: No name")
                failed += 1
                continue

            print(f"[{idx}/{len(rows)}] {name} ({city}, {state})")

            if dry_run:
                enriched_row = row.copy()
                enriched_row['enrichment_status'] = 'dry_run'
            else:
                enriched_data = search_eatery(name, city, state, osm_only)

                enriched_row = row.copy()
                if enriched_data:
                    enriched_row.update(enriched_data)
                    if enriched_data.get('enrichment_status') == 'success':
                        success += 1
                        if enriched_data.get('enrichment_source') == 'google_places_new':
                            google_count += 1
                        else:
                            osm_count += 1
                        print(f"  ✅ {enriched_data.get('enrichment_source')}: {enriched_data.get('address_street', 'No street')}")
                    else:
                        failed += 1
                else:
                    enriched_row['enrichment_status'] = 'not_found'
                    failed += 1
                    print(f"  ❌ Not found")

                # Rate limiting: OSM requires 1 req/sec
                time.sleep(1.1 if osm_only or enriched_data and enriched_data.get('enrichment_source') == 'osm' else 0.2)

            enriched_row['enrichment_date'] = datetime.now().isoformat()
            enriched_rows.append(enriched_row)

    # Output columns
    output_columns = [
        # Original fields
        'name', 'cuisine_style', 'hours_raw', 'city', 'state', 'tags',
        'source', 'source_ref', 'halal_status', 'needs_enrichment',
        # Enriched fields
        'google_place_id', 'google_name', 'address_full', 'address_street',
        'address_city', 'address_state', 'address_zip',
        'phone', 'website', 'google_rating', 'latitude', 'longitude',
        'enrichment_status', 'enrichment_source', 'enrichment_error', 'enrichment_date'
    ]

    with open(output_csv, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=output_columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(enriched_rows)

    # Summary
    print(f"\n{'='*50}")
    print(f"📊 Enrichment Summary")
    print(f"{'='*50}")
    print(f"Total:        {total}")
    print(f"Success:      {success} ({success/total*100:.1f}%)" if total > 0 else "Success: 0")
    print(f"  - Google:   {google_count}")
    print(f"  - OSM:      {osm_count}")
    print(f"Failed:       {failed}")
    print(f"\n📁 Output: {output_csv}")


def main():
    parser = argparse.ArgumentParser(description='Enrich halal eateries via Google Places (New) + OSM')
    parser.add_argument('--input', type=Path, default=INPUT_CSV, help='Input CSV path')
    parser.add_argument('--output', type=Path, default=OUTPUT_CSV, help='Output CSV path')
    parser.add_argument('--limit', type=int, help='Limit number of records to process')
    parser.add_argument('--dry-run', action='store_true', help='Preview without making API calls')
    parser.add_argument('--osm-only', action='store_true', help='Use OSM only (free, no Google API)')

    args = parser.parse_args()

    if not args.input.exists():
        print(f"❌ Input file not found: {args.input}")
        exit(1)

    enrich_eateries(args.input, args.output, args.limit, args.dry_run, args.osm_only)


if __name__ == "__main__":
    main()
