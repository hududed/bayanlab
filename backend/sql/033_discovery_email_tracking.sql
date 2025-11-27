-- Add discovery email tracking for businesses added from external sources
-- These are businesses we discovered (e.g., from MBC) and want to notify

ALTER TABLE business_claim_submissions
ADD COLUMN IF NOT EXISTS discovery_email_sent BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS discovery_email_sent_at TIMESTAMPTZ;

-- Index for finding businesses that need discovery emails
CREATE INDEX IF NOT EXISTS idx_business_claims_discovery_email
ON business_claim_submissions (discovery_email_sent)
WHERE submitted_from != 'web' AND owner_email != 'import@bayanlab.com';

COMMENT ON COLUMN business_claim_submissions.discovery_email_sent IS 'Whether discovery notification email was sent to businesses found from external sources';
COMMENT ON COLUMN business_claim_submissions.discovery_email_sent_at IS 'When discovery notification email was sent';
