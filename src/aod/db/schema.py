"""Database schema initialization."""

import logging

logger = logging.getLogger(__name__)


async def initialize_schema(conn) -> None:
    """
    Initialize database schema.

    Extracted from Database.initialize() - lines 156-379 of original.
    """
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            input_meta TEXT NOT NULL DEFAULT '{}',
            counts TEXT NOT NULL DEFAULT '{}',
            failure_reasons TEXT NOT NULL DEFAULT '[]',
            sync_status TEXT NOT NULL DEFAULT 'not_applicable',
            sync_error TEXT,
            policy_snapshot TEXT
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS assets (
            asset_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            name TEXT NOT NULL,
            asset_type TEXT NOT NULL,
            identifiers TEXT NOT NULL DEFAULT '{}',
            vendor TEXT,
            vendor_hypothesis TEXT,
            environment TEXT NOT NULL,
            evidence_refs TEXT NOT NULL DEFAULT '[]',
            lens_status TEXT NOT NULL DEFAULT '{}',
            lens_coverage TEXT NOT NULL DEFAULT '{}',
            activity_evidence TEXT NOT NULL DEFAULT '{}',
            tags TEXT NOT NULL DEFAULT '[]',
            admission_reason TEXT NOT NULL DEFAULT '',
            provisioning_status TEXT NOT NULL DEFAULT 'quarantine',
            created_at TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(run_id)
        )
    """)

    # Schema migrations - log failures instead of silently ignoring
    try:
        await conn.execute("ALTER TABLE assets ADD COLUMN IF NOT EXISTS vendor_hypothesis TEXT")
    except Exception as e:
        logger.debug("Migration assets.vendor_hypothesis: %s", e)

    try:
        await conn.execute("ALTER TABLE assets ADD COLUMN IF NOT EXISTS provisioning_status TEXT NOT NULL DEFAULT 'quarantine'")
    except Exception as e:
        logger.debug("Migration assets.provisioning_status: %s", e)

    try:
        await conn.execute("ALTER TABLE findings ADD COLUMN IF NOT EXISTS category TEXT NOT NULL DEFAULT 'governance_finding'")
    except Exception as e:
        logger.debug("Migration findings.category: %s", e)

    try:
        await conn.execute("ALTER TABLE findings ADD COLUMN IF NOT EXISTS confidence TEXT NOT NULL DEFAULT 'med'")
        await conn.execute("ALTER TABLE findings ADD COLUMN IF NOT EXISTS materiality TEXT NOT NULL DEFAULT 'med'")
        await conn.execute("ALTER TABLE findings ADD COLUMN IF NOT EXISTS triage_priority TEXT NOT NULL DEFAULT 'p2'")
        await conn.execute("ALTER TABLE findings ADD COLUMN IF NOT EXISTS conflict_field TEXT")
    except Exception as e:
        logger.debug("Migration findings.(confidence|materiality|triage_priority|conflict_field): %s", e)

    try:
        await conn.execute("ALTER TABLE assets ADD COLUMN IF NOT EXISTS has_critical_gap BOOLEAN NOT NULL DEFAULT FALSE")
    except Exception as e:
        logger.debug("Migration assets.has_critical_gap: %s", e)

    try:
        await conn.execute("ALTER TABLE assets ADD COLUMN IF NOT EXISTS owner TEXT")
    except Exception as e:
        logger.debug("Migration assets.owner: %s", e)

    try:
        await conn.execute("ALTER TABLE assets ADD COLUMN IF NOT EXISTS lens_match_debug TEXT")
    except Exception as e:
        logger.debug("Migration assets.lens_match_debug: %s", e)

    try:
        await conn.execute("ALTER TABLE assets ADD COLUMN IF NOT EXISTS discovery_sources TEXT NOT NULL DEFAULT '[]'")
    except Exception as e:
        logger.debug("Migration assets.discovery_sources: %s", e)

    try:
        await conn.execute("ALTER TABLE runs ADD COLUMN IF NOT EXISTS stage_timings TEXT")
    except Exception as e:
        logger.debug("Migration runs.stage_timings: %s", e)

    try:
        await conn.execute("ALTER TABLE runs ADD COLUMN IF NOT EXISTS policy_snapshot TEXT")
    except Exception as e:
        logger.debug("Migration runs.policy_snapshot: %s", e)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS artifacts (
            artifact_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            parent_asset_id TEXT,
            name TEXT NOT NULL,
            artifact_type TEXT NOT NULL,
            source TEXT NOT NULL,
            evidence_ref TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(run_id),
            FOREIGN KEY (parent_asset_id) REFERENCES assets(asset_id)
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS findings (
            finding_id TEXT PRIMARY KEY,
            asset_id TEXT,
            tenant_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            finding_type TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'governance_finding',
            severity TEXT NOT NULL,
            explanation TEXT NOT NULL,
            evidence_refs TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(run_id),
            FOREIGN KEY (asset_id) REFERENCES assets(asset_id)
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS observation_samples (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            name TEXT NOT NULL,
            domain TEXT,
            source TEXT NOT NULL,
            category TEXT,
            raw_preview TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(run_id)
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS ambiguous_matches (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            entity_key TEXT NOT NULL,
            entity_name TEXT NOT NULL,
            plane TEXT NOT NULL,
            candidate_ids TEXT NOT NULL DEFAULT '[]',
            candidate_names TEXT NOT NULL DEFAULT '[]',
            match_keys TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(run_id)
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS rejections (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            entity_key TEXT NOT NULL,
            entity_name TEXT NOT NULL,
            reason_code TEXT NOT NULL,
            reason_detail TEXT NOT NULL,
            evidence_summary TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(run_id)
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS llm_facts (
            fact_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            entity_key TEXT NOT NULL,
            asset_type TEXT,
            entity_role TEXT,
            canonical_vendor TEXT,
            canonical_product TEXT,
            cmdb_ci_id TEXT,
            idp_object_id TEXT,
            confidence REAL NOT NULL DEFAULT 0.0,
            reason TEXT NOT NULL DEFAULT '',
            llm_provider TEXT NOT NULL,
            llm_model_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(tenant_id, entity_key)
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS triage_actions (
            action_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            item_type TEXT NOT NULL,
            action TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'new',
            owner TEXT,
            defer_until TEXT,
            ignore_reason TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(run_id)
        )
    """)

    await conn.execute("CREATE INDEX IF NOT EXISTS idx_triage_actions_run_id ON triage_actions(run_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_triage_actions_item ON triage_actions(item_id, item_type)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_triage_actions_tenant ON triage_actions(tenant_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_triage_actions_tenant_run ON triage_actions(tenant_id, run_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_assets_run_id ON assets(run_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_run_id ON artifacts(run_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_findings_run_id ON findings(run_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_findings_asset_id ON findings(asset_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_observation_samples_run_id ON observation_samples(run_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_ambiguous_matches_run_id ON ambiguous_matches(run_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_rejections_run_id ON rejections(run_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_llm_facts_tenant_entity ON llm_facts(tenant_id, entity_key)")
