# BayanLab — Community Data Backbone

> *BAYĀN (البيان) = clarity/eloquence* — Our mission is to make community data clear, current, and consumable.

A scalable data backbone for Muslim community events and halal businesses, starting with Colorado and designed for nationwide and international expansion.

---

**📚 Documentation Map:**
[Quick Start](QUICKSTART.md) •
[Setup](docs/setup.md) •
[Roadmap](docs/roadmap.md) •
[Decisions](docs/decisions.md) •
[Troubleshooting](docs/troubleshooting.md) •
[Contributing](CONTRIBUTING.md) •
[Changelog](CHANGELOG.md)

---

## Features

- **Events Pipeline**: Ingest from Google Calendar/ICS feeds and CSV
- **Businesses Pipeline**: Aggregate Muslim-owned and halal-certified businesses from CSV, OpenStreetMap, and certifier feeds
- **Read-Only API**: FastAPI endpoints with filtering, pagination, and metrics
- **Static Exports**: JSON files for CDN distribution
- **Multi-Region Architecture**: Start with CO, expand to US-wide and international
- **Data Quality**: Built-in validation and deduplication
- **Docker-Ready**: Full docker-compose setup for local development and production

## Quick Start

```bash
# Clone and install
git clone https://github.com/bayanlab/backbone.git
cd bayanlab
uv sync

# Start database
cd infra/docker
docker-compose up -d

# Run pipeline
cd ../..
uv run python run_pipeline.py --pipeline all

# Start API
uv run uvicorn backend.services.api_service.main:app --reload

# Access API docs
open http://localhost:8000/docs
```

## API Examples

```bash
# Get Colorado events
curl "http://localhost:8000/v1/events?region=CO&limit=10"

# Get halal restaurants in Denver
curl "http://localhost:8000/v1/businesses?region=CO&city=Denver&category=restaurant"

# Get metrics
curl "http://localhost:8000/v1/metrics?region=CO"
```

## Project Structure

```
bayanlab/
├── backend/              # All Python services
│   ├── services/        # Microservices (ingest, process, publish)
│   ├── configs/         # YAML configuration files
│   ├── sql/            # Database schemas
│   └── tests/          # Unit and E2E tests
├── infra/              # Infrastructure (Docker, Terraform)
├── seed/               # Sample data
├── docs/               # Documentation
└── exports/            # Generated JSON files
```

## Documentation

### Getting Started
- **[QUICKSTART.md](QUICKSTART.md)** - 5-minute setup
- **[docs/setup.md](docs/setup.md)** - Complete setup & development guide
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - How to contribute (internal team only)

### Core Docs
- **[docs/roadmap.md](docs/roadmap.md)** - Product vision & current sprint
- **[docs/decisions.md](docs/decisions.md)** - Architectural Decision Records (ADRs)
- **[docs/troubleshooting.md](docs/troubleshooting.md)** - Common issues & solutions

### Reference
- **[CHANGELOG.md](CHANGELOG.md)** - Release history
- **[QA_CHECKLIST.md](QA_CHECKLIST.md)** - Validation checklist
- **[backend/sql/views.md](backend/sql/views.md)** - Database views & queries
- **[API Docs](http://localhost:8000/docs)** - Interactive OpenAPI docs (when running)

### Onboarding
- **[docs/google-calendar.md](docs/GOOGLE_CALENDAR_SETUP.md)** - Setup Google Calendar API
- **[docs/masjid-onboarding.md](docs/MASJID_ONBOARDING.md)** - Share your calendar with BayanLab

## Tech Stack

- **Language**: Python 3.11
- **API**: FastAPI
- **Database**: PostgreSQL 15 + PostGIS
- **Package Manager**: uv
- **Runtime**: Docker + docker-compose

## Adding New Regions

1. Update `backend/configs/regions.yaml` with new region (bbox, timezone, codes)
2. Add region-specific sources to `backend/configs/sources.yaml`
3. Run pipeline: `uv run python run_pipeline.py --pipeline all`

Example:
```yaml
# configs/regions.yaml
regions:
  US-CA:  # California
    name: "California"
    bbox: {west: -124.41, south: 32.53, east: -114.13, north: 42.01}
    timezone: "America/Los_Angeles"
    state_code: "CA"
```

## Data Flow

```
ICS Feeds ──┐
CSV Files ──┼──> Staging ──> Normalize ──> Geocode ──> DQ Checks ──> Canonical ──> API + Exports
OSM Data ───┤
Certifiers ─┘
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

## License

Copyright © 2025 BayanLab. All rights reserved.

## Contact

- **Website**: https://bayanlab.com
- **Email**: info@bayanlab.com
- **Issues**: https://github.com/bayanlab/backbone/issues

---

**Consumers**: Built for [The Ummah](https://theummah.app) (events) and [ProWasl](https://prowasl.com) (businesses)
