"""Artifact operations for database."""

import asyncpg

from ...models.output_contracts import Artifact
from ..serializers import deserialize_artifact_row


class ArtifactOperations:
    """Operations for artifact records."""

    def __init__(self, get_pool):
        self._get_pool = get_pool

    async def create_artifact(self, artifact: Artifact) -> Artifact:
        """Create a new artifact."""
        pool = await self._get_pool()

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
        """Get all artifacts for a run."""
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM artifacts WHERE run_id = $1 ORDER BY name",
                run_id
            )

        return [deserialize_artifact_row(row) for row in rows]

    async def create_artifacts_batch(self, artifacts: list[Artifact]) -> None:
        """Batch insert artifacts."""
        if not artifacts:
            return
        pool = await self._get_pool()
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
