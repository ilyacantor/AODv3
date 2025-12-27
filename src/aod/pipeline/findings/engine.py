"""Main findings generation orchestrator"""

import logging

from ...models.output_contracts import Asset, Finding, ProvisioningStatus, FindingType
from ..correlate_entities import CorrelationResult
from ..build_plane_indexes import PlaneIndexes
from .base import is_security_risk
from .identity_gap import generate_identity_gap_finding
from .cmdb_gap import generate_cmdb_gap_finding
from .governance_gap import generate_governance_gap_finding
from .duplication_risk import generate_duplication_risk_finding
from .data_conflict import generate_data_conflict_findings
from .finance_gap import generate_finance_gap_findings

logger = logging.getLogger(__name__)


def generate_findings(
    assets: list[Asset],
    correlations: list[CorrelationResult],
    indexes: PlaneIndexes,
    tenant_id: str,
    run_id: str,
    snapshot_id: str
) -> list[Finding]:
    """
    Generate findings deterministically from catalog + lens statuses.

    Rules:
    - identity_gap: admitted via CMDB/cloud/finance but no IdP match
    - cmdb_gap: admitted via IdP/finance but no CMDB match
    - governance_gap: no owner/system record
    - finance_gap: finance evidence exists but no corresponding asset admitted
    - duplication_risk: multiple entities ambiguous-match same plane record
    - data_conflict: plane evidence contradicts (e.g., env/lifecycle mismatch)

    All findings include explanation + evidence refs.

    Args:
        assets: Admitted assets
        correlations: All correlation results
        indexes: Plane indexes
        tenant_id: Tenant ID
        run_id: Run ID
        snapshot_id: Snapshot ID

    Returns:
        List of findings, deterministically sorted
    """
    logger.info("findings_engine.generate.start", extra={
        "tenant_id": tenant_id, "run_id": run_id, "asset_count": len(assets),
        "correlation_count": len(correlations)
    })

    findings = []

    correlation_by_name = {c.entity.original_name: c for c in correlations}

    identity_gap_count = 0
    cmdb_gap_count = 0
    governance_gap_count = 0
    duplication_risk_count = 0
    data_conflict_count = 0

    for asset in assets:
        correlation = correlation_by_name.get(asset.name)
        if not correlation:
            continue

        identity_gap = generate_identity_gap_finding(asset, correlation, tenant_id, run_id, snapshot_id)
        if identity_gap:
            findings.append(identity_gap)
            identity_gap_count += 1

        cmdb_gap = generate_cmdb_gap_finding(asset, correlation, tenant_id, run_id, snapshot_id)
        if cmdb_gap:
            findings.append(cmdb_gap)
            cmdb_gap_count += 1

        governance_gap = generate_governance_gap_finding(asset, correlation, tenant_id, run_id, snapshot_id)
        if governance_gap:
            findings.append(governance_gap)
            governance_gap_count += 1

        duplication_risk = generate_duplication_risk_finding(asset, correlation, tenant_id, run_id, snapshot_id)
        if duplication_risk:
            findings.append(duplication_risk)
            duplication_risk_count += 1

        data_conflicts = generate_data_conflict_findings(asset, correlation, tenant_id, run_id, snapshot_id)
        findings.extend(data_conflicts)
        data_conflict_count += len(data_conflicts)

    finance_gaps = generate_finance_gap_findings(
        indexes, assets, correlations, tenant_id, run_id, snapshot_id
    )
    findings.extend(finance_gaps)

    findings.sort(key=lambda f: (
        0 if is_security_risk(f.category) else 1,
        {"p0": 0, "p1": 1, "p2": 2}.get(f.triage_priority.value, 3),
        f.finding_type.value,
        str(f.asset_id) if f.asset_id else "",
        f.explanation
    ))

    # Post-process: Set has_critical_gap=True for ACTIVE assets with identity_gap finding
    # This is the "toxic trigger" - an ACTIVE asset without IdP governance is a critical risk
    identity_gap_asset_ids = {
        f.asset_id for f in findings 
        if f.finding_type == FindingType.IDENTITY_GAP and f.asset_id
    }
    
    critical_gap_count = 0
    for asset in assets:
        if (asset.provisioning_status == ProvisioningStatus.ACTIVE 
            and asset.asset_id in identity_gap_asset_ids):
            asset.has_critical_gap = True
            critical_gap_count += 1

    logger.info("findings_engine.generate.complete", extra={
        "tenant_id": tenant_id, "run_id": run_id, "total_findings": len(findings),
        "identity_gap": identity_gap_count, "cmdb_gap": cmdb_gap_count,
        "governance_gap": governance_gap_count, "duplication_risk": duplication_risk_count,
        "data_conflict": data_conflict_count, "finance_gap": len(finance_gaps),
        "critical_gap_assets": critical_gap_count
    })

    return findings
