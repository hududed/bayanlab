-- 025_business_claims.sql
-- Table for business owner claim submissions (self-service onboarding)

CREATE TABLE IF NOT EXISTS business_claim_submissions (
    claim_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Owner info
    owner_name VARCHAR(300) NOT NULL,
    owner_email VARCHAR(255) NOT NULL,
    owner_phone VARCHAR(50),

    -- Business essentials (required)
    business_name VARCHAR(300) NOT NULL,
    business_city VARCHAR(100) NOT NULL,
    business_state VARCHAR(2) NOT NULL DEFAULT 'CO',
    business_industry VARCHAR(100),
    business_website VARCHAR(1000),

    -- Optional enrichment (can follow up later)
    business_description TEXT, -- Services/products offered (free-form text)
    muslim_owned BOOLEAN DEFAULT FALSE

    -- Submission metadata
    submitted_at TIMESTAMPTZ DEFAULT NOW(),
    submitted_from VARCHAR(50), -- 'open_house', 'web', 'referral'
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'approved', 'imported', 'rejected'
    reviewed_at TIMESTAMPTZ,
    reviewed_by VARCHAR(100),
    notes TEXT,

    -- Link to canonical table (after import)
    business_id UUID REFERENCES business_canonical(business_id),

    CONSTRAINT valid_email CHECK (owner_email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),
    CONSTRAINT valid_state_claim CHECK (business_state IN ('CO', 'TX', 'CA', 'NY', 'IL', 'MI'))
);

CREATE INDEX idx_claims_status ON business_claim_submissions(status);
CREATE INDEX idx_claims_submitted ON business_claim_submissions(submitted_at DESC);
CREATE INDEX idx_claims_email ON business_claim_submissions(owner_email);
CREATE INDEX idx_claims_city_state ON business_claim_submissions(business_city, business_state);

-- Insert migration record
INSERT INTO migration_history (version) VALUES ('025_business_claims') ON CONFLICT DO NOTHING;
