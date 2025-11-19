-- Migration: Add geocoding fields to business claims
-- Date: 2025-11-19
-- Description: Add latitude/longitude for geocoded addresses

-- Add lat/lng columns to business_claim_submissions
ALTER TABLE business_claim_submissions
  ADD COLUMN IF NOT EXISTS latitude NUMERIC,
  ADD COLUMN IF NOT EXISTS longitude NUMERIC;

-- Add index for geospatial queries (if needed later)
CREATE INDEX IF NOT EXISTS idx_claims_coordinates
  ON business_claim_submissions(latitude, longitude)
  WHERE latitude IS NOT NULL AND longitude IS NOT NULL;

-- Add comments for documentation
COMMENT ON COLUMN business_claim_submissions.latitude IS 'Geocoded latitude (decimal degrees)';
COMMENT ON COLUMN business_claim_submissions.longitude IS 'Geocoded longitude (decimal degrees)';
