"""Asset operations for database."""

import json
from typing import Optional

import asyncpg

from ...models.output_contracts import Asset
from ..serializers import deserialize_asset_row


class AssetOperations:
    """Operations for asset records."""

    def __init__(self, get_pool):
        self._get_pool = get_pool

    async def create_asset(self, asset: Asset) -> Asset:
        """Create a new asset."""
        pool = await self._get_pool()

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
        """Get all assets for a run."""
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM assets WHERE run_id = $1 ORDER BY name",
                run_id
            )

        return [deserialize_asset_row(row) for row in rows]

    async def get_asset_by_id(self, asset_id: str) -> Optional[Asset]:
        """Get a single asset by ID."""
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM assets WHERE asset_id = $1",
                asset_id
            )

        if not row:
            return None

        return deserialize_asset_row(row)

    async def update_asset_owner(self, asset_id: str, owner: str) -> bool:
        """Update an asset's owner field."""
        pool = await self._get_pool()

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
        """Update an asset's provisioning status."""
        pool = await self._get_pool()

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

    async def create_assets_batch(self, assets: list[Asset]) -> None:
        """Batch insert assets."""
        if not assets:
            return
        pool = await self._get_pool()
        rows = []
        for asset in assets:
            rows.append((
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
                asset.lens_match_debug.model_dump_json() if asset.lens_match_debug else None,
                asset.activity_evidence.model_dump_json(),
                json.dumps(asset.tags),
                asset.admission_reason,
                asset.provisioning_status.value,
                asset.has_critical_gap,
                asset.owner,
                asset.created_at.isoformat()
            ))
        async with pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO assets (
                    asset_id, tenant_id, run_id, name, asset_type, identifiers,
                    vendor, vendor_hypothesis, environment, evidence_refs, lens_status, lens_coverage,
                    lens_match_debug, activity_evidence, tags, admission_reason, provisioning_status, has_critical_gap, owner, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20)
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
                    created_at = EXCLUDED.created_at
                """,
                rows
            )
