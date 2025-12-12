-- AOD Discover v3 Migration 002: Enhanced ingest_runs for Catalogs
-- Adds more detail columns for catalog run tracking

ALTER TABLE ingest_runs ADD COLUMN IF NOT EXISTS company_name TEXT;
ALTER TABLE ingest_runs ADD COLUMN IF NOT EXISTS cataloged_count INT DEFAULT 0;
ALTER TABLE ingest_runs ADD COLUMN IF NOT EXISTS findings_shadow_it INT DEFAULT 0;
ALTER TABLE ingest_runs ADD COLUMN IF NOT EXISTS findings_governance INT DEFAULT 0;
ALTER TABLE ingest_runs ADD COLUMN IF NOT EXISTS findings_data_conflicts INT DEFAULT 0;
ALTER TABLE ingest_runs ADD COLUMN IF NOT EXISTS findings_ops_risk INT DEFAULT 0;
ALTER TABLE ingest_runs ADD COLUMN IF NOT EXISTS findings_low_confidence INT DEFAULT 0;
ALTER TABLE ingest_runs ADD COLUMN IF NOT EXISTS blocking_sor_conflict INT DEFAULT 0;
ALTER TABLE ingest_runs ADD COLUMN IF NOT EXISTS blocking_schema_mismatch INT DEFAULT 0;
ALTER TABLE ingest_runs ADD COLUMN IF NOT EXISTS blocking_id_collision INT DEFAULT 0;
ALTER TABLE ingest_runs ADD COLUMN IF NOT EXISTS blocking_missing_id INT DEFAULT 0;

INSERT INTO schema_version (version) VALUES (2) ON CONFLICT DO NOTHING;
