#!/bin/bash
# Database backup script for BayanLab Backbone
# Creates PostgreSQL backups with automatic retention management

set -e  # Exit on error

# Configuration
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_ROOT/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/bayan_backbone_$TIMESTAMP.sql.gz"

# Database configuration (override with environment variables)
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5433}"
DB_NAME="${DB_NAME:-bayan_backbone}"
DB_USER="${DB_USER:-bayan}"
export PGPASSWORD="${PGPASSWORD:-bayan}"

# Email configuration (optional)
SEND_EMAIL="${SEND_EMAIL:-false}"
EMAIL_TO="${EMAIL_TO:-admin@example.com}"
EMAIL_FROM="${EMAIL_FROM:-noreply@bayanlab.com}"

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

# Send failure email
send_failure_email() {
    if [ "$SEND_EMAIL" = "true" ]; then
        if command -v mail >/dev/null 2>&1; then
            echo "Database backup failed at $(date)" | \
                mail -s "[BayanLab] Database Backup Failed" \
                     -r "$EMAIL_FROM" \
                     "$EMAIL_TO"
            log "Failure notification sent to $EMAIL_TO"
        fi
    fi
}

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"
log "Backup directory: $BACKUP_DIR"

# Check if database is accessible
log "Testing database connection..."
if ! psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c '\q' 2>/dev/null; then
    error "Cannot connect to database on $DB_HOST:$DB_PORT"
    send_failure_email
    exit 1
fi
log "Database connection successful"

# Get database statistics before backup
log "Gathering database statistics..."
DB_SIZE=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c \
    "SELECT pg_size_pretty(pg_database_size('$DB_NAME'))" | xargs)
EVENT_COUNT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c \
    "SELECT COUNT(*) FROM event_canonical" | xargs)
BUSINESS_COUNT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c \
    "SELECT COUNT(*) FROM business_canonical" | xargs)

log "Database size: $DB_SIZE"
log "Events: $EVENT_COUNT"
log "Businesses: $BUSINESS_COUNT"

# Create backup
log "Creating backup: $BACKUP_FILE"
START_TIME=$(date +%s)

# Use Docker's pg_dump if available (ensures version match)
if command -v docker >/dev/null 2>&1 && docker ps | grep -q bayan-postgres; then
    log "Using Docker pg_dump for version compatibility"
    if docker exec bayan-postgres pg_dump -U "$DB_USER" -d "$DB_NAME" \
        --format=plain \
        --no-owner \
        --no-acl \
        | gzip > "$BACKUP_FILE"; then
        BACKUP_METHOD="docker"
    else
        error "Docker pg_dump failed"
        send_failure_email
        exit 1
    fi
elif pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
    --format=plain \
    --no-owner \
    --no-acl \
    | gzip > "$BACKUP_FILE" 2>/dev/null; then
    BACKUP_METHOD="local"
else
    error "pg_dump failed"
    send_failure_email
    exit 1
fi

if [ -f "$BACKUP_FILE" ]; then

    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)

    log "Backup completed successfully in ${DURATION}s"
    log "Backup size: $BACKUP_SIZE"
    log "Backup file: $BACKUP_FILE"
else
    error "Backup failed"
    send_failure_email
    exit 1
fi

# Verify backup file
log "Verifying backup integrity..."
if gzip -t "$BACKUP_FILE" 2>/dev/null; then
    log "Backup file integrity verified"
else
    error "Backup file is corrupted"
    send_failure_email
    exit 1
fi

# Clean up old backups
log "Cleaning up backups older than $RETENTION_DAYS days..."
OLD_BACKUP_COUNT=$(find "$BACKUP_DIR" -name "bayan_backbone_*.sql.gz" -type f -mtime +$RETENTION_DAYS | wc -l | xargs)

if [ "$OLD_BACKUP_COUNT" -gt 0 ]; then
    find "$BACKUP_DIR" -name "bayan_backbone_*.sql.gz" -type f -mtime +$RETENTION_DAYS -delete
    log "Deleted $OLD_BACKUP_COUNT old backup(s)"
else
    log "No old backups to delete"
fi

# List current backups
CURRENT_BACKUP_COUNT=$(find "$BACKUP_DIR" -name "bayan_backbone_*.sql.gz" -type f | wc -l | xargs)
TOTAL_BACKUP_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
log "Current backups: $CURRENT_BACKUP_COUNT (total size: $TOTAL_BACKUP_SIZE)"

# Create backup metadata file
METADATA_FILE="$BACKUP_DIR/bayan_backbone_$TIMESTAMP.meta"
cat > "$METADATA_FILE" << EOF
{
  "timestamp": "$TIMESTAMP",
  "database_name": "$DB_NAME",
  "database_size": "$DB_SIZE",
  "backup_file": "$BACKUP_FILE",
  "backup_size": "$BACKUP_SIZE",
  "duration_seconds": $DURATION,
  "event_count": $EVENT_COUNT,
  "business_count": $BUSINESS_COUNT,
  "retention_days": $RETENTION_DAYS,
  "created_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF
log "Metadata saved: $METADATA_FILE"

log "Backup completed successfully!"
echo ""
echo "Summary:"
echo "  Database: $DB_NAME ($DB_SIZE)"
echo "  Events: $EVENT_COUNT"
echo "  Businesses: $BUSINESS_COUNT"
echo "  Backup: $BACKUP_FILE ($BACKUP_SIZE)"
echo "  Duration: ${DURATION}s"
echo "  Retention: $RETENTION_DAYS days"
echo ""

exit 0
