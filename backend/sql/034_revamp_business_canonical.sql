-- Migration 034: Revamp business_canonical table
-- Since table is empty, we can drop and recreate with clean schema
-- This table will be the source of truth for ProWasl business sync

-- Add new source enum values first (safe to run multiple times)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'mda_import' AND enumtypid = 'business_source'::regtype) THEN
        ALTER TYPE business_source ADD VALUE 'mda_import';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'mbc_import' AND enumtypid = 'business_source'::regtype) THEN
        ALTER TYPE business_source ADD VALUE 'mbc_import';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'muslimlistings_import' AND enumtypid = 'business_source'::regtype) THEN
        ALTER TYPE business_source ADD VALUE 'muslimlistings_import';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'emannest_import' AND enumtypid = 'business_source'::regtype) THEN
        ALTER TYPE business_source ADD VALUE 'emannest_import';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'claim_approved' AND enumtypid = 'business_source'::regtype) THEN
        ALTER TYPE business_source ADD VALUE 'claim_approved';
    END IF;
END$$;

-- Drop the empty table and recreate with clean schema
DROP TABLE IF EXISTS business_canonical CASCADE;

CREATE TABLE business_canonical (
    -- Identity
    business_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(300) NOT NULL,

    -- Location
    address_street VARCHAR(300),
    address_city VARCHAR(100) NOT NULL,
    address_state VARCHAR(10) NOT NULL,
    address_zip VARCHAR(10),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),

    -- Contact
    phone VARCHAR(50),
    email VARCHAR(255),
    website VARCHAR(1000),

    -- Business Info
    description TEXT,
    hours_raw TEXT,
    category business_category NOT NULL DEFAULT 'other',

    -- Ownership
    muslim_owned BOOLEAN DEFAULT TRUE,
    owner_name VARCHAR(300),
    owner_email VARCHAR(255),
    owner_phone VARCHAR(50),

    -- Verification Status
    verified BOOLEAN DEFAULT FALSE,  -- TRUE = syncs to ProWasl
    claim_id UUID,                   -- Link to original claim if from portal

    -- Source Tracking
    source business_source NOT NULL,
    source_ref VARCHAR(500),         -- Original ID/URL from source
    submitted_from VARCHAR(50),      -- 'mda_import', 'facebook_group', etc.

    -- Metadata
    region VARCHAR(10) DEFAULT 'US',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Dedup constraint: unique on (name, city, state) case-insensitive
CREATE UNIQUE INDEX idx_business_canonical_dedup
ON business_canonical (lower(name), lower(address_city), lower(address_state));

-- Query indexes
CREATE INDEX idx_business_canonical_verified ON business_canonical (verified);
CREATE INDEX idx_business_canonical_category ON business_canonical (category);
CREATE INDEX idx_business_canonical_city ON business_canonical (address_city);
CREATE INDEX idx_business_canonical_source ON business_canonical (source);
CREATE INDEX idx_business_canonical_region ON business_canonical (region);

-- Add comment documenting the table purpose
COMMENT ON TABLE business_canonical IS 'Source of truth for verified businesses. ProWasl syncs from this table where verified=TRUE.';
COMMENT ON COLUMN business_canonical.verified IS 'TRUE = business appears in ProWasl directory';
COMMENT ON COLUMN business_canonical.claim_id IS 'References business_claim_submissions if business came from claim portal';
