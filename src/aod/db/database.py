"""PostgreSQL persistence layer for AOD using asyncpg"""

import asyncpg
import json
import os
from datetime import datetime
from typing import Optional
from uuid import UUID

from ..models.output_contracts import (
    Asset, Artifact, Finding, RunLog, RunStatus, RunCounts, SyncStatus,
    AssetType, Environment, LensStatus, LensStatuses, LensCoverage,
    AssetIdentifiers, ActivityEvidence, ArtifactType, VendorHypothesis
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


_db_instance: Optional["Database"] = None


async def get_db() -> "Database":
    """Get or create database instance"""
    global _db_instance
    if _db_instance is None:
        db_url = get_database_url()
        _db_instance = Database(db_url)
        await _db_instance.initialize()
    return _db_instance


class Database:
    """PostgreSQL database for AOD persistence"""
    
    def __init__(self, db_url: str):
        self.db_url = db_url
        self._pool: Optional[asyncpg.Pool] = None
    
    async def get_pool(self) -> asyncpg.Pool:
        """Get database connection pool"""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(self.db_url, min_size=1, max_size=10)
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
                    sync_error TEXT
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
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                )
            """)
            
            try:
                await conn.execute("ALTER TABLE assets ADD COLUMN IF NOT EXISTS vendor_hypothesis TEXT")
            except Exception:
                pass
            
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
                INSERT INTO runs (run_id, tenant_id, status, started_at, completed_at, input_meta, counts, failure_reasons, sync_status, sync_error)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                run.run_id,
                run.tenant_id,
                run.status.value,
                run.started_at.isoformat(),
                run.completed_at.isoformat() if run.completed_at else None,
                json.dumps(run.input_meta),
                run.counts.model_dump_json(),
                json.dumps(run.failure_reasons),
                run.sync_status.value,
                run.sync_error
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
                    sync_error = $6
                WHERE run_id = $7
                """,
                run.status.value,
                run.completed_at.isoformat() if run.completed_at else None,
                run.counts.model_dump_json(),
                json.dumps(run.failure_reasons),
                run.sync_status.value,
                run.sync_error,
                run.run_id
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
        
        return RunLog(
            run_id=row["run_id"],
            tenant_id=row["tenant_id"],
            status=RunStatus(row["status"]),
            started_at=datetime.fromisoformat(row["started_at"]),
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            input_meta=json.loads(row["input_meta"]),
            counts=RunCounts.model_validate_json(row["counts"]),
            failure_reasons=json.loads(row["failure_reasons"]),
            sync_status=SyncStatus(sync_status_val),
            sync_error=sync_error_val
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
            runs.append(RunLog(
                run_id=row["run_id"],
                tenant_id=row["tenant_id"],
                status=RunStatus(row["status"]),
                started_at=datetime.fromisoformat(row["started_at"]),
                completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
                input_meta=json.loads(row["input_meta"]),
                counts=RunCounts.model_validate_json(row["counts"]),
                failure_reasons=json.loads(row["failure_reasons"]),
                sync_status=SyncStatus(sync_status_val),
                sync_error=sync_error_val
            ))
        return runs
    
    async def create_asset(self, asset: Asset) -> Asset:
        """Create a new asset"""
        pool = await self.get_pool()
        
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO assets (
                    asset_id, tenant_id, run_id, name, asset_type, identifiers,
                    vendor, vendor_hypothesis, environment, evidence_refs, lens_status, lens_coverage,
                    activity_evidence, tags, admission_reason, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
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
                    activity_evidence = EXCLUDED.activity_evidence,
                    tags = EXCLUDED.tags,
                    admission_reason = EXCLUDED.admission_reason,
                    created_at = EXCLUDED.created_at
                """,
                str(asset.asset_id),
                asset.tenant_id,
                asset.run_id,
                asset.name,
                asset.asset_type.value,
                asset.identifiers.model_dump_json(),
                asset.vendor,
                asset.vendor_hypothesis.model_dump_json() if asset.vendor_hypothesis else None,
                asset.environment.value,
                json.dumps(asset.evidence_refs),
                asset.lens_status.model_dump_json(),
                asset.lens_coverage.model_dump_json(),
                asset.activity_evidence.model_dump_json(),
                json.dumps(asset.tags),
                asset.admission_reason,
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
        
        assets = []
        for row in rows:
            activity_evidence_data = row.get("activity_evidence", "{}")
            vendor_hypothesis_data = row.get("vendor_hypothesis")
            vendor_hypothesis = None
            if vendor_hypothesis_data:
                vendor_hypothesis = VendorHypothesis.model_validate_json(vendor_hypothesis_data)
            
            assets.append(Asset(
                asset_id=UUID(row["asset_id"]),
                tenant_id=row["tenant_id"],
                run_id=row["run_id"],
                name=row["name"],
                asset_type=AssetType(row["asset_type"]),
                identifiers=AssetIdentifiers.model_validate_json(row["identifiers"]),
                vendor=row["vendor"],
                vendor_hypothesis=vendor_hypothesis,
                environment=Environment(row["environment"]),
                evidence_refs=json.loads(row["evidence_refs"]),
                lens_status=LensStatuses.model_validate_json(row["lens_status"]),
                lens_coverage=LensCoverage.model_validate_json(row["lens_coverage"]),
                activity_evidence=ActivityEvidence.model_validate_json(activity_evidence_data) if activity_evidence_data else ActivityEvidence(),
                tags=json.loads(row["tags"]),
                admission_reason=row["admission_reason"],
                created_at=datetime.fromisoformat(row["created_at"])
            ))
        return assets
    
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
                artifact.run_id,
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
                run_id=row["run_id"],
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
                    finding_id, asset_id, tenant_id, run_id,
                    explanation, evidence_refs, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                str(finding.finding_id),
                str(finding.asset_id) if finding.asset_id else None,
                finding.tenant_id,
                finding.run_id,
                finding.explanation,
                json.dumps(finding.evidence_refs),
                finding.created_at.isoformat()
            )
        return finding
    
    async def get_findings_by_run(self, run_id: str) -> list[Finding]:
        """Get all findings for a run"""
        pool = await self.get_pool()
        
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM findings WHERE run_id = $1 ORDER BY created_at",
                run_id
            )
        
        return [
            Finding(
                finding_id=UUID(row["finding_id"]),
                asset_id=UUID(row["asset_id"]) if row["asset_id"] else None,
                tenant_id=row["tenant_id"],
                run_id=row["run_id"],
                explanation=row["explanation"],
                evidence_refs=json.loads(row["evidence_refs"]),
                created_at=datetime.fromisoformat(row["created_at"])
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
                sample_id,
                run_id,
                name,
                domain,
                source,
                category,
                raw_preview,
                created_at.isoformat()
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
                match_id,
                run_id,
                entity_key,
                entity_name,
                plane,
                json.dumps(candidate_ids),
                json.dumps(candidate_names),
                json.dumps(match_keys),
                created_at.isoformat()
            )
    
    async def get_ambiguous_matches_by_run(self, run_id: str) -> list[dict]:
        """Get all ambiguous matches for a run"""
        pool = await self.get_pool()
        
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM ambiguous_matches WHERE run_id = $1 ORDER BY entity_name",
                run_id
            )
        
        return [
            {
                "id": row["id"],
                "run_id": row["run_id"],
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
                rejection_id,
                run_id,
                entity_key,
                entity_name,
                reason_code,
                reason_detail,
                json.dumps(evidence_summary),
                created_at.isoformat()
            )
    
    async def get_rejections_by_run(self, run_id: str) -> list[dict]:
        """Get all rejections for a run"""
        pool = await self.get_pool()
        
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM rejections WHERE run_id = $1 ORDER BY entity_name",
                run_id
            )
        
        return [
            {
                "id": row["id"],
                "run_id": row["run_id"],
                "entity_key": row["entity_key"],
                "entity_name": row["entity_name"],
                "reason_code": row["reason_code"],
                "reason_detail": row["reason_detail"],
                "evidence_summary": json.loads(row["evidence_summary"]),
                "created_at": row["created_at"]
            }
            for row in rows
        ]
    
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
        """Upsert an LLM fact (insert or update on conflict)"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO llm_facts (
                    fact_id, tenant_id, entity_key, asset_type, entity_role,
                    canonical_vendor, canonical_product, cmdb_ci_id, idp_object_id,
                    confidence, reason, llm_provider, llm_model_id, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                ON CONFLICT (tenant_id, entity_key) DO UPDATE SET
                    fact_id = EXCLUDED.fact_id,
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
                fact_id,
                tenant_id,
                entity_key,
                asset_type,
                entity_role,
                canonical_vendor,
                canonical_product,
                cmdb_ci_id,
                idp_object_id,
                confidence,
                reason,
                llm_provider,
                llm_model_id,
                created_at.isoformat()
            )
    
    async def get_llm_fact(self, tenant_id: str, entity_key: str) -> Optional[dict]:
        """Get an LLM fact by tenant and entity key"""
        pool = await self.get_pool()
        
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM llm_facts WHERE tenant_id = $1 AND entity_key = $2",
                tenant_id,
                entity_key
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
    
    async def get_all_llm_facts(self, tenant_id: str) -> list[dict]:
        """Get all LLM facts for a tenant"""
        pool = await self.get_pool()
        
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM llm_facts WHERE tenant_id = $1 ORDER BY entity_key",
                tenant_id
            )
        
        return [
            {
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
            for row in rows
        ]
