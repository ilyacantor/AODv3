"""Findings generation package - backward compatibility exports"""

from .base import (
    get_category,
    is_security_risk,
    compute_triage_priority,
    get_finance_gap_monthly_threshold,
    SECURITY_RISK_TYPES,
    VISIBILITY_GAP_TYPES,
    GOVERNANCE_HYGIENE_TYPES,
    SECURITY_RELEVANT_FIELDS,
)

from .identity_gap import generate_identity_gap_finding
from .cmdb_gap import generate_cmdb_gap_finding
from .governance_gap import generate_governance_gap_finding
from .duplication_risk import generate_duplication_risk_finding
from .data_conflict import generate_data_conflict_findings
from .finance_gap import generate_finance_gap_findings
from .engine import generate_findings
from .risk_cases import RiskCaseCounts, compute_risk_case_counts

__all__ = [
    # Base utilities
    'get_category',
    'is_security_risk',
    'compute_triage_priority',
    'get_finance_gap_monthly_threshold',
    'SECURITY_RISK_TYPES',
    'VISIBILITY_GAP_TYPES',
    'GOVERNANCE_HYGIENE_TYPES',
    'SECURITY_RELEVANT_FIELDS',

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
