#!/usr/bin/env python3
"""
Geocode staging businesses that don't have coordinates.
Includes address/city cleaning for better geocoding results.

Handles common issues like:
- Compound cities: "Boston | Everett" -> "Boston"
- Parenthetical notes: "Medford (Greater Boston)" -> "Medford"
- Suite in city: "Suite A, Sacramento" -> "Sacramento"
- Typos in addresses: "la gange" -> "la grange"
- Remove suite/apt from addresses for cleaner geocoding
"""

import sys
import re
import time
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.common.database import get_sync_session
from sqlalchemy import text


# Common typos/misspellings in addresses
ADDRESS_TYPOS = {
    r'\bla gange\b': 'la grange',
    r'\blincolnway\b': 'lincoln way',
    r'\bbethany dr\b': 'bethany drive',
    r'\bcollege ave\b': 'college avenue',
}

# City name corrections (typos, old names, special cases)
CITY_CORRECTIONS = {
    'tuscaloosa': 'Tucson',  # Common typo for AZ
    'camden wyoming': 'Camden',  # Camden-Wyoming, DE is actually Camden
    'shawnee mission': 'Overland Park',  # Old name, now part of Overland Park/Lenexa
}


def clean_city(city: str) -> str:
    """Clean up messy city names."""
    if not city:
        return city

    original = city

    # Check for known city corrections first
    city_lower = city.lower().strip()
    if city_lower in CITY_CORRECTIONS:
        return CITY_CORRECTIONS[city_lower]

    # Remove parenthetical notes: "Medford (Greater Boston)" -> "Medford"
    city = re.sub(r'\s*\([^)]+\)\s*', '', city).strip()

    # Handle pipe separator: "Boston | Everett" -> "Boston"
    if '|' in city:
        city = city.split('|')[0].strip()

    # Handle slash separator: "New Bedford / Fairhaven area" -> "New Bedford"
    if '/' in city:
        city = city.split('/')[0].strip()

    # Handle ampersand: "Okemos & Canton" -> "Okemos"
    if ' & ' in city:
        city = city.split(' & ')[0].strip()

    # Remove "Suite X," prefix: "Suite A, Sacramento" -> "Sacramento"
    city = re.sub(r'^Suite\s+\w+,?\s*', '', city, flags=re.IGNORECASE).strip()

    # Remove "area" suffix
    city = re.sub(r'\s+area$', '', city, flags=re.IGNORECASE).strip()

    return city


def clean_address(address: str) -> str:
    """Clean up address for better geocoding."""
    if not address:
        return address

    # Fix common typos
    for pattern, replacement in ADDRESS_TYPOS.items():
        address = re.sub(pattern, replacement, address, flags=re.IGNORECASE)

    # Remove suite/apt/unit numbers (they confuse geocoders)
    address = re.sub(r',?\s*(Suite|Ste|Apt|Unit|#)\s*[\w-]+\s*\w*$', '', address, flags=re.IGNORECASE).strip()
    address = re.sub(r',?\s*(Suite|Ste|Apt|Unit|#)\s*[\w-]+\s*\w*,', ',', address, flags=re.IGNORECASE).strip()

    # Remove trailing commas
    address = address.rstrip(',').strip()

    return address


def geocode_address(address: str, city: str, state: str, clean: bool = True) -> tuple:
    """Geocode using OSM Nominatim. Optionally cleans inputs first."""
    if not city or not state:
        return None, None

    # Clean inputs if requested
    if clean:
        city = clean_city(city)
        address = clean_address(address)

    # Use structured query parameters for better accuracy
    params = {
        "format": "json",
        "limit": 1,
        "countrycodes": "us",
        "city": city,
        "state": state,
    }

    # Only add street if we have it
    if address and address.strip():
        params["street"] = address.strip().rstrip(',')

    try:
        url = "https://nominatim.openstreetmap.org/search"
        headers = {"User-Agent": "BayanLab/1.0"}

        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            results = response.json()
            if results:
                return float(results[0]["lat"]), float(results[0]["lon"])

        # Fallback: try just city + state if street didn't work
        if "street" in params:
            fallback_params = {
                "format": "json",
                "limit": 1,
                "countrycodes": "us",
                "city": city,
                "state": state,
            }
            response = requests.get(url, params=fallback_params, headers=headers, timeout=10)
            if response.status_code == 200:
                results = response.json()
                if results:
                    return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as e:
        print(f"  Error: {e}")

    return None, None


def geocode_batch(batch_size: int = 50, source: str = None, clean: bool = True, update_cleaned: bool = False):
    """
    Geocode a batch of businesses without coordinates.

    Args:
        batch_size: Number of records to process
        source: Filter by submitted_from field
        clean: Whether to clean address/city before geocoding
        update_cleaned: Whether to save cleaned address/city to database
    """
    with get_sync_session() as conn:
        # Get businesses needing geocoding
        query = """
            SELECT claim_id, business_name, business_street_address, business_city, business_state
            FROM business_claim_submissions
            WHERE latitude IS NULL
            AND status IN ('staging', 'approved', 'staging_duplicate')
        """
        if source:
            query += f" AND submitted_from = '{source}'"
        query += f" LIMIT {batch_size}"

        result = conn.execute(text(query))
        rows = result.fetchall()

        if not rows:
            print("No businesses need geocoding!")
            return 0

        print(f"Geocoding {len(rows)} businesses...")
        print("-" * 50)

        geocoded = 0
        for i, row in enumerate(rows, 1):
            claim_id, name, address, city, state = row

            # Clean if requested
            cleaned_city = clean_city(city) if clean else city
            cleaned_address = clean_address(address) if clean else address

            lat, lng = geocode_address(cleaned_address, cleaned_city, state, clean=False)

            if lat and lng:
                if update_cleaned and clean:
                    # Update with cleaned values AND coordinates
                    conn.execute(text("""
                        UPDATE business_claim_submissions
                        SET latitude = :lat, longitude = :lng,
                            business_city = :city, business_street_address = :address
                        WHERE claim_id = :id
                    """), {"lat": lat, "lng": lng, "city": cleaned_city, "address": cleaned_address, "id": claim_id})
                else:
                    # Just update coordinates
                    conn.execute(text("""
                        UPDATE business_claim_submissions
                        SET latitude = :lat, longitude = :lng
                        WHERE claim_id = :id
                    """), {"lat": lat, "lng": lng, "id": claim_id})
                conn.commit()
                geocoded += 1
                print(f"[{i}/{len(rows)}] ✓ {name} ({city}, {state}) -> ({lat:.4f}, {lng:.4f})")
            else:
                print(f"[{i}/{len(rows)}] ✗ {name} ({city}, {state}) - not found")

            time.sleep(1)  # Rate limit

        print("-" * 50)
        print(f"Geocoded {geocoded}/{len(rows)} businesses")

        # Show remaining
        result = conn.execute(text("""
            SELECT COUNT(*) FROM business_claim_submissions
            WHERE latitude IS NULL AND status IN ('staging', 'approved', 'staging_duplicate')
        """))
        remaining = result.scalar()
        print(f"Remaining without coordinates: {remaining}")

        return geocoded


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Geocode staging businesses")
    parser.add_argument("--batch", type=int, default=50, help="Batch size (default 50)")
    parser.add_argument("--source", type=str, help="Filter by submitted_from (e.g., mda_import)")
    parser.add_argument("--all", action="store_true", help="Keep running until all done")
    parser.add_argument("--no-clean", action="store_true", help="Skip address/city cleaning")
    parser.add_argument("--update-cleaned", action="store_true", help="Save cleaned address/city to database")

    args = parser.parse_args()

    if args.all:
        total = 0
        while True:
            count = geocode_batch(
                args.batch,
                args.source,
                clean=not args.no_clean,
                update_cleaned=args.update_cleaned
            )
            total += count
            if count == 0:
                break
            print(f"\nTotal geocoded so far: {total}\n")
        print(f"\nFinished! Total geocoded: {total}")
    else:
        geocode_batch(
            args.batch,
            args.source,
            clean=not args.no_clean,
            update_cleaned=args.update_cleaned
        )
