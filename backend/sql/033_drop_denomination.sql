-- 033_drop_denomination.sql
-- Remove denomination column from masajid (all are Sunni, field is pointless)

ALTER TABLE masajid DROP COLUMN IF EXISTS denomination;

-- Insert migration record
INSERT INTO migration_history (version) VALUES ('033_drop_denomination') ON CONFLICT DO NOTHING;
