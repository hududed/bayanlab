#!/usr/bin/env python3
"""
Run SQL migration via Python (uses NEON_DB_URL from .env)
"""
import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

neon_url = os.getenv("NEON_DB_URL")
if not neon_url:
    print("❌ NEON_DB_URL not found!")
    exit(1)

if len(sys.argv) < 2:
    print("Usage: uv run python scripts/run_migration.py backend/sql/030_add_geocoding.sql")
    exit(1)

migration_file = sys.argv[1]

if not os.path.exists(migration_file):
    print(f"❌ File not found: {migration_file}")
    exit(1)

# Read SQL file
with open(migration_file, 'r') as f:
    sql = f.read()

# Convert to sync URL
sync_url = neon_url.replace("+asyncpg", "")
engine = create_engine(sync_url)

try:
    with engine.connect() as conn:
        print(f"🔧 Running migration: {migration_file}")

        # Split by semicolon and execute each statement
        statements = [s.strip() for s in sql.split(';') if s.strip() and not s.strip().startswith('--')]

        for stmt in statements:
            if stmt:
                conn.execute(text(stmt))

        conn.commit()
        print(f"✅ Migration completed successfully!")

finally:
    engine.dispose()
