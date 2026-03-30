"""
AOD Agent Reconciliation - Actual Results Emitter

REFACTORING NOTE: The reconcile/ package refactoring introduced logic changes.
This shim now imports directly from the preserved original file to maintain
correct behavior until the package modules are properly verified.

The reconcile/ package exists but should NOT be used until:
1. All 38 ReasonCode enum values are restored
2. AnchorType.DISCOVERY is added back
3. AssetActualResult structure matches original
4. Output format (string lists vs objects) is verified
5. FORMAT_PARITY_FIX logic is restored
6. Alias expansion is re-implemented

Original file: aod_agent_reconcile_old.py (1,275 lines - authoritative)
"""

# Import everything from the preserved original file
from .aod_agent_reconcile_old import (
    # Enums
    ReasonCode,
    AnchorType,
    # Result types
    AssetActualResult,
    ActualResultsOutput,
    # Utility functions
    _utc_now,
    _ensure_utc_aware,
    _deduplicate_reason_codes,
    # Eligibility
    _is_infrastructure_domain,
    is_reconciliation_eligible,
    # Reason computation
    compute_asset_reasons,
    # Domain helpers
    _extract_raw_domain,
    _extract_registered_domain,
    _normalize_to_canonical_vendor_domain,
    # Classification
    classify_actual,
    # Main emitter
    emit_actual_results,
)
from ..constants import INFRASTRUCTURE_DOMAINS

# Provide aliases for any code expecting non-underscore names
utc_now = _utc_now
ensure_utc_aware = _ensure_utc_aware
deduplicate_reason_codes = _deduplicate_reason_codes
is_infrastructure_domain = _is_infrastructure_domain
extract_raw_domain = _extract_raw_domain
extract_registered_domain = _extract_registered_domain

__all__ = [
    # Enums
    "ReasonCode",
    "AnchorType",
    # Result types
    "AssetActualResult",
    "ActualResultsOutput",
    # Utility functions
    "_utc_now",
    "_ensure_utc_aware",
    "_deduplicate_reason_codes",
    "utc_now",
    "ensure_utc_aware",
    "deduplicate_reason_codes",
    # Eligibility
    "_is_infrastructure_domain",
    "is_infrastructure_domain",
    "is_reconciliation_eligible",
    # Constants
    "INFRASTRUCTURE_DOMAINS",
    # Reason computation
    "compute_asset_reasons",
    # Domain helpers
    "_extract_raw_domain",
    "_extract_registered_domain",
    "_normalize_to_canonical_vendor_domain",
    "extract_raw_domain",
    "extract_registered_domain",
    # Classification
    "classify_actual",
    # Main emitter
    "emit_actual_results",
]
