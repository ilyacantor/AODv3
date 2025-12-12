-- Observed Breaches table for storing breach ledger per asset per run
CREATE TABLE IF NOT EXISTS observed_breaches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES ingest_runs(id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    breach_id VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    is_breached BOOLEAN NOT NULL DEFAULT true,
    severity_base VARCHAR(20) NOT NULL,
    evidence JSONB NOT NULL DEFAULT '{}',
    source VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_observed_breaches_run_id ON observed_breaches(run_id);
CREATE INDEX IF NOT EXISTS idx_observed_breaches_asset_id ON observed_breaches(asset_id);
CREATE INDEX IF NOT EXISTS idx_observed_breaches_breach_id ON observed_breaches(breach_id);
CREATE INDEX IF NOT EXISTS idx_observed_breaches_severity ON observed_breaches(severity_base);
