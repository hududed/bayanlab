#!/usr/bin/env python3
"""
Interactive CLI tool to review and approve/reject business claims
"""
import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime
import httpx
import time

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def display_claim(claim):
    """Display claim details in a formatted way"""
    print("\n" + "=" * 80)
    print(f"CLAIM ID: {claim['short_claim_id']} ({claim['claim_id']})")
    print("=" * 80)
    print(f"\n📋 BUSINESS INFORMATION")
    print(f"  Name:        {claim['business_name']}")
    print(f"  Industry:    {claim['business_industry'] or 'Not specified'}")
    print(f"  Location:    {claim['business_city']}, {claim['business_state']}")
    if claim['business_street_address']:
        print(f"  Address:     {claim['business_street_address']}")
    if claim['business_zip']:
        print(f"  ZIP:         {claim['business_zip']}")
    if claim['business_website']:
        print(f"  Website:     {claim['business_website']}")
    if claim['business_description']:
        print(f"  Services:    {claim['business_description']}")
    print(f"  Muslim-owned: {'Yes' if claim['muslim_owned'] else 'No'}")

    print(f"\n👤 OWNER INFORMATION")
    print(f"  Name:        {claim['owner_name']}")
    print(f"  Email:       {claim['owner_email']}")
    if claim['owner_phone']:
        print(f"  Phone:       {claim['owner_phone']}")

    print(f"\n📞 CONTACT INFORMATION")
    if claim['business_whatsapp']:
        print(f"  WhatsApp:    {claim['business_whatsapp']}")

    print(f"\n📅 SUBMISSION INFO")
    print(f"  Submitted:   {claim['submitted_at']}")
    print(f"  From:        {claim['submitted_from']}")
    print("=" * 80)


def get_user_decision():
    """Get user's decision on the claim"""
    while True:
        print("\n⚡ ACTIONS:")
        print("  [a] Approve and sync to ProWasl")
        print("  [r] Reject claim")
        print("  [s] Skip (review later)")
        print("  [q] Quit")

        choice = input("\nYour choice: ").lower().strip()

        if choice in ['a', 'r', 's', 'q']:
            return choice
        else:
            print("❌ Invalid choice. Please enter 'a', 'r', 's', or 'q'.")


def geocode_address(address: str) -> tuple[float, float] | None:
    """Geocode address using OSM Nominatim (free)"""
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": address,
        "format": "json",
        "limit": 1
    }
    headers = {
        "User-Agent": "BayanLab/1.0 (ProWasl Business Claims)"
    }

    try:
        response = httpx.get(url, params=params, headers=headers, timeout=30.0)
        data = response.json()

        if len(data) > 0:
            lat = float(data[0]["lat"])
            lon = float(data[0]["lon"])
            return (lat, lon)
    except Exception as e:
        print(f"  ⚠️  Geocoding error: {e}")

    return None


def approve_claim(conn, claim_id, address):
    """Approve a claim and geocode it"""
    # Geocode the address using OSM
    coords = None
    if address:
        print(f"  🌍 Geocoding: {address}")
        coords = geocode_address(address)
        if coords:
            print(f"  ✅ Geocoded: ({coords[0]:.6f}, {coords[1]:.6f})")
        else:
            print(f"  ⚠️  Geocoding failed - address may need manual correction")

    # Update database
    if coords:
        query = text("""
            UPDATE business_claim_submissions
            SET status = 'approved',
                reviewed_at = NOW(),
                latitude = :lat,
                longitude = :lng
            WHERE claim_id = :claim_id
        """)
        conn.execute(query, {
            'claim_id': str(claim_id),
            'lat': coords[0],
            'lng': coords[1]
        })
    else:
        query = text("""
            UPDATE business_claim_submissions
            SET status = 'approved',
                reviewed_at = NOW()
            WHERE claim_id = :claim_id
        """)
        conn.execute(query, {'claim_id': str(claim_id)})

    conn.commit()
    print("\n✅ Claim APPROVED! Business will sync to ProWasl.")


def reject_claim(conn, claim_id):
    """Reject a claim with optional reason"""
    reason = input("\nRejection reason (optional): ").strip()

    query = text("""
        UPDATE business_claim_submissions
        SET status = 'rejected',
            reviewed_at = NOW(),
            rejection_reason = :reason
        WHERE claim_id = :claim_id
    """)
    conn.execute(query, {
        'claim_id': str(claim_id),
        'reason': reason if reason else None
    })
    conn.commit()
    print("\n❌ Claim REJECTED.")


def main():
    """Main review loop"""
    # Get NEON database URL from environment
    neon_url = os.getenv("NEON_DB_URL")
    if not neon_url:
        print("❌ NEON_DB_URL not found in environment variables!")
        print("Make sure you have a .env file with NEON_DB_URL set.")
        return

    # Convert to sync URL (remove +asyncpg if present)
    sync_url = neon_url.replace("+asyncpg", "")

    print("🔍 BayanLab Business Claim Review Tool")
    print("=" * 80)
    print(f"Connecting to NEON database...")

    engine = create_engine(sync_url)

    try:
        with engine.connect() as conn:
            # Get all pending claims
            query = text("""
                SELECT
                    claim_id, short_claim_id, owner_name, owner_email, owner_phone,
                    business_name, business_city, business_state,
                    business_street_address, business_zip, business_industry,
                    business_website, business_whatsapp,
                    business_description, muslim_owned,
                    submitted_at, submitted_from
                FROM business_claim_submissions
                WHERE status = 'pending'
                ORDER BY submitted_at ASC
            """)

            result = conn.execute(query)
            claims = result.fetchall()

            if not claims:
                print("\n✨ No pending claims to review!")
                return

            print(f"\nFound {len(claims)} pending claims to review\n")

            approved_count = 0
            rejected_count = 0
            skipped_count = 0

            for i, claim in enumerate(claims, 1):
                # Convert to dict for easier access
                claim_dict = dict(claim._mapping)

                print(f"\n📊 Claim {i} of {len(claims)}")
                display_claim(claim_dict)

                decision = get_user_decision()

                if decision == 'a':
                    # Build full address from components
                    address_parts = [
                        claim_dict.get('business_street_address'),
                        claim_dict.get('business_city'),
                        claim_dict.get('business_state'),
                        claim_dict.get('business_zip')
                    ]
                    full_address = ', '.join(filter(None, address_parts))

                    approve_claim(conn, claim_dict['claim_id'], full_address)
                    approved_count += 1
                    time.sleep(1.0)  # Rate limit OSM API (max 1 req/sec)
                elif decision == 'r':
                    reject_claim(conn, claim_dict['claim_id'])
                    rejected_count += 1
                elif decision == 's':
                    print("\n⏭️  Skipped")
                    skipped_count += 1
                elif decision == 'q':
                    print("\n👋 Quitting review session...")
                    break

            # Summary
            print("\n" + "=" * 80)
            print("📊 REVIEW SUMMARY")
            print("=" * 80)
            print(f"  ✅ Approved: {approved_count}")
            print(f"  ❌ Rejected: {rejected_count}")
            print(f"  ⏭️  Skipped:  {skipped_count}")
            print(f"  📋 Total:    {len(claims)}")
            print("=" * 80)
            print("\n✨ Done! Approved businesses will sync to ProWasl on next sync.")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
