-- 036_api_keys.sql
-- API keys table for paid data access (per ADR-022)

CREATE TABLE IF NOT EXISTS api_keys (
    key_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- The actual API key (hashed for security)
    api_key VARCHAR(64) UNIQUE NOT NULL,  -- sha256 hash of the key
    api_key_prefix VARCHAR(16) NOT NULL,  -- First chars for display (e.g., "bl_abc123...")

    -- Customer info
    email VARCHAR(255) NOT NULL,
    stripe_customer_id VARCHAR(100),
    stripe_payment_id VARCHAR(100),

    -- Access tier (per ADR-022)
    tier VARCHAR(20) NOT NULL DEFAULT 'developer',  -- 'developer', 'complete', 'enterprise'
    datasets TEXT[] NOT NULL DEFAULT '{}',  -- Which datasets: 'masajid', 'eateries', 'markets', 'businesses'

    -- Validity
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,  -- 1 year from creation for developer/complete
    is_active BOOLEAN DEFAULT TRUE,

    -- Usage tracking
    last_used_at TIMESTAMPTZ,
    request_count INTEGER DEFAULT 0,

    -- Metadata
    notes TEXT
);

-- Index for fast key lookup
CREATE INDEX IF NOT EXISTS idx_api_keys_key ON api_keys(api_key);
CREATE INDEX IF NOT EXISTS idx_api_keys_email ON api_keys(email);
CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(is_active, expires_at);

-- Insert migration record
INSERT INTO migration_history (version) VALUES ('036_api_keys') ON CONFLICT DO NOTHING;
