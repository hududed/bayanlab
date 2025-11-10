# Database Views

SQL views and materialized views for querying and analytics.

**Schema Version:** 1.0
**Last Updated:** November 10, 2025

---

## Core Views

### `v_events_recent`
**Purpose:** Recent events (future + last 30 days) with full details

```sql
CREATE OR REPLACE VIEW v_events_recent AS
SELECT
  event_id,
  title,
  description,
  start_time,
  end_time,
  all_day,
  venue_name,
  address_city,
  address_state,
  latitude,
  longitude,
  url,
  region,
  source,
  dq_status
FROM event_canonical
WHERE start_time >= NOW() - INTERVAL '30 days'
  AND dq_status != 'error'
ORDER BY start_time ASC;
```

**Usage:**
```sql
-- Get upcoming events in Denver
SELECT * FROM v_events_recent
WHERE address_city = 'Denver'
LIMIT 10;
```

---

### `v_businesses_active`
**Purpose:** Active businesses with valid coordinates

```sql
CREATE OR REPLACE VIEW v_businesses_active AS
SELECT
  business_id,
  name,
  category,
  address_full,
  address_city,
  address_state,
  latitude,
  longitude,
  phone,
  website,
  halal_certified,
  certifier_name,
  region,
  source,
  dq_status
FROM business_canonical
WHERE latitude IS NOT NULL
  AND longitude IS NOT NULL
  AND dq_status != 'error'
ORDER BY name ASC;
```

**Usage:**
```sql
-- Get halal restaurants in Colorado Springs
SELECT * FROM v_businesses_active
WHERE address_city = 'Colorado Springs'
  AND category = 'restaurant'
  AND halal_certified = true;
```

---

### `v_event_summary_by_city`
**Purpose:** Event counts per city for analytics

```sql
CREATE OR REPLACE VIEW v_event_summary_by_city AS
SELECT
  region,
  address_city AS city,
  COUNT(*) AS event_count,
  COUNT(DISTINCT venue_name) AS unique_venues,
  MIN(start_time) AS earliest_event,
  MAX(start_time) AS latest_event
FROM event_canonical
WHERE dq_status != 'error'
GROUP BY region, address_city
ORDER BY event_count DESC;
```

**Usage:**
```sql
-- Find cities with most events
SELECT * FROM v_event_summary_by_city
WHERE region = 'CO'
ORDER BY event_count DESC;
```

---

### `v_business_summary_by_category`
**Purpose:** Business counts per category

```sql
CREATE OR REPLACE VIEW v_business_summary_by_category AS
SELECT
  region,
  category,
  COUNT(*) AS business_count,
  SUM(CASE WHEN halal_certified THEN 1 ELSE 0 END) AS halal_certified_count
FROM business_canonical
WHERE dq_status != 'error'
GROUP BY region, category
ORDER BY business_count DESC;
```

**Usage:**
```sql
-- See business distribution by category
SELECT * FROM v_business_summary_by_category
WHERE region = 'CO';
```

---

## Geospatial Views

### `v_events_with_geometry`
**Purpose:** Events with PostGIS geometry for spatial queries

```sql
CREATE OR REPLACE VIEW v_events_with_geometry AS
SELECT
  event_id,
  title,
  start_time,
  venue_name,
  address_city,
  latitude,
  longitude,
  region,
  ST_SetSRID(ST_Point(longitude, latitude), 4326) AS geom
FROM event_canonical
WHERE latitude IS NOT NULL
  AND longitude IS NOT NULL
  AND dq_status != 'error';
```

**Usage:**
```sql
-- Find events within 10km of Denver downtown
SELECT
  title,
  venue_name,
  ST_Distance(
    geom,
    ST_SetSRID(ST_Point(-104.9903, 39.7392), 4326)::geography
  ) / 1000 AS distance_km
FROM v_events_with_geometry
WHERE region = 'CO'
  AND ST_DWithin(
    geom::geography,
    ST_SetSRID(ST_Point(-104.9903, 39.7392), 4326)::geography,
    10000  -- 10km in meters
  )
ORDER BY distance_km ASC;
```

---

### `v_businesses_with_geometry`
**Purpose:** Businesses with PostGIS geometry

```sql
CREATE OR REPLACE VIEW v_businesses_with_geometry AS
SELECT
  business_id,
  name,
  category,
  address_city,
  latitude,
  longitude,
  halal_certified,
  region,
  ST_SetSRID(ST_Point(longitude, latitude), 4326) AS geom
FROM business_canonical
WHERE latitude IS NOT NULL
  AND longitude IS NOT NULL
  AND dq_status != 'error';
```

**Usage:**
```sql
-- Find halal restaurants near a masjid
WITH masjid_location AS (
  SELECT ST_SetSRID(ST_Point(-104.9903, 39.7392), 4326) AS geom
)
SELECT
  b.name,
  b.address_full,
  ST_Distance(b.geom::geography, m.geom::geography) / 1000 AS distance_km
FROM v_businesses_with_geometry b, masjid_location m
WHERE b.halal_certified = true
  AND b.category = 'restaurant'
  AND ST_DWithin(b.geom::geography, m.geom::geography, 5000)
ORDER BY distance_km ASC;
```

---

## Data Quality Views

### `v_dq_events_issues`
**Purpose:** Events with data quality warnings or errors

```sql
CREATE OR REPLACE VIEW v_dq_events_issues AS
SELECT
  event_id,
  title,
  venue_name,
  address_city,
  start_time,
  source,
  dq_status,
  CASE
    WHEN title IS NULL THEN 'Missing title'
    WHEN address_city IS NULL THEN 'Missing city'
    WHEN latitude IS NULL OR longitude IS NULL THEN 'Missing coordinates'
    WHEN start_time < NOW() - INTERVAL '30 days' THEN 'Event is old'
    ELSE 'Other issue'
  END AS issue_type
FROM event_canonical
WHERE dq_status IN ('warning', 'error')
ORDER BY dq_status DESC, start_time ASC;
```

**Usage:**
```sql
-- Review events with issues
SELECT issue_type, COUNT(*) AS count
FROM v_dq_events_issues
GROUP BY issue_type
ORDER BY count DESC;
```

---

### `v_dq_businesses_issues`
**Purpose:** Businesses with data quality issues

```sql
CREATE OR REPLACE VIEW v_dq_businesses_issues AS
SELECT
  business_id,
  name,
  category,
  address_city,
  source,
  dq_status,
  CASE
    WHEN name IS NULL THEN 'Missing name'
    WHEN category IS NULL THEN 'Missing category'
    WHEN address_city IS NULL THEN 'Missing city'
    WHEN latitude IS NULL OR longitude IS NULL THEN 'Missing coordinates'
    ELSE 'Other issue'
  END AS issue_type
FROM business_canonical
WHERE dq_status IN ('warning', 'error')
ORDER BY dq_status DESC, name ASC;
```

---

## Pipeline Monitoring Views

### `v_pipeline_runs`
**Purpose:** Recent pipeline execution history

```sql
CREATE OR REPLACE VIEW v_pipeline_runs AS
SELECT
  build_id,
  build_type,
  started_at,
  completed_at,
  EXTRACT(EPOCH FROM (completed_at - started_at)) AS runtime_seconds,
  status,
  errors
FROM build_metadata
ORDER BY started_at DESC
LIMIT 50;
```

**Usage:**
```sql
-- Check last 10 pipeline runs
SELECT
  build_type,
  started_at,
  runtime_seconds,
  status
FROM v_pipeline_runs
LIMIT 10;
```

---

### `v_source_health`
**Purpose:** Track data ingestion per source

```sql
CREATE OR REPLACE VIEW v_source_health AS
WITH latest_run AS (
  SELECT MAX(ingest_run_id) AS run_id FROM staging_events
)
SELECT
  source,
  COUNT(*) AS records_ingested,
  MIN(ingested_at) AS first_record_at,
  MAX(ingested_at) AS last_record_at
FROM staging_events
WHERE ingest_run_id = (SELECT run_id FROM latest_run)
GROUP BY source

UNION ALL

SELECT
  source,
  COUNT(*) AS records_ingested,
  MIN(ingested_at) AS first_record_at,
  MAX(ingested_at) AS last_record_at
FROM staging_businesses
WHERE ingest_run_id = (SELECT run_id FROM latest_run)
GROUP BY source

ORDER BY records_ingested DESC;
```

**Usage:**
```sql
-- Check if sources are working
SELECT * FROM v_source_health;
```

---

## Materialized Views (Future)

For performance-critical queries, consider materializing views:

### `mv_weekly_events`
**Purpose:** Pre-compute weekly event counts for dashboard

```sql
CREATE MATERIALIZED VIEW mv_weekly_events AS
SELECT
  DATE_TRUNC('week', start_time) AS week_start,
  region,
  address_city,
  COUNT(*) AS event_count
FROM event_canonical
WHERE dq_status != 'error'
GROUP BY week_start, region, address_city;

-- Refresh nightly
CREATE INDEX idx_mv_weekly_events ON mv_weekly_events(week_start, region);

-- Refresh command (run via cron)
REFRESH MATERIALIZED VIEW mv_weekly_events;
```

---

## View Maintenance

### Refresh Strategy
- **Regular views:** Auto-updated (no maintenance)
- **Materialized views:** Refresh after each pipeline run or nightly

### Performance Tips
1. **Index underlying tables:** Ensure canonical tables have indexes on `region`, `city`, `start_time`
2. **Use views in API:** Simplify API queries by using views
3. **Monitor view performance:** `EXPLAIN ANALYZE` slow views

### View Dependencies
```
v_events_recent          → event_canonical
v_businesses_active      → business_canonical
v_events_with_geometry   → event_canonical (PostGIS)
v_pipeline_runs          → build_metadata
```

---

## Example Queries

### Dashboard Query: Today's Events
```sql
SELECT
  title,
  venue_name,
  TO_CHAR(start_time, 'HH12:MI AM') AS start_time,
  address_city
FROM v_events_recent
WHERE DATE(start_time) = CURRENT_DATE
  AND region = 'CO'
ORDER BY start_time ASC;
```

### Map Query: Businesses Near Me
```sql
SELECT
  name,
  category,
  address_full,
  latitude,
  longitude,
  ST_Distance(
    ST_SetSRID(ST_Point(longitude, latitude), 4326)::geography,
    ST_SetSRID(ST_Point(-104.9903, 39.7392), 4326)::geography
  ) / 1000 AS distance_km
FROM v_businesses_active
WHERE region = 'CO'
  AND ST_DWithin(
    ST_SetSRID(ST_Point(longitude, latitude), 4326)::geography,
    ST_SetSRID(ST_Point(-104.9903, 39.7392), 4326)::geography,
    20000  -- 20km radius
  )
ORDER BY distance_km ASC
LIMIT 20;
```

### Analytics: Busiest Venues
```sql
SELECT
  venue_name,
  COUNT(*) AS event_count,
  COUNT(DISTINCT DATE(start_time)) AS unique_days
FROM v_events_recent
WHERE region = 'CO'
GROUP BY venue_name
ORDER BY event_count DESC
LIMIT 10;
```

---

**Maintained by:** BayanLab Engineering
**Review Cadence:** Quarterly or when schema changes
