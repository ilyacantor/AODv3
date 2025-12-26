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

This module now delegates to the findings package for better code organization.
"""

# Re-export all public APIs from findings package for backward compatibility
from .findings import (
    # Base utilities
    get_category,
    is_security_risk,
    compute_triage_priority,
    SECURITY_RISK_TYPES,
    VISIBILITY_GAP_TYPES,
    GOVERNANCE_HYGIENE_TYPES,
    SECURITY_RELEVANT_FIELDS,
    FINANCE_GAP_MONTHLY_THRESHOLD,

    # Finding generators
    generate_identity_gap_finding,
    generate_cmdb_gap_finding,
    generate_governance_gap_finding,
    generate_duplication_risk_finding,
    generate_data_conflict_findings,
    generate_finance_gap_findings,

    # Main orchestrator
    generate_findings,

    # Risk case counting
    RiskCaseCounts,
    compute_risk_case_counts,
)

__all__ = [
    # Base utilities
    'get_category',
    'is_security_risk',
    'compute_triage_priority',
    'SECURITY_RISK_TYPES',
    'VISIBILITY_GAP_TYPES',
    'GOVERNANCE_HYGIENE_TYPES',
    'SECURITY_RELEVANT_FIELDS',
    'FINANCE_GAP_MONTHLY_THRESHOLD',

    # Finding generators
    'generate_identity_gap_finding',
    'generate_cmdb_gap_finding',
    'generate_governance_gap_finding',
    'generate_duplication_risk_finding',
    'generate_data_conflict_findings',
    'generate_finance_gap_findings',

    # Main orchestrator
    'generate_findings',

    # Risk case counting
    'RiskCaseCounts',
    'compute_risk_case_counts',
]
