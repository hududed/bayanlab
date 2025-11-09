-- 020_canonical.sql
-- Canonical tables for normalized, deduplicated data

-- Canonical events table
CREATE TABLE IF NOT EXISTS event_canonical (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(500) NOT NULL,
    description TEXT,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    all_day BOOLEAN DEFAULT FALSE,

    -- Venue information
    venue_name VARCHAR(300),
    address_street VARCHAR(300),
    address_city VARCHAR(100) NOT NULL,
    address_state VARCHAR(2) NOT NULL,
    address_zip VARCHAR(10),

    -- Geolocation
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    geom GEOGRAPHY(POINT, 4326),

    -- Contact and reference
    url VARCHAR(1000),
    organizer_name VARCHAR(300),
    organizer_contact VARCHAR(300),

    -- Metadata
    source event_source NOT NULL,
    source_ref VARCHAR(500),
    region VARCHAR(10) NOT NULL DEFAULT 'CO',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_times CHECK (end_time > start_time),
    CONSTRAINT valid_region CHECK (region = 'CO'),
    CONSTRAINT valid_state CHECK (address_state = 'CO')
);

CREATE INDEX idx_events_start_time ON event_canonical(start_time);
CREATE INDEX idx_events_updated ON event_canonical(updated_at);
CREATE INDEX idx_events_city ON event_canonical(address_city);
CREATE INDEX idx_events_region ON event_canonical(region);
CREATE INDEX idx_events_source_ref ON event_canonical(source, source_ref);
CREATE INDEX idx_events_geom ON event_canonical USING GIST(geom);

-- Canonical businesses table
CREATE TABLE IF NOT EXISTS business_canonical (
    business_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(300) NOT NULL,
    category business_category NOT NULL,

    -- Address
    address_street VARCHAR(300),
    address_city VARCHAR(100) NOT NULL,
    address_state VARCHAR(2) NOT NULL,
    address_zip VARCHAR(10),

    -- Geolocation
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    geom GEOGRAPHY(POINT, 4326),

    -- Contact
    website VARCHAR(1000),
    phone VARCHAR(50),
    email VARCHAR(255),

    -- Business attributes
    self_identified_muslim_owned BOOLEAN DEFAULT FALSE,
    halal_certified BOOLEAN DEFAULT FALSE,
    certifier_name VARCHAR(200),
    certifier_ref VARCHAR(500),

    -- Enrichment
    placekey VARCHAR(100),

    -- Metadata
    source business_source NOT NULL,
    source_ref VARCHAR(500),
    region VARCHAR(10) NOT NULL DEFAULT 'CO',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_business_region CHECK (region = 'CO'),
    CONSTRAINT valid_business_state CHECK (address_state = 'CO')
);

CREATE INDEX idx_businesses_name ON business_canonical(name);
CREATE INDEX idx_businesses_category ON business_canonical(category);
CREATE INDEX idx_businesses_updated ON business_canonical(updated_at);
CREATE INDEX idx_businesses_city ON business_canonical(address_city);
CREATE INDEX idx_businesses_region ON business_canonical(region);
CREATE INDEX idx_businesses_source_ref ON business_canonical(source, source_ref);
CREATE INDEX idx_businesses_geom ON business_canonical USING GIST(geom);
CREATE INDEX idx_businesses_placekey ON business_canonical(placekey) WHERE placekey IS NOT NULL;

-- Provenance log table
CREATE TABLE IF NOT EXISTS provenance_log (
    prov_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type entity_type NOT NULL,
    entity_id UUID NOT NULL,
    action VARCHAR(100) NOT NULL,
    details JSONB,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_prov_entity ON provenance_log(entity_type, entity_id);
CREATE INDEX idx_prov_timestamp ON provenance_log(timestamp);

-- Insert migration record
INSERT INTO migration_history (version) VALUES ('020_canonical') ON CONFLICT DO NOTHING;
