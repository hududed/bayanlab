#!/usr/bin/env python3
"""
Send confirmation emails to existing business claims in NEON (production database)
"""
import asyncio
import sys
from pathlib import Path
import os

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.api_service.email_service import email_service
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


async def send_retroactive_emails_neon():
    """Send confirmation emails to all pending claims in NEON database"""

    # Get NEON database URL from environment
    neon_url = os.getenv("NEON_DB_URL")
    if not neon_url:
        print("❌ NEON_DB_URL not found in environment variables!")
        return

    # Convert to sync URL (remove +asyncpg if present)
    sync_url = neon_url.replace("+asyncpg", "")

    print(f"Connecting to NEON database...")
    engine = create_engine(sync_url)

    try:
        with engine.connect() as conn:
            # Get all pending claims that haven't received confirmation emails
            query = text("""
                SELECT claim_id, short_claim_id, owner_name, owner_email, business_name
                FROM business_claim_submissions
                WHERE status = 'pending'
                  AND (confirmation_email_sent IS NULL OR confirmation_email_sent = FALSE)
                ORDER BY submitted_at DESC
            """)

            result = conn.execute(query)
            claims = result.fetchall()

            print(f"Found {len(claims)} pending claims in NEON database")
            print("-" * 80)

            for claim in claims:
                claim_id, short_claim_id, owner_name, owner_email, business_name = claim

                print(f"\nSending email to: {owner_email}")
                print(f"  Business: {business_name}")
                print(f"  Claim ID: {short_claim_id}")

                try:
                    success = await email_service.send_claim_confirmation(
                        to_email=owner_email,
                        owner_name=owner_name,
                        business_name=business_name,
                        claim_id=short_claim_id
                    )

                    if success:
                        print(f"  ✅ Email sent successfully")

                        # Mark as sent in database
                        update_query = text("""
                            UPDATE business_claim_submissions
                            SET confirmation_email_sent = TRUE,
                                confirmation_email_sent_at = NOW()
                            WHERE claim_id = :claim_id
                        """)
                        conn.execute(update_query, {'claim_id': str(claim_id)})
                        conn.commit()
                    else:
                        print(f"  ❌ Email failed to send")

                except Exception as e:
                    print(f"  ❌ Error sending email: {e}")

            print("\n" + "=" * 80)
            print(f"Finished processing {len(claims)} claims from NEON database")

    finally:
        engine.dispose()


if __name__ == "__main__":
    asyncio.run(send_retroactive_emails_neon())
