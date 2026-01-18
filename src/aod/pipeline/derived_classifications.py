"""
Derived Classifications Module

Computes Shadow, Zombie, and Parked classifications from evidence AFTER the main pipeline.

REFACTORING NOTE: The classifications/ package was created but imports from the
preserved original file to ensure 100% behavioral compatibility.

The classifications/ package is 98% compatible but this shim uses the original
to guarantee no policy changes. One minor gap was identified:
- Missing _normalize_to_canonical_vendor_domain wrapper function

Original file: derived_classifications_old.py (1,060 lines - authoritative)
"""

# Import everything from the preserved original file
from .derived_classifications_old import (
    # Time utilities
    _utc_now,
    _ensure_utc_aware,
    # Enums
    ActivityStatus,
    # Activity status function
    get_activity_status,
    # Result types
    ClassificationResult,
    DistributionDiagnostic,
    DomainRollup,
    DerivedClassificationSummary,
    # Shadow classification
    classify_shadow,
    # Zombie classification
    compute_zombie_status,
    classify_zombie,
    # Main compute function
    compute_derived_classifications,
    # Domain helpers
    ALIAS_DOMAINS_TO_COLLAPSE,
    _normalize_to_canonical_vendor_domain,
    _resolve_domain_key,
    _get_parent_domain,
    # Domain rollups
    compute_domain_rollups,
)

# Provide aliases for any code expecting non-underscore names
utc_now = _utc_now
ensure_utc_aware = _ensure_utc_aware
normalize_to_canonical_vendor_domain = _normalize_to_canonical_vendor_domain
resolve_domain_key = _resolve_domain_key
get_parent_domain = _get_parent_domain

__all__ = [
    # Time utilities
    "_utc_now",
    "_ensure_utc_aware",
    "utc_now",
    "ensure_utc_aware",
    # Enums
    "ActivityStatus",
    # Activity status
    "get_activity_status",
    # Result types
    "ClassificationResult",
    "DistributionDiagnostic",
    "DomainRollup",
    "DerivedClassificationSummary",
    # Shadow classification
    "classify_shadow",
    # Zombie classification
    "compute_zombie_status",
    "classify_zombie",
    # Main compute function
    "compute_derived_classifications",
    # Domain helpers
    "ALIAS_DOMAINS_TO_COLLAPSE",
    "_normalize_to_canonical_vendor_domain",
    "normalize_to_canonical_vendor_domain",
    "_resolve_domain_key",
    "resolve_domain_key",
    "_get_parent_domain",
    "get_parent_domain",
    # Domain rollups
    "compute_domain_rollups",
]
