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
