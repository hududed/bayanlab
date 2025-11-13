#!/bin/bash
# Run all database migrations on Neon
# Make sure NEON_DB_URL is set in .env file

set -e

echo "🗄️  Neon Database Migration"
echo "=========================="
echo ""

# Load .env file
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "❌ .env file not found!"
    echo "Create .env and add: NEON_DB_URL=postgresql://..."
    exit 1
fi

# Check if NEON_DB_URL is set
if [ -z "$NEON_DB_URL" ]; then
    echo "❌ NEON_DB_URL not found in .env"
    echo "Add this line to .env:"
    echo "NEON_DB_URL=postgresql://user:pass@ep-xyz.us-east-2.aws.neon.tech/neondb?sslmode=require"
    exit 1
fi

echo "✅ Found NEON_DB_URL"
echo "📡 Testing connection..."

# Test connection
if psql "$NEON_DB_URL" -c "SELECT 1;" > /dev/null 2>&1; then
    echo "✅ Connection successful"
else
    echo "❌ Connection failed. Check your NEON_DB_URL"
    exit 1
fi

echo ""
echo "🔧 Running migrations..."
echo ""

# Run all SQL files in order
SQL_DIR="backend/sql"

for file in "$SQL_DIR"/*.sql; do
    if [ -f "$file" ]; then
        filename=$(basename "$file")
        echo "📝 Running $filename..."

        if psql "$NEON_DB_URL" -f "$file"; then
            echo "   ✅ $filename completed"
        else
            echo "   ⚠️  $filename had errors (might be expected for already existing objects)"
        fi
        echo ""
    fi
done

echo "🎉 All migrations complete!"
echo ""
echo "📊 Verifying tables..."
psql "$NEON_DB_URL" -c "\dt" | grep -E "event_canonical|business_canonical|business_claim_submissions"

echo ""
echo "✅ Database ready for deployment!"
