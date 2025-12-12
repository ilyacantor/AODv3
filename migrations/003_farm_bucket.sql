-- AOD Discover v3 Migration 003: Farm Bucket Classification
-- Adds farm_bucket column for Farm's mutually exclusive classification

ALTER TABLE assets ADD COLUMN IF NOT EXISTS farm_bucket TEXT CHECK (farm_bucket IN ('clean', 'non_blocking', 'blocking', 'shadow'));

CREATE INDEX IF NOT EXISTS idx_assets_farm_bucket ON assets(farm_bucket);

INSERT INTO schema_version (version) VALUES (3) ON CONFLICT DO NOTHING;
