"""Artifact database operations.

Extracted from Database class - lines 637-684 and 1046-1080 of original database_old.py.
"""

from datetime import datetime
from uuid import UUID

from aod.models.output_contracts import Artifact, ArtifactType


async def create_artifact(pool, artifact: Artifact) -> Artifact:
    """Create a new artifact"""
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


async def get_artifacts_by_run(pool, run_id: str) -> list[Artifact]:
    """Get all artifacts for a run"""
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


async def create_artifacts_batch(pool, artifacts: list[Artifact]) -> None:
    """Batch insert artifacts"""
    if not artifacts:
        return
    rows = []
    for artifact in artifacts:
        rows.append((
            str(artifact.artifact_id),
            artifact.tenant_id,
            artifact.run_id,
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
