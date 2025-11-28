#!/usr/bin/env python3
"""
Migrate halal food businesses from business_claim_submissions to specialized tables.

Handles:
- Halal eateries -> halal_eateries table
- Halal markets -> halal_markets table
- Hybrids (market+grill combos) -> BOTH tables
- Food pantries -> nonprofits table
"""

import os
import sys
import re
from pathlib import Path
from contextlib import contextmanager

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


@contextmanager
def get_db_session(use_prod: bool = False):
    """Get database session, optionally targeting prod Neon."""
    if use_prod:
        db_url = os.getenv("NEON_DB_URL") or "postgresql://neondb_owner:npg_EYf7wC3rGnhs@ep-orange-frost-ae2ocdvr-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require"
    else:
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


# Keywords for classification
MARKET_KEYWORDS = [
    'market', 'mart', 'grocery', 'supermarket', 'food store', 'foodmart',
    'meat shop', 'butcher', 'halal meat', 'deli', 'food land'
]

EATERY_KEYWORDS = [
    'restaurant', 'grill', 'cafe', 'kitchen', 'diner', 'bistro', 'eatery',
    'pizza', 'kabob', 'kebab', 'shawarma', 'falafel', 'gyro', 'biryani',
    'curry', 'tandoor', 'tikka', 'naan', 'thai', 'chinese', 'mediterranean',
    'indian', 'pakistani', 'afghan', 'turkish', 'lebanese', 'halal guys',
    'food truck', 'taco', 'burger', 'wing', 'chicken', 'seafood', 'bbq',
    'bakery', 'sweets', 'dessert', 'ice cream', 'smoothie', 'juice',
    'hookah', 'lounge', 'coffee', 'tea house', 'breakfast', 'brunch'
]

PANTRY_KEYWORDS = ['food pantry', 'food bank', 'food assistance', 'free food']


def classify_food_business(name: str, industry: str) -> list:
    """
    Classify a food business. Returns list of categories.
    Can return multiple categories for hybrids.
    """
    name_lower = name.lower()
    categories = []

    # Check for food pantry first
    for kw in PANTRY_KEYWORDS:
        if kw in name_lower:
            return ['pantry']

    # Check for market indicators
    is_market = any(kw in name_lower for kw in MARKET_KEYWORDS)

    # Check for eatery indicators
    is_eatery = any(kw in name_lower for kw in EATERY_KEYWORDS)

    # Also check industry
    if industry:
        industry_lower = industry.lower()
        if 'grocery' in industry_lower or 'market' in industry_lower:
            is_market = True
        if 'restaurant' in industry_lower or 'food' in industry_lower:
            is_eatery = True

    if is_market:
        categories.append('market')
    if is_eatery:
        categories.append('eatery')

    # Default to eatery if unclear but food-related
    if not categories and industry and 'food' in industry.lower():
        categories.append('eatery')

    return categories


def check_eatery_duplicate(conn, name: str, city: str, street: str = None) -> bool:
    """Check if eatery already exists."""
    if street:
        result = conn.execute(text("""
            SELECT eatery_id FROM halal_eateries
            WHERE LOWER(name) = LOWER(:name)
            AND LOWER(address_street) = LOWER(:street)
        """), {"name": name, "street": street})
    else:
        result = conn.execute(text("""
            SELECT eatery_id FROM halal_eateries
            WHERE LOWER(name) = LOWER(:name)
            AND LOWER(address_city) = LOWER(:city)
        """), {"name": name, "city": city})
    return result.fetchone() is not None


def check_market_duplicate(conn, name: str, city: str, street: str = None) -> bool:
    """Check if market already exists."""
    if street:
        result = conn.execute(text("""
            SELECT market_id FROM halal_markets
            WHERE LOWER(name) = LOWER(:name)
            AND LOWER(address_street) = LOWER(:street)
        """), {"name": name, "street": street})
    else:
        result = conn.execute(text("""
            SELECT market_id FROM halal_markets
            WHERE LOWER(name) = LOWER(:name)
            AND LOWER(address_city) = LOWER(:city)
        """), {"name": name, "city": city})
    return result.fetchone() is not None


def check_nonprofit_duplicate(conn, name: str, city: str) -> bool:
    """Check if nonprofit already exists."""
    result = conn.execute(text("""
        SELECT nonprofit_id FROM nonprofits
        WHERE LOWER(name) = LOWER(:name)
        AND LOWER(address_city) = LOWER(:city)
    """), {"name": name, "city": city})
    return result.fetchone() is not None


def get_food_entries(conn):
    """Get all food-related entries from business_claim_submissions."""
    result = conn.execute(text("""
        SELECT
            claim_id,
            business_name,
            business_industry,
            business_street_address,
            business_city,
            business_state,
            business_zip,
            latitude,
            longitude,
            business_phone,
            business_website,
            owner_email,
            submitted_from,
            status
        FROM business_claim_submissions
        WHERE (
            business_industry ILIKE '%food%'
            OR business_industry ILIKE '%restaurant%'
            OR business_industry ILIKE '%grocery%'
            OR LOWER(business_name) LIKE '%halal%'
            OR LOWER(business_name) LIKE '%market%'
            OR LOWER(business_name) LIKE '%grocery%'
            OR LOWER(business_name) LIKE '%restaurant%'
            OR LOWER(business_name) LIKE '%grill%'
            OR LOWER(business_name) LIKE '%cafe%'
            OR LOWER(business_name) LIKE '%kitchen%'
            OR LOWER(business_name) LIKE '%kabob%'
            OR LOWER(business_name) LIKE '%kebab%'
            OR LOWER(business_name) LIKE '%shawarma%'
            OR LOWER(business_name) LIKE '%falafel%'
            OR LOWER(business_name) LIKE '%pizza%'
            OR LOWER(business_name) LIKE '%biryani%'
            OR LOWER(business_name) LIKE '%tikka%'
            OR LOWER(business_name) LIKE '%bakery%'
            OR LOWER(business_name) LIKE '%food pantry%'
            OR LOWER(business_name) LIKE '%meat%'
            OR LOWER(business_name) LIKE '%butcher%'
        )
        ORDER BY business_state, business_city, business_name
    """))
    return result.fetchall()


def migrate_food(dry_run: bool = True, delete_after: bool = False, use_prod: bool = False):
    """
    Migrate food businesses from business_claim_submissions to specialized tables.

    Args:
        dry_run: If True, don't actually insert/delete (default)
        delete_after: If True, delete from business_claim_submissions after migration
        use_prod: If True, use Neon prod database
    """
    db_target = "NEON PROD" if use_prod else "LOCAL"
    print(f"Target database: {db_target}")
    print("=" * 70)

    with get_db_session(use_prod=use_prod) as conn:
        entries = get_food_entries(conn)

        print(f"Found {len(entries)} food-related entries to process")
        print("-" * 70)

        # Counters
        stats = {
            'eateries_migrated': 0,
            'markets_migrated': 0,
            'pantries_migrated': 0,
            'hybrids': 0,
            'skipped_duplicate': 0,
            'skipped_no_coords': 0,
            'skipped_unclassified': 0,
            'errors': 0,
            'claim_ids_to_delete': []
        }

        for row in entries:
            (claim_id, name, industry, address, city, state, zip_code,
             lat, lng, phone, website, email, source, status) = row

            # Classify
            categories = classify_food_business(name, industry)

            if not categories:
                print(f"  ? Unclassified: {name} ({industry})")
                stats['skipped_unclassified'] += 1
                continue

            # Skip if no coordinates
            if not lat or not lng:
                print(f"  ⚠ No coords: {name} ({city}, {state})")
                stats['skipped_no_coords'] += 1
                continue

            is_hybrid = len(categories) > 1
            if is_hybrid:
                stats['hybrids'] += 1
                print(f"  🔀 Hybrid: {name} -> {categories}")

            migrated_to = []

            # Process each category
            for cat in categories:
                if cat == 'eatery':
                    if check_eatery_duplicate(conn, name, city, address):
                        print(f"  ⚠ Dup eatery: {name}")
                        stats['skipped_duplicate'] += 1
                        continue

                    if not dry_run:
                        try:
                            conn.execute(text("""
                                INSERT INTO halal_eateries (
                                    name, address_street, address_city, address_state, address_zip,
                                    latitude, longitude, phone, website,
                                    halal_status, region, source
                                ) VALUES (
                                    :name, :address, :city, :state, :zip,
                                    :lat, :lng, :phone, :website,
                                    'unverified', :region, :source
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
                                "website": website,
                                "region": state,
                                "source": f"migrated_from_{source}",
                            })
                            conn.commit()
                        except Exception as e:
                            conn.rollback()
                            print(f"  ✗ Error (eatery): {name} - {str(e)[:60]}")
                            stats['errors'] += 1
                            continue

                    stats['eateries_migrated'] += 1
                    migrated_to.append('eatery')

                elif cat == 'market':
                    if check_market_duplicate(conn, name, city, address):
                        print(f"  ⚠ Dup market: {name}")
                        stats['skipped_duplicate'] += 1
                        continue

                    if not dry_run:
                        try:
                            conn.execute(text("""
                                INSERT INTO halal_markets (
                                    name, address_street, address_city, address_state, address_zip,
                                    latitude, longitude, phone, website,
                                    halal_status, region, source
                                ) VALUES (
                                    :name, :address, :city, :state, :zip,
                                    :lat, :lng, :phone, :website,
                                    'validated', :region, :source
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
                                "website": website,
                                "region": state,
                                "source": f"migrated_from_{source}",
                            })
                            conn.commit()
                        except Exception as e:
                            conn.rollback()
                            print(f"  ✗ Error (market): {name} - {str(e)[:60]}")
                            stats['errors'] += 1
                            continue

                    stats['markets_migrated'] += 1
                    migrated_to.append('market')

                elif cat == 'pantry':
                    if check_nonprofit_duplicate(conn, name, city):
                        print(f"  ⚠ Dup pantry: {name}")
                        stats['skipped_duplicate'] += 1
                        continue

                    if not dry_run:
                        try:
                            conn.execute(text("""
                                INSERT INTO nonprofits (
                                    name, address_street, address_city, address_state, address_zip,
                                    latitude, longitude, phone, website,
                                    org_type, region, source
                                ) VALUES (
                                    :name, :address, :city, :state, :zip,
                                    :lat, :lng, :phone, :website,
                                    'food_assistance', :region, :source
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
                                "website": website,
                                "region": state,
                                "source": f"migrated_from_{source}",
                            })
                            conn.commit()
                        except Exception as e:
                            conn.rollback()
                            print(f"  ✗ Error (pantry): {name} - {str(e)[:60]}")
                            stats['errors'] += 1
                            continue

                    stats['pantries_migrated'] += 1
                    migrated_to.append('pantry')

            if migrated_to:
                print(f"  ✓ {name} -> {migrated_to}")
                stats['claim_ids_to_delete'].append(claim_id)

        # Delete from claims if requested
        if delete_after and not dry_run and stats['claim_ids_to_delete']:
            for cid in stats['claim_ids_to_delete']:
                conn.execute(text("DELETE FROM business_claim_submissions WHERE claim_id = :id"), {"id": cid})
            conn.commit()

        # Summary
        print("\n" + "=" * 70)
        print("Migration Summary")
        print("=" * 70)
        print(f"  Total processed: {len(entries)}")
        print(f"  Eateries migrated: {stats['eateries_migrated']}")
        print(f"  Markets migrated: {stats['markets_migrated']}")
        print(f"  Pantries migrated: {stats['pantries_migrated']}")
        print(f"  Hybrids (dual-listed): {stats['hybrids']}")
        print(f"  Skipped (duplicate): {stats['skipped_duplicate']}")
        print(f"  Skipped (no coords): {stats['skipped_no_coords']}")
        print(f"  Skipped (unclassified): {stats['skipped_unclassified']}")
        print(f"  Errors: {stats['errors']}")

        if dry_run:
            print("\n[DRY RUN] No changes were made. Run with --migrate to execute.")
        elif delete_after:
            print(f"\n[DELETED] {len(stats['claim_ids_to_delete'])} entries removed from business_claim_submissions")
        else:
            print("\n[KEPT] Entries still exist in business_claim_submissions")
            print("       Run with --delete to remove after migration")

        # Show final counts
        result = conn.execute(text("SELECT COUNT(*) FROM halal_eateries"))
        eatery_count = result.scalar()

        result = conn.execute(text("SELECT COUNT(*) FROM halal_markets"))
        market_count = result.scalar()

        result = conn.execute(text("SELECT COUNT(*) FROM nonprofits"))
        nonprofit_count = result.scalar()

        result = conn.execute(text("SELECT COUNT(*) FROM business_claim_submissions"))
        claims_count = result.scalar()

        print(f"\nCurrent table counts:")
        print(f"  halal_eateries: {eatery_count}")
        print(f"  halal_markets: {market_count}")
        print(f"  nonprofits: {nonprofit_count}")
        print(f"  business_claim_submissions: {claims_count}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Migrate food businesses to specialized tables")
    parser.add_argument("--migrate", action="store_true", help="Actually perform migration (default is dry run)")
    parser.add_argument("--delete", action="store_true", help="Delete from business_claim_submissions after migration")
    parser.add_argument("--prod", action="store_true", help="Target Neon prod database (default is local)")

    args = parser.parse_args()

    migrate_food(dry_run=not args.migrate, delete_after=args.delete, use_prod=args.prod)
