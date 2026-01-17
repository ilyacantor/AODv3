"""Finding database operations.

Extracted from Database class - lines 686-744 and 1008-1044 of original database_old.py.
"""

import json
from datetime import datetime
from uuid import UUID

from aod.models.output_contracts import (
    Finding,
    FindingType,
    FindingCategory,
    Severity,
    Confidence,
    Materiality,
    TriagePriority,
)


async def create_finding(pool, finding: Finding) -> Finding:
    """Create a new finding"""
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
            finding.run_id,
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


async def get_findings_by_run(pool, run_id: str) -> list[Finding]:
    """Get all findings for a run"""
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
            run_id=row["run_id"],
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


async def create_findings_batch(pool, findings: list[Finding]) -> None:
    """Batch insert findings"""
    if not findings:
        return
    rows = []
    for f in findings:
        rows.append((
            str(f.finding_id),
            str(f.asset_id) if f.asset_id else None,
            f.tenant_id,
            f.run_id,
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
