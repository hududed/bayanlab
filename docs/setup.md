# BayanLab Setup Guide

Complete setup guide for BayanLab Community Data Backbone.

---

## Quick Start (5 min)

```bash
# 1. Clone & install
git clone https://github.com/bayanlab/backbone.git
cd bayanlab
uv sync

# 2. Environment
cp .env.example .env

# 3. Start database
cd infra/docker && docker-compose up -d db && cd ../..

# 4. Run pipeline
uv run python run_pipeline.py --pipeline all

# 5. Start API
uv run uvicorn backend.services.api_service.main:app --reload

# 6. Test
curl http://localhost:8000/v1/metrics
open http://localhost:8000/docs
```

---

## Prerequisites

- **Docker** (for PostgreSQL)
- **Python 3.11+**
- **uv**: `curl -LsSf https://astral.sh/uv/install.sh | sh`

---

## Architecture

```
Sources → Ingest → Staging → Process → Canonical → Publish (API)
```

**Tables:**
- `staging_*` - Raw JSONB data
- `*_canonical` - Validated schema
- Specialized: `masajid`, `halal_eateries`, `halal_markets`, `nonprofits`

---

## Configuration

### Environment (.env)

```bash
DATABASE_URL=postgresql+asyncpg://bayan:bayan@localhost:5432/bayan_backbone
DATABASE_URL_SYNC=postgresql://bayan:bayan@localhost:5432/bayan_backbone
DEFAULT_REGION=CO
```

### Data Sources (backend/configs/sources.yaml)

```yaml
ics_sources:
  - id: "denver_masjid"
    calendar_id: "calendar@example.com"
    venue_name: "Denver Islamic Society"
    enabled: true
```

---

## Common Commands

```bash
# Run pipeline
uv run python run_pipeline.py --pipeline all
uv run python run_pipeline.py --pipeline events
uv run python run_pipeline.py --pipeline businesses

# Start API (dev)
uv run uvicorn backend.services.api_service.main:app --reload

# Run tests
uv run pytest backend/tests/ -v

# Database
docker exec -it $(docker ps -qf "name=postgres") psql -U bayan -d bayan_backbone
```

---

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /v1/events?region=CO` | List events |
| `GET /v1/businesses?region=CO` | List businesses |
| `GET /v1/metrics` | System metrics |
| `GET /healthz` | Health check |
| `GET /metrics` | Prometheus metrics |

**Rate Limit:** 100 req/min per IP

---

## Cron Scheduling

```bash
# Install crontab (runs every 4 hours)
cp scripts/crontab.example scripts/crontab
# Edit PROJECT_ROOT path
crontab scripts/crontab

# Monitor
tail -f logs/cron.log
```

---

## Database Backups

```bash
# Manual backup
./scripts/backup_database.sh

# Restore
./scripts/restore_database.sh
```

Backups run daily at 3am with 30-day retention.

---

## Troubleshooting

**"No module named backend"** → Run from repo root

**"Database connection refused"** → `docker-compose up -d db`

**Pipeline errors** → Check `LOG_LEVEL=DEBUG`

---

## Related Docs

- [DECISIONS.md](DECISIONS.md) - Architecture decisions
- [SECURITY.md](SECURITY.md) - Security configuration
- [scripts/README.md](../scripts/README.md) - Automation scripts

---

*Last updated: November 2025*
