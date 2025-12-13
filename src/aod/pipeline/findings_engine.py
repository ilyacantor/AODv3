"""Stage 7: Findings Engine - Generate deterministic, explainable findings"""

from typing import Optional
from uuid import uuid4

from ..models.output_contracts import (
    Asset, Finding, FindingType, Severity, LensStatus
)
from .correlate_entities import CorrelationResult, MatchStatus
from .build_plane_indexes import PlaneIndexes


def generate_identity_gap_finding(
    asset: Asset,
    correlation: CorrelationResult,
    tenant_id: str,
    run_id: str
) -> Optional[Finding]:
    """
    Generate identity_gap finding:
    Admitted via CMDB/cloud/finance but no IdP match
    """
    if asset.lens_status.idp != LensStatus.UNMATCHED:
        return None
    
    if not (asset.lens_coverage.cmdb or asset.lens_coverage.cloud or asset.lens_coverage.finance):
        return None
    
    admitted_via = []
    if asset.lens_coverage.cmdb:
        admitted_via.append("CMDB")
    if asset.lens_coverage.cloud:
        admitted_via.append("Cloud")
    if asset.lens_coverage.finance:
        admitted_via.append("Finance")
    
    return Finding(
        finding_id=uuid4(),
        asset_id=asset.asset_id,
        tenant_id=tenant_id,
        run_id=run_id,
        finding_type=FindingType.IDENTITY_GAP,
        severity=Severity.HIGH,
        explanation=f"Asset '{asset.name}' admitted via {', '.join(admitted_via)} but has no identity provider integration (no SSO/SCIM)",
        evidence_refs=asset.evidence_refs
    )


def generate_cmdb_gap_finding(
    asset: Asset,
    correlation: CorrelationResult,
    tenant_id: str,
    run_id: str
) -> Optional[Finding]:
    """
    Generate cmdb_gap finding:
    Admitted via IdP/finance but no CMDB match
    """
    if asset.lens_status.cmdb != LensStatus.UNMATCHED:
        return None
    
    if not (asset.lens_coverage.idp or asset.lens_coverage.finance):
        return None
    
    admitted_via = []
    if asset.lens_coverage.idp:
        admitted_via.append("IdP")
    if asset.lens_coverage.finance:
        admitted_via.append("Finance")
    
    return Finding(
        finding_id=uuid4(),
        asset_id=asset.asset_id,
        tenant_id=tenant_id,
        run_id=run_id,
        finding_type=FindingType.CMDB_GAP,
        severity=Severity.MED,
        explanation=f"Asset '{asset.name}' admitted via {', '.join(admitted_via)} but not registered in CMDB",
        evidence_refs=asset.evidence_refs
    )


def generate_governance_gap_finding(
    asset: Asset,
    correlation: CorrelationResult,
    tenant_id: str,
    run_id: str
) -> Optional[Finding]:
    """
    Generate governance_gap finding:
    No owner/system record found
    """
    has_owner = False
    
    if correlation.cmdb.status == MatchStatus.MATCHED:
        for record in correlation.cmdb.matched_records:
            if hasattr(record, 'owner') and record.owner:
                has_owner = True
                break
    
    if not has_owner and correlation.idp.status == MatchStatus.MATCHED:
        for record in correlation.idp.matched_records:
            if hasattr(record, 'owner') and record.owner:
                has_owner = True
                break
    
    if has_owner:
        return None
    
    return Finding(
        finding_id=uuid4(),
        asset_id=asset.asset_id,
        tenant_id=tenant_id,
        run_id=run_id,
        finding_type=FindingType.GOVERNANCE_GAP,
        severity=Severity.LOW,
        explanation=f"Asset '{asset.name}' has no designated owner in CMDB or IdP records",
        evidence_refs=asset.evidence_refs
    )


def generate_duplication_risk_finding(
    asset: Asset,
    correlation: CorrelationResult,
    tenant_id: str,
    run_id: str
) -> Optional[Finding]:
    """
    Generate duplication_risk finding:
    Multiple entities ambiguous-match same plane record
    """
    ambiguous_planes = []
    
    if correlation.idp.status == MatchStatus.AMBIGUOUS:
        ambiguous_planes.append(f"IdP ({len(correlation.idp.matched_ids)} matches)")
    if correlation.cmdb.status == MatchStatus.AMBIGUOUS:
        ambiguous_planes.append(f"CMDB ({len(correlation.cmdb.matched_ids)} matches)")
    if correlation.cloud.status == MatchStatus.AMBIGUOUS:
        ambiguous_planes.append(f"Cloud ({len(correlation.cloud.matched_ids)} matches)")
    if correlation.finance.status == MatchStatus.AMBIGUOUS:
        ambiguous_planes.append(f"Finance ({len(correlation.finance.matched_ids)} matches)")
    
    if not ambiguous_planes:
        return None
    
    return Finding(
        finding_id=uuid4(),
        asset_id=asset.asset_id,
        tenant_id=tenant_id,
        run_id=run_id,
        finding_type=FindingType.DUPLICATION_RISK,
        severity=Severity.MED,
        explanation=f"Asset '{asset.name}' has ambiguous matches in: {', '.join(ambiguous_planes)}. Manual review recommended.",
        evidence_refs=asset.evidence_refs
    )


def generate_data_conflict_finding(
    asset: Asset,
    correlation: CorrelationResult,
    tenant_id: str,
    run_id: str
) -> Optional[Finding]:
    """
    Generate data_conflict finding:
    Plane evidence contradicts (e.g., env/lifecycle mismatch)
    """
    environments_found = []
    
    if correlation.cmdb.status == MatchStatus.MATCHED:
        for record in correlation.cmdb.matched_records:
            if hasattr(record, 'environment') and record.environment:
                environments_found.append(f"CMDB:{record.environment}")
    
    if correlation.cloud.status == MatchStatus.MATCHED:
        for record in correlation.cloud.matched_records:
            if hasattr(record, 'environment') and record.environment:
                environments_found.append(f"Cloud:{record.environment}")
    
    unique_envs = set(env.split(':')[1].lower() for env in environments_found if ':' in env)
    unique_envs = {e for e in unique_envs if e != 'unknown'}
    
    if len(unique_envs) <= 1:
        return None
    
    return Finding(
        finding_id=uuid4(),
        asset_id=asset.asset_id,
        tenant_id=tenant_id,
        run_id=run_id,
        finding_type=FindingType.DATA_CONFLICT,
        severity=Severity.MED,
        explanation=f"Asset '{asset.name}' has conflicting environment data: {', '.join(environments_found)}",
        evidence_refs=asset.evidence_refs
    )


def generate_finance_gap_findings(
    indexes: PlaneIndexes,
    admitted_assets: list[Asset],
    correlations: list[CorrelationResult],
    tenant_id: str,
    run_id: str
) -> list[Finding]:
    """
    Generate finance_gap findings:
    Finance evidence exists but no corresponding asset admitted
    """
    findings = []
    
    matched_finance_ids = set()
    for correlation in correlations:
        if correlation.finance.status == MatchStatus.MATCHED:
            matched_finance_ids.update(correlation.finance.matched_ids)
    
    for record_id, record in indexes.finance.records.items():
        if record_id in matched_finance_ids:
            continue
        
        if record_id.startswith("contract:") or (record_id.startswith("transaction:") and hasattr(record, 'is_recurring') and record.is_recurring):
            product_name = getattr(record, 'product', None) or getattr(record, 'vendor_name', None) or record_id
            
            findings.append(Finding(
                finding_id=uuid4(),
                asset_id=None,
                tenant_id=tenant_id,
                run_id=run_id,
                finding_type=FindingType.FINANCE_GAP,
                severity=Severity.HIGH,
                explanation=f"Finance record '{product_name}' ({record_id}) has no corresponding asset in catalog. Possible undiscovered system.",
                evidence_refs=[record_id]
            ))
    
    return findings


def generate_findings(
    assets: list[Asset],
    correlations: list[CorrelationResult],
    indexes: PlaneIndexes,
    tenant_id: str,
    run_id: str
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
        
    Returns:
        List of findings, deterministically sorted
    """
    findings = []
    
    correlation_by_name = {c.entity.original_name: c for c in correlations}
    
    for asset in assets:
        correlation = correlation_by_name.get(asset.name)
        if not correlation:
            continue
        
        identity_gap = generate_identity_gap_finding(asset, correlation, tenant_id, run_id)
        if identity_gap:
            findings.append(identity_gap)
        
        cmdb_gap = generate_cmdb_gap_finding(asset, correlation, tenant_id, run_id)
        if cmdb_gap:
            findings.append(cmdb_gap)
        
        governance_gap = generate_governance_gap_finding(asset, correlation, tenant_id, run_id)
        if governance_gap:
            findings.append(governance_gap)
        
        duplication_risk = generate_duplication_risk_finding(asset, correlation, tenant_id, run_id)
        if duplication_risk:
            findings.append(duplication_risk)
        
        data_conflict = generate_data_conflict_finding(asset, correlation, tenant_id, run_id)
        if data_conflict:
            findings.append(data_conflict)
    
    finance_gaps = generate_finance_gap_findings(
        indexes, assets, correlations, tenant_id, run_id
    )
    findings.extend(finance_gaps)
    
    findings.sort(key=lambda f: (
        {"high": 0, "med": 1, "low": 2}.get(f.severity.value, 3),
        f.finding_type.value,
        str(f.asset_id) if f.asset_id else "",
        f.explanation
    ))
    
    return findings
