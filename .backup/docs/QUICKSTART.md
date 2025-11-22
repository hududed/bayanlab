# BayanLab Backbone - Quick Start Guide

## ✅ System Status

**All systems operational!** The backbone has been fully restructured and tested.

- ✅ Clean repository structure (`backend/` instead of `backbone/`)
- ✅ All SQL queries properly wrapped with `text()`
- ✅ CSV/seed data loading correctly
- ✅ OSM integration fetching real halal businesses from Colorado
- ✅ Pipeline running end-to-end successfully
- ✅ API endpoints working
- ✅ Static exports generating

## Quick Start (5 minutes)

```bash
# 1. Start database
cd infra/docker
docker-compose up -d db
cd ../..

# 2. Run pipeline
uv run python run_pipeline.py --pipeline all

# 3. Start API
uv run uvicorn backend.services.api_service.main:app --reload

# 4. Test API
curl http://localhost:8000/v1/metrics
curl http://localhost:8000/v1/events?region=CO
curl http://localhost:8000/v1/businesses?region=CO&category=restaurant

# 5. View interactive docs
open http://localhost:8000/docs
```

## What You Get

### Data Ingested
- **5 events** from CSV (`seed/events.csv`)
- **5 businesses** from CSV (`seed/businesses.csv`)
- **6+ halal businesses** from OpenStreetMap (Denver/Colorado Springs)
- **2 certified businesses** from ISNA certifier feed

### API Endpoints Available
- `GET /v1/events?region=CO` - Query events
- `GET /v1/businesses?region=CO` - Query businesses  
- `GET /v1/metrics` - System metrics

### Static Exports Generated
- `exports/CO-events.json` - All Colorado events
- `exports/CO-businesses.json` - All Colorado businesses

## Pipeline Details

The pipeline runs 4 stages:

```
INGEST → PROCESS → CANONICAL → PUBLISH
```

**Ingest Services:**
- ICS Poller (Google Calendar feeds - URLs are placeholders)
- CSV Loader (loads sample events/businesses)
- OSM Importer (fetches real halal businesses via Overpass API)
- Certifier Importer (loads halal-certified businesses)

**Process Services:**
- Normalizer (converts to canonical format)
- Geocoder (fills missing coordinates via Nominatim)
- Placekeyer (generates Placekeys for deduplication - requires API key)
- DQ Checker (validates data quality)

**Publish Services:**
- Exporter (generates static JSON files)
- API Service (FastAPI endpoints)

## Sample Data

The system comes with sample data in `seed/`:

**Events:** 5 Colorado Muslim community events
- Jummah prayers in Denver
- Quran study in Aurora
- Youth basketball in Boulder
- Community iftar in Colorado Springs
- Islamic history lecture in Denver

**Businesses:** 5 halal businesses
- Zabiha Halal Market (grocery)
- Mediterranean Grill (restaurant)
- Crescent Moon Cafe (restaurant)
- Salam Halal Butcher (butcher)
- Al-Noor Bookstore (retail)

**OSM Data:** 6+ real halal businesses from Denver/Colorado Springs area
- Zamzam Halal International Market & Deli
- Jerusalem Restaurant
- And more from OpenStreetMap...

## Expected Pipeline Output

```json
{"level": "INFO", "service": "pipeline_runner", "message": "Starting events pipeline"}
{"level": "INFO", "message": "Loaded 5 events from events.csv"}
{"level": "INFO", "message": "Loaded 5 businesses from businesses.csv"}
{"level": "INFO", "message": "Ingested 6 businesses from OSM query halal_restaurants_denver_metro"}
{"level": "INFO", "message": "Ingested 2 businesses from certifier isna_halal_colorado"}
{"level": "INFO", "message": "Normalized 5 events"}
{"level": "INFO", "message": "Normalized 13 businesses"}
{"level": "INFO", "message": "Geocoded 2 businesses"}
{"level": "INFO", "message": "DQ checks completed: 3 errors, 4 warnings"}
```

**Note:** 3 DQ errors are expected (OSM data missing some required fields like street addresses).

## Configuration

All configuration is in `backend/configs/`:

- `regions.yaml` - Colorado region with bbox, timezone
- `sources.yaml` - Data sources (ICS feeds, CSV paths, OSM queries)
- `dq_rules.yaml` - Data quality validation rules

## Architecture

```
backend/
├── services/
│   ├── api_service/       # FastAPI endpoints
│   ├── ingest/           # ICS, CSV, OSM, Certifier importers
│   ├── process/          # Normalizer, Geocoder, Placekeyer, DQ
│   ├── publish/          # Exporter
│   └── common/           # Config, Logger, Database
├── configs/              # YAML configuration
├── sql/                  # PostgreSQL schemas
└── tests/                # Unit and E2E tests

infra/
└── docker/               # Docker Compose setup

seed/                     # Sample data (CSV files)
exports/                  # Generated JSON exports
docs/                     # Documentation
```

## Next Steps

1. **Replace placeholder ICS feeds** in `backend/configs/sources.yaml` with real Google Calendar URLs
2. **Add your data** to `seed/events.csv` and `seed/businesses.csv`
3. **Add new regions** by updating `backend/configs/regions.yaml`
4. **Configure Placekey API** in `.env` for business deduplication
5. **Deploy to production** using Docker Compose

## Full Documentation

- **[Setup Guide](docs/README.md)** - Complete installation instructions
- **[Local Development](docs/LOCAL_DEVELOPMENT.md)** - Development workflow
- **[QA Checklist](QA_CHECKLIST.md)** - Test the system thoroughly
- **[API Docs](http://localhost:8000/docs)** - Interactive API reference (when running)

## Tech Stack

- **Python 3.11** with `uv` package manager
- **PostgreSQL 15 + PostGIS** for geospatial data
- **FastAPI** for read-only API
- **SQLAlchemy 2.0** for database ORM
- **Docker Compose** for local development

## Support

- **Issues:** https://github.com/bayanlab/backbone/issues
- **Email:** info@bayanlab.com

---

**Built for:** The Ummah (events) and ProWasl (businesses)
**Last Updated:** November 9, 2025
