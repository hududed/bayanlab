#!/bin/bash
# Database restore script for BayanLab Backbone
# Restores PostgreSQL database from backup file

set -e  # Exit on error

# Configuration
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_ROOT/backups}"

# Database configuration (override with environment variables)
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5433}"
DB_NAME="${DB_NAME:-bayan_backbone}"
DB_USER="${DB_USER:-bayan}"
export PGPASSWORD="${PGPASSWORD:-bayan}"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" >&2
}

warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

# Show usage
usage() {
    echo "Usage: $0 [BACKUP_FILE]"
    echo ""
    echo "Restore BayanLab database from backup."
    echo ""
    echo "Arguments:"
    echo "  BACKUP_FILE    Path to backup file (default: latest backup)"
    echo ""
    echo "Examples:"
    echo "  $0                                          # Restore from latest backup"
    echo "  $0 backups/bayan_backbone_20251110.sql.gz  # Restore from specific backup"
    echo ""
    exit 1
}

# Get backup file
if [ -z "$1" ]; then
    # Find latest backup
    BACKUP_FILE=$(find "$BACKUP_DIR" -name "bayan_backbone_*.sql.gz" -type f | sort -r | head -1)
    if [ -z "$BACKUP_FILE" ]; then
        error "No backup files found in $BACKUP_DIR"
        exit 1
    fi
    log "Using latest backup: $BACKUP_FILE"
else
    BACKUP_FILE="$1"
    if [ ! -f "$BACKUP_FILE" ]; then
        error "Backup file not found: $BACKUP_FILE"
        exit 1
    fi
fi

# Verify backup file integrity
log "Verifying backup file integrity..."
if ! gzip -t "$BACKUP_FILE" 2>/dev/null; then
    error "Backup file is corrupted: $BACKUP_FILE"
    exit 1
fi
log "Backup file integrity verified"

# Show backup info
BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
BACKUP_DATE=$(basename "$BACKUP_FILE" | sed 's/bayan_backbone_\(.*\)\.sql\.gz/\1/')
log "Backup file: $BACKUP_FILE"
log "Backup size: $BACKUP_SIZE"
log "Backup date: $BACKUP_DATE"

# Load metadata if available
METADATA_FILE="${BACKUP_FILE%.sql.gz}.meta"
if [ -f "$METADATA_FILE" ]; then
    log "Found metadata file: $METADATA_FILE"
    cat "$METADATA_FILE"
    echo ""
fi

# Confirm restore
warning "This will REPLACE the current database: $DB_NAME"
warning "Database host: $DB_HOST:$DB_PORT"
echo ""
read -p "Are you sure you want to continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    log "Restore cancelled"
    exit 0
fi

# Check if database is accessible
log "Testing database connection..."
if ! psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c '\q' 2>/dev/null; then
    error "Cannot connect to database server on $DB_HOST:$DB_PORT"
    exit 1
fi
log "Database connection successful"

# Get current database size (if exists)
if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -lqt | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
    CURRENT_SIZE=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -t -c \
        "SELECT pg_size_pretty(pg_database_size('$DB_NAME'))" | xargs)
    log "Current database size: $CURRENT_SIZE"

    # Create pre-restore backup
    PRE_RESTORE_BACKUP="$BACKUP_DIR/pre_restore_$(date +%Y%m%d_%H%M%S).sql.gz"
    log "Creating pre-restore backup: $PRE_RESTORE_BACKUP"
    pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" | gzip > "$PRE_RESTORE_BACKUP"
    log "Pre-restore backup created"
fi

# Terminate existing connections
log "Terminating existing connections to $DB_NAME..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c \
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();" \
    >/dev/null 2>&1 || true

# Drop and recreate database
log "Dropping database $DB_NAME..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c "DROP DATABASE IF EXISTS $DB_NAME;" >/dev/null

log "Creating database $DB_NAME..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c "CREATE DATABASE $DB_NAME;" >/dev/null

# Restore from backup
log "Restoring from backup..."
START_TIME=$(date +%s)

if gunzip -c "$BACKUP_FILE" | psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; then
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    log "Restore completed successfully in ${DURATION}s"
else
    error "Restore failed"
    exit 1
fi

# Verify restore
log "Verifying restore..."
RESTORED_SIZE=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -t -c \
    "SELECT pg_size_pretty(pg_database_size('$DB_NAME'))" | xargs)
EVENT_COUNT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c \
    "SELECT COUNT(*) FROM event_canonical" 2>/dev/null | xargs || echo "0")
BUSINESS_COUNT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c \
    "SELECT COUNT(*) FROM business_canonical" 2>/dev/null | xargs || echo "0")

log "Database restored successfully!"
echo ""
echo "Summary:"
echo "  Database: $DB_NAME"
echo "  Restored size: $RESTORED_SIZE"
echo "  Events: $EVENT_COUNT"
echo "  Businesses: $BUSINESS_COUNT"
echo "  Duration: ${DURATION}s"
echo ""

exit 0
