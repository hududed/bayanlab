# BayanLab Community Data Backbone - Setup Guide

**BAYĀN (البيان) = clarity/eloquence** — Our mission is to make community data clear, current, and consumable.

## Overview

The BayanLab Community Data Backbone is a regional data pipeline that ingests, normalizes, and publishes:
- **Events** (masjid/community gatherings) from Google Calendar/ICS and CSV
- **Businesses** (self-identified Muslim-owned + halal-certified) from CSV, OpenStreetMap, and certifier feeds

**Starting Region:** Colorado (CO), designed for multi-region expansion (US-wide, international)

**Primary Consumers:** The Ummah app (events) and ProWasl (businesses)

## Prerequisites

- **Docker & Docker Compose** (for database)
- **Python 3.11+**
- **uv** package manager: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **PostgreSQL client** (optional, for manual SQL operations)

## Installation

### Option 1: Full Docker Setup (Recommended for Production)

```bash
# Start all services
cd infra/docker
docker-compose up -d

# Check logs
docker-compose logs -f

# Run pipeline
docker-compose run --rm pipeline

# API available at http://localhost:8000
# Docs at http://localhost:8000/docs
```

### Option 2: Local Development (Recommended for Development)

```bash
# 1. Install dependencies
uv sync

# 2. Set up environment
cp .env.example .env
# Edit .env with your settings (database URL, API keys, etc.)

# 3. Start PostgreSQL with PostGIS
cd infra/docker
docker-compose up -d db
cd ../..

# 4. Run database migrations
psql -h localhost -p 5433 -U bayan -d bayan_backbone -f backend/sql/000_init.sql
psql -h localhost -p 5433 -U bayan -d bayan_backbone -f backend/sql/010_staging.sql
psql -h localhost -p 5433 -U bayan -d bayan_backbone -f backend/sql/020_canonical.sql
psql -h localhost -p 5433 -U bayan -d bayan_backbone -f backend/sql/030_views.sql

# 5. Run pipeline
uv run python run_pipeline.py --pipeline all

# 6. Start API
uv run uvicorn backend.services.api_service.main:app --reload
```

## API Endpoints

### Events

```bash
# Get all events for Colorado
curl "http://localhost:8000/v1/events?region=CO"

# Filter by city
curl "http://localhost:8000/v1/events?region=CO&city=Denver"

# Pagination
curl "http://localhost:8000/v1/events?region=CO&limit=10&offset=0"

# Get recent updates
curl "http://localhost:8000/v1/events?region=CO&updated_since=2025-11-01T00:00:00Z"
```

### Businesses

```bash
# Get all businesses for Colorado
curl "http://localhost:8000/v1/businesses?region=CO"

# Filter by category
curl "http://localhost:8000/v1/businesses?region=CO&category=restaurant"

# Filter by city and halal certification
curl "http://localhost:8000/v1/businesses?region=CO&city=Denver&halal_certified=true"
```

### Metrics

```bash
# Get overall metrics
curl "http://localhost:8000/v1/metrics"

# Get region-specific metrics
curl "http://localhost:8000/v1/metrics?region=CO"
```

## Static Exports

After running the pipeline, static JSON files are generated in `/exports/`:

- `exports/CO-events.json` - All Colorado events
- `exports/CO-businesses.json` - All Colorado businesses

These files can be served directly via CDN or consumed by your frontend.

## Architecture

```
┌─────────────┐
│   INGEST    │  ICS Poller, CSV Loader, OSM Import, Certifier Import
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   STAGING   │  Raw data from all sources
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   PROCESS   │  Normalizer → Geocoder → Placekeyer → DQ Checks
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  CANONICAL  │  Clean, validated, deduplicated data
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   PUBLISH   │  API Service + Static JSON Exports
└─────────────┘
```

### Services

**Ingest Services:**
- `ics_poller` - Poll ICS/iCalendar feeds from Google Calendar
- `csv_loader` - Load events & businesses from CSV files
- `osm_import` - Import businesses from OpenStreetMap via Overpass API
- `certifier_import` - Import halal-certified businesses from certifier CSVs (ISNA, IFANCA, etc.)

**Process Services:**
- `normalizer` - Convert staging data to canonical format
- `geocoder` - Fill missing coordinates using Nominatim
- `placekeyer` - Generate Placekeys for deduplication (requires API key)
- `dq_checks` - Data quality validation (missing fields, duplicates, bbox checks)

**Publish Services:**
- `api_service` - FastAPI read-only endpoints with filtering and pagination
- `exporter` - Generate static JSON files for CDN distribution

## Configuration

All configuration is in `backend/configs/`:

### `regions.yaml`
Defines regions with bounding boxes, timezones, and state codes:

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

### `sources.yaml`
Defines data sources for each region:

```yaml
ics_sources:
  - id: "denver_masjid"
    url: "https://calendar.google.com/calendar/ical/..."
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
      out body;
```

### `dq_rules.yaml`
Data quality validation rules:

```yaml
events:
  required_fields: [title, start_time, city, state]
  warnings:
    - old_event_days: 30

businesses:
  required_fields: [name, city, state, category]
  warnings:
    - missing_coords: true
```

## Adding a New Region

1. **Add region to `backend/configs/regions.yaml`:**
```yaml
regions:
  US-CA:
    name: "California"
    bbox: {west: -124.41, south: 32.53, east: -114.13, north: 42.01}
    timezone: "America/Los_Angeles"
    state_code: "CA"
```

2. **Add sources to `backend/configs/sources.yaml`:**
```yaml
ics_sources:
  - id: "sf_masjid"
    url: "https://calendar.google.com/..."
    city: "San Francisco"
    enabled: true

osm_queries:
  - id: "halal_sf"
    region: "US-CA"
    bbox: [-122.5149, 37.7089, -122.3549, 37.8324]
    query_template: ...
```

3. **Run pipeline:**
```bash
uv run python run_pipeline.py --pipeline all
```

## Development

### Project Structure

```
backend/
├── services/
│   ├── api_service/          # FastAPI application
│   ├── common/               # Shared utilities (config, logger, database)
│   ├── ingest/               # Data ingestion services
│   │   ├── ics_poller/
│   │   ├── csv_loader/
│   │   ├── osm_import/
│   │   └── certifier_import/
│   ├── process/              # Data processing services
│   │   ├── normalizer/
│   │   ├── geocoder/
│   │   ├── placekeyer/
│   │   └── dq_checks/
│   ├── publish/              # Publishing services
│   │   └── exporter/
│   └── pipeline_runner.py    # Main pipeline orchestrator
├── configs/                  # YAML configuration files
├── sql/                      # Database schemas
└── tests/                    # Tests
```

### Running Tests

```bash
# Run all tests
uv run pytest backend/tests/ -v

# Run with coverage
uv run pytest backend/tests/ --cov=backend --cov-report=html

# Run specific test
uv run pytest backend/tests/unit/test_models.py -v
```

### Code Quality

```bash
# Format code
uv run black backend/

# Lint code
uv run ruff backend/

# Type checking
uv run mypy backend/
```

## Troubleshooting

### Database Connection Issues

```bash
# Check if database is running
docker ps | grep postgres

# Check database logs
docker logs bayan-db

# Test connection
psql -h localhost -p 5433 -U bayan -d bayan_backbone -c "SELECT version();"
```

### Pipeline Errors

```bash
# Run with verbose logging
LOG_LEVEL=DEBUG uv run python run_pipeline.py --pipeline all

# Check specific pipeline
uv run python run_pipeline.py --pipeline events
uv run python run_pipeline.py --pipeline businesses
```

### API Issues

```bash
# Check API logs
tail -f pipeline.log

# Test API health
curl http://localhost:8000/health

# View interactive docs
open http://localhost:8000/docs
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://bayan:bayan@localhost:5433/bayan_backbone
DATABASE_URL_SYNC=postgresql://bayan:bayan@localhost:5433/bayan_backbone

# API
API_HOST=0.0.0.0
API_PORT=8000

# Geocoding
GEOCODER_PROVIDER=nominatim
GEOCODER_USER_AGENT=BayanLab/1.0
GEOCODER_RATE_LIMIT=1.0

# Placekey (optional, for deduplication)
PLACEKEY_API_KEY=your_api_key_here

# Region
DEFAULT_REGION=CO

# Logging
LOG_LEVEL=INFO
```

## License

Copyright © 2025 BayanLab. All rights reserved.

## Support

- **Issues**: https://github.com/bayanlab/backbone/issues
- **Email**: info@bayanlab.com
- **Docs**: https://docs.bayanlab.com
