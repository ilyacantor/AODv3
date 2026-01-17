"""
Derived Classifications package - Shadow, Zombie, and Parked classification.

This package computes derived classifications for assets based on governance
signals and activity evidence. Classifications are computed on-read, not stored.

Public API:
- compute_derived_classifications: Main entry point
- classify_shadow, classify_zombie: Individual asset classification
- compute_zombie_status: Shared zombie logic
- compute_domain_rollups: Domain-level aggregation
- ActivityStatus: Activity status enum
- DomainRollup, DerivedClassificationSummary: Result types

Original file preserved as: derived_classifications_old.py
"""

# Enums
from .enums import ActivityStatus

# Time utilities
from .time_utils import (
    utc_now,
    ensure_utc_aware,
    get_activity_status,
    _utc_now,
    _ensure_utc_aware,
)

# Result types
from .result_types import (
    ClassificationResult,
    DistributionDiagnostic,
    DomainRollup,
    DerivedClassificationSummary,
)

# Shadow classification
from .shadow import classify_shadow

# Zombie classification
from .zombie import (
    compute_zombie_status,
    classify_zombie,
)

# Domain helpers
from .domain_helpers import (
    resolve_domain_key,
    get_parent_domain,
    _resolve_domain_key,
    _get_parent_domain,
)

# Domain rollups
from .domain_rollups import compute_domain_rollups

# Main engine
from .engine import compute_derived_classifications

# Re-export canonical_key functions for backwards compatibility
from ..canonical_key import (
    ALIAS_DOMAINS_TO_COLLAPSE,
    normalize_to_canonical_vendor_domain,
)

# Provide underscore alias
_normalize_to_canonical_vendor_domain = normalize_to_canonical_vendor_domain

__all__ = [
    # Enums
    "ActivityStatus",
    # Time utilities
    "utc_now",
    "ensure_utc_aware",
    "get_activity_status",
    "_utc_now",
    "_ensure_utc_aware",
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
    # Domain helpers
    "resolve_domain_key",
    "get_parent_domain",
    "_resolve_domain_key",
    "_get_parent_domain",
    # Domain rollups
    "compute_domain_rollups",
    # Main engine
    "compute_derived_classifications",
    # Canonical key re-exports
    "ALIAS_DOMAINS_TO_COLLAPSE",
    "normalize_to_canonical_vendor_domain",
    "_normalize_to_canonical_vendor_domain",
]
