"""PostgreSQL persistence layer for AOD using asyncpg"""

import asyncpg
import json
import logging
import os
from datetime import datetime
from typing import Optional, AsyncGenerator
from uuid import UUID

logger = logging.getLogger(__name__)

from ..models.output_contracts import (
    Asset, Artifact, Finding, RunLog, RunStatus, RunCounts, SyncStatus,
    AssetType, Environment, LensStatus, LensStatuses, LensCoverage, LensMatchDebug,
    AssetIdentifiers, ActivityEvidence, FindingType, FindingCategory, Severity, ArtifactType,
    VendorHypothesis, Confidence, Materiality, TriagePriority, PipelineStageTimings,
    ProvisioningStatus, FabricPlaneTag, SORTagging
)


def get_database_url() -> str:
    """
    Get database URL with single selection rule:
    1. Use SUPABASE_DB_URL if set
    2. Else use DATABASE_URL
    3. If neither is set, fail fast with clear error
    
    No SQLite fallback or other defaults are allowed.
    """
    db_url = os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")
    
    if not db_url:
        raise RuntimeError(
            "No database configured. Set SUPABASE_DB_URL or DATABASE_URL environment variable. "
            "No SQLite fallback or other defaults are allowed."
        )
    
    return db_url


def get_active_db_source() -> str:
    """Return which env var is providing the database URL."""
    if os.environ.get("SUPABASE_DB_URL"):
        return "SUPABASE_DB_URL"
    elif os.environ.get("DATABASE_URL"):
        return "DATABASE_URL"
    else:
        return "NONE"


def _deserialize_asset_row(row: asyncpg.Record) -> Asset:
    """Deserialize a database row into an Asset object.

    Centralized helper to avoid duplication between get_assets_by_run and get_asset_by_id.
    """
    activity_evidence_data = row.get("activity_evidence", "{}")
    vendor_hypothesis_data = row.get("vendor_hypothesis")
    lens_match_debug_data = row.get("lens_match_debug")
    fabric_plane_tag_data = row.get("fabric_plane_tag")
    sor_tagging_data = row.get("sor_tagging")

    vendor_hypothesis = None
    lens_match_debug = None
    fabric_plane_tag = None
    sor_tagging = None
    
    if vendor_hypothesis_data:
        vendor_hypothesis = VendorHypothesis.model_validate_json(vendor_hypothesis_data)
    if lens_match_debug_data:
        lens_match_debug = LensMatchDebug.model_validate_json(lens_match_debug_data)
    if fabric_plane_tag_data:
        fabric_plane_tag = FabricPlaneTag.model_validate_json(fabric_plane_tag_data)
    if sor_tagging_data:
        sor_tagging = SORTagging.model_validate_json(sor_tagging_data)

    prov_status_raw = row.get("provisioning_status", "quarantine")
    try:
        prov_status = ProvisioningStatus(prov_status_raw)
    except ValueError:
        prov_status = ProvisioningStatus.QUARANTINE

    return Asset(
        asset_id=UUID(row["asset_id"]),
        tenant_id=row["tenant_id"],
        aod_discovery_id=row["run_id"],
        name=row["name"],
        asset_type=AssetType(row["asset_type"]),
        identifiers=AssetIdentifiers.model_validate_json(row["identifiers"]),
        vendor=row["vendor"],
        vendor_hypothesis=vendor_hypothesis,
        environment=Environment(row["environment"]),
        evidence_refs=json.loads(row["evidence_refs"]),
        lens_status=LensStatuses.model_validate_json(row["lens_status"]),
        lens_coverage=LensCoverage.model_validate_json(row["lens_coverage"]),
        lens_match_debug=lens_match_debug,
        activity_evidence=ActivityEvidence.model_validate_json(activity_evidence_data) if activity_evidence_data else ActivityEvidence(),
        tags=json.loads(row["tags"]),
        admission_reason=row["admission_reason"],
        provisioning_status=prov_status,
        has_critical_gap=row.get("has_critical_gap", False),
        owner=row.get("owner"),
        discovery_sources=json.loads(row.get("discovery_sources", "[]")),
        fabric_plane_tag=fabric_plane_tag,
        sor_tagging=sor_tagging,
        created_at=datetime.fromisoformat(row["created_at"])
    )


_db_instance: Optional["Database"] = None


async def get_db() -> AsyncGenerator["Database", None]:
    """
    FastAPI dependency for database access.

    Yields a Database instance for use in route handlers.
    Maintains a singleton pool but compatible with dependency injection.

    Usage:
        @router.get("/example")
        async def example(db: Database = Depends(get_db)):
            await db.get_run(run_id)
    """
    global _db_instance
    if _db_instance is None:
        db_url = get_database_url()
        _db_instance = Database(db_url)
        await _db_instance.initialize()
    yield _db_instance


async def get_db_direct() -> "Database":
    """
    Direct database access for non-FastAPI contexts (e.g., pipeline executor).

    Returns the Database instance directly instead of yielding.
    Use this in pipeline code where Depends() is not available.
    """
    global _db_instance
    if _db_instance is None:
        db_url = get_database_url()
        _db_instance = Database(db_url)
        await _db_instance.initialize()
    return _db_instance


async def close_db() -> None:
    """Close the singleton DB pool. Call on app shutdown.

    Without this, an unclosed asyncpg pool's connections linger on the
    Supabase pooler after the worker stops. In session mode they hold client
    slots against the per-tenant cap (pool_size 15) until the pooler reaps
    them, so repeated restarts/reloads accumulate orphans and new runs fail
    with EMAXCONNSESSION. Closing on shutdown releases them immediately.
    """
    global _db_instance
    if _db_instance is not None:
        await _db_instance.close()
        _db_instance = None


class Database:
    """PostgreSQL database for AOD persistence"""
    
    def __init__(self, db_url: str):
        self.db_url = db_url
        self._pool: Optional[asyncpg.Pool] = None
    
    async def get_pool(self) -> asyncpg.Pool:
        """Get database connection pool"""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self.db_url,
                min_size=1,
                max_size=10,
                # statement_cache_size=0 makes asyncpg safe behind a
                # transaction-mode pooler (Supavisor :6543), which multiplexes
                # server connections and breaks on cached named prepared
                # statements. Harmless in session mode.
                statement_cache_size=0,
            )
        return self._pool
    
    async def close(self):
        """Close database connection pool"""
        if self._pool:
            await self._pool.close()
            self._pool = None
    
    async def initialize(self):
        """Initialize database schema"""
        pool = await self.get_pool()
        
        async with pool.acquire() as conn:
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

            try:
                await conn.execute("ALTER TABLE runs ADD COLUMN IF NOT EXISTS entity_id TEXT")
            except Exception as e:
                logger.debug("Migration runs.entity_id: %s", e)

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
    
    async def create_run(self, run: RunLog) -> RunLog:
        """Create a new run log entry"""
        pool = await self.get_pool()
        
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO runs (run_id, tenant_id, entity_id, status, started_at, completed_at, input_meta, counts, failure_reasons, sync_status, sync_error, stage_timings, policy_snapshot)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                """,
                run.aod_discovery_id,
                run.tenant_id,
                run.entity_id,
                run.status.value,
                run.started_at.isoformat(),
                run.completed_at.isoformat() if run.completed_at else None,
                json.dumps(run.input_meta),
                run.counts.model_dump_json(),
                json.dumps(run.failure_reasons),
                run.sync_status.value,
                run.sync_error,
                run.stage_timings.model_dump_json() if run.stage_timings else None,
                json.dumps(run.policy_snapshot) if run.policy_snapshot else None
            )
        return run
    
    async def update_run(self, run: RunLog) -> RunLog:
        """Update an existing run log entry"""
        pool = await self.get_pool()
        
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE runs SET
                    status = $1,
                    completed_at = $2,
                    counts = $3,
                    failure_reasons = $4,
                    sync_status = $5,
                    sync_error = $6,
                    stage_timings = $7,
                    policy_snapshot = $8,
                    input_meta = $9,
                    entity_id = $10
                WHERE run_id = $11
                """,
                run.status.value,
                run.completed_at.isoformat() if run.completed_at else None,
                run.counts.model_dump_json(),
                json.dumps(run.failure_reasons),
                run.sync_status.value,
                run.sync_error,
                run.stage_timings.model_dump_json() if run.stage_timings else None,
                json.dumps(run.policy_snapshot) if run.policy_snapshot else None,
                json.dumps(run.input_meta),
                run.entity_id,
                run.aod_discovery_id
            )
        return run

    async def get_run(self, run_id: str) -> Optional[RunLog]:
        """Get a run log entry by ID"""
        pool = await self.get_pool()
        
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM runs WHERE run_id = $1",
                run_id
            )
        
        if not row:
            return None
        
        sync_status_val = row.get("sync_status", "not_applicable")
        sync_error_val = row.get("sync_error")
        stage_timings_data = row.get("stage_timings")
        policy_snapshot_data = row.get("policy_snapshot")
        
        return RunLog(
            aod_discovery_id=row["run_id"],
            tenant_id=row["tenant_id"],
            entity_id=row.get("entity_id"),
            status=RunStatus(row["status"]),
            started_at=datetime.fromisoformat(row["started_at"]),
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            input_meta=json.loads(row["input_meta"]),
            counts=RunCounts.model_validate_json(row["counts"]),
            stage_timings=PipelineStageTimings.model_validate_json(stage_timings_data) if stage_timings_data else None,
            failure_reasons=json.loads(row["failure_reasons"]),
            sync_status=SyncStatus(sync_status_val),
            sync_error=sync_error_val,
            policy_snapshot=json.loads(policy_snapshot_data) if policy_snapshot_data else None
        )

    async def get_latest_run_for_tenant(
        self, tenant_id: str, snapshot_id: Optional[str] = None
    ) -> Optional[RunLog]:
        """Get the latest run for a tenant, optionally filtered by snapshot_id.

        Uses a SQL WHERE clause — does NOT load all runs.
        """
        pool = await self.get_pool()

        async with pool.acquire() as conn:
            if snapshot_id:
                row = await conn.fetchrow(
                    """
                    SELECT * FROM runs
                    WHERE tenant_id = $1
                      AND input_meta::jsonb ->> 'snapshot_id' = $2
                    ORDER BY started_at DESC
                    LIMIT 1
                    """,
                    tenant_id,
                    snapshot_id,
                )
            else:
                row = await conn.fetchrow(
                    """
                    SELECT * FROM runs
                    WHERE tenant_id = $1
                    ORDER BY started_at DESC
                    LIMIT 1
                    """,
                    tenant_id,
                )

        if not row:
            return None

        sync_status_val = row.get("sync_status", "not_applicable")
        sync_error_val = row.get("sync_error")
        stage_timings_data = row.get("stage_timings")
        policy_snapshot_data = row.get("policy_snapshot")

        return RunLog(
            aod_discovery_id=row["run_id"],
            tenant_id=row["tenant_id"],
            entity_id=row.get("entity_id"),
            status=RunStatus(row["status"]),
            started_at=datetime.fromisoformat(row["started_at"]),
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            input_meta=json.loads(row["input_meta"]),
            counts=RunCounts.model_validate_json(row["counts"]),
            stage_timings=PipelineStageTimings.model_validate_json(stage_timings_data) if stage_timings_data else None,
            failure_reasons=json.loads(row["failure_reasons"]),
            sync_status=SyncStatus(sync_status_val),
            sync_error=sync_error_val,
            policy_snapshot=json.loads(policy_snapshot_data) if policy_snapshot_data else None
        )

    async def get_all_runs(self) -> list[RunLog]:
        """Get all run logs"""
        pool = await self.get_pool()
        
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM runs ORDER BY started_at DESC"
            )
        
        runs = []
        for row in rows:
            sync_status_val = row.get("sync_status", "not_applicable")
            sync_error_val = row.get("sync_error")
            stage_timings_data = row.get("stage_timings")
            policy_snapshot_data = row.get("policy_snapshot")
            runs.append(RunLog(
                aod_discovery_id=row["run_id"],
                tenant_id=row["tenant_id"],
                entity_id=row.get("entity_id"),
                status=RunStatus(row["status"]),
                started_at=datetime.fromisoformat(row["started_at"]),
                completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
                input_meta=json.loads(row["input_meta"]),
                counts=RunCounts.model_validate_json(row["counts"]),
                stage_timings=PipelineStageTimings.model_validate_json(stage_timings_data) if stage_timings_data else None,
                failure_reasons=json.loads(row["failure_reasons"]),
                sync_status=SyncStatus(sync_status_val),
                sync_error=sync_error_val,
                policy_snapshot=json.loads(policy_snapshot_data) if policy_snapshot_data else None
            ))
        return runs
    
    async def delete_all_runs(self) -> int:
        """Delete all runs and associated data (assets, findings, etc.)"""
        pool = await self.get_pool()
        
        async with pool.acquire() as conn:
            for table in ["triage_actions", "observation_samples", "derived_classifications", "llm_facts", "rejections", "ambiguous_matches", "artifacts", "findings", "assets"]:
                try:
                    await conn.execute(f"DELETE FROM {table}")
                except Exception as e:
                    logger.warning("Failed to DELETE FROM %s during clear_all_data: %s", table, e)
            result = await conn.execute("DELETE FROM runs")
            deleted = int(result.split()[-1]) if result else 0
        return deleted
    
    async def prune_old_runs(self, keep: int = 6) -> int:
        """Delete oldest runs keeping only the most recent `keep` runs."""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            old_run_ids = await conn.fetch(
                """
                SELECT run_id FROM runs
                ORDER BY started_at DESC
                OFFSET $1
                """,
                keep,
            )
            if not old_run_ids:
                return 0
            ids = [r["run_id"] for r in old_run_ids]
            for table in ["triage_actions", "observation_samples", "derived_classifications", "llm_facts", "rejections", "ambiguous_matches", "artifacts", "findings", "assets"]:
                try:
                    await conn.execute(f"DELETE FROM {table} WHERE run_id = ANY($1)", ids)
                except Exception as e:
                    logger.warning("Failed to DELETE FROM %s during prune_old_runs: %s", table, e)
            result = await conn.execute("DELETE FROM runs WHERE run_id = ANY($1)", ids)
            deleted = int(result.split()[-1]) if result else 0
            return deleted

    async def get_recent_tenants(self, limit: int = 5) -> list[str]:
        """Get unique tenant_ids from recent runs for offline fallback."""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT ON (tenant_id) tenant_id
                FROM runs
                WHERE tenant_id IS NOT NULL AND tenant_id != ''
                ORDER BY tenant_id, started_at DESC
                LIMIT $1
                """,
                limit,
            )
            return sorted([r["tenant_id"] for r in rows])

    async def create_asset(self, asset: Asset) -> Asset:
        """Create a new asset"""
        pool = await self.get_pool()
        
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO assets (
                    asset_id, tenant_id, run_id, name, asset_type, identifiers,
                    vendor, vendor_hypothesis, environment, evidence_refs, lens_status, lens_coverage,
                    lens_match_debug, activity_evidence, tags, admission_reason, provisioning_status, has_critical_gap, owner, discovery_sources, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21)
                ON CONFLICT (asset_id) DO UPDATE SET
                    run_id = EXCLUDED.run_id,
                    asset_type = EXCLUDED.asset_type,
                    identifiers = EXCLUDED.identifiers,
                    vendor = EXCLUDED.vendor,
                    vendor_hypothesis = EXCLUDED.vendor_hypothesis,
                    environment = EXCLUDED.environment,
                    evidence_refs = EXCLUDED.evidence_refs,
                    lens_status = EXCLUDED.lens_status,
                    lens_coverage = EXCLUDED.lens_coverage,
                    lens_match_debug = EXCLUDED.lens_match_debug,
                    activity_evidence = EXCLUDED.activity_evidence,
                    tags = EXCLUDED.tags,
                    admission_reason = EXCLUDED.admission_reason,
                    provisioning_status = EXCLUDED.provisioning_status,
                    has_critical_gap = EXCLUDED.has_critical_gap,
                    owner = COALESCE(assets.owner, EXCLUDED.owner),
                    discovery_sources = EXCLUDED.discovery_sources,
                    created_at = EXCLUDED.created_at
                """,
                str(asset.asset_id),
                asset.tenant_id,
                asset.aod_discovery_id,
                asset.name,
                asset.asset_type.value,
                asset.identifiers.model_dump_json(),
                asset.vendor,
                asset.vendor_hypothesis.model_dump_json() if asset.vendor_hypothesis else None,
                asset.environment.value,
                json.dumps(asset.evidence_refs),
                asset.lens_status.model_dump_json(),
                asset.lens_coverage.model_dump_json(),
                asset.lens_match_debug.model_dump_json() if asset.lens_match_debug else None,
                asset.activity_evidence.model_dump_json(),
                json.dumps(asset.tags),
                asset.admission_reason,
                asset.provisioning_status.value,
                asset.has_critical_gap,
                asset.owner,
                json.dumps(asset.discovery_sources),
                asset.created_at.isoformat()
            )
        return asset
    
    async def get_assets_by_run(self, run_id: str) -> list[Asset]:
        """Get all assets for a run"""
        pool = await self.get_pool()
        
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM assets WHERE run_id = $1 ORDER BY name",
                run_id
            )
        
        return [_deserialize_asset_row(row) for row in rows]
    
    async def get_asset_by_id(self, asset_id: str) -> Optional[Asset]:
        """Get a single asset by ID"""
        pool = await self.get_pool()
        
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM assets WHERE asset_id = $1",
                asset_id
            )
        
        if not row:
            return None

        return _deserialize_asset_row(row)
    
    async def update_asset_owner(self, asset_id: str, owner: str) -> bool:
        """Update an asset's owner field"""
        pool = await self.get_pool()
        
        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE assets 
                SET owner = $2
                WHERE asset_id = $1
                """,
                asset_id,
                owner
            )
        
        return "UPDATE 1" in result
    
    async def update_asset_provisioning_status(
        self, 
        asset_id: str, 
        new_status: str,
        reason: Optional[str] = None,
        actor: Optional[str] = None
    ) -> bool:
        """Update an asset's provisioning status"""
        pool = await self.get_pool()
        
        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE assets 
                SET provisioning_status = $2
                WHERE asset_id = $1
                """,
                asset_id,
                new_status
            )
        
        return "UPDATE 1" in result
    
    async def create_artifact(self, artifact: Artifact) -> Artifact:
        """Create a new artifact"""
        pool = await self.get_pool()
        
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO artifacts (
                    artifact_id, tenant_id, run_id, parent_asset_id, name,
                    artifact_type, source, evidence_ref, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                str(artifact.artifact_id),
                artifact.tenant_id,
                artifact.aod_discovery_id,
                str(artifact.parent_asset_id) if artifact.parent_asset_id else None,
                artifact.name,
                artifact.artifact_type.value,
                artifact.source,
                artifact.evidence_ref,
                artifact.created_at.isoformat()
            )
        return artifact
    
    async def get_artifacts_by_run(self, run_id: str) -> list[Artifact]:
        """Get all artifacts for a run"""
        pool = await self.get_pool()
        
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM artifacts WHERE run_id = $1 ORDER BY name",
                run_id
            )
        
        return [
            Artifact(
                artifact_id=UUID(row["artifact_id"]),
                tenant_id=row["tenant_id"],
                aod_discovery_id=row["run_id"],
                parent_asset_id=UUID(row["parent_asset_id"]) if row["parent_asset_id"] else None,
                name=row["name"],
                artifact_type=ArtifactType(row["artifact_type"]),
                source=row["source"],
                evidence_ref=row["evidence_ref"],
                created_at=datetime.fromisoformat(row["created_at"])
            )
            for row in rows
        ]
    
    async def create_finding(self, finding: Finding) -> Finding:
        """Create a new finding"""
        pool = await self.get_pool()
        
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO findings (
                    finding_id, asset_id, tenant_id, run_id, finding_type,
                    category, severity, explanation, evidence_refs, created_at,
                    confidence, materiality, triage_priority, conflict_field
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                """,
                str(finding.finding_id),
                str(finding.asset_id) if finding.asset_id else None,
                finding.tenant_id,
                finding.aod_discovery_id,
                finding.finding_type.value,
                finding.category.value,
                finding.severity.value,
                finding.explanation,
                json.dumps(finding.evidence_refs),
                finding.created_at.isoformat(),
                finding.confidence.value,
                finding.materiality.value,
                finding.triage_priority.value,
                finding.conflict_field
            )
        return finding
    
    async def get_findings_by_run(self, run_id: str) -> list[Finding]:
        """Get all findings for a run"""
        pool = await self.get_pool()
        
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM findings WHERE run_id = $1 ORDER BY triage_priority ASC, finding_type",
                run_id
            )
        
        return [
            Finding(
                finding_id=UUID(row["finding_id"]),
                asset_id=UUID(row["asset_id"]) if row["asset_id"] else None,
                tenant_id=row["tenant_id"],
                aod_discovery_id=row["run_id"],
                finding_type=FindingType(row["finding_type"]),
                category=FindingCategory(row["category"]) if row.get("category") else FindingCategory.GOVERNANCE_FINDING,
                severity=Severity(row["severity"]),
                explanation=row["explanation"],
                evidence_refs=json.loads(row["evidence_refs"]),
                created_at=datetime.fromisoformat(row["created_at"]),
                confidence=Confidence(row["confidence"]) if row.get("confidence") else Confidence.MED,
                materiality=Materiality(row["materiality"]) if row.get("materiality") else Materiality.MED,
                triage_priority=TriagePriority(row["triage_priority"]) if row.get("triage_priority") else TriagePriority.P2,
                conflict_field=row.get("conflict_field")
            )
            for row in rows
        ]
    
    async def create_observation_sample(
        self,
        sample_id: str,
        run_id: str,
        name: str,
        domain: Optional[str],
        source: str,
        category: Optional[str],
        raw_preview: str,
        created_at: datetime
    ) -> None:
        """Create an observation sample record"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO observation_samples (id, run_id, name, domain, source, category, raw_preview, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                sample_id, run_id, name, domain, source, category, raw_preview, created_at.isoformat()
            )
    
    async def create_ambiguous_match(
        self,
        match_id: str,
        run_id: str,
        entity_key: str,
        entity_name: str,
        plane: str,
        candidate_ids: list[str],
        candidate_names: list[str],
        match_keys: list[str],
        created_at: datetime
    ) -> None:
        """Create an ambiguous match record"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO ambiguous_matches (id, run_id, entity_key, entity_name, plane, candidate_ids, candidate_names, match_keys, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                match_id, run_id, entity_key, entity_name, plane,
                json.dumps(candidate_ids), json.dumps(candidate_names), json.dumps(match_keys),
                created_at.isoformat()
            )
    
    async def create_rejection(
        self,
        rejection_id: str,
        run_id: str,
        entity_key: str,
        entity_name: str,
        reason_code: str,
        reason_detail: str,
        evidence_summary: dict,
        created_at: datetime
    ) -> None:
        """Create a rejection record"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO rejections (id, run_id, entity_key, entity_name, reason_code, reason_detail, evidence_summary, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                rejection_id, run_id, entity_key, entity_name, reason_code, reason_detail,
                json.dumps(evidence_summary), created_at.isoformat()
            )
    
    async def get_observation_samples_by_run(self, run_id: str, limit: int = 100, offset: int = 0) -> tuple[list[dict], int]:
        """Get observation samples for a run with pagination"""
        pool = await self.get_pool()
        
        async with pool.acquire() as conn:
            count_row = await conn.fetchrow(
                "SELECT COUNT(*) as total FROM observation_samples WHERE run_id = $1",
                run_id
            )
            total = count_row["total"] if count_row else 0
            
            rows = await conn.fetch(
                "SELECT * FROM observation_samples WHERE run_id = $1 ORDER BY name LIMIT $2 OFFSET $3",
                run_id, limit, offset
            )
        
        items = [
            {
                "id": row["id"],
                "name": row["name"],
                "domain": row["domain"],
                "source": row["source"],
                "category": row["category"],
                "raw_preview": row["raw_preview"],
                "created_at": row["created_at"]
            }
            for row in rows
        ]
        return items, total
    
    async def get_ambiguous_matches_by_run(self, run_id: str, limit: int = 100, offset: int = 0) -> tuple[list[dict], int]:
        """Get ambiguous matches for a run with pagination"""
        pool = await self.get_pool()
        
        async with pool.acquire() as conn:
            count_row = await conn.fetchrow(
                "SELECT COUNT(*) as total FROM ambiguous_matches WHERE run_id = $1",
                run_id
            )
            total = count_row["total"] if count_row else 0
            
            rows = await conn.fetch(
                "SELECT * FROM ambiguous_matches WHERE run_id = $1 ORDER BY entity_name LIMIT $2 OFFSET $3",
                run_id, limit, offset
            )
        
        items = [
            {
                "id": row["id"],
                "entity_key": row["entity_key"],
                "entity_name": row["entity_name"],
                "plane": row["plane"],
                "candidate_ids": json.loads(row["candidate_ids"]),
                "candidate_names": json.loads(row["candidate_names"]),
                "match_keys": json.loads(row["match_keys"]),
                "created_at": row["created_at"]
            }
            for row in rows
        ]
        return items, total
    
    async def get_rejections_by_run(self, run_id: str, limit: int = 100, offset: int = 0) -> tuple[list[dict], int]:
        """Get rejections for a run with pagination"""
        pool = await self.get_pool()
        
        async with pool.acquire() as conn:
            count_row = await conn.fetchrow(
                "SELECT COUNT(*) as total FROM rejections WHERE run_id = $1",
                run_id
            )
            total = count_row["total"] if count_row else 0
            
            rows = await conn.fetch(
                "SELECT * FROM rejections WHERE run_id = $1 ORDER BY entity_name LIMIT $2 OFFSET $3",
                run_id, limit, offset
            )
        
        items = [
            {
                "id": row["id"],
                "entity_key": row["entity_key"],
                "entity_name": row["entity_name"],
                "reason_code": row["reason_code"],
                "reason_detail": row["reason_detail"],
                "evidence_summary": json.loads(row["evidence_summary"]),
                "created_at": row["created_at"]
            }
            for row in rows
        ]
        return items, total
    
    async def create_observation_samples_batch(self, samples: list[tuple]) -> None:
        """Batch insert observation samples. Each tuple: (id, run_id, name, domain, source, category, raw_preview, created_at)"""
        if not samples:
            return
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO observation_samples (id, run_id, name, domain, source, category, raw_preview, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                samples
            )
    
    async def create_ambiguous_matches_batch(self, matches: list[tuple]) -> None:
        """Batch insert ambiguous matches. Each tuple: (id, run_id, entity_key, entity_name, plane, candidate_ids_json, candidate_names_json, match_keys_json, created_at)"""
        if not matches:
            return
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO ambiguous_matches (id, run_id, entity_key, entity_name, plane, candidate_ids, candidate_names, match_keys, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                matches
            )
    
    async def create_rejections_batch(self, rejections: list[tuple]) -> None:
        """Batch insert rejections. Each tuple: (id, run_id, entity_key, entity_name, reason_code, reason_detail, evidence_summary_json, created_at)"""
        if not rejections:
            return
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO rejections (id, run_id, entity_key, entity_name, reason_code, reason_detail, evidence_summary, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                rejections
            )
    
    async def create_assets_batch(self, assets: list[Asset]) -> None:
        """Batch insert assets"""
        if not assets:
            return
        pool = await self.get_pool()
        rows = []
        for asset in assets:
            rows.append((
                str(asset.asset_id),
                asset.tenant_id,
                asset.aod_discovery_id,
                asset.name,
                asset.asset_type.value,
                asset.identifiers.model_dump_json(),
                asset.vendor,
                asset.vendor_hypothesis.model_dump_json() if asset.vendor_hypothesis else None,
                asset.environment.value,
                json.dumps(asset.evidence_refs),
                asset.lens_status.model_dump_json(),
                asset.lens_coverage.model_dump_json(),
                asset.lens_match_debug.model_dump_json() if asset.lens_match_debug else None,
                asset.activity_evidence.model_dump_json(),
                json.dumps(asset.tags),
                asset.admission_reason,
                asset.provisioning_status.value,
                asset.has_critical_gap,
                asset.owner,
                json.dumps(asset.discovery_sources),
                asset.fabric_plane_tag.model_dump_json() if asset.fabric_plane_tag else None,
                asset.sor_tagging.model_dump_json() if asset.sor_tagging else None,
                asset.created_at.isoformat()
            ))
        async with pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO assets (
                    asset_id, tenant_id, run_id, name, asset_type, identifiers,
                    vendor, vendor_hypothesis, environment, evidence_refs, lens_status, lens_coverage,
                    lens_match_debug, activity_evidence, tags, admission_reason, provisioning_status, 
                    has_critical_gap, owner, discovery_sources, fabric_plane_tag, sor_tagging, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23)
                ON CONFLICT (asset_id) DO UPDATE SET
                    run_id = EXCLUDED.run_id,
                    asset_type = EXCLUDED.asset_type,
                    identifiers = EXCLUDED.identifiers,
                    vendor = EXCLUDED.vendor,
                    vendor_hypothesis = EXCLUDED.vendor_hypothesis,
                    environment = EXCLUDED.environment,
                    evidence_refs = EXCLUDED.evidence_refs,
                    lens_status = EXCLUDED.lens_status,
                    lens_coverage = EXCLUDED.lens_coverage,
                    lens_match_debug = EXCLUDED.lens_match_debug,
                    activity_evidence = EXCLUDED.activity_evidence,
                    tags = EXCLUDED.tags,
                    admission_reason = EXCLUDED.admission_reason,
                    provisioning_status = EXCLUDED.provisioning_status,
                    has_critical_gap = EXCLUDED.has_critical_gap,
                    owner = COALESCE(assets.owner, EXCLUDED.owner),
                    discovery_sources = EXCLUDED.discovery_sources,
                    fabric_plane_tag = EXCLUDED.fabric_plane_tag,
                    sor_tagging = EXCLUDED.sor_tagging,
                    created_at = EXCLUDED.created_at
                """,
                rows
            )
    
    async def create_findings_batch(self, findings: list[Finding]) -> None:
        """Batch insert findings"""
        if not findings:
            return
        pool = await self.get_pool()
        rows = []
        for f in findings:
            rows.append((
                str(f.finding_id),
                str(f.asset_id) if f.asset_id else None,
                f.tenant_id,
                f.aod_discovery_id,
                f.finding_type.value,
                f.category.value,
                f.severity.value,
                f.explanation,
                json.dumps(f.evidence_refs),
                f.created_at.isoformat()
            ))
        async with pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO findings (
                    finding_id, asset_id, tenant_id, run_id, finding_type,
                    category, severity, explanation, evidence_refs, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (finding_id) DO UPDATE SET
                    asset_id = EXCLUDED.asset_id,
                    finding_type = EXCLUDED.finding_type,
                    category = EXCLUDED.category,
                    severity = EXCLUDED.severity,
                    explanation = EXCLUDED.explanation,
                    evidence_refs = EXCLUDED.evidence_refs,
                    created_at = EXCLUDED.created_at
                """,
                rows
            )
    
    async def create_artifacts_batch(self, artifacts: list[Artifact]) -> None:
        """Batch insert artifacts"""
        if not artifacts:
            return
        pool = await self.get_pool()
        rows = []
        for artifact in artifacts:
            rows.append((
                str(artifact.artifact_id),
                artifact.tenant_id,
                artifact.aod_discovery_id,
                str(artifact.parent_asset_id) if artifact.parent_asset_id else None,
                artifact.name,
                artifact.artifact_type.value,
                artifact.source,
                artifact.evidence_ref,
                artifact.created_at.isoformat()
            ))
        async with pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO artifacts (
                    artifact_id, tenant_id, run_id, parent_asset_id, name,
                    artifact_type, source, evidence_ref, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (artifact_id) DO UPDATE SET
                    parent_asset_id = EXCLUDED.parent_asset_id,
                    name = EXCLUDED.name,
                    artifact_type = EXCLUDED.artifact_type,
                    source = EXCLUDED.source,
                    evidence_ref = EXCLUDED.evidence_ref,
                    created_at = EXCLUDED.created_at
                """,
                rows
            )
    
    async def get_llm_fact(self, tenant_id: str, entity_key: str) -> Optional[dict]:
        """Get an LLM fact by tenant and entity key"""
        pool = await self.get_pool()
        
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM llm_facts WHERE tenant_id = $1 AND entity_key = $2",
                tenant_id, entity_key
            )
        
        if not row:
            return None
        
        return {
            "fact_id": row["fact_id"],
            "tenant_id": row["tenant_id"],
            "entity_key": row["entity_key"],
            "asset_type": row["asset_type"],
            "entity_role": row["entity_role"],
            "canonical_vendor": row["canonical_vendor"],
            "canonical_product": row["canonical_product"],
            "cmdb_ci_id": row["cmdb_ci_id"],
            "idp_object_id": row["idp_object_id"],
            "confidence": row["confidence"],
            "reason": row["reason"],
            "llm_provider": row["llm_provider"],
            "llm_model_id": row["llm_model_id"],
            "created_at": row["created_at"]
        }
    
    async def upsert_llm_fact(
        self,
        fact_id: str,
        tenant_id: str,
        entity_key: str,
        asset_type: Optional[str],
        entity_role: Optional[str],
        canonical_vendor: Optional[str],
        canonical_product: Optional[str],
        cmdb_ci_id: Optional[str],
        idp_object_id: Optional[str],
        confidence: float,
        reason: str,
        llm_provider: str,
        llm_model_id: str,
        created_at: datetime
    ) -> None:
        """Insert or update an LLM fact"""
        pool = await self.get_pool()
        
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO llm_facts (
                    fact_id, tenant_id, entity_key, asset_type, entity_role,
                    canonical_vendor, canonical_product, cmdb_ci_id, idp_object_id,
                    confidence, reason, llm_provider, llm_model_id, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                ON CONFLICT (tenant_id, entity_key)
                DO UPDATE SET
                    asset_type = EXCLUDED.asset_type,
                    entity_role = EXCLUDED.entity_role,
                    canonical_vendor = EXCLUDED.canonical_vendor,
                    canonical_product = EXCLUDED.canonical_product,
                    cmdb_ci_id = EXCLUDED.cmdb_ci_id,
                    idp_object_id = EXCLUDED.idp_object_id,
                    confidence = EXCLUDED.confidence,
                    reason = EXCLUDED.reason,
                    llm_provider = EXCLUDED.llm_provider,
                    llm_model_id = EXCLUDED.llm_model_id,
                    created_at = EXCLUDED.created_at
                """,
                fact_id, tenant_id, entity_key, asset_type, entity_role,
                canonical_vendor, canonical_product, cmdb_ci_id, idp_object_id,
                confidence, reason, llm_provider, llm_model_id, created_at.isoformat()
            )
    
    async def get_llm_facts_batch(self, tenant_id: str, entity_keys: list[str]) -> dict[str, dict]:
        """Get LLM facts for multiple entity keys in a batch"""
        if not entity_keys:
            return {}
        
        pool = await self.get_pool()
        
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM llm_facts WHERE tenant_id = $1 AND entity_key = ANY($2)",
                tenant_id, entity_keys
            )
        
        result = {}
        for row in rows:
            result[row["entity_key"]] = {
                "fact_id": row["fact_id"],
                "tenant_id": row["tenant_id"],
                "entity_key": row["entity_key"],
                "asset_type": row["asset_type"],
                "entity_role": row["entity_role"],
                "canonical_vendor": row["canonical_vendor"],
                "canonical_product": row["canonical_product"],
                "cmdb_ci_id": row["cmdb_ci_id"],
                "idp_object_id": row["idp_object_id"],
                "confidence": row["confidence"],
                "reason": row["reason"],
                "llm_provider": row["llm_provider"],
                "llm_model_id": row["llm_model_id"],
                "created_at": row["created_at"]
            }
        return result
    
    async def save_triage_action(
        self, 
        tenant_id: str,
        run_id: str,
        item_id: str,
        item_type: str,
        action: str,
        state: str,
        owner: Optional[str] = None,
        defer_until: Optional[str] = None,
        ignore_reason: Optional[str] = None
    ) -> dict:
        """Save or update a triage action"""
        import uuid
        pool = await self.get_pool()
        now = datetime.utcnow().isoformat()
        action_id = str(uuid.uuid4())
        
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT action_id FROM triage_actions WHERE run_id = $1 AND item_id = $2 AND item_type = $3",
                run_id, item_id, item_type
            )
            
            if existing:
                action_id = existing["action_id"]
                await conn.execute(
                    """
                    UPDATE triage_actions SET 
                        action = $1, state = $2, owner = $3, defer_until = $4, 
                        ignore_reason = $5, updated_at = $6
                    WHERE action_id = $7
                    """,
                    action, state, owner, defer_until, ignore_reason, now, action_id
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO triage_actions (
                        action_id, tenant_id, run_id, item_id, item_type, 
                        action, state, owner, defer_until, ignore_reason, 
                        created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    """,
                    action_id, tenant_id, run_id, item_id, item_type,
                    action, state, owner, defer_until, ignore_reason, now, now
                )
        
        return {
            "action_id": action_id,
            "item_id": item_id,
            "item_type": item_type,
            "action": action,
            "state": state,
            "owner": owner,
            "defer_until": defer_until,
            "ignore_reason": ignore_reason,
            "updated_at": now
        }
    
    async def get_triage_actions_by_run(self, run_id: str) -> list[dict]:
        """Get all triage actions for a run"""
        pool = await self.get_pool()
        
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM triage_actions WHERE run_id = $1 ORDER BY updated_at DESC",
                run_id
            )
        
        return [dict(row) for row in rows]
    
    async def delete_triage_action(self, run_id: str, item_id: str) -> bool:
        """Delete a triage action (revert/undo)"""
        pool = await self.get_pool()
        
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM triage_actions WHERE run_id = $1 AND item_id = $2",
                run_id, item_id
            )
        
        return "DELETE" in result
