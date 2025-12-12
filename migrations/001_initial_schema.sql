-- AOD Discover v3 Initial Schema
-- Migration 001: Create core tables

CREATE TABLE IF NOT EXISTS schema_version (
    version INT PRIMARY KEY,
    applied_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    farm_asset_id TEXT NOT NULL,
    name TEXT NOT NULL,
    asset_kind TEXT NOT NULL,
    asset_type TEXT,
    vendor TEXT,
    environment TEXT,
    business_domain TEXT,
    tech_domain TEXT,
    system_role TEXT,
    owner TEXT,
    owner_email TEXT,
    owner_team TEXT,
    lifecycle_state TEXT NOT NULL CHECK (lifecycle_state IN ('DISCOVERED', 'PARKED', 'CATALOGED')) DEFAULT 'DISCOVERED',
    parked_reason TEXT,
    is_shadow_it BOOLEAN DEFAULT FALSE,
    has_data_conflicts BOOLEAN DEFAULT FALSE,
    lens_coverage JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, farm_asset_id)
);

CREATE TABLE IF NOT EXISTS findings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    finding_type TEXT NOT NULL,
    rule_id TEXT,
    severity TEXT NOT NULL CHECK (severity IN ('critical', 'warn', 'info')),
    status TEXT NOT NULL CHECK (status IN ('open', 'acknowledged', 'resolved', 'suppressed')) DEFAULT 'open',
    description TEXT NOT NULL,
    evidence JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ingest_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    archetype TEXT NOT NULL,
    scale TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'success', 'failed')) DEFAULT 'running',
    started_at TIMESTAMPTZ DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    total_assets INT DEFAULT 0,
    shadow_it_count INT DEFAULT 0,
    parked_count INT DEFAULT 0,
    message TEXT
);

CREATE INDEX IF NOT EXISTS idx_assets_tenant ON assets(tenant_id);
CREATE INDEX IF NOT EXISTS idx_assets_lifecycle ON assets(lifecycle_state);
CREATE INDEX IF NOT EXISTS idx_assets_shadow ON assets(is_shadow_it);
CREATE INDEX IF NOT EXISTS idx_findings_asset ON findings(asset_id);
CREATE INDEX IF NOT EXISTS idx_findings_type ON findings(finding_type);
CREATE INDEX IF NOT EXISTS idx_ingest_runs_tenant ON ingest_runs(tenant_id);

INSERT INTO schema_version (version) VALUES (1) ON CONFLICT DO NOTHING;
