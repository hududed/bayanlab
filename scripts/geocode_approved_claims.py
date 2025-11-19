#!/usr/bin/env python3
"""
Geocode approved business claims using Google Geocoding API
Adds latitude/longitude to businesses that have addresses
"""
import os
import asyncio
import httpx
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from typing import Optional, Tuple

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_GEOCODING_API_KEY") or os.getenv("GOOGLE_PLACES_API_KEY")
NEON_DB_URL = os.getenv("NEON_DB_URL")

if not GOOGLE_API_KEY:
    print("❌ GOOGLE_GEOCODING_API_KEY or GOOGLE_PLACES_API_KEY not found!")
    print("Enable Geocoding API at: https://console.cloud.google.com/apis/library/geocoding-backend.googleapis.com")
    exit(1)

if not NEON_DB_URL:
    print("❌ NEON_DB_URL not found!")
    exit(1)


async def geocode_address(address: str, api_key: str) -> Optional[Tuple[float, float]]:
    """
    Geocode an address using Google Geocoding API
    Returns (latitude, longitude) or None if not found
    """
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": address,
        "key": api_key
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, timeout=10.0)
            data = response.json()

            if data.get("status") == "OK" and len(data.get("results", [])) > 0:
                location = data["results"][0]["geometry"]["location"]
                lat = location["lat"]
                lng = location["lng"]

                # Get formatted address from Google (more accurate)
                formatted_address = data["results"][0].get("formatted_address", "")

                print(f"  ✅ Geocoded: {formatted_address}")
                print(f"     → ({lat}, {lng})")

                return (lat, lng)
            else:
                print(f"  ❌ Geocoding failed: {data.get('status')}")
                if data.get("error_message"):
                    print(f"     Error: {data['error_message']}")
                return None

        except Exception as e:
            print(f"  ❌ Exception during geocoding: {e}")
            return None


async def main():
    # Convert to sync URL
    sync_url = NEON_DB_URL.replace("+asyncpg", "")
    engine = create_engine(sync_url)

    try:
        with engine.connect() as conn:
            # Get approved claims without geocoding
            query = text("""
                SELECT
                    claim_id,
                    short_claim_id,
                    business_name,
                    business_full_address,
                    business_street_address,
                    business_city,
                    business_state,
                    business_zip
                FROM business_claim_submissions
                WHERE status = 'approved'
                ORDER BY reviewed_at DESC
            """)

            result = conn.execute(query)
            claims = result.fetchall()

            if not claims:
                print("\n⚠️  No approved claims found!")
                return

            print(f"\n🌍 Geocoding {len(claims)} approved businesses...\n")
            print("=" * 80)

            geocoded_count = 0
            failed_count = 0

            for claim in claims:
                print(f"\n📍 {claim.short_claim_id} | {claim.business_name}")
                print(f"   Address: {claim.business_full_address}")

                # Use full address for geocoding
                address = claim.business_full_address

                if not address or address.strip() == "":
                    print(f"  ⚠️  Skipping - no address provided")
                    failed_count += 1
                    continue

                # Geocode the address
                coords = await geocode_address(address, GOOGLE_API_KEY)

                if coords:
                    lat, lng = coords

                    # Update database with coordinates
                    update_query = text("""
                        UPDATE business_claim_submissions
                        SET latitude = :lat,
                            longitude = :lng
                        WHERE claim_id = :claim_id
                    """)

                    conn.execute(update_query, {
                        'lat': lat,
                        'lng': lng,
                        'claim_id': str(claim.claim_id)
                    })
                    conn.commit()

                    geocoded_count += 1
                else:
                    failed_count += 1

                # Be nice to Google API (rate limiting)
                await asyncio.sleep(0.2)  # 200ms delay between requests

            print("\n" + "=" * 80)
            print(f"\n📊 GEOCODING SUMMARY")
            print(f"  ✅ Geocoded: {geocoded_count}")
            print(f"  ❌ Failed:    {failed_count}")
            print(f"  📋 Total:     {len(claims)}")
            print("\n💡 Cost estimate: ${:.4f} (@ $5 per 1,000 requests)\n".format(geocoded_count * 0.005))

    finally:
        engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
