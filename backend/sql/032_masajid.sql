-- 032_masajid.sql
-- Masajid (mosques) table for Colorado Muslim community
-- Supports: events calendar, waqf beneficiary eligibility, community directory

-- Masajid table
CREATE TABLE IF NOT EXISTS masajid (
    masjid_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(300) NOT NULL,

    -- Address
    address_street VARCHAR(300),
    address_city VARCHAR(100) NOT NULL,
    address_state VARCHAR(10) NOT NULL DEFAULT 'CO',
    address_zip VARCHAR(20),

    -- Geolocation
    latitude DECIMAL(10, 7),
    longitude DECIMAL(10, 7),

    -- Contact
    phone VARCHAR(50),
    website VARCHAR(500),
    email VARCHAR(255),

    -- Social media
    facebook_url VARCHAR(500),
    instagram_url VARCHAR(500),

    -- Calendar integration (for BayanLab events sync)
    google_calendar_id VARCHAR(255),        -- e.g., "masjiddenver@gmail.com"
    calendar_shared BOOLEAN DEFAULT FALSE,  -- Has shared calendar with us

    -- Organization details
    established_year INTEGER,
    denomination VARCHAR(100),              -- e.g., "Sunni", "Shia", "Non-denominational"
    languages TEXT,                         -- Semicolon-separated: "English;Arabic;Urdu"

    -- Facilities
    has_womens_section BOOLEAN DEFAULT TRUE,
    has_parking BOOLEAN DEFAULT TRUE,
    has_wudu_facilities BOOLEAN DEFAULT TRUE,
    has_wheelchair_access BOOLEAN,
    capacity_estimate INTEGER,              -- Approximate prayer hall capacity

    -- Services offered
    offers_jumah BOOLEAN DEFAULT TRUE,
    offers_daily_prayers BOOLEAN DEFAULT TRUE,
    offers_quran_classes BOOLEAN,
    offers_weekend_school BOOLEAN,
    offers_nikah_services BOOLEAN,
    offers_janazah_services BOOLEAN,
    offers_ramadan_programs BOOLEAN,

    -- Waqf/501(c)(3) eligibility (for future grantmaking)
    is_501c3 BOOLEAN,                       -- IRS tax-exempt status
    ein VARCHAR(20),                        -- Employer Identification Number (XX-XXXXXXX)

    -- Verification & status
    verification_status VARCHAR(50) NOT NULL DEFAULT 'unverified',  -- 'verified', 'unverified', 'pending'
    verified_at TIMESTAMPTZ,
    verified_by VARCHAR(100),

    -- Provenance
    region VARCHAR(10) NOT NULL DEFAULT 'CO',
    source VARCHAR(100) NOT NULL,           -- 'manual', 'google_places', 'isna', etc.
    google_place_id VARCHAR(255),
    google_rating DECIMAL(2, 1),
    google_review_count INTEGER,

    -- Notes (internal)
    notes TEXT,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_masjid_state CHECK (address_state ~ '^[A-Z]{2,3}$'),
    CONSTRAINT valid_ein CHECK (ein IS NULL OR ein ~ '^[0-9]{2}-[0-9]{7}$')
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_masajid_name ON masajid(name);
CREATE INDEX IF NOT EXISTS idx_masajid_city ON masajid(address_city);
CREATE INDEX IF NOT EXISTS idx_masajid_region ON masajid(region);
CREATE INDEX IF NOT EXISTS idx_masajid_verification ON masajid(verification_status);
CREATE INDEX IF NOT EXISTS idx_masajid_calendar ON masajid(google_calendar_id) WHERE google_calendar_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_masajid_501c3 ON masajid(is_501c3) WHERE is_501c3 = TRUE;

-- Unique constraint: name + city (same mosque name unlikely in same city)
CREATE UNIQUE INDEX IF NOT EXISTS idx_masajid_name_city
ON masajid(LOWER(name), LOWER(address_city));

-- Google Place ID index for deduplication
CREATE INDEX IF NOT EXISTS idx_masajid_google_place_id
ON masajid(google_place_id) WHERE google_place_id IS NOT NULL;

-- Trigger to auto-update updated_at
CREATE OR REPLACE FUNCTION update_masjid_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_masjid_timestamp ON masajid;
CREATE TRIGGER trigger_update_masjid_timestamp
    BEFORE UPDATE ON masajid
    FOR EACH ROW
    EXECUTE FUNCTION update_masjid_timestamp();

-- Insert migration record
INSERT INTO migration_history (version) VALUES ('032_masajid') ON CONFLICT DO NOTHING;
