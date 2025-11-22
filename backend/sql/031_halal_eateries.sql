-- 031_halal_eateries.sql
-- Separate table for halal eateries (discovery/data API)
-- NOT for ProWasl monetization - these are established restaurants with fixed menus

-- Halal status enum
DO $$ BEGIN
    CREATE TYPE halal_status AS ENUM ('validated', 'likely_halal', 'unverified');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Halal eateries table
CREATE TABLE IF NOT EXISTS halal_eateries (
    eatery_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(300) NOT NULL,
    cuisine_style VARCHAR(100),

    -- Address
    address_street VARCHAR(300),
    address_city VARCHAR(100) NOT NULL,
    address_state VARCHAR(2) NOT NULL DEFAULT 'CO',
    address_zip VARCHAR(10),

    -- Geolocation
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    geom GEOGRAPHY(POINT, 4326),

    -- Contact
    phone VARCHAR(50),
    website VARCHAR(1000),

    -- Eatery-specific
    hours_raw TEXT,                    -- Original hours string
    google_rating DECIMAL(2, 1),       -- e.g., 4.5
    halal_status halal_status NOT NULL DEFAULT 'unverified',

    -- Flags (from Colorado Halal icons)
    is_favorite BOOLEAN DEFAULT FALSE,       -- Community favorite
    is_new_listed BOOLEAN DEFAULT FALSE,     -- Recently added
    is_food_truck BOOLEAN DEFAULT FALSE,     -- Mobile vendor
    is_carry_out_only BOOLEAN DEFAULT FALSE, -- No dine-in
    is_cafe_bakery BOOLEAN DEFAULT FALSE,    -- Café or bakery
    has_many_locations BOOLEAN DEFAULT FALSE, -- Chain restaurant

    -- Provenance
    source VARCHAR(50) NOT NULL,             -- 'colorado_halal', 'zabihah', etc.
    source_ref VARCHAR(500),                 -- URL or reference
    google_place_id VARCHAR(100),            -- For deduplication

    -- Metadata
    region VARCHAR(10) NOT NULL DEFAULT 'CO',
    tags TEXT,                               -- Semicolon-separated tags
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_eatery_state CHECK (address_state ~ '^[A-Z]{2}$')
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_eateries_name ON halal_eateries(name);
CREATE INDEX IF NOT EXISTS idx_eateries_city ON halal_eateries(address_city);
CREATE INDEX IF NOT EXISTS idx_eateries_region ON halal_eateries(region);
CREATE INDEX IF NOT EXISTS idx_eateries_cuisine ON halal_eateries(cuisine_style);
CREATE INDEX IF NOT EXISTS idx_eateries_halal_status ON halal_eateries(halal_status);
CREATE INDEX IF NOT EXISTS idx_eateries_geom ON halal_eateries USING GIST(geom);
-- Unique constraint on name + street address (prevents duplicates when reloading)
-- Same restaurant can have multiple locations in same city (e.g., Gyros Town has 2 in Denver)
CREATE UNIQUE INDEX IF NOT EXISTS idx_eateries_name_street ON halal_eateries(LOWER(name), LOWER(address_street));

-- Non-unique index for google_place_id lookups
CREATE INDEX IF NOT EXISTS idx_eateries_google_place_id ON halal_eateries(google_place_id) WHERE google_place_id IS NOT NULL AND google_place_id != '';
CREATE INDEX IF NOT EXISTS idx_eateries_source ON halal_eateries(source);

-- Trigger to auto-update geom from lat/lng
CREATE OR REPLACE FUNCTION update_eatery_geom()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.latitude IS NOT NULL AND NEW.longitude IS NOT NULL THEN
        NEW.geom = ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326)::geography;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_eatery_geom ON halal_eateries;
CREATE TRIGGER trigger_update_eatery_geom
    BEFORE INSERT OR UPDATE ON halal_eateries
    FOR EACH ROW
    EXECUTE FUNCTION update_eatery_geom();

-- Trigger to auto-update updated_at
CREATE OR REPLACE FUNCTION update_eatery_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_eatery_timestamp ON halal_eateries;
CREATE TRIGGER trigger_update_eatery_timestamp
    BEFORE UPDATE ON halal_eateries
    FOR EACH ROW
    EXECUTE FUNCTION update_eatery_timestamp();

-- Insert migration record
INSERT INTO migration_history (version) VALUES ('031_halal_eateries') ON CONFLICT DO NOTHING;
