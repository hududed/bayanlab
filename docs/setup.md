# Setup Guide

Complete setup and development guide for BayanLab Community Data Backbone.

**Last Updated:** November 10, 2025

---

## Overview

BayanLab Backbone is a **data pipeline and API service** that ingests, processes, and publishes Muslim community events and halal businesses.

**Architecture:** `Sources → Ingest → Staging → Process → Canonical → Publish (API + Exports)`

**Starting Region:** Colorado (CO), designed for multi-region expansion

---

## Prerequisites

- **Docker & Docker Compose** (for PostgreSQL)
- **Python 3.11+**
- **uv** package manager: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **PostgreSQL client** (optional): `brew install postgresql` (macOS)

---

## Quick Start (5 minutes)

```bash
# 1. Clone repository
git clone https://github.com/bayanlab/backbone.git
cd bayanlab

# 2. Install dependencies
uv sync

# 3. Set up environment
cp .env.example .env
# Edit .env if needed (defaults work for local dev)

# 4. Start PostgreSQL
cd infra/docker
docker-compose up -d db
cd ../..

# 5. Run pipeline
uv run python run_pipeline.py --pipeline all

# 6. Start API
uv run uvicorn backend.services.api_service.main:app --reload

# 7. Test API
curl http://localhost:8000/v1/metrics
open http://localhost:8000/docs
```

---

## Architecture Overview

### Data Flow

```
┌─── Sources ────────────────────┐
│ ICS/Calendar, CSV, OSM, Certs │
└───────────┬────────────────────┘
            │
    ┌───────▼────────┐
    │ INGEST SERVICE │
    └───────┬────────┘
            │
    ┌───────▼────────┐
    │ STAGING TABLES │  Raw data (JSONB)
    └───────┬────────┘
            │
    ┌───────▼────────┐
    │ PROCESS SERVICES│  Normalize → Geocode → DQ
    └───────┬────────┘
            │
    ┌───────▼────────┐
    │ CANONICAL TABLES│  Clean, validated data
    └───────┬────────┘
            │
    ┌───────▼────────┐
    │ PUBLISH SERVICES│  API + Static Exports
    └────────────────┘
```

### Services

**Ingest:**
- `ics_poller` - Fetch events from Google Calendar (API or ICS URL)
- `csv_loader` - Load events/businesses from CSV
- `osm_import` - Fetch halal businesses from OpenStreetMap
- `certifier_import` - Load certified businesses from CSV

**Process:**
- `normalizer` - Convert staging → canonical format
- `geocoder` - Fill missing coordinates (Nominatim)
- `placekeyer` - Generate Placekeys for deduplication (optional)
- `dq_checks` - Data quality validation

**Publish:**
- `api_service` - FastAPI read-only endpoints
- `exporter` - Generate static JSON files

### Database Schema

**Staging Tables:** `staging_events`, `staging_businesses` (raw JSONB)

**Canonical Tables:** `event_canonical`, `business_canonical` (validated schema)

**Key Fields:**
- `event_canonical`: event_id, title, start_time, venue_name, city, state, lat/lon, region, source
- `business_canonical`: business_id, name, category, city, state, lat/lon, halal_certified, placekey, region

See [sql/schema.sql](../backend/sql/) for full schema.

---

## Installation Options

### Option 1: Local Development (Recommended)

**Best for:** Daily development, debugging

```bash
# Install Python dependencies
uv sync

# Start PostgreSQL only (runs in Docker)
cd infra/docker
docker-compose up -d db
cd ../..

# Run pipeline natively
uv run python run_pipeline.py --pipeline all

# Start API natively (with hot reload)
uv run uvicorn backend.services.api_service.main:app --reload
```

**Benefits:**
- Fast iteration (hot reload)
- Easy debugging
- Native Python performance

---

### Option 2: Full Docker Setup

**Best for:** Production, CI/CD, team consistency

```bash
# Start all services
cd infra/docker
docker-compose up -d

# Check logs
docker-compose logs -f

# API available at http://localhost:8000
# Docs at http://localhost:8000/docs
```

**Services:**
- `db` - PostgreSQL + PostGIS
- `api` - FastAPI service
- `pipeline` - One-shot pipeline run

---

## Configuration

### Environment Variables (.env)

```bash
# Database
DATABASE_URL=postgresql+asyncpg://bayan:bayan@localhost:5432/bayan_backbone
DATABASE_URL_SYNC=postgresql://bayan:bayan@localhost:5432/bayan_backbone

# API
API_HOST=0.0.0.0
API_PORT=8000

# Google Calendar API (optional)
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json

# Geocoding
GEOCODER_PROVIDER=nominatim
GEOCODER_RATE_LIMIT=1.0

# Placekey (optional)
PLACEKEY_API_KEY=

# Region
DEFAULT_REGION=CO

# Logging
LOG_LEVEL=INFO
```

### Data Sources (backend/configs/sources.yaml)

```yaml
ics_sources:
  - id: "denver_masjid"
    calendar_id: "calendar@example.com"  # Calendar API
    url: "https://calendar.google.com/..." # ICS fallback
    venue_name: "Denver Islamic Society"
    city: "Denver"
    enabled: true

csv_sources:
  events:
    - path: "events.csv"
      enabled: true

osm_queries:
  - id: "halal_restaurants_denver"
    region: "CO"
    bbox: [-105.1099, 39.6144, -104.6002, 39.9142]
    query_template: |
      [out:json];
      (node["cuisine"="halal"]({{bbox}}););
```

### Regions (backend/configs/regions.yaml)

```yaml
regions:
  CO:
    name: "Colorado"
    bbox:
      west: -109.060253
      south: 36.992426
      east: -102.041524
      north: 41.003444
    timezone: "America/Denver"
    state_code: "CO"
```

---

## Development Workflow

### Making Changes

1. **Edit code** in your IDE
2. **Run tests:** `uv run pytest backend/tests/ -v`
3. **Test manually** with API running
4. **Run pipeline** to verify end-to-end

### Running Services Individually

```bash
# ICS Poller only
python -c "from backend.services.ingest.ics_poller import ICSPoller; ICSPoller().run()"

# Normalizer only
python -c "from backend.services.process.normalizer import Normalizer; Normalizer().run()"

# Export only
python -c "from backend.services.publish.exporter import Exporter; Exporter().run()"
```

### Debugging

```bash
# Run with debug logging
LOG_LEVEL=DEBUG uv run python run_pipeline.py --pipeline all

# Use Python debugger
python -m pdb run_pipeline.py --pipeline events

# VS Code launch.json
{
  "name": "Pipeline",
  "type": "python",
  "request": "launch",
  "program": "${workspaceFolder}/run_pipeline.py",
  "args": ["--pipeline", "all"]
}
```

### Database Management

```bash
# Connect to database
docker exec -it $(docker ps -qf "name=postgres") psql -U bayan -d bayan_backbone

# Reset data (WARNING: deletes all data)
psql -h localhost -p 5432 -U bayan -d bayan_backbone -c "
  TRUNCATE staging_events, staging_businesses, event_canonical, business_canonical CASCADE;
"

# Check table sizes
psql -h localhost -p 5432 -U bayan -d bayan_backbone -c "
  SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
  FROM pg_tables WHERE schemaname = 'public';
"
```

---

## API Endpoints

### Events

```bash
# Get all Colorado events
curl "http://localhost:8000/v1/events?region=CO"

# Filter by city
curl "http://localhost:8000/v1/events?region=CO&city=Denver"

# Pagination
curl "http://localhost:8000/v1/events?region=CO&limit=10&offset=0"

# Date range
curl "http://localhost:8000/v1/events?region=CO&start_after=2025-11-10"
```

### Businesses

```bash
# Get all businesses
curl "http://localhost:8000/v1/businesses?region=CO"

# Halal restaurants only
curl "http://localhost:8000/v1/businesses?region=CO&category=restaurant&halal_certified=true"

# By city
curl "http://localhost:8000/v1/businesses?region=CO&city=Denver"
```

### Metrics

```bash
# System metrics
curl "http://localhost:8000/v1/metrics?region=CO"

# Returns:
{
  "region": "CO",
  "events_count": 5,
  "businesses_count": 10,
  "last_updated": "2025-11-09T20:50:31Z"
}
```

---

## Testing

```bash
# Run all tests
uv run pytest backend/tests/ -v

# With coverage
uv run pytest backend/tests/ --cov=backend --cov-report=html
open htmlcov/index.html

# Unit tests only
uv run pytest backend/tests/unit/ -v

# Specific test file
uv run pytest backend/tests/unit/test_models.py -v
```

---

## Common Tasks

### Add a New Region

1. Update `backend/configs/regions.yaml`:
```yaml
US-TX:
  name: "Texas"
  bbox: {west: -106.65, south: 25.84, east: -93.51, north: 36.50}
  timezone: "America/Chicago"
  state_code: "TX"
```

2. Add sources to `backend/configs/sources.yaml`

3. Run pipeline: `uv run python run_pipeline.py --pipeline all`

### Add a New Data Source

Edit `backend/configs/sources.yaml`:
```yaml
ics_sources:
  - id: "new_masjid"
    calendar_id: "newmasjid@gmail.com"
    venue_name: "New Masjid Name"
    city: "Austin"
    enabled: true
```

Run pipeline to ingest.

### Update Dependencies

```bash
# Update all dependencies
uv sync

# Add new dependency
uv add fastapi

# Remove dependency
uv remove package-name
```

---

## Troubleshooting

### Pipeline Errors

**Issue:** "No module named 'backend'"

**Fix:** Always run from repository root:
```bash
cd /path/to/bayanlab
uv run python run_pipeline.py --pipeline all
```

**Issue:** "Database connection refused"

**Fix:** Check PostgreSQL is running:
```bash
docker ps | grep postgres
docker-compose up -d db
```

**Issue:** "ICS fetch 404"

**Fix:** Calendar is private. Use Calendar API mode or make calendar public.

### API Errors

**Issue:** API returns 500

**Fix:** Check database has data:
```sql
SELECT COUNT(*) FROM event_canonical WHERE region = 'CO';
```

**Issue:** Slow API (> 1s)

**Fix:** Check database indexes:
```sql
\d event_canonical  -- Should show indexes on region, city, start_time
```

See [TROUBLESHOOTING.md](troubleshooting.md) for comprehensive guide.

---

## Automated Scheduling

### Production Cron Setup

For production deployments, use cron to run the pipeline automatically every 4 hours.

#### 1. Test the Cron Script

```bash
# Test the script manually first
cd /path/to/bayanlab
./scripts/run_pipeline_cron.sh all

# Check the logs
tail -f logs/cron.log
```

#### 2. Install Crontab

```bash
# Copy example crontab
cp scripts/crontab.example scripts/crontab

# Edit with your project path
nano scripts/crontab
# Change: PROJECT_ROOT=/Users/hfox/Developments/bayanlab
# To:     PROJECT_ROOT=/path/to/your/bayanlab

# Install crontab
crontab scripts/crontab

# Verify installation
crontab -l
```

#### 3. Enable Email Notifications (Optional)

```bash
# Set environment variables for email alerts
export SEND_EMAIL=true
export EMAIL_TO=your-email@example.com
export EMAIL_FROM=noreply@bayanlab.com

# Or add to ~/.bashrc or ~/.zshrc
```

**Note:** Requires `mail` or `sendmail` command available on the system.

#### 4. Monitor Logs

```bash
# Watch cron execution
tail -f logs/cron.log

# View recent pipeline logs
ls -lt logs/pipeline_*.log | head -5

# Check for errors
grep -i error logs/pipeline_*.log
```

### Cron Schedule Options

```bash
# Every 4 hours (default - recommended)
0 */4 * * * cd $PROJECT_ROOT && ./scripts/run_pipeline_cron.sh all

# Every 2 hours (more frequent updates)
0 */2 * * * cd $PROJECT_ROOT && ./scripts/run_pipeline_cron.sh all

# Daily at 6am (less frequent)
0 6 * * * cd $PROJECT_ROOT && ./scripts/run_pipeline_cron.sh all

# Run events and businesses separately
0 */4 * * * cd $PROJECT_ROOT && ./scripts/run_pipeline_cron.sh events
0 */6 * * * cd $PROJECT_ROOT && ./scripts/run_pipeline_cron.sh businesses
```

### Log Rotation

Logs are automatically cleaned up (30-day retention) by the cron script. For more control:

```bash
# Manual logrotate (optional)
logrotate -f scripts/logrotate.conf

# Or install system-wide
sudo cp scripts/logrotate.conf /etc/logrotate.d/bayanlab
```

### Troubleshooting Cron

**Cron not running:**
```bash
# Check cron service
systemctl status cron  # Linux
# or
sudo launchctl list | grep cron  # macOS

# Check cron logs
tail -f /var/log/syslog | grep CRON  # Linux
tail -f /var/log/system.log | grep cron  # macOS
```

**Script permission errors:**
```bash
chmod +x scripts/run_pipeline_cron.sh
```

**Database connection errors:**
```bash
# Verify database is accessible
PGPASSWORD=bayan psql -h localhost -p 5433 -U bayan -d bayan_backbone -c '\q'
```

---

## Health Checks and Monitoring

### Health Check Endpoint

The API provides a `/healthz` endpoint for Kubernetes-style health checks:

```bash
# Check API health
curl http://localhost:8000/healthz

# Healthy response (200):
{
  "status": "healthy",
  "service": "bayan_backbone_api",
  "version": "1.0.0",
  "database": "connected",
  "timestamp": "2025-11-10T22:41:44.412756+00:00"
}

# Unhealthy response (503):
{
  "status": "unhealthy",
  "service": "bayan_backbone_api",
  "database": "disconnected",
  "error": "[Errno 61] Connection refused",
  "timestamp": "2025-11-10T22:41:05.841183+00:00"
}
```

**Features:**
- Returns HTTP 200 when healthy, 503 when unhealthy
- Tests database connectivity automatically
- Includes timestamp for monitoring
- Safe to call frequently (no rate limiting)

### Prometheus Metrics

Prometheus-compatible metrics are available at `/metrics`:

```bash
# Get Prometheus metrics
curl http://localhost:8000/metrics

# Output format:
# HELP bayanlab_events_total Total number of events in database
# TYPE bayanlab_events_total gauge
bayanlab_events_total 108

# HELP bayanlab_businesses_total Total number of businesses in database
# TYPE bayanlab_businesses_total gauge
bayanlab_businesses_total 108

# HELP bayanlab_events_by_region Events count by region
# TYPE bayanlab_events_by_region gauge
bayanlab_events_by_region{region="CO"} 108

# HELP bayanlab_businesses_by_region Businesses count by region
# TYPE bayanlab_businesses_by_region gauge
bayanlab_businesses_by_region{region="CO"} 108
```

**Metrics Available:**
- `bayanlab_events_total` - Total events in database
- `bayanlab_businesses_total` - Total businesses in database
- `bayanlab_events_by_region{region="XX"}` - Events per region
- `bayanlab_businesses_by_region{region="XX"}` - Businesses per region

### Monitoring with Prometheus

**prometheus.yml configuration:**
```yaml
scrape_configs:
  - job_name: 'bayanlab_api'
    scrape_interval: 30s
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

### Simple Health Monitoring

**Shell script for monitoring:**
```bash
#!/bin/bash
# Simple health check script

HEALTH_URL="http://localhost:8000/healthz"

while true; do
  if curl -f -s "$HEALTH_URL" > /dev/null; then
    echo "$(date): API healthy"
  else
    echo "$(date): API unhealthy - sending alert"
    # Send alert (email, Slack, PagerDuty, etc.)
    echo "API down at $(date)" | mail -s "BayanLab API Alert" admin@example.com
  fi
  sleep 60  # Check every minute
done
```

**Cron-based health check:**
```bash
# Add to crontab - check every 5 minutes
*/5 * * * * curl -f http://localhost:8000/healthz || echo "API down at $(date)" >> /var/log/bayanlab_health.log
```

---

## Rate Limiting

The API implements rate limiting to prevent abuse and ensure fair usage for all clients.

### Rate Limits

All API endpoints have the following rate limits per IP address:

| Endpoint | Rate Limit | Notes |
|----------|-----------|-------|
| `/v1/events` | 100 requests/minute | Per IP address |
| `/v1/businesses` | 100 requests/minute | Per IP address |
| `/v1/metrics` | 100 requests/minute | Per IP address |
| `/healthz` | Unlimited | Health checks not rate limited |
| `/metrics` (Prometheus) | Unlimited | Monitoring not rate limited |

### Rate Limit Response

When rate limit is exceeded, the API returns HTTP 429 (Too Many Requests):

```bash
# Example: Make 101 requests in quick succession
curl http://localhost:8000/v1/events?region=CO

# Response after 100 requests:
HTTP/1.1 429 Too Many Requests
{"error":"Rate limit exceeded: 100 per 1 minute"}
```

### Rate Limit Headers

slowapi includes helpful headers in responses:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1699564800
```

### Testing Rate Limits

```bash
# Test script to verify rate limiting
for i in {1..105}; do
  status=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/v1/events?region=CO")
  echo "Request $i: $status"
done

# Expected: First 100 return 200, next 5 return 429
```

### Best Practices for API Consumers

1. **Respect rate limits** - Don't exceed 100 requests/minute
2. **Implement exponential backoff** - Wait before retrying on 429 errors
3. **Cache responses** - Reduce unnecessary API calls
4. **Use pagination** - Request only what you need with `limit` and `offset`
5. **Monitor headers** - Check `X-RateLimit-Remaining` to avoid hitting limits

### Configuring Rate Limits

To adjust rate limits, edit [backend/services/api_service/main.py](../backend/services/api_service/main.py):

```python
@app.get("/v1/events")
@limiter.limit("100/minute")  # Change this value
async def get_events(request: Request, ...):
    ...
```

Common configurations:
- Development: `"1000/minute"` (generous for testing)
- Production: `"100/minute"` (current setting)
- Strict: `"50/minute"` (high-traffic scenarios)

---

## Database Backups

Automated daily backups with 30-day retention ensure data safety and disaster recovery.

### Manual Backup

```bash
# Run backup script
./scripts/backup_database.sh

# Output:
# Backup completed successfully!
# Summary:
#   Database: bayan_backbone (16 MB)
#   Events: 108
#   Businesses: 108
#   Backup: backups/bayan_backbone_20251110_154934.sql.gz (28K)
#   Duration: 1s
#   Retention: 30 days
```

### Automated Backups (Cron)

Backups run daily at 3am (configured in `scripts/crontab.example`):

```bash
# Daily backup at 3am with 30-day retention
0 3 * * * cd $PROJECT_ROOT && ./scripts/backup_database.sh >> logs/backup.log 2>&1
```

### Restore from Backup

```bash
# Restore from latest backup
./scripts/restore_database.sh

# Restore from specific backup
./scripts/restore_database.sh backups/bayan_backbone_20251110_154934.sql.gz
```

**Warning:** Restore will drop and recreate the database. Always creates pre-restore backup for safety.

### Backup Features

- **Automated retention**: Deletes backups older than 30 days
- **Integrity verification**: Tests gzip files after creation
- **Metadata tracking**: JSON metadata with each backup (size, counts, timestamp)
- **Email alerts**: Optional notifications on failure
- **Version compatibility**: Uses Docker pg_dump to match database version

### Monitoring

```bash
# Check backup logs
tail -f logs/backup.log

# List all backups
ls -lh backups/

# View backup metadata
cat backups/bayan_backbone_*.meta | jq .
```

### Configuration

```bash
# Custom retention (60 days)
RETENTION_DAYS=60 ./scripts/backup_database.sh

# Custom location
BACKUP_DIR=/mnt/backups ./scripts/backup_database.sh

# Enable email notifications
SEND_EMAIL=true EMAIL_TO=admin@example.com ./scripts/backup_database.sh
```

See [scripts/README.md](../scripts/README.md) for complete backup documentation.

---

## Business Enrichment Pipeline (ProWasl)

Automated pipeline to enrich Muslim business owner data from Muslim Professionals network.

### Overview

**Goal:** Transform 197 filtered business owners → 10-20 verified Colorado businesses for ProWasl

**Pipeline:**
1. Filter Muslim Professionals CSV → 197 service business owners ✅
2. Google Places API → Get location, phone, website
3. Crawl4AI + LLM → Scrape websites for services, about, team size
4. Manual QA → Verify and onboard to ProWasl

### Step 1: Filter Business Owners (✅ Complete)

```bash
# Filter 7,485 professionals → 197 high-priority owners
python scripts/filter_business_owners.py

# Output:
# - exports/business_filtering/high_priority_owners.csv (197 records)
# - exports/business_filtering/all_business_owners.csv (584 records)
# - exports/business_filtering/service_industry_professionals.csv (2,260 records)
```

### Step 2: Google Places API Enrichment

**Setup (one-time, 10 minutes):**

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create new project "ProWasl" or use existing
3. Enable "Places API (New)"
4. Create API key (restrict to Places API)
5. Add to `.env`:
   ```bash
   GOOGLE_PLACES_API_KEY=your_api_key_here
   ```

**Run enrichment:**

```bash
# Install dependency
uv add googlemaps

# Enrich all 197 businesses (takes ~30 minutes)
uv run python scripts/enrich_google_places.py

# Output: exports/enrichment/google_places_enriched.csv
# Contains: address, city, state, zip, phone, website, hours, rating
```

**Filter for Colorado:**

```bash
# Extract Colorado businesses
grep -i "colorado\|, CO" exports/enrichment/google_places_enriched.csv > exports/enrichment/colorado_businesses.csv

# Count
wc -l exports/enrichment/colorado_businesses.csv
# Expected: 10-20 businesses
```

**Cost:** $0 (free tier covers 11,700 searches/month, you're using 197)

### Step 3: Deep Website Scraping (Crawl4AI)

**Setup:**

```bash
# Install Crawl4AI and LLM provider
uv add crawl4ai openai

# Add OpenAI API key to .env (or use Claude/local LLM)
echo "OPENAI_API_KEY=your_key" >> .env
```

**Run deep scraping:**

```bash
# Scrape Colorado business websites (takes ~1 hour for 20 sites)
uv run python scripts/deep_scrape_websites.py \
  --input exports/enrichment/colorado_businesses.csv \
  --output exports/enrichment/fully_enriched_colorado.csv

# Extracts: services, description, service_area, years_in_business, team_size, certifications
```

**Cost:** ~$0.01 per business with GPT-4o-mini = $0.20 for 20 businesses

### Step 4: Manual QA

For each business:
1. ✅ Google the business (confirm exists)
2. ✅ Call phone number (verify working)
3. ✅ Visit website (still active?)
4. ✅ Check services match ProWasl use case
5. ✅ Add to `business_canonical` table

**Time:** 5-10 min per business = 1-2 hours for 20 businesses

### Fallback Options

If Google Places API unavailable:

**Option A: Crawl4AI Google Search Scraping**
```bash
# Scrape Google search results (slower, less reliable)
uv run python scripts/crawl4ai_google_search.py --limit 197
```

**Option B: Manual LinkedIn Enrichment**
- Use LinkedIn Helper to get city/state from profiles
- Takes 2-5 min per person
- Total: 6-16 hours for 197 people

**Option C: Hire VA on Fiverr**
- $50-100 for someone to enrich 197 businesses manually
- Provide them with template spreadsheet

### Documentation

See detailed guides:
- [docs/complete_enrichment_pipeline.md](complete_enrichment_pipeline.md) - Full pipeline overview
- [docs/google_enrichment_options.md](google_enrichment_options.md) - Alternative approaches
- [docs/business_enrichment_strategy.md](business_enrichment_strategy.md) - Phase 1-3 strategy
- [docs/linkedin_helper_workflow.md](linkedin_helper_workflow.md) - Manual LinkedIn workflow

---

## Next Steps

1. **Test the system:** Run QA checklist (`./test_qa.sh`)
2. **Add real data:** Replace sample ICS URLs in `sources.yaml`
3. **Set up Google Calendar API:** See [google-calendar.md](google-calendar.md)
4. **Onboard masjids:** Share [masjid-onboarding.md](masjid-onboarding.md)
5. **Enrich businesses:** Run enrichment pipeline (see above)
6. **Deploy to production:** See [architecture.md](architecture.md) for deployment guide

---

**Support:** info@bayanlab.com
**Issues:** https://github.com/bayanlab/backbone/issues
