#!/usr/bin/env python3
"""
Migrate Islamic Centers / Mosques from business_claim_submissions to masajid table.

Identifies Religious Services entries and mosque-like businesses and moves them
to the proper masajid table.
"""

import os
import sys
from pathlib import Path
from contextlib import contextmanager

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


@contextmanager
def get_db_session(use_prod: bool = False):
    """Get database session, optionally targeting prod Neon."""
    if use_prod:
        # Use Neon prod database
        db_url = os.getenv("NEON_DB_URL") or "postgresql://neondb_owner:npg_EYf7wC3rGnhs@ep-orange-frost-ae2ocdvr-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require"
    else:
        # Use local database
        db_url = os.getenv("DATABASE_URL_SYNC", "postgresql://bayan:bayan@localhost:5433/bayan_backbone")

    engine = create_engine(db_url, echo=False, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_mosque_entries(conn):
    """Get all mosque/Islamic center entries from business_claim_submissions."""
    result = conn.execute(text("""
        SELECT
            claim_id,
            business_name,
            business_street_address,
            business_city,
            business_state,
            business_zip,
            latitude,
            longitude,
            business_phone,
            owner_email,
            submitted_from,
            status
        FROM business_claim_submissions
        WHERE business_industry = 'Religious Services'
           OR LOWER(business_name) LIKE '%islamic center%'
           OR LOWER(business_name) LIKE '%masjid%'
           OR LOWER(business_name) LIKE '%mosque%'
           OR LOWER(business_name) LIKE '%muslim center%'
           OR LOWER(business_name) LIKE '%islamic society%'
           OR LOWER(business_name) LIKE '%islamic association%'
           OR LOWER(business_name) LIKE '%islamic foundation%'
           OR LOWER(business_name) LIKE '%darul%'
        ORDER BY business_state, business_city, business_name
    """))
    return result.fetchall()


def check_duplicate(conn, name: str, city: str) -> bool:
    """Check if masjid already exists in masajid table."""
    result = conn.execute(text("""
        SELECT masjid_id FROM masajid
        WHERE LOWER(name) = LOWER(:name)
        AND LOWER(address_city) = LOWER(:city)
    """), {"name": name, "city": city})
    return result.fetchone() is not None


def migrate_to_masajid(dry_run: bool = True, delete_after: bool = False, use_prod: bool = False):
    """
    Migrate mosque entries from business_claim_submissions to masajid.

    Args:
        dry_run: If True, don't actually insert/delete (default)
        delete_after: If True, delete from business_claim_submissions after migration
        use_prod: If True, use Neon prod database
    """
    db_target = "NEON PROD" if use_prod else "LOCAL"
    print(f"Target database: {db_target}")
    print("=" * 60)

    with get_db_session(use_prod=use_prod) as conn:
        entries = get_mosque_entries(conn)

        print(f"Found {len(entries)} mosque/Islamic center entries to migrate")
        print("-" * 60)

        migrated = 0
        skipped_duplicate = 0
        skipped_no_coords = 0
        errors = 0

        for row in entries:
            claim_id, name, address, city, state, zip_code, lat, lng, phone, email, source, status = row

            # Skip if no coordinates (masajid table needs them for map display)
            if not lat or not lng:
                print(f"  ⚠ Skipping (no coords): {name} ({city}, {state})")
                skipped_no_coords += 1
                continue

            # Check for duplicates
            if check_duplicate(conn, name, city):
                print(f"  ⚠ Duplicate in masajid: {name} ({city}, {state})")
                skipped_duplicate += 1
                continue

            # Clean email - don't use placeholder
            clean_email = email if email and email != 'import@bayanlab.com' else None

            if dry_run:
                print(f"  Would migrate: {name} ({city}, {state})")
                migrated += 1
                continue

            try:
                # Insert into masajid
                conn.execute(text("""
                    INSERT INTO masajid (
                        name,
                        address_street,
                        address_city,
                        address_state,
                        address_zip,
                        latitude,
                        longitude,
                        phone,
                        email,
                        region,
                        source,
                        verification_status
                    ) VALUES (
                        :name,
                        :address,
                        :city,
                        :state,
                        :zip,
                        :lat,
                        :lng,
                        :phone,
                        :email,
                        :region,
                        :source,
                        'unverified'
                    )
                """), {
                    "name": name,
                    "address": address,
                    "city": city,
                    "state": state,
                    "zip": zip_code,
                    "lat": lat,
                    "lng": lng,
                    "phone": phone,
                    "email": clean_email,
                    "region": state,  # Use state as region
                    "source": f"migrated_from_{source}",
                })

                # Optionally delete from business_claim_submissions
                if delete_after:
                    conn.execute(text("""
                        DELETE FROM business_claim_submissions WHERE claim_id = :id
                    """), {"id": claim_id})

                conn.commit()
                migrated += 1
                print(f"  ✓ Migrated: {name} ({city}, {state})")

            except Exception as e:
                conn.rollback()
                print(f"  ✗ Error: {name} - {str(e)[:80]}")
                errors += 1

        print("\n" + "=" * 60)
        print("Migration Summary")
        print("=" * 60)
        print(f"  Total found: {len(entries)}")
        print(f"  Migrated: {migrated}")
        print(f"  Skipped (duplicate): {skipped_duplicate}")
        print(f"  Skipped (no coords): {skipped_no_coords}")
        print(f"  Errors: {errors}")

        if dry_run:
            print("\n[DRY RUN] No changes were made. Run with --migrate to execute.")
        elif delete_after:
            print("\n[DELETED] Entries were removed from business_claim_submissions")
        else:
            print("\n[KEPT] Entries still exist in business_claim_submissions")
            print("       Run with --delete to remove after migration")

        # Show final counts
        result = conn.execute(text("SELECT COUNT(*) FROM masajid"))
        masajid_count = result.scalar()

        result = conn.execute(text("""
            SELECT COUNT(*) FROM business_claim_submissions
            WHERE business_industry = 'Religious Services'
        """))
        remaining = result.scalar()

        print(f"\nCurrent masajid table count: {masajid_count}")
        print(f"Remaining Religious Services in claims: {remaining}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Migrate mosques to masajid table")
    parser.add_argument("--migrate", action="store_true", help="Actually perform migration (default is dry run)")
    parser.add_argument("--delete", action="store_true", help="Delete from business_claim_submissions after migration")
    parser.add_argument("--prod", action="store_true", help="Target Neon prod database (default is local)")

    args = parser.parse_args()

    migrate_to_masajid(dry_run=not args.migrate, delete_after=args.delete, use_prod=args.prod)
