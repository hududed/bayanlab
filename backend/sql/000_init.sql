-- 000_init.sql
-- Initialize database with PostGIS extension and base structure

-- Enable PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create enum types
CREATE TYPE event_source AS ENUM ('ics', 'csv');
CREATE TYPE business_source AS ENUM ('osm', 'certifier', 'csv');
CREATE TYPE business_category AS ENUM ('restaurant', 'service', 'retail', 'grocery', 'butcher', 'other');
CREATE TYPE entity_type AS ENUM ('event', 'business');

-- Create metadata table for tracking migrations and builds
CREATE TABLE IF NOT EXISTS migration_history (
    id SERIAL PRIMARY KEY,
    version VARCHAR(50) NOT NULL,
    applied_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS build_metadata (
    id SERIAL PRIMARY KEY,
    build_type VARCHAR(50) NOT NULL, -- 'events' or 'businesses'
    ingest_run_id UUID NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL, -- 'running', 'success', 'failed'
    records_processed INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,
    error_log TEXT
);

-- Insert initial migration record
INSERT INTO migration_history (version) VALUES ('000_init') ON CONFLICT DO NOTHING;
