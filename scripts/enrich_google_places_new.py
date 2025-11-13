#!/usr/bin/env python3
"""
Enrich business owner data using Google Places API (New).

Usage:
    python scripts/enrich_google_places_new.py --limit 5
    python scripts/enrich_google_places_new.py  # Full run

Requirements:
    uv add requests python-dotenv
    GOOGLE_PLACES_API_KEY in .env
"""

import argparse
import csv
import json
import os
import time
from pathlib import Path
from typing import Dict, Optional
import requests
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Load API key from environment
API_KEY = os.getenv('GOOGLE_PLACES_API_KEY')

if not API_KEY:
    print("❌ Error: GOOGLE_PLACES_API_KEY not found in environment")
    print("Add to .env: GOOGLE_PLACES_API_KEY=your_key_here")
    exit(1)

# New Places API endpoint
PLACES_API_BASE = "https://places.googleapis.com/v1"


def search_place(company_name: str, industry: str = None) -> Optional[Dict]:
    """Search Google Places (New API) for a business."""

    query = company_name
    if industry:
        query += f" {industry}"

    print(f"  Searching: {query}")

    try:
        search_url = f"{PLACES_API_BASE}/places:searchText"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": API_KEY,
            "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.addressComponents,places.internationalPhoneNumber,places.websiteUri,places.rating,places.location,places.regularOpeningHours"
        }

        payload = {"textQuery": query}

        response = requests.post(search_url, headers=headers, json=payload)

        if response.status_code != 200:
            print(f"  ❌ API Error: {response.status_code} - {response.text[:200]}")
            return None

        result = response.json()

        if not result.get('places'):
            print(f"  ⚠️  No results found")
            return None

        place = result['places'][0]

        # Parse address
        parsed = parse_address(place.get('addressComponents', []))

        # Format hours
        hours = None
        if place.get('regularOpeningHours'):
            hours_list = place['regularOpeningHours'].get('weekdayDescriptions', [])
            if hours_list:
                hours = '; '.join(hours_list)

        enriched = {
            'place_id': place.get('id'),
            'google_name': place.get('displayName', {}).get('text'),
            'address': place.get('formattedAddress'),
            'street': parsed.get('street'),
            'city': parsed.get('city'),
            'state': parsed.get('state'),
            'zip': parsed.get('zip'),
            'country': parsed.get('country'),
            'phone': place.get('internationalPhoneNumber'),
            'website': place.get('websiteUri'),
            'hours': hours,
            'rating': place.get('rating'),
            'lat': place.get('location', {}).get('latitude'),
            'lng': place.get('location', {}).get('longitude'),
        }

        print(f"  ✅ Found: {enriched.get('city')}, {enriched.get('state')} | {enriched.get('phone', 'No phone')}")
        return enriched

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None


def parse_address(components: list) -> Dict:
    """Parse address components from New API format."""

    result = {'street': None, 'city': None, 'state': None, 'zip': None, 'country': None}
    street_number = None
    route = None

    for component in components:
        types = component.get('types', [])
        long_text = component.get('longText', '')
        short_text = component.get('shortText', '')

        if 'street_number' in types:
            street_number = long_text
        elif 'route' in types:
            route = long_text
        elif 'locality' in types:
            result['city'] = long_text
        elif 'administrative_area_level_1' in types:
            result['state'] = short_text
        elif 'postal_code' in types:
            result['zip'] = long_text
        elif 'country' in types:
            result['country'] = short_text

    if street_number and route:
        result['street'] = f"{street_number} {route}"
    elif route:
        result['street'] = route

    return result


def enrich_businesses(input_csv: Path, output_csv: Path, limit: Optional[int] = None):
    """Read business CSV, enrich via Google Places, save results."""

    enriched = []
    total = 0
    success = 0
    skipped = 0
    failed = 0

    with open(input_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

        if limit:
            rows = rows[:limit]

        print(f"\n🔍 Enriching {len(rows)} businesses via Google Places API (New)...\n")

        for idx, row in enumerate(rows, start=1):
            total += 1
            company = row.get('Company Name', '').strip()
            industry = row.get('Industry ', '').strip()
            name = row.get('Name', '').strip()

            print(f"[{idx}/{len(rows)}] {name} - {company}")

            if not company or company.lower() in ['n/a', 'student', 'unemployed', 'freelance']:
                print("  ⏭️  Skipping (no valid company)")
                enriched.append({**row, 'enrichment_status': 'skipped', 'skip_reason': 'no_company'})
                skipped += 1
                continue

            place_data = search_place(company, industry)

            if place_data:
                success += 1
                enriched.append({
                    **row,
                    'enriched_place_id': place_data.get('place_id'),
                    'enriched_google_name': place_data.get('google_name'),
                    'enriched_address': place_data.get('address'),
                    'enriched_street': place_data.get('street'),
                    'enriched_city': place_data.get('city'),
                    'enriched_state': place_data.get('state'),
                    'enriched_zip': place_data.get('zip'),
                    'enriched_country': place_data.get('country'),
                    'enriched_phone': place_data.get('phone'),
                    'enriched_website': place_data.get('website'),
                    'enriched_hours': place_data.get('hours'),
                    'enriched_rating': place_data.get('rating'),
                    'enriched_lat': place_data.get('lat'),
                    'enriched_lng': place_data.get('lng'),
                    'enrichment_status': 'success'
                })
            else:
                failed += 1
                enriched.append({**row, 'enrichment_status': 'failed'})

            time.sleep(0.5)

            if idx % 25 == 0:
                print(f"\n  📊 Progress: {success}/{total} successful ({success/total*100:.1f}%)\n")

    # Save results
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    if enriched:
        fieldnames = list(enriched[0].keys())

        with open(output_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(enriched)

        print(f"\n{'='*60}")
        print(f"✅ Enrichment complete!")
        print(f"{'='*60}")
        print(f"Total processed: {total}")
        print(f"Successfully enriched: {success} ({success/total*100:.1f}%)")
        print(f"Skipped: {skipped}")
        print(f"Failed: {failed}")
        print(f"\nOutput: {output_csv}")
        print(f"\n💡 Next steps:")
        print(f"   grep -i 'colorado\\|, CO' {output_csv} > {output_csv.parent}/colorado_businesses.csv")
        print(f"   wc -l {output_csv.parent}/colorado_businesses.csv")
        print(f"{'='*60}\n")
    else:
        print("❌ No data to save")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=str, default='exports/business_filtering/high_priority_owners.csv')
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--output', type=str, default=None)

    args = parser.parse_args()

    input_csv = Path(args.input)

    if not input_csv.exists():
        print(f"❌ Error: Input file not found: {input_csv}")
        return 1

    output_csv = Path(args.output) if args.output else Path('exports/enrichment/google_places_enriched.csv')

    print(f"📂 Input: {input_csv}")
    print(f"📂 Output: {output_csv}")
    if args.limit:
        print(f"📊 Limit: {args.limit} businesses")

    enrich_businesses(input_csv, output_csv, args.limit)

    return 0


if __name__ == "__main__":
    exit(main())
