# Local Development Guide

This guide shows how to run BayanLab Backbone locally on your Mac without Docker (except for PostgreSQL).

## Prerequisites

- Python 3.11+
- uv package manager
- Docker (only for PostgreSQL)

## Setup Steps

### 1. Install Python Dependencies

From the **repository root** (`/bayanlab/`):

```bash
cd /Users/hfox/Developments/bayanlab

# Sync dependencies
uv sync

# Or install manually
uv pip install -e .
```

### 2. Start PostgreSQL (Docker)

```bash
# Start PostgreSQL with PostGIS
docker run -d \
  --name bayan-postgres \
  -e POSTGRES_DB=bayan_backbone \
  -e POSTGRES_USER=bayan \
  -e POSTGRES_PASSWORD=bayan \
  -p 5432:5432 \
  -v $(pwd)/backend/sql:/docker-entrypoint-initdb.d:ro \
  postgis/postgis:15-3.3-alpine

# Check it's running
docker ps | grep bayan-postgres

# View logs
docker logs bayan-postgres
```

The SQL migrations in `/backend/sql/` will run automatically on first start.

### 3. Set Up Environment

```bash
# Create .env file
cat > backend/.env << 'EOF'
DATABASE_URL=postgresql+asyncpg://bayan:bayan@localhost:5432/bayan_backbone
DATABASE_URL_SYNC=postgresql://bayan:bayan@localhost:5432/bayan_backbone
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO
DEFAULT_REGION=CO
EOF
```

### 4. Verify Database Setup

```bash
# Connect to database
docker exec -it bayan-postgres psql -U bayan -d bayan_backbone

# Check tables exist
\dt

# Should see:
# - staging_events
# - staging_businesses
# - event_canonical
# - business_canonical
# - build_metadata
# - migration_history

# Exit
\q
```

### 5. Run Tests

```bash
cd backbone

# Run unit tests
pytest tests/unit/ -v

# Run all tests
pytest tests/ -v
```

### 6. Run Pipeline

```bash
cd backbone

# Run full pipeline
python services/pipeline_runner.py --pipeline all

# Or run individual pipelines
python services/pipeline_runner.py --pipeline events
python services/pipeline_runner.py --pipeline businesses
```

### 7. Start API Server

```bash
cd backbone

# Run API with auto-reload
uvicorn services.api_service.main:app --reload --host 0.0.0.0 --port 8000

# API available at:
# http://localhost:8000
# http://localhost:8000/docs (Swagger UI)
```

### 8. Test API Endpoints

```bash
# Get events
curl "http://localhost:8000/v1/events?region=CO&limit=5" | jq

# Get businesses
curl "http://localhost:8000/v1/businesses?region=CO&limit=5" | jq

# Get metrics
curl "http://localhost:8000/v1/metrics" | jq

# Check health
curl "http://localhost:8000/healthz"
```

## Development Workflow

### Making Changes

1. **Edit code** in your IDE
2. **Run tests** to verify: `pytest tests/unit/test_models.py -v`
3. **Test manually** with the API running
4. **Run pipeline** to test end-to-end

### Debugging

```bash
# Run with debugger
python -m pdb services/pipeline_runner.py --pipeline events

# Or use VS Code debugger with this launch.json:
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: Pipeline",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/backend/services/pipeline_runner.py",
      "args": ["--pipeline", "all"],
      "console": "integratedTerminal",
      "cwd": "${workspaceFolder}/backend"
    },
    {
      "name": "Python: API",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["services.api_service.main:app", "--reload"],
      "console": "integratedTerminal",
      "cwd": "${workspaceFolder}/backend"
    }
  ]
}
```

### Database Management

```bash
# Reset database (WARNING: deletes all data)
docker exec bayan-postgres psql -U bayan -d bayan_backbone -c "
  TRUNCATE staging_events, staging_businesses, event_canonical, business_canonical, build_metadata CASCADE;
"

# Restart PostgreSQL
docker restart bayan-postgres

# Stop PostgreSQL
docker stop bayan-postgres

# Remove PostgreSQL (and all data)
docker rm -f bayan-postgres
```

### Run Individual Services

```bash
cd backbone

# ICS Poller
python -c "from services.ingest.ics_poller import ICSPoller; ICSPoller().run()"

# CSV Loader
python -c "from services.ingest.csv_loader import CSVLoader; CSVLoader().run()"

# Normalizer
python -c "from services.process.normalizer import Normalizer; Normalizer().run()"

# Exporter
python -c "from services.publish.exporter import Exporter; Exporter().run()"
```

## Troubleshooting

### "No module named 'services'"

Make sure you're running from `/backend/` directory and PYTHONPATH is set:

```bash
export PYTHONPATH=/Users/hfox/Developments/bayanlab/backend:$PYTHONPATH
cd /Users/hfox/Developments/bayanlab/backend
python services/pipeline_runner.py --pipeline all
```

### Database Connection Errors

```bash
# Check PostgreSQL is running
docker ps | grep bayan-postgres

# Check logs
docker logs bayan-postgres

# Test connection
psql postgresql://bayan:bayan@localhost:5432/bayan_backbone -c "SELECT 1;"
```

### Import Errors

```bash
# Reinstall dependencies
cd /Users/hfox/Developments/bayanlab
uv sync

# Or
uv pip install -e .
```

## VS Code Setup

Create `.vscode/settings.json`:

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "python.analysis.extraPaths": [
    "${workspaceFolder}/backend"
  ],
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": [
    "backend/tests"
  ],
  "python.formatting.provider": "black",
  "python.linting.enabled": true,
  "python.linting.ruffEnabled": true,
  "[python]": {
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.organizeImports": true
    }
  }
}
```

## When to Use Docker

Use Docker for:
- **CI/CD pipelines** - Consistent environment
- **Production deployment** - Easier to deploy
- **Team sharing** - "Works on my machine" prevention
- **Integration tests** - Full stack testing

Don't use Docker for:
- **Daily development** - Slower iteration
- **Unit tests** - Should run without containers
- **Debugging** - Harder to debug in containers
