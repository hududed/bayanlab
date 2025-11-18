-- Add short claim ID for better UX
-- Format: PRW-XXXXX (e.g., PRW-A3X9K) - 8 characters total
-- Uses random alphanumeric to avoid exposing claim count

-- Function to generate random short code (uppercase alphanumeric, no confusing chars like O/0, I/1)
CREATE OR REPLACE FUNCTION generate_short_claim_id() RETURNS VARCHAR(10) AS $$
DECLARE
    chars TEXT := '23456789ABCDEFGHJKLMNPQRSTUVWXYZ';  -- No 0,1,I,O to avoid confusion
    result TEXT := 'PRW-';
    i INTEGER;
BEGIN
    FOR i IN 1..5 LOOP
        result := result || substr(chars, floor(random() * length(chars) + 1)::int, 1);
    END LOOP;
    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- Add short_claim_id column with random default
ALTER TABLE business_claim_submissions
  ADD COLUMN IF NOT EXISTS short_claim_id VARCHAR(10) DEFAULT generate_short_claim_id();

-- Make it unique (only if column was just created)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'unique_short_claim_id'
    ) THEN
        ALTER TABLE business_claim_submissions
          ADD CONSTRAINT unique_short_claim_id UNIQUE (short_claim_id);
    END IF;
END $$;

-- Create index for quick lookups
CREATE INDEX IF NOT EXISTS idx_business_claims_short_id
  ON business_claim_submissions(short_claim_id);
