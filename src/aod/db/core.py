"""Core Database class with modular operations."""

import logging
import os
from datetime import datetime
from typing import Optional, AsyncGenerator

import asyncpg

# Database connection pool configuration (environment-configurable)
DB_POOL_MIN_SIZE = int(os.getenv("DB_POOL_MIN", "2"))
DB_POOL_MAX_SIZE = int(os.getenv("DB_POOL_MAX", "20"))

from .config import get_database_url
from .schema import initialize_schema
from .operations.runs import RunOperations
from .operations.assets import AssetOperations
from .operations.artifacts import ArtifactOperations
from .operations.findings import FindingOperations
from .operations.observations import ObservationOperations
from .operations.llm_facts import LLMFactOperations
from .operations.triage import TriageOperations
from ..models.output_contracts import Asset, Artifact, Finding, RunLog

logger = logging.getLogger(__name__)


class Database:
    """
    PostgreSQL database for AOD persistence.

    This class provides the main interface for all database operations.
    Operations are organized into logical groups (runs, assets, etc.)
    and delegated to specialized operation classes.
    """

    def __init__(self, db_url: str):
        self.db_url = db_url
        self._pool: Optional[asyncpg.Pool] = None

        # Initialize operation handlers
        self._runs = RunOperations(self.get_pool)
        self._assets = AssetOperations(self.get_pool)
        self._artifacts = ArtifactOperations(self.get_pool)
        self._findings = FindingOperations(self.get_pool)
        self._observations = ObservationOperations(self.get_pool)
        self._llm_facts = LLMFactOperations(self.get_pool)
        self._triage = TriageOperations(self.get_pool)

    async def get_pool(self) -> asyncpg.Pool:
        """Get database connection pool."""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self.db_url,
                min_size=DB_POOL_MIN_SIZE,
                max_size=DB_POOL_MAX_SIZE
            )
        return self._pool

    async def close(self):
        """Close database connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def initialize(self):
        """Initialize database schema."""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            await initialize_schema(conn)

    # Run operations
    async def create_run(self, run: RunLog) -> RunLog:
        return await self._runs.create_run(run)

    async def update_run(self, run: RunLog) -> RunLog:
        return await self._runs.update_run(run)

    async def get_run(self, run_id: str) -> Optional[RunLog]:
        return await self._runs.get_run(run_id)

    async def get_all_runs(self) -> list[RunLog]:
        return await self._runs.get_all_runs()

    async def delete_all_runs(self) -> int:
        return await self._runs.delete_all_runs()

    async def prune_old_runs(self, keep: int = 6) -> int:
        return await self._runs.prune_old_runs(keep)

    async def get_latest_run_for_tenant(self, tenant_id: str, snapshot_id=None):
        return await self._runs.get_latest_run_for_tenant(tenant_id, snapshot_id)

    async def get_recent_tenants(self, limit: int = 5) -> list[str]:
        return await self._runs.get_recent_tenants(limit)

    # Asset operations
    async def create_asset(self, asset: Asset) -> Asset:
        return await self._assets.create_asset(asset)

    async def get_assets_by_run(self, run_id: str) -> list[Asset]:
        return await self._assets.get_assets_by_run(run_id)

    async def get_asset_by_id(self, asset_id: str) -> Optional[Asset]:
        return await self._assets.get_asset_by_id(asset_id)

    async def update_asset_owner(self, asset_id: str, owner: str) -> bool:
        return await self._assets.update_asset_owner(asset_id, owner)

    async def update_asset_provisioning_status(
        self,
        asset_id: str,
        new_status: str,
        reason: Optional[str] = None,
        actor: Optional[str] = None
    ) -> bool:
        return await self._assets.update_asset_provisioning_status(asset_id, new_status, reason, actor)

    async def create_assets_batch(self, assets: list[Asset]) -> None:
        return await self._assets.create_assets_batch(assets)

    # Artifact operations
    async def create_artifact(self, artifact: Artifact) -> Artifact:
        return await self._artifacts.create_artifact(artifact)

    async def get_artifacts_by_run(self, run_id: str) -> list[Artifact]:
        return await self._artifacts.get_artifacts_by_run(run_id)

    async def create_artifacts_batch(self, artifacts: list[Artifact]) -> None:
        return await self._artifacts.create_artifacts_batch(artifacts)

    # Finding operations
    async def create_finding(self, finding: Finding) -> Finding:
        return await self._findings.create_finding(finding)

    async def get_findings_by_run(self, run_id: str) -> list[Finding]:
        return await self._findings.get_findings_by_run(run_id)

    async def create_findings_batch(self, findings: list[Finding]) -> None:
        return await self._findings.create_findings_batch(findings)

    # Observation operations
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
        return await self._observations.create_observation_sample(
            sample_id, run_id, name, domain, source, category, raw_preview, created_at
        )

    async def get_observation_samples_by_run(self, run_id: str, limit: int = 100, offset: int = 0) -> tuple[list[dict], int]:
        return await self._observations.get_observation_samples_by_run(run_id, limit, offset)

    async def create_observation_samples_batch(self, samples: list[tuple]) -> None:
        return await self._observations.create_observation_samples_batch(samples)

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
        return await self._observations.create_ambiguous_match(
            match_id, run_id, entity_key, entity_name, plane,
            candidate_ids, candidate_names, match_keys, created_at
        )

    async def get_ambiguous_matches_by_run(self, run_id: str, limit: int = 100, offset: int = 0) -> tuple[list[dict], int]:
        return await self._observations.get_ambiguous_matches_by_run(run_id, limit, offset)

    async def create_ambiguous_matches_batch(self, matches: list[tuple]) -> None:
        return await self._observations.create_ambiguous_matches_batch(matches)

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
        return await self._observations.create_rejection(
            rejection_id, run_id, entity_key, entity_name,
            reason_code, reason_detail, evidence_summary, created_at
        )

    async def get_rejections_by_run(self, run_id: str, limit: int = 100, offset: int = 0) -> tuple[list[dict], int]:
        return await self._observations.get_rejections_by_run(run_id, limit, offset)

    async def create_rejections_batch(self, rejections: list[tuple]) -> None:
        return await self._observations.create_rejections_batch(rejections)

    # LLM facts operations
    async def get_llm_fact(self, tenant_id: str, entity_key: str) -> Optional[dict]:
        return await self._llm_facts.get_llm_fact(tenant_id, entity_key)

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
        return await self._llm_facts.upsert_llm_fact(
            fact_id, tenant_id, entity_key, asset_type, entity_role,
            canonical_vendor, canonical_product, cmdb_ci_id, idp_object_id,
            confidence, reason, llm_provider, llm_model_id, created_at
        )

    async def get_llm_facts_batch(self, tenant_id: str, entity_keys: list[str]) -> dict[str, dict]:
        return await self._llm_facts.get_llm_facts_batch(tenant_id, entity_keys)

    # Triage operations
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
        return await self._triage.save_triage_action(
            tenant_id, run_id, item_id, item_type, action, state,
            owner, defer_until, ignore_reason
        )

    async def get_triage_actions_by_run(self, run_id: str) -> list[dict]:
        return await self._triage.get_triage_actions_by_run(run_id)

    async def delete_triage_action(self, run_id: str, item_id: str) -> bool:
        return await self._triage.delete_triage_action(run_id, item_id)


# Singleton instance
_db_instance: Optional[Database] = None


async def get_db() -> AsyncGenerator[Database, None]:
    """
    FastAPI dependency for database access.

    Yields a Database instance for use in route handlers.
    Maintains a singleton pool but compatible with dependency injection.
    """
    global _db_instance
    if _db_instance is None:
        db_url = get_database_url()
        _db_instance = Database(db_url)
        await _db_instance.initialize()
    yield _db_instance


async def get_db_direct() -> Database:
    """
    Direct database access for non-FastAPI contexts (e.g., pipeline executor).

    Returns the Database instance directly instead of yielding.
    """
    global _db_instance
    if _db_instance is None:
        db_url = get_database_url()
        _db_instance = Database(db_url)
        await _db_instance.initialize()
    return _db_instance
