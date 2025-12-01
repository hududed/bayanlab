#!/usr/bin/env python3
"""
Unified Ingestion Pipeline for BayanLab

This script:
1. Loads scraped data from JSON files (MDA, MBC, EmanNest, MuslimListings)
2. Cleans and normalizes the data
3. Categorizes into: masajid, halal_eateries, halal_markets, businesses
4. Deduplicates against existing database records
5. Upserts to the appropriate tables

Usage:
    # Dry run (no DB writes)
    uv run python scripts/unified_ingest.py --dry-run

    # Ingest specific source
    uv run python scripts/unified_ingest.py --source muslimlistings

    # Ingest all sources
    uv run python scripts/unified_ingest.py --all

    # With email notification
    uv run python scripts/unified_ingest.py --all --email hudwahab@gmail.com
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from html import unescape

import psycopg2
from psycopg2.extras import execute_values

# Data directory (on Pi this would be ~/scripts/bayanlab/data/)
DATA_DIR = Path(__file__).parent.parent / "data"

# Categorization keywords
# NOTE: Order matters - more specific keywords should match first
MASJID_KEYWORDS = [
    'masjid', 'mosque', 'islamic center', 'islamic society', 'islamic foundation',
    'islamic association', 'islamic community', 'muslim community', 'muslim society',
    'msa ', 'muslim student', 'icna', 'isna', 'dar al-', 'darul ', 'jamia', 'jami masjid',
    'muslims of', 'masjed', 'musallah', 'prayer room', 'islamic school',
    'madrasah', 'madrasa', 'islamic academy', 'quran center', 'dawah center',
    'al-farooq', 'al-noor', 'al-iman', 'al-huda', 'al-salam', 'baitul', 'bait ul'
]

EATERY_KEYWORDS = [
    'restaurant', 'cafe', 'café', 'grill', 'kitchen', 'bistro', 'food', 'halal food',
    'kabab', 'kebab', 'shawarma', 'biryani', 'tandoori', 'curry', 'diner', 'eatery',
    'pizza', 'burger', 'chicken', 'wings', 'falafel', 'hummus', 'mediterranean',
    'indian cuisine', 'pakistani cuisine', 'afghan', 'turkish', 'lebanese', 'moroccan',
    'catering', 'bakery', 'sweets', 'dessert', 'tea house', 'coffee'
]

MARKET_KEYWORDS = [
    'market', 'grocery', 'supermarket', 'meat', 'butcher', 'halal meat', 'bazaar',
    'store', 'mart', 'zabiha', 'deli', 'food mart', 'international market',
    'middle eastern market', 'asian market', 'indian grocery', 'pakistani grocery'
]


def categorize_by_name(name: str) -> str:
    """Categorize a business by its name using keywords.

    Priority order:
    1. Check eatery keywords first (restaurants, cafes, etc.)
    2. Check market keywords (grocery, meat, etc.)
    3. Check masjid keywords (mosques, islamic centers)
    4. Default to business

    This order prevents "Halal Meat" from being categorized as masjid
    just because it has "halal" in the name.
    """
    if not name:
        return 'business'

    name_lower = name.lower()

    # Check eatery keywords FIRST (restaurants, cafes, food)
    for kw in EATERY_KEYWORDS:
        if kw in name_lower:
            return 'eatery'

    # Check market keywords (grocery, meat, butcher)
    for kw in MARKET_KEYWORDS:
        if kw in name_lower:
            return 'market'

    # Check masjid keywords (mosques, islamic centers)
    for kw in MASJID_KEYWORDS:
        if kw in name_lower:
            return 'masjid'

    return 'business'


def normalize_phone(phone: str, digits_only: bool = False) -> Optional[str]:
    """Normalize phone number.

    Args:
        phone: The phone number to normalize
        digits_only: If True, return only digits (for DB constraints that require it)

    Returns:
        Normalized phone number in E.164 format (+1XXXXXXXXXX) or digits only
    """
    if not phone:
        return None

    # Remove all non-digits
    digits = re.sub(r'\D', '', str(phone))

    # Handle US numbers
    if len(digits) == 10:
        full = f"1{digits}"
    elif len(digits) == 11 and digits[0] == '1':
        full = digits
    elif len(digits) > 11:
        full = digits
    else:
        return None if digits_only else phone

    return full if digits_only else f"+{full}"


def clean_text(text: str) -> Optional[str]:
    """Clean text by decoding HTML entities and trimming."""
    if not text:
        return None

    # Decode HTML entities
    cleaned = unescape(str(text))
    # Remove excessive whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    return cleaned if cleaned else None


def normalize_state(state: str) -> Optional[str]:
    """Normalize state to 2-letter abbreviation."""
    if not state:
        return None

    state = state.strip().upper()

    # Already 2-letter code
    if len(state) == 2:
        return state

    # Common full names to abbreviations
    STATE_MAP = {
        'ALABAMA': 'AL', 'ALASKA': 'AK', 'ARIZONA': 'AZ', 'ARKANSAS': 'AR',
        'CALIFORNIA': 'CA', 'COLORADO': 'CO', 'CONNECTICUT': 'CT', 'DELAWARE': 'DE',
        'FLORIDA': 'FL', 'GEORGIA': 'GA', 'HAWAII': 'HI', 'IDAHO': 'ID',
        'ILLINOIS': 'IL', 'INDIANA': 'IN', 'IOWA': 'IA', 'KANSAS': 'KS',
        'KENTUCKY': 'KY', 'LOUISIANA': 'LA', 'MAINE': 'ME', 'MARYLAND': 'MD',
        'MASSACHUSETTS': 'MA', 'MICHIGAN': 'MI', 'MINNESOTA': 'MN', 'MISSISSIPPI': 'MS',
        'MISSOURI': 'MO', 'MONTANA': 'MT', 'NEBRASKA': 'NE', 'NEVADA': 'NV',
        'NEW HAMPSHIRE': 'NH', 'NEW JERSEY': 'NJ', 'NEW MEXICO': 'NM', 'NEW YORK': 'NY',
        'NORTH CAROLINA': 'NC', 'NORTH DAKOTA': 'ND', 'OHIO': 'OH', 'OKLAHOMA': 'OK',
        'OREGON': 'OR', 'PENNSYLVANIA': 'PA', 'RHODE ISLAND': 'RI', 'SOUTH CAROLINA': 'SC',
        'SOUTH DAKOTA': 'SD', 'TENNESSEE': 'TN', 'TEXAS': 'TX', 'UTAH': 'UT',
        'VERMONT': 'VT', 'VIRGINIA': 'VA', 'WASHINGTON': 'WA', 'WEST VIRGINIA': 'WV',
        'WISCONSIN': 'WI', 'WYOMING': 'WY', 'DISTRICT OF COLUMBIA': 'DC',
    }

    return STATE_MAP.get(state, state[:2] if len(state) >= 2 else None)


def make_dedup_key(name: str, city: str) -> str:
    """Create a deduplication key from name and city."""
    name_clean = re.sub(r'[^a-z0-9]', '', (name or '').lower())
    city_clean = re.sub(r'[^a-z0-9]', '', (city or '').lower())
    return f"{name_clean}:{city_clean}"


def load_json_file(filepath: Path) -> list[dict]:
    """Load a JSON file, handling both wrapped and raw formats."""
    if not filepath.exists():
        print(f"  File not found: {filepath}")
        return []

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Handle wrapped formats
    if isinstance(data, dict):
        if 'listings' in data:
            return data['listings']
        elif 'businesses' in data:
            return data['businesses']
        elif 'masjids' in data:
            return data['masjids']
        else:
            # Single dict, wrap in list
            return [data]
    elif isinstance(data, list):
        return data

    return []


def load_muslimlistings(data_dir: Path) -> list[dict]:
    """Load MuslimListings data from JSON file."""
    filepath = data_dir / "muslimlistings" / "listings.json"
    listings = load_json_file(filepath)

    # Normalize field names
    normalized = []
    for item in listings:
        normalized.append({
            'name': clean_text(item.get('name')),
            'address': clean_text(item.get('address')),
            'city': clean_text(item.get('city')),
            'state': normalize_state(item.get('state')),
            'zip': item.get('zip'),
            'latitude': item.get('latitude'),
            'longitude': item.get('longitude'),
            'phone': normalize_phone(item.get('phone')),
            'email': item.get('email'),
            'website': item.get('website'),
            'description': clean_text(item.get('description')),
            'hours': item.get('hours'),
            'source': 'muslimlistings',
            'source_ref': item.get('url'),
        })

    return normalized


def load_mda(data_dir: Path) -> list[dict]:
    """Load MDA (Muslim Directory App) data."""
    filepath = data_dir / "mda" / "listings.json"
    data = load_json_file(filepath)

    # MDA uses 'businesses' wrapper
    if isinstance(data, dict) and 'businesses' in data:
        listings = data['businesses']
    else:
        listings = data

    normalized = []
    for item in listings:
        normalized.append({
            'name': clean_text(item.get('name')),
            'address': clean_text(item.get('address')),
            'city': clean_text(item.get('city')),
            'state': normalize_state(item.get('state')),
            'zip': item.get('zipcode'),
            'latitude': None,  # MDA doesn't have coords
            'longitude': None,
            'phone': normalize_phone(item.get('phone')),
            'email': item.get('email'),
            'website': item.get('website'),
            'description': None,
            'hours': None,
            'source': 'mda',
            'source_ref': item.get('json_id'),
        })

    return normalized


def load_mbc(data_dir: Path) -> list[dict]:
    """Load MBC (Muslim Business Central) data."""
    filepath = data_dir / "mbc" / "businesses.json"
    listings = load_json_file(filepath)

    normalized = []
    for item in listings:
        # MBC has category field we can use
        category = item.get('category', '').lower()

        normalized.append({
            'name': clean_text(item.get('name')),
            'address': clean_text(item.get('address')),
            'city': clean_text(item.get('city')),
            'state': normalize_state(item.get('state')),
            'zip': item.get('zipCode'),
            'latitude': item.get('latitude'),
            'longitude': item.get('longitude'),
            'phone': normalize_phone(item.get('phone')),
            'email': item.get('email'),
            'website': item.get('website'),
            'description': clean_text(item.get('description')),
            'hours': item.get('hours'),
            'source': 'mbc',
            'source_ref': item.get('id'),
            'mbc_category': category,  # Keep original category for reference
        })

    return normalized


def load_emannest(data_dir: Path) -> list[dict]:
    """Load EmanNest data (businesses and masjids)."""
    businesses_file = data_dir / "emannest" / "emannest_businesses.json"
    masjids_file = data_dir / "emannest" / "emannest_masjids.json"

    all_listings = []

    # Load businesses
    for item in load_json_file(businesses_file):
        all_listings.append({
            'name': clean_text(item.get('name')),
            'address': clean_text(item.get('address')),
            'city': clean_text(item.get('city')),
            'state': normalize_state(item.get('state')),
            'zip': item.get('zipCode'),
            'latitude': item.get('latitude'),
            'longitude': item.get('longitude'),
            'phone': normalize_phone(item.get('contact_info')),
            'email': None,
            'website': item.get('website_url'),
            'description': clean_text(item.get('description')),
            'hours': None,
            'source': 'emannest',
            'source_ref': str(item.get('id')),
            'emannest_category': item.get('category'),
        })

    # Load masjids (force category)
    for item in load_json_file(masjids_file):
        all_listings.append({
            'name': clean_text(item.get('name')),
            'address': clean_text(item.get('address')),
            'city': clean_text(item.get('city')),
            'state': normalize_state(item.get('state')),
            'zip': item.get('zipCode'),
            'latitude': item.get('latitude'),
            'longitude': item.get('longitude'),
            'phone': normalize_phone(item.get('contact_info')),
            'email': None,
            'website': item.get('website_url'),
            'description': clean_text(item.get('description')),
            'hours': None,
            'source': 'emannest',
            'source_ref': str(item.get('id')),
            'force_category': 'masjid',  # Force masjid category
        })

    return all_listings


def get_existing_keys(conn) -> set[str]:
    """Get all existing dedup keys from all tables.

    Note: We check business_canonical (for scraped businesses) instead of
    business_claim_submissions (which is for user-submitted claims only).
    """
    keys = set()

    queries = [
        "SELECT name, address_city FROM masajid",
        "SELECT name, address_city FROM halal_eateries",
        "SELECT name, address_city FROM halal_markets",
        "SELECT name, address_city FROM business_canonical",
    ]

    with conn.cursor() as cur:
        for query in queries:
            try:
                cur.execute(query)
                for row in cur.fetchall():
                    key = make_dedup_key(row[0], row[1])
                    keys.add(key)
            except Exception as e:
                print(f"  Warning: Could not query table: {e}")

    return keys


def insert_masajid(conn, records: list[dict], dry_run: bool = False) -> int:
    """Insert records into masajid table."""
    if not records or dry_run:
        return 0

    sql = """
        INSERT INTO masajid (name, address_street, address_city, address_state, address_zip,
                            latitude, longitude, phone, website, email, source, region)
        VALUES %s
        ON CONFLICT (lower(name), lower(address_city)) DO UPDATE SET
            address_street = EXCLUDED.address_street,
            phone = COALESCE(EXCLUDED.phone, masajid.phone),
            website = COALESCE(EXCLUDED.website, masajid.website),
            email = COALESCE(EXCLUDED.email, masajid.email),
            latitude = COALESCE(EXCLUDED.latitude, masajid.latitude),
            longitude = COALESCE(EXCLUDED.longitude, masajid.longitude)
    """

    values = [
        (r['name'], r['address'], r['city'], r['state'], r['zip'],
         r.get('latitude'), r.get('longitude'), r['phone'], r['website'], r['email'],
         r['source'], r['state'] or 'US')
        for r in records
    ]

    with conn.cursor() as cur:
        execute_values(cur, sql, values)
        conn.commit()

    return len(records)


def insert_halal_eateries(conn, records: list[dict], dry_run: bool = False) -> int:
    """Insert records into halal_eateries table."""
    if not records or dry_run:
        return 0

    # halal_eateries has unique constraint on (name, address_street)
    sql = """
        INSERT INTO halal_eateries (name, address_street, address_city, address_state, address_zip,
                                   latitude, longitude, phone, website, hours_raw, source, source_ref, region)
        VALUES %s
        ON CONFLICT (lower(name), lower(address_street)) DO UPDATE SET
            phone = COALESCE(EXCLUDED.phone, halal_eateries.phone),
            website = COALESCE(EXCLUDED.website, halal_eateries.website),
            hours_raw = COALESCE(EXCLUDED.hours_raw, halal_eateries.hours_raw),
            latitude = COALESCE(EXCLUDED.latitude, halal_eateries.latitude),
            longitude = COALESCE(EXCLUDED.longitude, halal_eateries.longitude)
    """

    values = [
        (r['name'], r['address'] or '', r['city'], r['state'], r['zip'],
         r.get('latitude'), r.get('longitude'), r['phone'], r['website'], r.get('hours'),
         r['source'], r.get('source_ref'), r['state'] or 'US')
        for r in records
    ]

    with conn.cursor() as cur:
        execute_values(cur, sql, values)
        conn.commit()

    return len(records)


def insert_halal_markets(conn, records: list[dict], dry_run: bool = False) -> int:
    """Insert records into halal_markets table.

    halal_markets has TWO partial unique indexes:
    - (name, address_street) WHERE address_street IS NOT NULL
    - (name, address_city) WHERE address_street IS NULL

    We need to handle both cases separately.
    """
    if not records or dry_run:
        return 0

    # Split records into those with and without address_street
    with_street = [r for r in records if r.get('address')]
    without_street = [r for r in records if not r.get('address')]

    inserted = 0

    # Insert records WITH street address
    if with_street:
        sql = """
            INSERT INTO halal_markets (name, address_street, address_city, address_state, address_zip,
                                      latitude, longitude, phone, website, hours_raw, source, region)
            VALUES %s
            ON CONFLICT (lower(name), lower(address_street)) WHERE address_street IS NOT NULL DO UPDATE SET
                phone = COALESCE(EXCLUDED.phone, halal_markets.phone),
                website = COALESCE(EXCLUDED.website, halal_markets.website),
                hours_raw = COALESCE(EXCLUDED.hours_raw, halal_markets.hours_raw),
                latitude = COALESCE(EXCLUDED.latitude, halal_markets.latitude),
                longitude = COALESCE(EXCLUDED.longitude, halal_markets.longitude)
        """
        values = [
            (r['name'], r['address'], r['city'], r['state'], r['zip'],
             r.get('latitude'), r.get('longitude'), r['phone'], r['website'], r.get('hours'),
             r['source'], r['state'] or 'US')
            for r in with_street
        ]
        with conn.cursor() as cur:
            execute_values(cur, sql, values)
        inserted += len(with_street)

    # Insert records WITHOUT street address
    if without_street:
        sql = """
            INSERT INTO halal_markets (name, address_street, address_city, address_state, address_zip,
                                      latitude, longitude, phone, website, hours_raw, source, region)
            VALUES %s
            ON CONFLICT (lower(name), lower(address_city)) WHERE address_street IS NULL DO UPDATE SET
                phone = COALESCE(EXCLUDED.phone, halal_markets.phone),
                website = COALESCE(EXCLUDED.website, halal_markets.website),
                hours_raw = COALESCE(EXCLUDED.hours_raw, halal_markets.hours_raw),
                latitude = COALESCE(EXCLUDED.latitude, halal_markets.latitude),
                longitude = COALESCE(EXCLUDED.longitude, halal_markets.longitude)
        """
        values = [
            (r['name'], None, r['city'], r['state'], r['zip'],
             r.get('latitude'), r.get('longitude'), r['phone'], r['website'], r.get('hours'),
             r['source'], r['state'] or 'US')
            for r in without_street
        ]
        with conn.cursor() as cur:
            execute_values(cur, sql, values)
        inserted += len(without_street)

    conn.commit()
    return inserted


def insert_business_canonical(conn, records: list[dict], dry_run: bool = False) -> int:
    """Insert scraped businesses directly into business_canonical as unverified.

    Uses ON CONFLICT with dedup index (name, city, state) for upsert.
    All scraped data starts with verified=FALSE.
    """
    if not records or dry_run:
        return 0

    # Filter out records missing required fields
    valid_records = [r for r in records if r.get('state') and r.get('city')]

    if not valid_records:
        return 0

    # Map source names to enum values
    source_map = {
        'muslimlistings': 'muslimlistings_import',
        'mda': 'mda_import',
        'mbc': 'mbc_import',
        'emannest': 'emannest_import',
    }

    sql = """
        INSERT INTO business_canonical
            (name, address_street, address_city, address_state, address_zip,
             latitude, longitude, phone, email, website, description, hours_raw,
             category, muslim_owned, source, source_ref, submitted_from, region, verified)
        VALUES %s
        ON CONFLICT (lower(name), lower(address_city), lower(address_state))
        DO UPDATE SET
            phone = COALESCE(EXCLUDED.phone, business_canonical.phone),
            email = COALESCE(EXCLUDED.email, business_canonical.email),
            website = COALESCE(EXCLUDED.website, business_canonical.website),
            description = COALESCE(EXCLUDED.description, business_canonical.description),
            hours_raw = COALESCE(EXCLUDED.hours_raw, business_canonical.hours_raw),
            latitude = COALESCE(EXCLUDED.latitude, business_canonical.latitude),
            longitude = COALESCE(EXCLUDED.longitude, business_canonical.longitude),
            updated_at = NOW()
    """

    values = [
        (r['name'], r['address'], r['city'], r['state'], r['zip'],
         r.get('latitude'), r.get('longitude'), r['phone'], r['email'], r['website'],
         r.get('description'), r.get('hours'),
         'service',  # Default category for general businesses
         True,  # muslim_owned
         source_map.get(r['source'], 'csv'),  # Map to enum value
         r.get('source_ref') or r.get('url'),  # Original URL/ID
         'scraper',  # submitted_from - how it entered the system
         r['state'] or 'US',  # region
         False)  # verified=FALSE for all scraped data
        for r in valid_records
    ]

    with conn.cursor() as cur:
        execute_values(cur, sql, values)
        conn.commit()

    return len(valid_records)


def send_email(to_email: str, subject: str, body: str):
    """Send email notification using mail command."""
    try:
        process = subprocess.Popen(
            ['mail', '-s', subject, to_email],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        process.communicate(input=body.encode())
    except Exception as e:
        print(f"  Warning: Could not send email: {e}")


def main():
    parser = argparse.ArgumentParser(description='Unified BayanLab Data Ingestion')
    parser.add_argument('--source', type=str, choices=['muslimlistings', 'mda', 'mbc', 'emannest'],
                        help='Ingest specific source only')
    parser.add_argument('--all', action='store_true', help='Ingest all sources')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without writing to DB')
    parser.add_argument('--data-dir', type=str, help='Override data directory')
    parser.add_argument('--email', type=str, help='Send notification email on completion')
    args = parser.parse_args()

    if not args.source and not args.all:
        print("Error: Specify --source or --all")
        parser.print_help()
        sys.exit(1)

    # Determine data directory
    data_dir = Path(args.data_dir) if args.data_dir else DATA_DIR
    print(f"Data directory: {data_dir}")

    # Get database URL from environment
    db_url = os.environ.get('DATABASE_URL_SYNC')
    if not db_url:
        # Try to load from .env file
        env_file = Path(__file__).parent.parent / '.env'
        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    if line.startswith('DATABASE_URL_SYNC='):
                        db_url = line.split('=', 1)[1].strip()
                        break

    if not db_url:
        print("Error: DATABASE_URL_SYNC not found in environment or .env file")
        sys.exit(1)

    # Connect to database
    conn = None
    if not args.dry_run:
        try:
            conn = psycopg2.connect(db_url)
            print("Connected to database")
        except Exception as e:
            print(f"Error connecting to database: {e}")
            sys.exit(1)

    # Load all data
    all_records = []
    sources_to_load = [args.source] if args.source else ['muslimlistings', 'mda', 'mbc', 'emannest']

    for source in sources_to_load:
        print(f"\nLoading {source}...")

        if source == 'muslimlistings':
            records = load_muslimlistings(data_dir)
        elif source == 'mda':
            records = load_mda(data_dir)
        elif source == 'mbc':
            records = load_mbc(data_dir)
        elif source == 'emannest':
            records = load_emannest(data_dir)
        else:
            records = []

        print(f"  Loaded {len(records)} records")
        all_records.extend(records)

    print(f"\nTotal records loaded: {len(all_records)}")

    # Filter out records without required fields
    valid_records = [r for r in all_records if r.get('name') and r.get('city')]
    print(f"Valid records (with name+city): {len(valid_records)}")

    # Get existing keys for deduplication
    existing_keys = set()
    if conn:
        print("\nFetching existing records for deduplication...")
        existing_keys = get_existing_keys(conn)
        print(f"  Found {len(existing_keys)} existing records")

    # Deduplicate
    new_records = []
    seen_keys = set()
    for record in valid_records:
        key = make_dedup_key(record['name'], record['city'])
        if key not in existing_keys and key not in seen_keys:
            new_records.append(record)
            seen_keys.add(key)

    print(f"New records after deduplication: {len(new_records)}")

    # Categorize records
    categorized = {
        'masjid': [],
        'eatery': [],
        'market': [],
        'business': [],
    }

    for record in new_records:
        # Check for forced category (e.g., EmanNest masjids file)
        if record.get('force_category'):
            category = record['force_category']
        else:
            category = categorize_by_name(record['name'])

        categorized[category].append(record)

    print(f"\nCategorization:")
    print(f"  Masajid: {len(categorized['masjid'])}")
    print(f"  Halal Eateries: {len(categorized['eatery'])}")
    print(f"  Halal Markets: {len(categorized['market'])}")
    print(f"  General Businesses: {len(categorized['business'])}")

    if args.dry_run:
        print("\n[DRY RUN] No database changes made")

        # Show some samples
        print("\n--- Sample Masajid ---")
        for r in categorized['masjid'][:3]:
            print(f"  {r['name']} - {r['city']}, {r['state']}")

        print("\n--- Sample Eateries ---")
        for r in categorized['eatery'][:3]:
            print(f"  {r['name']} - {r['city']}, {r['state']}")

        print("\n--- Sample Markets ---")
        for r in categorized['market'][:3]:
            print(f"  {r['name']} - {r['city']}, {r['state']}")

        print("\n--- Sample Businesses ---")
        for r in categorized['business'][:3]:
            print(f"  {r['name']} - {r['city']}, {r['state']}")

        return

    # Insert into database
    print("\nInserting into database...")

    inserted = {
        'masajid': insert_masajid(conn, categorized['masjid'], args.dry_run),
        'halal_eateries': insert_halal_eateries(conn, categorized['eatery'], args.dry_run),
        'halal_markets': insert_halal_markets(conn, categorized['market'], args.dry_run),
        'business_canonical': insert_business_canonical(conn, categorized['business'], args.dry_run),
    }

    print(f"\nInserted:")
    print(f"  Masajid: {inserted['masajid']}")
    print(f"  Halal Eateries: {inserted['halal_eateries']}")
    print(f"  Halal Markets: {inserted['halal_markets']}")
    print(f"  Business Canonical: {inserted['business_canonical']}")

    total_inserted = sum(inserted.values())
    print(f"\nTotal inserted: {total_inserted}")

    # Close connection
    if conn:
        conn.close()

    # Send email notification
    if args.email and total_inserted > 0:
        subject = f"BayanLab Ingest: {total_inserted} new records"
        body = f"""BayanLab Data Ingestion Complete

Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

New Records Inserted:
- Masajid: {inserted['masajid']}
- Halal Eateries: {inserted['halal_eateries']}
- Halal Markets: {inserted['halal_markets']}
- Business Canonical: {inserted['business_canonical']}

Total: {total_inserted}
"""
        send_email(args.email, subject, body)
        print(f"\nEmail notification sent to {args.email}")

    print("\nDone!")


if __name__ == '__main__':
    main()
