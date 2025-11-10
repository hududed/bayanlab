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

## Next Steps

1. **Test the system:** Run QA checklist (`./test_qa.sh`)
2. **Add real data:** Replace sample ICS URLs in `sources.yaml`
3. **Set up Google Calendar API:** See [google-calendar.md](google-calendar.md)
4. **Onboard masjids:** Share [masjid-onboarding.md](masjid-onboarding.md)
5. **Deploy to production:** See [architecture.md](architecture.md) for deployment guide

---

**Support:** info@bayanlab.com
**Issues:** https://github.com/bayanlab/backbone/issues
