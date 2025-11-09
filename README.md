# BayanLab — Community Data Backbone

> *BAYĀN (البيان) = clarity/eloquence* — Our mission is to make community data clear, current, and consumable.

A scalable data backbone for Muslim community events and halal businesses, starting with Colorado and designed for nationwide and international expansion.

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

- **[Setup Guide](docs/README.md)** - Detailed installation and configuration
- **[Local Development](docs/LOCAL_DEVELOPMENT.md)** - Development workflow
- **[API Reference](http://localhost:8000/docs)** - Interactive API docs (when running)

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
