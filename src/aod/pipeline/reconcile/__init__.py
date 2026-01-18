"""
Reconciliation package - Asset classification and output emission.

This package handles the reconciliation output stage of AOD, which
classifies assets as shadow, zombie, parked, or active based on
governance signals and activity evidence.

Public API:
- emit_actual_results: Main entry point for reconciliation output
- classify_actual: Classify a single asset
- AssetActualResult, ActualResultsOutput: Result types
- ReasonCode, AnchorType: Enums
- is_reconciliation_eligible: Eligibility check

Original file preserved as: aod_agent_reconcile_old.py
"""

# Enums
from .enums import (
    ReasonCode,
    AnchorType,
)

# Result types
from .result_types import (
    AssetActualResult,
    RejectionResult,
    ActualResultsOutput,
)

# Utilities
from .utils import (
    utc_now,
    ensure_utc_aware,
    deduplicate_reason_codes,
    _utc_now,
    _ensure_utc_aware,
    _deduplicate_reason_codes,
)

# Eligibility
from .eligibility import (
    is_infrastructure_domain,
    is_reconciliation_eligible,
    INFRASTRUCTURE_DOMAIN_PATTERNS,
    _is_infrastructure_domain,
)

# Reason codes
from .reason_codes import (
    compute_asset_reasons,
)

# Domain helpers
from .domain_helpers import (
    extract_raw_domain,
    extract_registered_domain,
    resolve_domain_key,
    get_parent_domain,
    _extract_raw_domain,
    _extract_registered_domain,
    _normalize_to_canonical_vendor_domain,
)

# Classification
from .classify import (
    classify_actual,
    merge_results,
)

# Emitter
from .emitter import (
    emit_actual_results,
    compute_rejection_reasons,
    _compute_rejection_reasons,
)

__all__ = [
    # Enums
    "ReasonCode",
    "AnchorType",
    # Result types
    "AssetActualResult",
    "RejectionResult",
    "ActualResultsOutput",
    # Utilities
    "utc_now",
    "ensure_utc_aware",
    "deduplicate_reason_codes",
    "_utc_now",
    "_ensure_utc_aware",
    "_deduplicate_reason_codes",
    # Eligibility
    "is_infrastructure_domain",
    "is_reconciliation_eligible",
    "INFRASTRUCTURE_DOMAIN_PATTERNS",
    "_is_infrastructure_domain",
    # Reason codes
    "compute_asset_reasons",
    # Domain helpers
    "extract_raw_domain",
    "extract_registered_domain",
    "resolve_domain_key",
    "get_parent_domain",
    "_extract_raw_domain",
    "_extract_registered_domain",
    "_normalize_to_canonical_vendor_domain",
    # Classification
    "classify_actual",
    "merge_results",
    # Emitter
    "emit_actual_results",
    "compute_rejection_reasons",
    "_compute_rejection_reasons",
]
