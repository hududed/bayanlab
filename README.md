# BayanLab — Community Data Backbone

> *BAYĀN (البيان) = clarity/eloquence* — Our mission is to make community data clear, current, and consumable.

A scalable data backbone for Muslim community events, halal businesses, and halal eateries. Starting with Colorado and designed for nationwide expansion.

---

## Features

- **Events Pipeline**: Ingest from Google Calendar/ICS feeds and CSV
- **Businesses Pipeline**: Muslim-owned businesses from claims, CSV, OpenStreetMap
- **Halal Eateries**: Community-sourced halal restaurant directory
- **Read-Only API**: FastAPI endpoints with filtering, pagination, and metrics
- **Multi-Region Architecture**: Start with CO, expand to US-wide

## Quick Start

```bash
# Clone and install
git clone https://github.com/hududed/bayanlab.git
cd bayanlab
uv sync

# Start database
cd infra/docker && docker-compose up -d && cd ../..

# Run pipeline (events + businesses)
uv run python run_pipeline.py --pipeline all

# Start API
uv run uvicorn backend.services.api_service.main:app --reload

# Access API docs
open http://localhost:8000/docs
```

## API Endpoints

```bash
# Events
curl "http://localhost:8000/v1/events?region=CO"

# Businesses (ProWasl)
curl "http://localhost:8000/v1/businesses?region=CO"

# Halal Eateries (Ummah App)
curl "http://localhost:8000/v1/halal-eateries?region=CO"

# Metrics
curl "http://localhost:8000/v1/metrics"
```

## Project Structure

```
bayanlab/
├── backend/
│   ├── services/        # API, ingest, process, publish
│   ├── configs/         # YAML configuration
│   ├── sql/             # Database migrations
│   └── tests/           # Unit and E2E tests
├── scripts/             # Utility scripts (enrichment, geocoding)
├── infra/               # Docker, deployment configs
├── seed/                # Sample data
├── docs/                # Documentation
└── exports/             # Generated JSON files
```

## Documentation

- **[docs/setup.md](docs/setup.md)** - Complete setup guide
- **[docs/DECISIONS.md](docs/DECISIONS.md)** - Architecture Decision Records
- **[docs/onboarding_masjids.md](docs/onboarding_masjids.md)** - Masjid calendar setup
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Contribution guidelines
- **[CHANGELOG.md](CHANGELOG.md)** - Release history

## Tech Stack

- **Language**: Python 3.11 + uv
- **API**: FastAPI
- **Database**: PostgreSQL 15 + PostGIS (Neon)
- **Deployment**: Render (Docker)

## Data Flow

```
Claims Portal ──┐
ICS Feeds ──────┼──> Staging ──> Normalize ──> Geocode ──> Canonical ──> API
OSM Data ───────┤
Community Lists ┘
```

## Consumers

- **[The Ummah](https://theummah.app)** - Events + Halal Eateries
- **[ProWasl](https://prowasl.com)** - Muslim-owned Businesses

---

## License

Copyright © 2025 BayanLab. All rights reserved.
