# BayanLab Scripts

Automation scripts for production deployment and maintenance.

## Files

### `run_pipeline_cron.sh`
Production-ready cron wrapper for running the pipeline automatically.

**Features:**
- Error handling and exit codes
- Automatic log file creation with timestamps
- Email notifications on failure (optional)
- Database connectivity checks
- Auto-cleanup of old logs (30-day retention)

**Usage:**
```bash
# Run manually
./scripts/run_pipeline_cron.sh all

# Available pipeline types
./scripts/run_pipeline_cron.sh events
./scripts/run_pipeline_cron.sh businesses
./scripts/run_pipeline_cron.sh all
```

**Environment Variables:**
- `SEND_EMAIL=true` - Enable email notifications
- `EMAIL_TO=your@email.com` - Recipient email address
- `EMAIL_FROM=noreply@bayanlab.com` - Sender email address

### `crontab.example`
Example crontab configuration for automated pipeline execution.

**Default Schedule:** Every 4 hours

**Installation:**
```bash
# 1. Copy and customize
cp scripts/crontab.example scripts/crontab
nano scripts/crontab  # Edit PROJECT_ROOT path

# 2. Install
crontab scripts/crontab

# 3. Verify
crontab -l
```

### `logrotate.conf`
Logrotate configuration for managing pipeline logs.

**Retention:**
- Pipeline logs: 30 days (daily rotation)
- Cron logs: 12 weeks (weekly rotation)

**Installation:**
```bash
# System-wide (Linux)
sudo cp scripts/logrotate.conf /etc/logrotate.d/bayanlab

# Manual rotation
logrotate -f scripts/logrotate.conf
```

### `backup_database.sh`
Automated database backup script with retention management.

**Features:**
- Full PostgreSQL database dumps (compressed with gzip)
- Automatic 30-day retention (configurable)
- Backup integrity verification
- Metadata tracking (database size, record counts)
- Email notifications on failure (optional)
- Uses Docker pg_dump for version compatibility

**Usage:**
```bash
# Run manual backup
./scripts/backup_database.sh

# With custom retention
RETENTION_DAYS=60 ./scripts/backup_database.sh

# With email notifications
SEND_EMAIL=true EMAIL_TO=admin@example.com ./scripts/backup_database.sh
```

**Environment Variables:**
- `BACKUP_DIR` - Backup directory (default: `$PROJECT_ROOT/backups`)
- `RETENTION_DAYS` - Days to keep backups (default: 30)
- `DB_HOST` - Database host (default: localhost)
- `DB_PORT` - Database port (default: 5433)
- `DB_NAME` - Database name (default: bayan_backbone)
- `DB_USER` - Database user (default: bayan)
- `PGPASSWORD` - Database password (default: bayan)
- `SEND_EMAIL` - Enable email notifications (default: false)
- `EMAIL_TO` - Recipient email
- `EMAIL_FROM` - Sender email

**Output:**
- Backup file: `backups/bayan_backbone_YYYYMMDD_HHMMSS.sql.gz`
- Metadata: `backups/bayan_backbone_YYYYMMDD_HHMMSS.meta`

### `restore_database.sh`
Database restore script from backup files.

**Features:**
- Restore from latest or specific backup
- Automatic pre-restore backup creation
- Connection termination before restore
- Verification after restore

**Usage:**
```bash
# Restore from latest backup
./scripts/restore_database.sh

# Restore from specific backup
./scripts/restore_database.sh backups/bayan_backbone_20251110_154934.sql.gz

# Restore to different database
DB_NAME=bayan_test ./scripts/restore_database.sh
```

**Warning:** This script will **drop and recreate** the target database. Always creates a pre-restore backup for safety.

## Monitoring

### Check Logs
```bash
# Watch cron execution
tail -f logs/cron.log

# View recent pipeline runs
ls -lt logs/pipeline_*.log | head -5

# Search for errors
grep -i error logs/pipeline_*.log
```

### Check Cron Status
```bash
# Verify crontab is installed
crontab -l

# Check cron service (Linux)
systemctl status cron

# Check cron logs (macOS)
tail -f /var/log/system.log | grep cron
```

## Troubleshooting

**Cron not running:**
```bash
# Make script executable
chmod +x scripts/run_pipeline_cron.sh

# Test manually
./scripts/run_pipeline_cron.sh all

# Check cron service
systemctl status cron  # Linux
sudo launchctl list | grep cron  # macOS
```

**Database connection errors:**
```bash
# Verify database is accessible
PGPASSWORD=bayan psql -h localhost -p 5433 -U bayan -d bayan_backbone -c '\q'

# Check database is running
docker ps | grep postgres
```

**Email notifications not working:**
```bash
# Check mail command is available
which mail
which sendmail

# Test email manually
echo "Test" | mail -s "Test Subject" your@email.com
```

## Production Deployment

1. **Set up environment variables** in `~/.bashrc` or `~/.zshrc`:
   ```bash
   export SEND_EMAIL=true
   export EMAIL_TO=your@email.com
   ```

2. **Install crontab**:
   ```bash
   cp scripts/crontab.example scripts/crontab
   # Edit PROJECT_ROOT path
   crontab scripts/crontab
   ```

3. **Monitor first few runs**:
   ```bash
   tail -f logs/cron.log
   ```

4. **Set up log rotation** (optional):
   ```bash
   sudo cp scripts/logrotate.conf /etc/logrotate.d/bayanlab
   ```

See [docs/setup.md](../docs/setup.md) for comprehensive setup guide.

---

## Data Management Scripts

Scripts for managing data migration and geocoding. These are **not tracked in git** as they may contain sensitive configuration.

### `geocode_staging.py` (tracked)
Geocodes businesses in `staging_businesses` table using OSM Nominatim.

**Features:**
- Address cleaning (removes suite numbers, normalizes city names)
- Batch processing with rate limiting
- Supports filtering by source
- Dry-run mode for previewing changes

**Usage:**
```bash
# Preview geocoding (dry run)
uv run python scripts/geocode_staging.py --dry-run

# Geocode specific source
uv run python scripts/geocode_staging.py --source emannest_import --batch 50

# Geocode all pending
uv run python scripts/geocode_staging.py --batch 100
```

### `migrate_masajid.py` (untracked)
Migrates mosques/Islamic centers from `business_claim_submissions` to `masajid` table.

**Usage:**
```bash
# Dry run (preview)
uv run python scripts/migrate_masajid.py

# Execute migration (local DB)
uv run python scripts/migrate_masajid.py --migrate

# Execute on production
uv run python scripts/migrate_masajid.py --migrate --prod

# Delete from claims after migration
uv run python scripts/migrate_masajid.py --migrate --delete
```

**Requires:** `NEON_DB_URL` env var for `--prod` flag.

### `migrate_food.py` (untracked)
Migrates food businesses from `business_claim_submissions` to specialized tables:
- Halal eateries → `halal_eateries`
- Halal markets → `halal_markets`
- Food pantries → `nonprofits` (as food_assistance)
- Hybrid businesses → both eatery and market tables

**Usage:**
```bash
# Dry run (preview)
uv run python scripts/migrate_food.py

# Execute migration
uv run python scripts/migrate_food.py --migrate

# Execute on production with cleanup
uv run python scripts/migrate_food.py --migrate --delete --prod
```

**Requires:** `NEON_DB_URL` env var for `--prod` flag.

### `scripts/archive/`
Contains one-time migration scripts that have been executed and archived for reference.
