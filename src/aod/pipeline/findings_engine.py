"""Stage 7: Findings Engine - Generate deterministic, explainable findings

Risk Case Model (Dec 2025):
- Raw triggers are grouped into Risk Cases for KPI display
- Each finding carries confidence, materiality, and triage_priority
- Triage priority: P0 (immediate), P1 (high priority), P2 (backlog)
- Default KPI shows "Actionable" = P0 + P1 cases only

Tighter Trigger Gates:
- IDENTITY_GAP: Require strong activity (cloud/finance/audit) + no IdP
- FINANCE_GAP: Require recurring spend >= $200/mo + no governance visibility
- DATA_CONFLICT: Only security-relevant fields, dedupe by (asset, field)
"""

from typing import Optional

from ..models.output_contracts import (
    Asset, Finding, FindingType, FindingCategory, Severity, LensStatus,
    Confidence, Materiality, TriagePriority
)
from ..models.input_contracts import Contract, Transaction

SECURITY_RISKS = {
    FindingType.IDENTITY_GAP,
    FindingType.FINANCE_GAP,
    FindingType.DATA_CONFLICT,
}

GOVERNANCE_FINDINGS = {
    FindingType.CMDB_GAP,
    FindingType.GOVERNANCE_GAP,
    FindingType.DUPLICATION_RISK,
}

# Security-relevant fields that can trigger DATA_CONFLICT
SECURITY_RELEVANT_FIELDS = {
    "owner",
    "business_owner",
    "environment",
    "data_classification",
    "auth_state",
    "governance_state",
    "lifecycle",
}

# Minimum monthly spend threshold for FINANCE_GAP (in USD)
FINANCE_GAP_MONTHLY_THRESHOLD = 200.0


from .correlate_entities import CorrelationResult, MatchStatus
from .build_plane_indexes import PlaneIndexes
from .deterministic_ids import deterministic_uuid


def get_category(finding_type: FindingType) -> FindingCategory:
    """Map finding type to category"""
    if finding_type in SECURITY_RISKS:
        return FindingCategory.SECURITY_RISK
    return FindingCategory.GOVERNANCE_FINDING


def compute_triage_priority(confidence: Confidence, materiality: Materiality) -> TriagePriority:
    """
    Compute triage priority from confidence and materiality.
    
    P0: HIGH confidence + HIGH materiality
    P1: HIGH confidence + MED materiality OR MED confidence + HIGH materiality
    P2: Everything else
    """
    if confidence == Confidence.HIGH and materiality == Materiality.HIGH:
        return TriagePriority.P0
    if confidence == Confidence.HIGH and materiality == Materiality.MED:
        return TriagePriority.P1
    if confidence == Confidence.MED and materiality == Materiality.HIGH:
        return TriagePriority.P1
    return TriagePriority.P2


def generate_identity_gap_finding(
    asset: Asset,
    correlation: CorrelationResult,
    tenant_id: str,
    run_id: str,
    snapshot_id: str
) -> Optional[Finding]:
    """
    Generate identity_gap finding with TIGHTER GATE (Dec 2025):
    
    Trigger ONLY if:
    - No IdP governance (idp_present == false)
    - Has STRONG activity evidence (any of):
      - Cloud evidence (passed cloud admission = valid resource type)
      - Finance recurring spend (passed finance admission)
      - CMDB + other plane (multi-plane corroboration)
    
    Uses lens_coverage which is set from direct admission checks (not propagated).
    """
    if asset.lens_status.idp != LensStatus.UNMATCHED:
        return None
    
    # lens_coverage is set from check_*_admission results - direct evidence only
    has_cloud = asset.lens_coverage.cloud if asset.lens_coverage else False
    has_finance = asset.lens_coverage.finance if asset.lens_coverage else False
    has_cmdb = asset.lens_coverage.cmdb if asset.lens_coverage else False
    has_discovery = asset.lens_coverage.discovery if asset.lens_coverage else False
    
    # Count independent planes for multi-plane corroboration
    strong_planes = sum([has_cloud, has_finance, has_cmdb])
    has_multi_plane = (has_discovery and strong_planes >= 1) or strong_planes >= 2
    
    # Require strong activity: cloud OR finance OR multi-plane corroboration
    if not (has_cloud or has_finance or has_multi_plane):
        return None
    
    # Build evidence summary
    admitted_via = []
    if has_cmdb:
        admitted_via.append("CMDB")
    if has_cloud:
        admitted_via.append("Cloud")
    if has_finance:
        admitted_via.append("Finance")
    if has_discovery:
        admitted_via.append("Discovery")
    
    # Determine confidence based on evidence strength
    if has_cloud and has_finance:
        confidence = Confidence.HIGH
    elif has_cloud or has_finance:
        confidence = Confidence.HIGH
    elif has_multi_plane:
        confidence = Confidence.MED
    else:
        confidence = Confidence.LOW
    
    # Determine materiality based on governance coverage
    if has_cmdb:
        materiality = Materiality.HIGH  # In CMDB but no SSO = significant gap
    elif has_finance:
        materiality = Materiality.HIGH  # Paying for it but no SSO = significant
    elif has_cloud:
        materiality = Materiality.MED
    else:
        materiality = Materiality.LOW
    
    triage = compute_triage_priority(confidence, materiality)
    
    return Finding(
        finding_id=deterministic_uuid(snapshot_id, run_id, asset.name, "identity_gap"),
        asset_id=asset.asset_id,
        tenant_id=tenant_id,
        run_id=run_id,
        finding_type=FindingType.IDENTITY_GAP,
        category=get_category(FindingType.IDENTITY_GAP),
        severity=Severity.HIGH,
        explanation=f"Asset '{asset.name}' has strong activity evidence ({', '.join(admitted_via)}) but no identity provider governance (no SSO/SCIM)",
        evidence_refs=asset.evidence_refs,
        confidence=confidence,
        materiality=materiality,
        triage_priority=triage
    )


def generate_cmdb_gap_finding(
    asset: Asset,
    correlation: CorrelationResult,
    tenant_id: str,
    run_id: str,
    snapshot_id: str
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
        finding_id=deterministic_uuid(snapshot_id, run_id, asset.name, "cmdb_gap"),
        asset_id=asset.asset_id,
        tenant_id=tenant_id,
        run_id=run_id,
        finding_type=FindingType.CMDB_GAP,
        category=get_category(FindingType.CMDB_GAP),
        severity=Severity.MED,
        explanation=f"Asset '{asset.name}' admitted via {', '.join(admitted_via)} but not registered in CMDB",
        evidence_refs=asset.evidence_refs
    )


def generate_governance_gap_finding(
    asset: Asset,
    correlation: CorrelationResult,
    tenant_id: str,
    run_id: str,
    snapshot_id: str
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
        finding_id=deterministic_uuid(snapshot_id, run_id, asset.name, "governance_gap"),
        asset_id=asset.asset_id,
        tenant_id=tenant_id,
        run_id=run_id,
        finding_type=FindingType.GOVERNANCE_GAP,
        category=get_category(FindingType.GOVERNANCE_GAP),
        severity=Severity.LOW,
        explanation=f"Asset '{asset.name}' has no designated owner in CMDB or IdP records",
        evidence_refs=asset.evidence_refs
    )


def generate_duplication_risk_finding(
    asset: Asset,
    correlation: CorrelationResult,
    tenant_id: str,
    run_id: str,
    snapshot_id: str
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
        finding_id=deterministic_uuid(snapshot_id, run_id, asset.name, "duplication_risk"),
        asset_id=asset.asset_id,
        tenant_id=tenant_id,
        run_id=run_id,
        finding_type=FindingType.DUPLICATION_RISK,
        category=get_category(FindingType.DUPLICATION_RISK),
        severity=Severity.MED,
        explanation=f"Asset '{asset.name}' has ambiguous matches in: {', '.join(ambiguous_planes)}. Manual review recommended.",
        evidence_refs=asset.evidence_refs
    )


def generate_data_conflict_findings(
    asset: Asset,
    correlation: CorrelationResult,
    tenant_id: str,
    run_id: str,
    snapshot_id: str
) -> list[Finding]:
    """
    Generate data_conflict findings with TIGHTER GATE (Dec 2025):
    
    Trigger ONLY if:
    - Conflict is on a security-relevant field (owner, environment, lifecycle, etc.)
    - Conflict persists across trusted planes (CMDB vs IdP vs Cloud)
    - Dedupe by (asset, field_name) to avoid duplicate findings
    
    Returns one finding per conflicting field.
    """
    findings = []
    
    # Collect field values from each trusted plane (not discovery which is inference)
    field_values: dict[str, dict[str, set]] = {}  # field -> plane -> values
    
    for field_name in SECURITY_RELEVANT_FIELDS:
        field_values[field_name] = {}
        
        if correlation.cmdb.status == MatchStatus.MATCHED:
            for record in correlation.cmdb.matched_records:
                if hasattr(record, field_name):
                    val = getattr(record, field_name)
                    if val and str(val).lower() not in ("unknown", "none", ""):
                        if "cmdb" not in field_values[field_name]:
                            field_values[field_name]["cmdb"] = set()
                        field_values[field_name]["cmdb"].add(str(val).lower())
        
        if correlation.idp.status == MatchStatus.MATCHED:
            for record in correlation.idp.matched_records:
                if hasattr(record, field_name):
                    val = getattr(record, field_name)
                    if val and str(val).lower() not in ("unknown", "none", ""):
                        if "idp" not in field_values[field_name]:
                            field_values[field_name]["idp"] = set()
                        field_values[field_name]["idp"].add(str(val).lower())
        
        if correlation.cloud.status == MatchStatus.MATCHED:
            for record in correlation.cloud.matched_records:
                if hasattr(record, field_name):
                    val = getattr(record, field_name)
                    if val and str(val).lower() not in ("unknown", "none", ""):
                        if "cloud" not in field_values[field_name]:
                            field_values[field_name]["cloud"] = set()
                        field_values[field_name]["cloud"].add(str(val).lower())
    
    # Check each field for conflicts across trusted planes
    for field_name, plane_values in field_values.items():
        if len(plane_values) < 2:
            continue  # Need at least 2 planes to have conflict
        
        # Collect all unique values across planes
        all_values = set()
        sources_with_values = []
        for plane, values in plane_values.items():
            all_values.update(values)
            for v in values:
                sources_with_values.append(f"{plane.upper()}:{v}")
        
        if len(all_values) <= 1:
            continue  # No actual conflict
        
        # Determine priority based on field
        if field_name in ("owner", "business_owner"):
            confidence = Confidence.HIGH
            materiality = Materiality.HIGH
        elif field_name == "environment":
            confidence = Confidence.HIGH
            materiality = Materiality.MED
        else:
            confidence = Confidence.MED
            materiality = Materiality.MED
        
        triage = compute_triage_priority(confidence, materiality)
        
        findings.append(Finding(
            finding_id=deterministic_uuid(snapshot_id, run_id, asset.name, f"data_conflict_{field_name}"),
            asset_id=asset.asset_id,
            tenant_id=tenant_id,
            run_id=run_id,
            finding_type=FindingType.DATA_CONFLICT,
            category=get_category(FindingType.DATA_CONFLICT),
            severity=Severity.MED,
            explanation=f"Asset '{asset.name}' has conflicting '{field_name}' values: {', '.join(sources_with_values)}",
            evidence_refs=asset.evidence_refs,
            confidence=confidence,
            materiality=materiality,
            triage_priority=triage,
            conflict_field=field_name
        ))
    
    return findings


def generate_finance_gap_findings(
    indexes: PlaneIndexes,
    admitted_assets: list[Asset],
    correlations: list[CorrelationResult],
    tenant_id: str,
    run_id: str,
    snapshot_id: str
) -> list[Finding]:
    """
    Generate finance_gap findings with TIGHTER GATE (Dec 2025):
    
    Trigger ONLY if:
    - Recurring spend OR contract exists
    - Spend >= $200/month OR $2,000/year threshold
    - No governance visibility (no CMDB owner, no IdP app, etc.)
    
    DEDUPLICATION: Aggregates by vendor/product name to prevent multiple findings
    for the same vendor with many transactions.
    """
    matched_finance_ids = set()
    for correlation in correlations:
        if correlation.finance.status == MatchStatus.MATCHED:
            matched_finance_ids.update(correlation.finance.matched_ids)
    
    # Aggregate unmatched finance by vendor/product name
    vendor_aggregates: dict[str, dict] = {}
    
    for record_id, record in indexes.finance.records.items():
        if record_id in matched_finance_ids:
            continue
        
        # Check if this is recurring spend
        is_recurring = False
        monthly_amount = 0.0
        
        if record_id.startswith("contract:"):
            is_recurring = True
            if isinstance(record, Contract):
                amount = record.amount or 0.0
                monthly_amount = amount / 12.0
        elif record_id.startswith("transaction:"):
            if hasattr(record, 'is_recurring') and record.is_recurring:
                is_recurring = True
                if isinstance(record, Transaction):
                    monthly_amount = record.amount or 0.0
        
        if not is_recurring:
            continue
        
        if monthly_amount < FINANCE_GAP_MONTHLY_THRESHOLD:
            continue
        
        # Get vendor/product name for aggregation
        vendor_name = getattr(record, 'vendor_name', None) or getattr(record, 'vendor', None)
        product_name = getattr(record, 'product', None)
        aggregate_key = (vendor_name or product_name or record_id).lower().strip()
        
        if aggregate_key not in vendor_aggregates:
            vendor_aggregates[aggregate_key] = {
                'display_name': vendor_name or product_name or record_id,
                'total_monthly': 0.0,
                'record_count': 0,
                'evidence_refs': []
            }
        
        vendor_aggregates[aggregate_key]['total_monthly'] += monthly_amount
        vendor_aggregates[aggregate_key]['record_count'] += 1
        vendor_aggregates[aggregate_key]['evidence_refs'].append(record_id)
    
    # Generate one finding per vendor/product (deduplicated)
    findings = []
    for aggregate_key, agg in vendor_aggregates.items():
        total_monthly = agg['total_monthly']
        display_name = agg['display_name']
        record_count = agg['record_count']
        
        # Determine confidence/materiality based on spend level
        if total_monthly >= 1000:
            confidence = Confidence.HIGH
            materiality = Materiality.HIGH
        elif total_monthly >= 500:
            confidence = Confidence.HIGH
            materiality = Materiality.MED
        else:
            confidence = Confidence.MED
            materiality = Materiality.MED
        
        triage = compute_triage_priority(confidence, materiality)
        
        if record_count > 1:
            explanation = f"Vendor '{display_name}' has ${total_monthly:.0f}/mo across {record_count} finance records with no corresponding asset. Possible undiscovered system(s)."
        else:
            explanation = f"Finance record '{display_name}' (${total_monthly:.0f}/mo) has no corresponding asset in catalog. Possible undiscovered system."
        
        findings.append(Finding(
            finding_id=deterministic_uuid(snapshot_id, run_id, aggregate_key, "finance_gap"),
            asset_id=None,
            tenant_id=tenant_id,
            run_id=run_id,
            finding_type=FindingType.FINANCE_GAP,
            category=get_category(FindingType.FINANCE_GAP),
            severity=Severity.HIGH,
            explanation=explanation,
            evidence_refs=agg['evidence_refs'][:50],  # Limit refs
            confidence=confidence,
            materiality=materiality,
            triage_priority=triage
        ))
    
    return findings


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
        
    Returns:
        List of findings, deterministically sorted
    """
    findings = []
    
    correlation_by_name = {c.entity.original_name: c for c in correlations}
    
    for asset in assets:
        correlation = correlation_by_name.get(asset.name)
        if not correlation:
            continue
        
        identity_gap = generate_identity_gap_finding(asset, correlation, tenant_id, run_id, snapshot_id)
        if identity_gap:
            findings.append(identity_gap)
        
        cmdb_gap = generate_cmdb_gap_finding(asset, correlation, tenant_id, run_id, snapshot_id)
        if cmdb_gap:
            findings.append(cmdb_gap)
        
        governance_gap = generate_governance_gap_finding(asset, correlation, tenant_id, run_id, snapshot_id)
        if governance_gap:
            findings.append(governance_gap)
        
        duplication_risk = generate_duplication_risk_finding(asset, correlation, tenant_id, run_id, snapshot_id)
        if duplication_risk:
            findings.append(duplication_risk)
        
        data_conflicts = generate_data_conflict_findings(asset, correlation, tenant_id, run_id, snapshot_id)
        findings.extend(data_conflicts)
    
    finance_gaps = generate_finance_gap_findings(
        indexes, assets, correlations, tenant_id, run_id, snapshot_id
    )
    findings.extend(finance_gaps)
    
    findings.sort(key=lambda f: (
        {"security_risk": 0, "governance_finding": 1}.get(f.category.value, 2),
        {"p0": 0, "p1": 1, "p2": 2}.get(f.triage_priority.value, 3),
        {"high": 0, "med": 1, "low": 2}.get(f.severity.value, 3),
        f.finding_type.value,
        str(f.asset_id) if f.asset_id else "",
        f.explanation
    ))
    
    return findings


from dataclasses import dataclass


@dataclass
class RiskCaseCounts:
    """Aggregated risk case counts for KPI display"""
    # Total security risk cases
    security_risk_cases_total: int = 0
    
    # Breakdown by type
    identity_gap_cases: int = 0
    finance_gap_cases: int = 0
    data_conflict_cases: int = 0
    
    # Breakdown by priority
    p0_immediate: int = 0
    p1_high_priority: int = 0
    p2_backlog: int = 0
    
    # Actionable = P0 + P1 (default KPI)
    actionable_cases: int = 0
    
    # Raw trigger count (for drill-down)
    raw_triggers: int = 0


def compute_risk_case_counts(findings: list[Finding]) -> RiskCaseCounts:
    """
    Compute Risk Case counts for KPI display.
    
    Risk Cases group raw triggers by asset + finding_type.
    Default KPI shows "Actionable" = P0 + P1 cases only.
    """
    counts = RiskCaseCounts()
    
    # Filter to security risks only
    security_findings = [f for f in findings if f.category == FindingCategory.SECURITY_RISK]
    counts.raw_triggers = len(security_findings)
    
    # Dedupe into cases by (asset_id, finding_type, conflict_field)
    # For data_conflict, also key by field to maintain per-field deduplication
    seen_cases: set[tuple] = set()
    
    for f in security_findings:
        if f.finding_type == FindingType.DATA_CONFLICT:
            case_key = (str(f.asset_id), f.finding_type.value, f.conflict_field or "")
        else:
            case_key = (str(f.asset_id) if f.asset_id else f.evidence_refs[0] if f.evidence_refs else "", f.finding_type.value, "")
        
        if case_key in seen_cases:
            continue
        seen_cases.add(case_key)
        
        counts.security_risk_cases_total += 1
        
        # Count by type
        if f.finding_type == FindingType.IDENTITY_GAP:
            counts.identity_gap_cases += 1
        elif f.finding_type == FindingType.FINANCE_GAP:
            counts.finance_gap_cases += 1
        elif f.finding_type == FindingType.DATA_CONFLICT:
            counts.data_conflict_cases += 1
        
        # Count by priority
        if f.triage_priority == TriagePriority.P0:
            counts.p0_immediate += 1
        elif f.triage_priority == TriagePriority.P1:
            counts.p1_high_priority += 1
        else:
            counts.p2_backlog += 1
    
    counts.actionable_cases = counts.p0_immediate + counts.p1_high_priority
    
    return counts
