#!/usr/bin/env python3
"""
Enrich halal_markets table using Google Places API (New).

Usage:
    uv run python scripts/enrich_halal_markets.py
"""

import os
import time
from typing import Dict, Optional
import requests
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

load_dotenv()

API_KEY = os.getenv('GOOGLE_PLACES_API_KEY')
DATABASE_URL = os.getenv('DATABASE_URL_SYNC', os.getenv('DATABASE_URL'))

if not API_KEY:
    print("Error: GOOGLE_PLACES_API_KEY not found")
    exit(1)

PLACES_API_BASE = "https://places.googleapis.com/v1"


def search_place(name: str, city: str, state: str) -> Optional[Dict]:
    """Search Google Places for a market."""
    query = f"{name} {city} {state}"
    print(f"  Searching: {query}")

    try:
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": API_KEY,
            "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.addressComponents,places.internationalPhoneNumber,places.websiteUri,places.rating,places.userRatingCount,places.location,places.regularOpeningHours"
        }
        response = requests.post(
            f"{PLACES_API_BASE}/places:searchText",
            headers=headers,
            json={"textQuery": query}
        )

        if response.status_code != 200:
            print(f"  API Error: {response.status_code}")
            return None

        result = response.json()
        if not result.get('places'):
            print(f"  No results")
            return None

        place = result['places'][0]
        parsed = parse_address(place.get('addressComponents', []))

        hours = None
        if place.get('regularOpeningHours'):
            hours_list = place['regularOpeningHours'].get('weekdayDescriptions', [])
            if hours_list:
                hours = '; '.join(hours_list)

        enriched = {
            'place_id': place.get('id'),
            'street': parsed.get('street'),
            'city': parsed.get('city'),
            'state': parsed.get('state'),
            'zip': parsed.get('zip'),
            'phone': place.get('internationalPhoneNumber'),
            'website': place.get('websiteUri'),
            'hours': hours,
            'rating': place.get('rating'),
            'review_count': place.get('userRatingCount'),
            'lat': place.get('location', {}).get('latitude'),
            'lng': place.get('location', {}).get('longitude'),
        }
        print(f"  Found: {parsed.get('city')}, {parsed.get('state')} | Rating: {enriched.get('rating')}")
        return enriched

    except Exception as e:
        print(f"  Error: {e}")
        return None


def parse_address(components: list) -> Dict:
    result = {'street': None, 'city': None, 'state': None, 'zip': None}
    street_number = None
    route = None

    for comp in components:
        types = comp.get('types', [])
        long_text = comp.get('longText', '')
        short_text = comp.get('shortText', '')

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

    if street_number and route:
        result['street'] = f"{street_number} {route}"
    elif route:
        result['street'] = route

    return result


def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Get markets without google_place_id
    cur.execute("""
        SELECT market_id, name, address_city, address_state
        FROM halal_markets
        WHERE google_place_id IS NULL
        ORDER BY name
    """)
    markets = cur.fetchall()

    print(f"\nEnriching {len(markets)} halal markets...\n")

    success = 0
    for idx, market in enumerate(markets, 1):
        print(f"[{idx}/{len(markets)}] {market['name']}")

        data = search_place(market['name'], market['address_city'], market['address_state'])

        if data:
            cur.execute("""
                UPDATE halal_markets SET
                    address_street = COALESCE(%s, address_street),
                    address_city = COALESCE(%s, address_city),
                    address_state = COALESCE(%s, address_state),
                    address_zip = COALESCE(%s, address_zip),
                    latitude = %s,
                    longitude = %s,
                    phone = %s,
                    website = %s,
                    hours_raw = %s,
                    google_rating = %s,
                    google_review_count = %s,
                    google_place_id = %s,
                    updated_at = NOW()
                WHERE market_id = %s
            """, (
                data.get('street'),
                data.get('city'),
                data.get('state'),
                data.get('zip'),
                data.get('lat'),
                data.get('lng'),
                data.get('phone'),
                data.get('website'),
                data.get('hours'),
                data.get('rating'),
                data.get('review_count'),
                data.get('place_id'),
                market['market_id']
            ))
            conn.commit()
            success += 1

        time.sleep(0.3)

    cur.close()
    conn.close()

    print(f"\nDone! Enriched {success}/{len(markets)} markets")


if __name__ == "__main__":
    main()
