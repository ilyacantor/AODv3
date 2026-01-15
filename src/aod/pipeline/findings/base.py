"""Common utilities for findings generation"""

from ...models.output_contracts import (
    FindingType, FindingCategory, Confidence, Materiality, TriagePriority
)
from ...core.policy import get_current_config

# Finding type categories
SECURITY_RISK_TYPES = {
    FindingType.IDENTITY_GAP,
    FindingType.FINANCE_GAP,
    FindingType.DATA_CONFLICT,
}

VISIBILITY_GAP_TYPES = {
    FindingType.CMDB_GAP,
}

GOVERNANCE_HYGIENE_TYPES = {
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


def get_finance_gap_monthly_threshold() -> float:
    """Get the minimum monthly spend threshold for FINANCE_GAP from policy."""
    return get_current_config().finance_thresholds.finance_gap_monthly_threshold


def get_category(finding_type: FindingType) -> FindingCategory:
    """Map finding type to specific category (Dec 2025 taxonomy)

    Security Risks:
    - IDENTITY_GAP → Identity & Access
    - FINANCE_GAP → Shadow IT (financially-backed)
    - DATA_CONFLICT → Data Integrity

    Non-Security:
    - CMDB_GAP → Visibility Gap
    - GOVERNANCE_GAP, DUPLICATION_RISK → Governance Hygiene
    """
    if finding_type == FindingType.IDENTITY_GAP:
        return FindingCategory.IDENTITY_ACCESS
    if finding_type == FindingType.FINANCE_GAP:
        return FindingCategory.SHADOW_IT
    if finding_type == FindingType.DATA_CONFLICT:
        return FindingCategory.DATA_INTEGRITY
    if finding_type in VISIBILITY_GAP_TYPES:
        return FindingCategory.VISIBILITY_GAP
    return FindingCategory.GOVERNANCE_HYGIENE


def is_security_risk(category: FindingCategory) -> bool:
    """Check if a category is a security risk (for headline KPI)"""
    return category in {
        FindingCategory.IDENTITY_ACCESS,
        FindingCategory.SHADOW_IT,
        FindingCategory.DATA_INTEGRITY,
    }


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
