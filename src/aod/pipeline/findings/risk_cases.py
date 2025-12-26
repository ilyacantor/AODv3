"""Risk case counting for KPI display"""

from dataclasses import dataclass

from ...models.output_contracts import Finding, FindingType, TriagePriority
from .base import is_security_risk


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

    # Filter to security risks only (new taxonomy)
    security_findings = [f for f in findings if is_security_risk(f.category)]
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
