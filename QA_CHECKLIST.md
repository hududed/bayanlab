# BayanLab Backbone - QA Checklist

Use this checklist to verify the system is working correctly after changes.

## Prerequisites Check

- [ ] Python 3.11+ installed: `python --version`
- [ ] uv installed: `uv --version`
- [ ] Docker installed: `docker --version`
- [ ] PostgreSQL client installed (optional): `psql --version`

## 1. Environment Setup

```bash
# Clone/pull latest
cd /Users/hfox/Developments/bayanlab

# Install dependencies
uv sync

# Verify .env exists
ls -la .env

# Check database is running
docker ps | grep postgres
```

**Expected:**
- ✅ Dependencies installed without errors
- ✅ `.env` file exists at root
- ✅ PostgreSQL container running on port 5433

## 2. Database Verification

```bash
# Test database connection
psql -h localhost -p 5433 -U bayan -d bayan_backbone -c "SELECT version();"

# Check PostGIS extension
psql -h localhost -p 5433 -U bayan -d bayan_backbone -c "SELECT PostGIS_Version();"

# Verify tables exist
psql -h localhost -p 5433 -U bayan -d bayan_backbone -c "\dt"
```

**Expected:**
- ✅ PostgreSQL 15.x version shown
- ✅ PostGIS version shown
- ✅ 8 tables: `staging_events`, `staging_businesses`, `event_canonical`, `business_canonical`, `build_metadata`, etc.

## 3. Pipeline Execution

```bash
# Run full pipeline
uv run python run_pipeline.py --pipeline all

# Check for errors in output
echo $?  # Should be 0 for success
```

**Expected Output:**
```json
{"level": "INFO", "service": "pipeline_runner", "message": "Starting events pipeline"}
{"level": "INFO", "service": "pipeline_runner", "message": "ICS poller completed", "count_out": 0}
{"level": "INFO", "service": "pipeline_runner", "message": "Loaded 5 events from events.csv"}
{"level": "INFO", "service": "pipeline_runner", "message": "Loaded 5 businesses from businesses.csv"}
{"level": "INFO", "service": "pipeline_runner", "message": "Ingested 6 businesses from OSM query halal_restaurants_denver_metro"}
{"level": "INFO", "service": "pipeline_runner", "message": "Normalized 5 events"}
{"level": "INFO", "service": "pipeline_runner", "message": "Normalized 13 businesses"}
{"level": "INFO", "service": "pipeline_runner", "message": "DQ checks completed"}
```

**Verify:**
- [ ] No Python import errors
- [ ] CSV files loaded (5 events, 5 businesses)
- [ ] OSM data imported (6+ businesses)
- [ ] Certifier data imported (2 businesses)
- [ ] Normalizer processed all records
- [ ] Geocoder ran (may geocode 0-2 records if coords exist)
- [ ] DQ checks completed (expect 3 errors from OSM missing data - OK)
- [ ] Exit code is 0

## 4. Database Content Verification

```bash
# Check staging tables
psql -h localhost -p 5433 -U bayan -d bayan_backbone -c "SELECT COUNT(*) FROM staging_events;"
psql -h localhost -p 5433 -U bayan -d bayan_backbone -c "SELECT COUNT(*) FROM staging_businesses;"

# Check canonical tables
psql -h localhost -p 5433 -U bayan -d bayan_backbone -c "SELECT COUNT(*) FROM event_canonical;"
psql -h localhost -p 5433 -U bayan -d bayan_backbone -c "SELECT COUNT(*) FROM business_canonical;"

# Sample data check
psql -h localhost -p 5433 -U bayan -d bayan_backbone -c "SELECT title, city, source FROM event_canonical LIMIT 3;"
psql -h localhost -p 5433 -U bayan -d bayan_backbone -c "SELECT name, category, source FROM business_canonical LIMIT 5;"
```

**Expected:**
- [ ] `staging_events`: ~5 records
- [ ] `staging_businesses`: ~13 records (5 CSV + 6 OSM + 2 certifier)
- [ ] `event_canonical`: ~5 records
- [ ] `business_canonical`: ~13 records
- [ ] Records show correct cities (Denver, Boulder, Colorado Springs)
- [ ] Sources: 'csv', 'osm', 'certifier'

## 5. API Testing

```bash
# Start API (in separate terminal)
uv run uvicorn backend.services.api_service.main:app --reload

# Wait for startup, then test endpoints:
```

### Health Check
```bash
curl http://localhost:8000/health
```
**Expected:** `{"status":"healthy"}`

### Metrics Endpoint
```bash
curl http://localhost:8000/v1/metrics
```
**Expected:**
```json
{
  "total_events": 5,
  "total_businesses": 13,
  "regions": ["CO"]
}
```

### Events Endpoint
```bash
# All events
curl "http://localhost:8000/v1/events?region=CO"

# Filter by city
curl "http://localhost:8000/v1/events?region=CO&city=Denver"

# Pagination
curl "http://localhost:8000/v1/events?region=CO&limit=2&offset=0"
```

**Expected:**
- [ ] Returns JSON array of events
- [ ] Each event has: `event_id`, `title`, `start_time`, `city`, `venue`
- [ ] Filtering works correctly
- [ ] Pagination works

### Businesses Endpoint
```bash
# All businesses
curl "http://localhost:8000/v1/businesses?region=CO"

# Filter by category
curl "http://localhost:8000/v1/businesses?region=CO&category=restaurant"

# Filter by city
curl "http://localhost:8000/v1/businesses?region=CO&city=Denver"
```

**Expected:**
- [ ] Returns JSON array of businesses
- [ ] Each business has: `business_id`, `name`, `category`, `city`, `source`
- [ ] Categories include: `restaurant`, `grocery`, `butcher`, `retail`
- [ ] Sources include: `csv`, `osm`, `certifier`

### Interactive Docs
```bash
open http://localhost:8000/docs
```

**Expected:**
- [ ] Swagger UI loads
- [ ] All 3 endpoints visible: `/v1/events`, `/v1/businesses`, `/v1/metrics`
- [ ] Can test endpoints interactively

## 6. Static Exports Verification

```bash
# Check export files exist
ls -lh exports/

# View contents
cat exports/CO-events.json | jq '.count'
cat exports/CO-businesses.json | jq '.count'
```

**Expected:**
- [ ] `exports/CO-events.json` exists
- [ ] `exports/CO-businesses.json` exists
- [ ] Events count: 5
- [ ] Businesses count: 13
- [ ] JSON is valid and formatted

## 7. Configuration Files Check

```bash
# Verify all config files
cat backend/configs/regions.yaml
cat backend/configs/sources.yaml
cat backend/configs/dq_rules.yaml
```

**Expected:**
- [ ] `regions.yaml`: CO region defined with bbox, timezone
- [ ] `sources.yaml`: ICS sources, CSV paths, OSM queries, certifier feeds
- [ ] `dq_rules.yaml`: Event and business validation rules
- [ ] Paths use `events.csv` not `seed/events.csv`

## 8. Code Quality Checks

```bash
# Check imports
grep -r "from services\." backend/services/ | wc -l  # Should be 0
grep -r "from backend.services" backend/services/ | wc -l  # Should be >0

# Check for text() wrapper
grep -r "session.execute(\"" backend/services/ | wc -l  # Should be 0
grep -r "session.execute(text(" backend/services/ | wc -l  # Should be >0
```

**Expected:**
- [ ] No `from services.` imports (should be `from backend.services.`)
- [ ] All SQL queries wrapped with `text()`
- [ ] No duplicate `.gitignore` files
- [ ] No duplicate `pyproject.toml` files

## 9. Error Scenarios Testing

### Test with Invalid Region
```bash
curl "http://localhost:8000/v1/events?region=INVALID"
```
**Expected:** Empty array or appropriate error

### Test Database Connection Failure
```bash
# Stop database
docker stop $(docker ps -q --filter "ancestor=postgis/postgis:15-3.3")

# Try to run pipeline
uv run python run_pipeline.py --pipeline all

# Should fail gracefully with connection error
```

**Expected:**
- [ ] Clear error message about database connection
- [ ] No Python traceback or crash

### Restart Database
```bash
cd infra/docker
docker-compose up -d db
```

## 10. Performance Check

```bash
# Time the pipeline
time uv run python run_pipeline.py --pipeline all
```

**Expected:**
- [ ] Completes in < 30 seconds for sample data
- [ ] No memory errors
- [ ] Reasonable geocoding delay (1 second between requests)

## 11. Logging Verification

```bash
# Check logs are generated
tail -50 pipeline.log

# Verify JSON format
tail -1 pipeline.log | jq .
```

**Expected:**
- [ ] Log file exists
- [ ] Contains structured JSON logs
- [ ] Each log has: `timestamp`, `level`, `service`, `message`
- [ ] No ERROR level logs (except expected DQ errors)

## 12. Clean State Test

```bash
# Truncate all data
psql -h localhost -p 5433 -U bayan -d bayan_backbone << EOF
TRUNCATE TABLE staging_events CASCADE;
TRUNCATE TABLE staging_businesses CASCADE;
TRUNCATE TABLE event_canonical CASCADE;
TRUNCATE TABLE business_canonical CASCADE;
TRUNCATE TABLE build_metadata CASCADE;
EOF

# Re-run pipeline
uv run python run_pipeline.py --pipeline all

# Verify data is back
psql -h localhost -p 5433 -U bayan -d bayan_backbone -c "SELECT COUNT(*) FROM event_canonical;"
```

**Expected:**
- [ ] Clean truncate works
- [ ] Pipeline re-populates all data
- [ ] Same counts as before

## Summary Checklist

### Critical (Must Pass)
- [ ] Database connection works
- [ ] Pipeline runs without Python errors
- [ ] Data appears in canonical tables
- [ ] API returns data
- [ ] All imports use `backend.services.*`
- [ ] All SQL uses `text()` wrapper

### Important (Should Pass)
- [ ] OSM data imports (6+ businesses)
- [ ] CSV data loads (5 events, 5 businesses)
- [ ] Geocoding works (even if 0 records need geocoding)
- [ ] DQ checks run
- [ ] Export files generated

### Nice to Have
- [ ] Certifier data imports (2 businesses)
- [ ] Interactive API docs work
- [ ] Logs are clean and structured

## Common Issues

### Issue: "ModuleNotFoundError: No module named 'services'"
**Fix:** Check imports use `backend.services` not `services`

### Issue: "Text SQL expression should be explicitly declared"
**Fix:** Wrap SQL with `text()`: `session.execute(text("SELECT..."))`

### Issue: "CSV file not found: .../seed/seed/events.csv"
**Fix:** Check `config.py` paths use correct parent levels

### Issue: Database connection refused
**Fix:** Ensure database is running: `docker ps | grep postgres`

### Issue: Port 5432 already in use
**Fix:** Use port 5433 (configured in `.env`)

---

**Date:** November 9, 2025
**Version:** 1.0
**Status:** All tests passing ✅
