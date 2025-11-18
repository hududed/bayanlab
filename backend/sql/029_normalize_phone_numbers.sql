-- Normalize phone numbers to consistent format
-- Remove all non-digit characters, keep only numbers

-- Function to normalize phone numbers (US format: 10 digits)
CREATE OR REPLACE FUNCTION normalize_phone(phone_text TEXT) RETURNS TEXT AS $$
DECLARE
    digits_only TEXT;
BEGIN
    IF phone_text IS NULL OR phone_text = '' THEN
        RETURN NULL;
    END IF;

    -- Remove all non-digit characters
    digits_only := regexp_replace(phone_text, '[^0-9]', '', 'g');

    IF digits_only = '' THEN
        RETURN NULL;
    END IF;

    -- Remove leading 1 if 11 digits (US country code)
    IF LEFT(digits_only, 1) = '1' AND LENGTH(digits_only) = 11 THEN
        digits_only := SUBSTRING(digits_only FROM 2);
    END IF;

    RETURN digits_only;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Normalize existing phone numbers
UPDATE business_claim_submissions
SET owner_phone = normalize_phone(owner_phone)
WHERE owner_phone IS NOT NULL AND owner_phone != '';

UPDATE business_claim_submissions
SET business_phone = normalize_phone(business_phone)
WHERE business_phone IS NOT NULL AND business_phone != '';

UPDATE business_claim_submissions
SET business_whatsapp = normalize_phone(business_whatsapp)
WHERE business_whatsapp IS NOT NULL AND business_whatsapp != '';

-- Add check constraints to ensure only digits in phone fields
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'owner_phone_digits_only'
    ) THEN
        ALTER TABLE business_claim_submissions
          ADD CONSTRAINT owner_phone_digits_only
          CHECK (owner_phone IS NULL OR owner_phone ~ '^[0-9]*$');
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'business_phone_digits_only'
    ) THEN
        ALTER TABLE business_claim_submissions
          ADD CONSTRAINT business_phone_digits_only
          CHECK (business_phone IS NULL OR business_phone ~ '^[0-9]*$');
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'business_whatsapp_digits_only'
    ) THEN
        ALTER TABLE business_claim_submissions
          ADD CONSTRAINT business_whatsapp_digits_only
          CHECK (business_whatsapp IS NULL OR business_whatsapp ~ '^[0-9]*$');
    END IF;
END $$;
