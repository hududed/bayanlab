#!/usr/bin/env python3
"""
Geocode approved business claims using OpenStreetMap Nominatim (FREE)
No API key needed, completely free to use
"""
import os
import asyncio
import httpx
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from typing import Optional, Tuple

load_dotenv()

NEON_DB_URL = os.getenv("NEON_DB_URL")
USER_AGENT = os.getenv("GEOCODER_USER_AGENT", "BayanLab/1.0")

if not NEON_DB_URL:
    print("❌ NEON_DB_URL not found!")
    exit(1)


async def geocode_address_osm(address: str, user_agent: str) -> Optional[Tuple[float, float]]:
    """
    Geocode an address using OpenStreetMap Nominatim (FREE)
    Returns (latitude, longitude) or None if not found
    """
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": address,
        "format": "json",
        "limit": 1
    }
    headers = {
        "User-Agent": user_agent
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, headers=headers, timeout=10.0)
            data = response.json()

            if len(data) > 0:
                result = data[0]
                lat = float(result["lat"])
                lng = float(result["lon"])
                display_name = result.get("display_name", "")

                print(f"  ✅ Geocoded: {display_name}")
                print(f"     → ({lat}, {lng})")

                return (lat, lng)
            else:
                print(f"  ❌ No results found")
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
                    latitude,
                    longitude
                FROM business_claim_submissions
                WHERE status = 'approved'
                  AND (latitude IS NULL OR longitude IS NULL)
                ORDER BY reviewed_at DESC
            """)

            result = conn.execute(query)
            claims = result.fetchall()

            if not claims:
                print("\n✨ All approved claims already have geocoding!")
                return

            print(f"\n🌍 Geocoding {len(claims)} businesses using OpenStreetMap (FREE)...\n")
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
                coords = await geocode_address_osm(address, USER_AGENT)

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

                # Be nice to OSM (required: 1 request per second max)
                await asyncio.sleep(1.0)

            print("\n" + "=" * 80)
            print(f"\n📊 GEOCODING SUMMARY")
            print(f"  ✅ Geocoded: {geocoded_count}")
            print(f"  ❌ Failed:    {failed_count}")
            print(f"  📋 Total:     {len(claims)}")
            print("\n💰 Cost: $0.00 (OpenStreetMap is FREE!)")
            print("\n📝 Note: OSM Nominatim accuracy is typically within 10-50 meters of Google\n")

    finally:
        engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
