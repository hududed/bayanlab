# Troubleshooting Guide

Common issues and solutions for BayanLab Community Data Backbone.

**Last Updated:** November 10, 2025

---

## Quick Diagnostics

Run this health check script:

```bash
# Check all systems
./test_qa.sh

# Or manually:
docker ps | grep postgres     # Database running?
uv --version                   # uv installed?
python --version              # Python 3.11+?
curl http://localhost:8000/healthz  # API responding?
```

---

## Database Issues

### Issue: "Could not connect to database"

**Symptoms:**
```
ERROR: could not connect to server: Connection refused
```

**Causes & Solutions:**

1. **PostgreSQL not running**
   ```bash
   # Check if container is running
   docker ps | grep postgres

   # Start database
   cd infra/docker
   docker-compose up -d db
   ```

2. **Wrong port**
   ```bash
   # Check which port PostgreSQL is on
   docker ps | grep postgres

   # Update .env to match
   DATABASE_URL=postgresql+asyncpg://bayan:bayan@localhost:5432/bayan_backbone
   ```

3. **Database not initialized**
   ```bash
   # Check if tables exist
   docker exec -it $(docker ps -qf "name=postgres") psql -U bayan -d bayan_backbone -c "\dt"

   # If no tables, run migrations
   docker exec -it $(docker ps -qf "name=postgres") psql -U bayan -d bayan_backbone -f /docker-entrypoint-initdb.d/000_init.sql
   ```

---

### Issue: "PostGIS extension not found"

**Symptoms:**
```
ERROR: type "geography" does not exist
```

**Solution:**
```bash
# Ensure using postgis image
docker ps | grep postgis

# If not, recreate with correct image
docker-compose down
docker-compose up -d db

# Verify PostGIS installed
docker exec -it $(docker ps -qf "name=postgres") psql -U bayan -d bayan_backbone -c "SELECT PostGIS_Version();"
```

---

### Issue: "Database locked" or slow queries

**Symptoms:**
- Pipeline hangs
- API timeouts

**Solutions:**

1. **Check for long-running queries**
   ```sql
   SELECT pid, now() - pg_stat_activity.query_start AS duration, query
   FROM pg_stat_activity
   WHERE state = 'active'
   ORDER BY duration DESC;
   ```

2. **Kill stuck query**
   ```sql
   SELECT pg_terminate_backend(pid)
   FROM pg_stat_activity
   WHERE pid = <pid_from_above>;
   ```

3. **Check connection pool**
   ```sql
   SELECT count(*) FROM pg_stat_activity;
   ```

   If > 100 connections, restart API/pipeline.

---

## Pipeline Issues

### Issue: "No module named 'backend'"

**Symptoms:**
```
ModuleNotFoundError: No module named 'backend'
```

**Solution:**
```bash
# Run from repository root
cd /Users/hfox/Developments/bayanlab

# Use run_pipeline.py wrapper
uv run python run_pipeline.py --pipeline all

# NOT:
# cd backend && python services/pipeline_runner.py  # This will fail
```

---

### Issue: Pipeline fails with "404 Not Found" on ICS URL

**Symptoms:**
```json
{"level": "ERROR", "message": "Failed to fetch ICS: 404 Not Found"}
```

**Causes & Solutions:**

1. **Calendar is private**
   - Public ICS URL doesn't work for private calendars
   - Solution: Use Google Calendar API instead
   ```yaml
   ics_sources:
     - id: "my_calendar"
       calendar_id: "calendar@example.com"  # Use this
       # url: "..."  # Remove or comment out
   ```

2. **Calendar ID is wrong**
   - Verify the calendar ID in Google Calendar settings
   - Format: `email@domain.com` or `randomstring@group.calendar.google.com`

3. **Calendar was deleted**
   - Check if calendar still exists in Google Calendar
   - Disable source in `sources.yaml`:
   ```yaml
   enabled: false
   ```

---

### Issue: "Google Calendar API not initialized"

**Symptoms:**
```json
{"level": "WARNING", "message": "Google Calendar credentials not found"}
```

**Solutions:**

1. **Check if credentials file exists**
   ```bash
   ls -la $GOOGLE_APPLICATION_CREDENTIALS
   ```

2. **Verify .env has correct path**
   ```bash
   cat .env | grep GOOGLE_APPLICATION_CREDENTIALS
   ```

3. **Test credentials manually**
   ```bash
   python -c "
   import os
   from google.oauth2 import service_account
   creds = service_account.Credentials.from_service_account_file(
       os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
   )
   print('Credentials loaded:', creds.service_account_email)
   "
   ```

4. **Missing dependencies**
   ```bash
   uv sync
   ```

---

### Issue: Pipeline runs but ingests 0 events

**Symptoms:**
```json
{"level": "INFO", "message": "ICS poller completed", "count_out": 0}
```

**Debugging:**

1. **Check if sources are enabled**
   ```bash
   grep "enabled: true" backend/configs/sources.yaml
   ```

2. **Check source logs**
   - Look for "Failed to ingest source" errors
   - Check if ICS URL is accessible:
   ```bash
   curl -I "https://calendar.google.com/calendar/ical/..."
   ```

3. **Verify calendar has future events**
   - Open calendar in Google Calendar web UI
   - Ensure events are in the future (pipeline fetches from `now` onwards)

4. **Check staging tables**
   ```sql
   SELECT COUNT(*) FROM staging_events;
   SELECT source, COUNT(*) FROM staging_events GROUP BY source;
   ```

---

### Issue: "DQ checks: 10 errors"

**Symptoms:**
```json
{"level": "ERROR", "message": "Business xyz: Missing required fields"}
```

**Understanding DQ Errors:**

DQ errors mean data is incomplete but still ingested. Check:

```sql
-- See which records have errors
SELECT * FROM event_canonical WHERE dq_status = 'error';
SELECT * FROM business_canonical WHERE dq_status = 'error';
```

**Common Errors:**
- `Missing required fields` → Source data incomplete (fix CSV or ICS feed)
- `Coordinates outside region bbox` → Wrong coordinates or wrong region assigned
- `Missing coordinates` → Geocoder failed (check address format)

**Acceptable Error Rate:** < 5% for V1

---

## API Issues

### Issue: API not starting

**Symptoms:**
```
uvicorn.error: Error loading ASGI app
```

**Solutions:**

1. **Check import paths**
   ```bash
   # Run from repository root
   cd /Users/hfox/Developments/bayanlab
   uv run uvicorn backend.services.api_service.main:app --reload
   ```

2. **Check database connection**
   ```bash
   # Test DB connection in Python
   python -c "
   from backend.services.common.database import get_sync_session
   with get_sync_session() as session:
       print('Database connected!')
   "
   ```

3. **Check for port conflicts**
   ```bash
   # See if port 8000 is in use
   lsof -i :8000

   # Kill process if needed
   kill -9 <pid>
   ```

---

### Issue: API returns 500 errors

**Symptoms:**
```json
{"detail": "Internal Server Error"}
```

**Debugging:**

1. **Check API logs**
   ```bash
   # Run with DEBUG logging
   LOG_LEVEL=DEBUG uv run uvicorn backend.services.api_service.main:app --reload
   ```

2. **Check database has data**
   ```sql
   SELECT COUNT(*) FROM event_canonical WHERE region = 'CO';
   SELECT COUNT(*) FROM business_canonical WHERE region = 'CO';
   ```

3. **Test endpoint directly**
   ```bash
   curl -v "http://localhost:8000/v1/events?region=CO&limit=1"
   ```

---

### Issue: API slow (> 1 second response time)

**Symptoms:**
- API responds but takes > 1s

**Diagnostics:**

1. **Check database query performance**
   ```sql
   -- Enable query logging
   ALTER DATABASE bayan_backbone SET log_statement = 'all';
   ALTER DATABASE bayan_backbone SET log_duration = 'on';

   -- View slow queries
   SELECT * FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;
   ```

2. **Check indexes exist**
   ```sql
   \d event_canonical
   \d business_canonical
   ```

   Should see indexes on `region`, `address_city`, `start_time`.

3. **Optimize query**
   ```sql
   EXPLAIN ANALYZE SELECT * FROM event_canonical WHERE region = 'CO' LIMIT 10;
   ```

**Solutions:**
- Add missing indexes
- Reduce data volume (filter by date range)
- Use caching (Redis) in Phase 2

---

## Google Calendar Issues

### Issue: "Permission denied" when accessing calendar

**Symptoms:**
```json
{"level": "ERROR", "message": "Google Calendar API error: 403 Forbidden"}
```

**Solutions:**

1. **Calendar not shared with service account**
   - Share calendar with `bayanlab-calendar@bayanlab-477720.iam.gserviceaccount.com`
   - Permission: "See all event details" (not "See only free/busy")

2. **Service account credentials expired**
   - Regenerate service account key in Google Cloud Console
   - Update `GOOGLE_APPLICATION_CREDENTIALS` path

3. **Calendar API not enabled**
   - Go to Google Cloud Console → APIs & Services
   - Enable "Google Calendar API"

---

### Issue: "Calendar not found"

**Symptoms:**
```json
{"level": "ERROR", "message": "Calendar not found: abc123@group.calendar.google.com"}
```

**Solutions:**

1. **Wrong calendar ID**
   - Get calendar ID from Google Calendar settings:
     - Open calendar → Settings → Integrate calendar → Calendar ID

2. **Calendar deleted**
   - Verify calendar exists in Google Calendar
   - Disable in `sources.yaml` if no longer available

---

## Geocoding Issues

### Issue: Geocoding fails for all addresses

**Symptoms:**
```json
{"level": "WARNING", "message": "Geocoding failed for address: ..."}
```

**Causes & Solutions:**

1. **Rate limit exceeded**
   - Nominatim allows 1 request/second
   - Solution: Increase `GEOCODER_RATE_LIMIT` in `.env`:
   ```bash
   GEOCODER_RATE_LIMIT=2.0  # 2 seconds between requests
   ```

2. **Nominatim service down**
   - Test manually:
   ```bash
   curl "https://nominatim.openstreetmap.org/search?q=Denver,CO&format=json"
   ```
   - If down, wait and retry later

3. **Invalid address format**
   - Check address in staging table:
   ```sql
   SELECT raw_payload->>'address' FROM staging_businesses LIMIT 10;
   ```
   - Format should be: "123 Main St, Denver, CO 80202"

---

## Docker Issues

### Issue: "Port already in use"

**Symptoms:**
```
Error: bind: address already in use
```

**Solution:**
```bash
# Find process using port
lsof -i :5432  # or :8000

# Kill process
kill -9 <pid>

# Or change port in docker-compose.yml
ports:
  - "5433:5432"  # Use 5433 instead
```

---

### Issue: Docker out of disk space

**Symptoms:**
```
Error: no space left on device
```

**Solution:**
```bash
# Clean up Docker
docker system prune -a --volumes

# Check disk usage
docker system df
```

---

## Import/Module Issues

### Issue: "ImportError: No module named 'google.oauth2'"

**Symptoms:**
```
ImportError: No module named 'google.oauth2'
```

**Solution:**
```bash
# Sync dependencies
uv sync

# Verify installed
uv pip list | grep google
```

---

### Issue: "ModuleNotFoundError: No module named 'icalendar'"

**Solution:**
```bash
uv sync
# Or manually:
uv pip install icalendar
```

---

## Performance Issues

### Issue: Pipeline takes > 10 minutes

**Expected Runtime:** < 5 minutes for Colorado (V1)

**Debugging:**

1. **Check which stage is slow**
   - Look for timestamps in pipeline logs
   - Stages: Ingest → Process → Publish

2. **Slow ingest**
   - ICS fetch timeout: Increase timeout in `ics_poller.py`
   - OSM query timeout: Simplify query or reduce bbox

3. **Slow geocoding**
   - Check rate limiting: `GEOCODER_RATE_LIMIT`
   - Skip geocoding for testing:
   ```bash
   # Comment out geocoder in pipeline_runner.py
   ```

4. **Slow database writes**
   - Batch inserts (already implemented)
   - Check database CPU/memory usage:
   ```bash
   docker stats $(docker ps -qf "name=postgres")
   ```

---

## Testing Issues

### Issue: "pytest: command not found"

**Solution:**
```bash
uv sync
uv run pytest backend/tests/ -v
```

---

### Issue: Tests fail with database errors

**Solution:**
```bash
# Ensure test database is clean
docker exec -it $(docker ps -qf "name=postgres") psql -U bayan -d bayan_backbone -c "
  TRUNCATE staging_events, staging_businesses, event_canonical, business_canonical CASCADE;
"

# Run tests
uv run pytest backend/tests/ -v
```

---

## Getting Help

If you're still stuck:

1. **Check logs:**
   ```bash
   # Pipeline logs
   tail -100 pipeline.log

   # Docker logs
   docker logs $(docker ps -qf "name=postgres")
   ```

2. **Run QA checklist:**
   ```bash
   ./test_qa.sh
   ```

3. **Create GitHub issue:**
   - Include error message
   - Include steps to reproduce
   - Include logs (redact sensitive info)

4. **Contact support:**
   - Email: info@bayanlab.com
   - Include system info: `uv --version`, `python --version`, `docker --version`

---

## Emergency Procedures

### Pipeline is stuck/hanging

```bash
# Find Python process
ps aux | grep pipeline_runner

# Kill it
kill -9 <pid>

# Reset database (WARNING: deletes data)
docker exec -it $(docker ps -qf "name=postgres") psql -U bayan -d bayan_backbone -c "
  TRUNCATE staging_events, staging_businesses, event_canonical, business_canonical, build_metadata CASCADE;
"

# Rerun pipeline
uv run python run_pipeline.py --pipeline all
```

---

### API is down

```bash
# Stop API
pkill -f "uvicorn.*api_service"

# Check database
docker ps | grep postgres

# Restart API
uv run uvicorn backend.services.api_service.main:app --reload
```

---

### Database corrupted

```bash
# Backup first (if possible)
docker exec $(docker ps -qf "name=postgres") pg_dump -U bayan bayan_backbone > backup.sql

# Recreate database
docker-compose down
docker volume rm docker_postgres_data  # WARNING: Deletes all data
docker-compose up -d db

# Restore from backup (if available)
docker exec -i $(docker ps -qf "name=postgres") psql -U bayan -d bayan_backbone < backup.sql
```

---

**Last Updated:** November 10, 2025
**Maintained by:** BayanLab Engineering
