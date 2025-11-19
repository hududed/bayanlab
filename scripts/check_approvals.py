#!/usr/bin/env python3
"""
Quick script to check claim statuses
"""
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

neon_url = os.getenv("NEON_DB_URL")
if not neon_url:
    print("❌ NEON_DB_URL not found!")
    exit(1)

sync_url = neon_url.replace("+asyncpg", "")
engine = create_engine(sync_url)

try:
    with engine.connect() as conn:
        # Get status counts
        query = text("""
            SELECT status, COUNT(*) as count
            FROM business_claim_submissions
            GROUP BY status
            ORDER BY status
        """)
        result = conn.execute(query)

        print("\n📊 CLAIM STATUS SUMMARY")
        print("=" * 40)
        for row in result:
            print(f"  {row.status:12} {row.count:3} claims")
        print("=" * 40)

        # Get approved claims
        approved_query = text("""
            SELECT short_claim_id, business_name, owner_email, reviewed_at
            FROM business_claim_submissions
            WHERE status = 'approved'
            ORDER BY reviewed_at DESC NULLS LAST
        """)
        result = conn.execute(approved_query)
        approved = result.fetchall()

        if approved:
            print(f"\n✅ APPROVED CLAIMS ({len(approved)})")
            print("=" * 80)
            for claim in approved:
                reviewed = claim.reviewed_at.strftime('%Y-%m-%d %H:%M') if claim.reviewed_at else 'Not set'
                print(f"  {claim.short_claim_id} | {claim.business_name:30} | {reviewed}")
            print("=" * 80)

finally:
    engine.dispose()
