-- Track whether confirmation email has been sent
-- Useful for retroactive emails and debugging

ALTER TABLE business_claim_submissions
  ADD COLUMN IF NOT EXISTS confirmation_email_sent BOOLEAN DEFAULT FALSE;

ALTER TABLE business_claim_submissions
  ADD COLUMN IF NOT EXISTS confirmation_email_sent_at TIMESTAMP WITH TIME ZONE;

-- Create index for quick lookups
CREATE INDEX IF NOT EXISTS idx_business_claims_email_sent
  ON business_claim_submissions(confirmation_email_sent);
