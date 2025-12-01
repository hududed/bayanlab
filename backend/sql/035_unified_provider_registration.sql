-- 035_unified_provider_registration.sql
-- Add columns for unified provider registration (Business + Individual/Tasker)
-- Per ADR-023: Unified Provider Registration

-- Provider type: 'business' or 'individual'
ALTER TABLE business_claim_submissions
ADD COLUMN IF NOT EXISTS provider_type VARCHAR(20) DEFAULT 'business';

-- Individual/Tasker specific fields
ALTER TABLE business_claim_submissions
ADD COLUMN IF NOT EXISTS display_name VARCHAR(200);

ALTER TABLE business_claim_submissions
ADD COLUMN IF NOT EXISTS skills TEXT[];  -- Array of skill tags

ALTER TABLE business_claim_submissions
ADD COLUMN IF NOT EXISTS service_area_miles INTEGER;

ALTER TABLE business_claim_submissions
ADD COLUMN IF NOT EXISTS hourly_rate_min DECIMAL(10,2);

ALTER TABLE business_claim_submissions
ADD COLUMN IF NOT EXISTS hourly_rate_max DECIMAL(10,2);

ALTER TABLE business_claim_submissions
ADD COLUMN IF NOT EXISTS availability TEXT[];  -- Array: weekday_morning, weekend_afternoon, etc.

-- Make owner_name and business_name optional (individuals don't have business_name)
-- Note: owner_name was previously NOT NULL, but individuals use display_name instead
ALTER TABLE business_claim_submissions
ALTER COLUMN owner_name DROP NOT NULL;

ALTER TABLE business_claim_submissions
ALTER COLUMN business_name DROP NOT NULL;

-- Index for filtering by provider type
CREATE INDEX IF NOT EXISTS idx_claims_provider_type ON business_claim_submissions(provider_type);

-- Index for skill-based queries (GIN index for array contains)
CREATE INDEX IF NOT EXISTS idx_claims_skills ON business_claim_submissions USING GIN(skills);

-- Insert migration record
INSERT INTO migration_history (version) VALUES ('035_unified_provider_registration') ON CONFLICT DO NOTHING;
