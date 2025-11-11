#!/usr/bin/env python3
"""
Enrich business owner data using Google Places API.

For each business, searches Google Places and extracts:
- Address (street, city, state, zip)
- Phone number
- Website
- Business hours
- Google Maps rating
- Coordinates (lat/long)

Usage:
    python scripts/enrich_google_places.py
    python scripts/enrich_google_places.py --input custom.csv --limit 50

Requirements:
    uv add googlemaps
    GOOGLE_PLACES_API_KEY in .env
"""

import argparse
import csv
import os
import re
import time
from pathlib import Path
from typing import Dict, Optional
import googlemaps

# Load API key from environment
API_KEY = os.getenv('GOOGLE_PLACES_API_KEY')

if not API_KEY:
    print("❌ Error: GOOGLE_PLACES_API_KEY not found in environment")
    print("Add to .env: GOOGLE_PLACES_API_KEY=your_key_here")
    exit(1)

# Initialize Google Maps client
gmaps = googlemaps.Client(key=API_KEY)


def search_place(company_name: str, industry: str = None) -> Optional[Dict]:
    """
    Search Google Places for a business and return enriched data.

    Returns:
        Dict with keys: place_id, name, address, city, state, zip, phone, website, hours, rating, lat, lng
    """

    # Build search query
    query = company_name
    if industry:
        query += f" {industry}"

    print(f"  Searching: {query}")

    try:
        # Search for place
        places_result = gmaps.places(query=query)

        if not places_result.get('results'):
            print(f"  ⚠️  No results found")
            return None

        # Get first result (most relevant)
        place = places_result['results'][0]
        place_id = place['place_id']

        # Get detailed place information
        details_result = gmaps.place(place_id=place_id, fields=[
            'formatted_address',
            'address_components',
            'formatted_phone_number',
            'website',
            'opening_hours',
            'rating',
            'geometry'
        ])

        if not details_result.get('result'):
            print(f"  ⚠️  No details found")
            return None

        details = details_result['result']

        # Parse address components
        address_components = details.get('address_components', [])
        parsed_address = parse_address_components(address_components)

        # Extract data
        enriched = {
            'place_id': place_id,
            'google_name': details.get('name', place.get('name')),
            'address': details.get('formatted_address'),
            'street': parsed_address.get('street'),
            'city': parsed_address.get('city'),
            'state': parsed_address.get('state'),
            'zip': parsed_address.get('zip'),
            'country': parsed_address.get('country'),
            'phone': details.get('formatted_phone_number'),
            'website': details.get('website'),
            'hours': format_hours(details.get('opening_hours')),
            'rating': details.get('rating'),
            'lat': details.get('geometry', {}).get('location', {}).get('lat'),
            'lng': details.get('geometry', {}).get('location', {}).get('lng'),
        }

        print(f"  ✅ Found: {enriched.get('city')}, {enriched.get('state')} | {enriched.get('phone', 'No phone')}")
        return enriched

    except googlemaps.exceptions.ApiError as e:
        print(f"  ❌ API Error: {e}")
        return None
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None


def parse_address_components(components: list) -> Dict:
    """Parse Google address_components into street, city, state, zip."""

    result = {
        'street': None,
        'city': None,
        'state': None,
        'zip': None,
        'country': None
    }

    street_number = None
    route = None

    for component in components:
        types = component.get('types', [])

        if 'street_number' in types:
            street_number = component.get('long_name')
        elif 'route' in types:
            route = component.get('long_name')
        elif 'locality' in types:
            result['city'] = component.get('long_name')
        elif 'administrative_area_level_1' in types:
            result['state'] = component.get('short_name')  # e.g., "CO" instead of "Colorado"
        elif 'postal_code' in types:
            result['zip'] = component.get('long_name')
        elif 'country' in types:
            result['country'] = component.get('short_name')  # e.g., "US"

    # Combine street number + route
    if street_number and route:
        result['street'] = f"{street_number} {route}"
    elif route:
        result['street'] = route

    return result


def format_hours(opening_hours: Optional[Dict]) -> Optional[str]:
    """Format opening hours to a readable string."""

    if not opening_hours:
        return None

    weekday_text = opening_hours.get('weekday_text', [])
    if weekday_text:
        return '; '.join(weekday_text)

    return None


def enrich_businesses(input_csv: Path, output_csv: Path, limit: Optional[int] = None):
    """
    Read business owners CSV, enrich via Google Places API, save results.
    """

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

        print(f"\n🔍 Enriching {len(rows)} businesses via Google Places API...\n")

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

            # Search Google Places
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

            # Rate limiting (Google Places free tier: no explicit limit, but be conservative)
            time.sleep(0.5)  # 2 requests per second max

            # Progress updates every 25 businesses
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

        # Filter for Colorado
        print(f"\n💡 Next steps:")
        print(f"   # Filter for Colorado businesses:")
        print(f"   grep -i 'colorado\\|, CO' {output_csv} > {output_csv.parent}/colorado_businesses.csv")
        print(f"   wc -l {output_csv.parent}/colorado_businesses.csv")
        print(f"{'='*60}\n")
    else:
        print("❌ No data to save")


def main():
    parser = argparse.ArgumentParser(description='Enrich business owners via Google Places API')
    parser.add_argument('--input', type=str, default='exports/business_filtering/high_priority_owners.csv',
                        help='Input CSV file')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit number of businesses to enrich (for testing)')
    parser.add_argument('--output', type=str, default=None,
                        help='Output CSV file')

    args = parser.parse_args()

    input_csv = Path(args.input)

    if not input_csv.exists():
        print(f"❌ Error: Input file not found: {input_csv}")
        return 1

    if args.output:
        output_csv = Path(args.output)
    else:
        output_csv = Path('exports/enrichment/google_places_enriched.csv')

    print(f"📂 Input: {input_csv}")
    print(f"📂 Output: {output_csv}")
    if args.limit:
        print(f"📊 Limit: {args.limit} businesses")

    enrich_businesses(input_csv, output_csv, args.limit)

    return 0


if __name__ == "__main__":
    exit(main())
