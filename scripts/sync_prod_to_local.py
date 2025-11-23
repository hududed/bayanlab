#!/usr/bin/env python3
"""
Sync approved businesses from production Neon DB to local Neon DB
"""
import asyncio
import asyncpg
import os
from datetime import datetime

PROD_DB = "postgresql://neondb_owner:npg_EYf7wC3rGnhs@ep-steep-cloud-a5lkbj7r.us-east-2.aws.neon.tech/neondb?sslmode=require"
LOCAL_DB = os.getenv("DATABASE_URL", "postgresql://neondb_owner:npg_EYf7wC3rGnhs@ep-steep-cloud-a5lkbj7r.us-east-2.aws.neon.tech/neondb?sslmode=require")

async def sync_businesses():
    """Copy approved businesses from production to local"""

    # Connect to both databases
    prod_conn = await asyncpg.connect(PROD_DB)
    local_conn = await asyncpg.connect(LOCAL_DB)

    try:
        # Fetch approved businesses from production
        businesses = await prod_conn.fetch("""
            SELECT *
            FROM business_claim_submissions
            WHERE status = 'approved'
            ORDER BY submitted_at
        """)

        print(f"Found {len(businesses)} approved businesses in production")

        # Clear local table (careful!)
        await local_conn.execute("TRUNCATE business_claim_submissions CASCADE")
        print("Cleared local business_claim_submissions table")

        # Insert each business into local
        for biz in businesses:
            await local_conn.execute("""
                INSERT INTO business_claim_submissions (
                    claim_id, owner_name, owner_email, owner_phone,
                    business_name, business_city, business_state, business_street_address,
                    business_zip, business_industry, business_industry_other,
                    business_website, business_phone, business_whatsapp,
                    business_description, muslim_owned, latitude, longitude,
                    google_place_id, google_rating, google_review_count,
                    business_hours, photos, status, submitted_at, approved_at,
                    submitted_from
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14,
                    $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27
                )
            """,
                biz['claim_id'], biz['owner_name'], biz['owner_email'], biz['owner_phone'],
                biz['business_name'], biz['business_city'], biz['business_state'], biz['business_street_address'],
                biz['business_zip'], biz['business_industry'], biz['business_industry_other'],
                biz['business_website'], biz['business_phone'], biz['business_whatsapp'],
                biz['business_description'], biz['muslim_owned'], biz['latitude'], biz['longitude'],
                biz['google_place_id'], biz['google_rating'], biz['google_review_count'],
                biz['business_hours'], biz['photos'], biz['status'], biz['submitted_at'], biz['approved_at'],
                biz['submitted_from']
            )
            print(f"  ✓ Synced: {biz['business_name']}")

        # Verify count
        count = await local_conn.fetchval("SELECT COUNT(*) FROM business_claim_submissions WHERE status = 'approved'")
        print(f"\n✅ Sync complete! Local DB now has {count} approved businesses")

    finally:
        await prod_conn.close()
        await local_conn.close()

if __name__ == "__main__":
    asyncio.run(sync_businesses())
