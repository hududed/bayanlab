#!/usr/bin/env python3
"""
Export approved claims for ProWasl ingestion
"""
import os
import json
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

neon_url = os.getenv("NEON_DB_URL")
if not neon_url:
    print("❌ NEON_DB_URL not found!")
    exit(1)

# Convert to sync URL
sync_url = neon_url.replace("+asyncpg", "")
engine = create_engine(sync_url)

try:
    with engine.connect() as conn:
        # Get all approved claims
        query = text("""
            SELECT
                claim_id::text as business_id,
                short_claim_id,
                business_name,
                business_industry,
                business_description,
                business_website,
                business_city,
                business_state,
                business_street_address,
                business_zip,
                business_full_address,
                business_phone,
                business_whatsapp,
                owner_name,
                owner_email,
                owner_phone,
                muslim_owned,
                status,
                submitted_at,
                reviewed_at,
                latitude,
                longitude
            FROM business_claim_submissions
            WHERE status = 'approved'
            ORDER BY reviewed_at DESC
        """)

        result = conn.execute(query)
        claims = result.fetchall()

        if not claims:
            print("\\n⚠️  No approved claims found!")
            exit(0)

        print(f"\\n✅ Found {len(claims)} approved claims\\n")
        print("=" * 100)

        # Convert to list of dicts for ProWasl
        businesses = []
        for claim in claims:
            business = {
                "business_id": claim.business_id,
                "short_claim_id": claim.short_claim_id,
                "business_name": claim.business_name,
                "business_industry": claim.business_industry,
                "business_description": claim.business_description,
                "business_website": claim.business_website,
                "business_city": claim.business_city,
                "business_state": claim.business_state,
                "business_street_address": claim.business_street_address,
                "business_zip": claim.business_zip,
                "business_full_address": claim.business_full_address,
                "business_phone": claim.business_phone,
                "business_whatsapp": claim.business_whatsapp,
                "owner_name": claim.owner_name,
                "owner_email": claim.owner_email,
                "owner_phone": claim.owner_phone,
                "muslim_owned": claim.muslim_owned,
                "status": claim.status,
                "submitted_at": claim.submitted_at.isoformat() if claim.submitted_at else None,
                "reviewed_at": claim.reviewed_at.isoformat() if claim.reviewed_at else None,

                # Geocoding (from Google Geocoding API)
                "latitude": float(claim.latitude) if claim.latitude else None,
                "longitude": float(claim.longitude) if claim.longitude else None,
                "google_place_id": None,
                "google_rating": None,
                "google_review_count": None,
                "business_hours": None,
                "photos": []
            }
            businesses.append(business)

            # Print summary
            print(f"  {claim.short_claim_id:10} | {claim.business_name:40} | {claim.business_city:20} | {claim.business_state}")

        print("=" * 100)

        # Export to JSON file
        output_file = "exports/prowasl_approved_businesses.json"
        os.makedirs("exports", exist_ok=True)

        with open(output_file, 'w') as f:
            json.dump({
                "businesses": businesses,
                "exported_at": datetime.now().isoformat(),
                "total": len(businesses)
            }, f, indent=2)

        print(f"\\n✅ Exported {len(businesses)} businesses to: {output_file}")
        print(f"\\n📋 Next steps:")
        print(f"   1. Review the JSON file: cat {output_file}")
        print(f"   2. Send to ProWasl team or POST to their API")
        print(f"   3. Update this script to auto-sync to ProWasl endpoint\\n")

finally:
    engine.dispose()
