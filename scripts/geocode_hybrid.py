#!/usr/bin/env python3
"""
Hybrid geocoding: Try Google first (best accuracy), fallback to OSM (free)

This gives you:
- Best accuracy when Google works (billing enabled)
- Free fallback when Google doesn't work
- Easy migration path when you enable Google billing
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
USER_AGENT = os.getenv("GEOCODER_USER_AGENT", "BayanLab/1.0")

if not NEON_DB_URL:
    print("❌ NEON_DB_URL not found!")
    exit(1)


async def geocode_google(address: str, api_key: str) -> Optional[Tuple[float, float, str]]:
    """
    Try Google Geocoding API first (best accuracy)
    Returns (latitude, longitude, source) or None
    """
    if not api_key:
        return None

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
                formatted_address = data["results"][0].get("formatted_address", "")

                print(f"  ✅ Google: {formatted_address}")
                print(f"     → ({lat}, {lng})")

                return (lat, lng, "google")

            # Google failed, will try OSM
            return None

        except Exception:
            # Google failed, will try OSM
            return None


async def geocode_osm(address: str, user_agent: str) -> Optional[Tuple[float, float, str]]:
    """
    Fallback to OpenStreetMap Nominatim (FREE)
    Returns (latitude, longitude, source) or None
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

                print(f"  ✅ OSM: {display_name}")
                print(f"     → ({lat}, {lng})")

                return (lat, lng, "osm")

            return None

        except Exception as e:
            print(f"  ❌ OSM failed: {e}")
            return None


async def geocode_address_hybrid(address: str, google_key: Optional[str], user_agent: str) -> Optional[Tuple[float, float, str]]:
    """
    Hybrid approach: Try Google first, fallback to OSM
    Returns (latitude, longitude, source) or None
    """
    # Try Google first (best accuracy)
    if google_key:
        result = await geocode_google(address, google_key)
        if result:
            return result
        else:
            print(f"  ℹ️  Google failed (billing issue?), trying OSM...")

    # Fallback to OSM (free)
    result = await geocode_osm(address, user_agent)
    return result


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

            print(f"\n🌍 Geocoding {len(claims)} businesses (Google → OSM fallback)...\n")
            print("=" * 80)

            geocoded_count = 0
            failed_count = 0
            google_count = 0
            osm_count = 0

            for claim in claims:
                print(f"\n📍 {claim.short_claim_id} | {claim.business_name}")
                print(f"   Address: {claim.business_full_address}")

                address = claim.business_full_address

                if not address or address.strip() == "":
                    print(f"  ⚠️  Skipping - no address provided")
                    failed_count += 1
                    continue

                # Geocode with hybrid approach
                result = await geocode_address_hybrid(address, GOOGLE_API_KEY, USER_AGENT)

                if result:
                    lat, lng, source = result

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
                    if source == "google":
                        google_count += 1
                    else:
                        osm_count += 1
                else:
                    failed_count += 1

                # Rate limiting (OSM requires 1 req/sec, Google allows 50/sec)
                await asyncio.sleep(1.0)

            print("\n" + "=" * 80)
            print(f"\n📊 GEOCODING SUMMARY")
            print(f"  ✅ Total geocoded: {geocoded_count}")
            print(f"     🔵 Google:      {google_count}")
            print(f"     🟢 OSM:         {osm_count}")
            print(f"  ❌ Failed:         {failed_count}")
            print(f"  📋 Total:          {len(claims)}")

            google_cost = google_count * 0.005
            print(f"\n💰 Cost: ${google_cost:.4f} (Google) + $0.00 (OSM)")

            if google_count == 0 and GOOGLE_API_KEY:
                print("\n⚠️  Google API didn't work - likely billing not set up")
                print("   To enable Google (optional):")
                print("   1. Go to https://console.cloud.google.com/billing")
                print("   2. Add a credit card (you get $200 free credit)")
                print("   3. Re-run this script")
                print("\n   OSM works great for now! 🌍")

            print()

    finally:
        engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
