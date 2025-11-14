-- Migration: Improve business claim data structure for ProWasl integration
-- Date: 2025-11-14
-- Description: Add missing fields for better business data quality

-- Add new columns to business_claim_submissions table
ALTER TABLE business_claim_submissions
  ADD COLUMN IF NOT EXISTS business_street_address TEXT,
  ADD COLUMN IF NOT EXISTS business_zip VARCHAR(10),
  ADD COLUMN IF NOT EXISTS business_phone VARCHAR(20),
  ADD COLUMN IF NOT EXISTS business_whatsapp VARCHAR(20),
  ADD COLUMN IF NOT EXISTS rejection_reason TEXT;

-- Add computed column for full address
ALTER TABLE business_claim_submissions
  ADD COLUMN IF NOT EXISTS business_full_address TEXT GENERATED ALWAYS AS (
    CASE
      WHEN business_street_address IS NOT NULL AND business_street_address != '' THEN
        business_street_address || ', ' || business_city || ', ' || business_state ||
        CASE WHEN business_zip IS NOT NULL AND business_zip != '' THEN ' ' || business_zip ELSE '' END
      ELSE
        business_city || ', ' || business_state
    END
  ) STORED;

-- Add index for faster lookups
CREATE INDEX IF NOT EXISTS idx_claims_full_address ON business_claim_submissions(business_full_address);
CREATE INDEX IF NOT EXISTS idx_claims_zip ON business_claim_submissions(business_zip) WHERE business_zip IS NOT NULL;

-- Add comments for documentation
COMMENT ON COLUMN business_claim_submissions.business_street_address IS 'Street address without city/state (e.g., "123 Main St")';
COMMENT ON COLUMN business_claim_submissions.business_zip IS 'ZIP/postal code';
COMMENT ON COLUMN business_claim_submissions.business_phone IS 'Business phone number (if different from owner phone)';
COMMENT ON COLUMN business_claim_submissions.business_whatsapp IS 'WhatsApp number for business communication';
COMMENT ON COLUMN business_claim_submissions.business_full_address IS 'Computed full address: street, city, state zip (or just city, state if no street)';
COMMENT ON COLUMN business_claim_submissions.rejection_reason IS 'Admin explanation for why claim was rejected';
