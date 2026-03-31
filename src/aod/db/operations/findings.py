"""Finding operations for database."""

import json

import asyncpg

from ...models.output_contracts import Finding
from ..serializers import deserialize_finding_row


class FindingOperations:
    """Operations for finding records."""

    def __init__(self, get_pool):
        self._get_pool = get_pool

    async def create_finding(self, finding: Finding) -> Finding:
        """Create a new finding."""
        pool = await self._get_pool()

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
        """Get all findings for a run."""
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM findings WHERE run_id = $1 ORDER BY triage_priority ASC, finding_type",
                run_id
            )

        return [deserialize_finding_row(row) for row in rows]

    async def create_findings_batch(self, findings: list[Finding]) -> None:
        """Batch insert findings."""
        if not findings:
            return
        pool = await self._get_pool()
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
