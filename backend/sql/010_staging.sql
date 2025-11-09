-- 010_staging.sql
-- Staging tables for raw ingested data

-- Staging table for events
CREATE TABLE IF NOT EXISTS staging_events (
    staging_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ingest_run_id UUID NOT NULL,
    source event_source NOT NULL,
    source_ref VARCHAR(500),
    raw_payload JSONB NOT NULL,
    ingested_at TIMESTAMPTZ DEFAULT NOW(),
    processed BOOLEAN DEFAULT FALSE,
    error_message TEXT
);

CREATE INDEX idx_staging_events_run ON staging_events(ingest_run_id);
CREATE INDEX idx_staging_events_processed ON staging_events(processed);
CREATE INDEX idx_staging_events_ingested ON staging_events(ingested_at);

-- Staging table for businesses
CREATE TABLE IF NOT EXISTS staging_businesses (
    staging_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ingest_run_id UUID NOT NULL,
    source business_source NOT NULL,
    source_ref VARCHAR(500),
    raw_payload JSONB NOT NULL,
    ingested_at TIMESTAMPTZ DEFAULT NOW(),
    processed BOOLEAN DEFAULT FALSE,
    error_message TEXT
);

CREATE INDEX idx_staging_businesses_run ON staging_businesses(ingest_run_id);
CREATE INDEX idx_staging_businesses_processed ON staging_businesses(processed);
CREATE INDEX idx_staging_businesses_ingested ON staging_businesses(ingested_at);

-- Insert migration record
INSERT INTO migration_history (version) VALUES ('010_staging') ON CONFLICT DO NOTHING;
