"""
Correlation package - Entity to plane matching with disambiguation.

This package provides the correlation logic for matching candidate entities
to records in the various data planes (IdP, CMDB, Cloud, Finance).

Public API (backwards compatible):
- correlate_entities_to_planes: Main entry point
- correlate_to_plane: Single-entity, single-plane correlation
- MatchStatus, AmbiguityCode, MatchQuality: Enums
- PlaneMatch, CorrelationResult: Result types
- disambiguate_matches: Disambiguation logic

Internal functions are also exported for backwards compatibility.
"""

# Enums
from .enums import (
    MatchStatus,
    AmbiguityCode,
    MatchQuality,
)

# Result types
from .result_types import (
    RelatedDomainVariant,
    PlaneMatch,
    CorrelationResult,
    PrecomputedEntityData,
)

# Constants
from .constants import (
    CONTAINS_MATCH_MIN_LENGTH,
    CONTAINS_MATCH_RATIO_THRESHOLD,
    MIN_TOKEN_LENGTH_FOR_MATCH,
    MIN_DOMAIN_TOKEN_LENGTH_FOR_FINANCE,
    LRU_CACHE_SIZE,
    ENV_SUFFIXES,
    LEGACY_MARKERS,
    AUTHORITATIVE_MATCH_METHODS,
    HEURISTIC_MATCH_METHODS,
    CROSS_TLD_MATCH_METHODS,
    KNOWN_DISTINCT_PRODUCTS,
    GENERIC_TOKENS_FOR_FINANCE,
    GENERIC_TOKENS,
    VENDOR_PREFIXES,
)

# String matching
from .string_matching import (
    _levenshtein_distance,
    _levenshtein_distance_cached,
    _is_fuzzy_match,
    is_fuzzy_match,
)

# Record helpers
from .record_helpers import (
    extract_base_name,
    is_legacy_name,
    get_record_name,
    get_record_vendor,
    extract_domain_base_token,
    get_record_field,
    is_deprecated_by_field,
    get_environment_field,
    # Underscore aliases for backwards compatibility
    _extract_base_name,
    _is_legacy_name,
    _get_record_name,
    _get_record_vendor,
    _extract_domain_base_token,
    _get_record_field,
    _is_deprecated_by_field,
    _get_environment_field,
)

# Contains matching
from .contains_matching import (
    is_valid_contains_match,
    _is_valid_contains_match,
)

# Disambiguation
from .disambiguation import disambiguate_matches

# Debug
from .debug import (
    log_match_debug,
    _log_match_debug,
)

# Plane correlator
from .plane_correlator import correlate_to_plane

# Domain recovery
from .domain_recovery import (
    recover_domain_from_planes,
    _recover_domain_from_planes,
)

# Finance expander
from .finance_expander import (
    expand_finance_to_include_all_vendor_records,
    _expand_finance_to_include_all_vendor_records,
)

# Main engine
from .engine import (
    correlate_entities_to_planes,
    precompute_entity_data,
    _precompute_entity_data,
)


__all__ = [
    # Enums
    "MatchStatus",
    "AmbiguityCode",
    "MatchQuality",
    # Result types
    "RelatedDomainVariant",
    "PlaneMatch",
    "CorrelationResult",
    "PrecomputedEntityData",
    # Constants
    "CONTAINS_MATCH_MIN_LENGTH",
    "CONTAINS_MATCH_RATIO_THRESHOLD",
    "MIN_TOKEN_LENGTH_FOR_MATCH",
    "MIN_DOMAIN_TOKEN_LENGTH_FOR_FINANCE",
    "LRU_CACHE_SIZE",
    "ENV_SUFFIXES",
    "LEGACY_MARKERS",
    "AUTHORITATIVE_MATCH_METHODS",
    "HEURISTIC_MATCH_METHODS",
    "CROSS_TLD_MATCH_METHODS",
    "KNOWN_DISTINCT_PRODUCTS",
    "GENERIC_TOKENS_FOR_FINANCE",
    "GENERIC_TOKENS",
    "VENDOR_PREFIXES",
    # String matching
    "_levenshtein_distance",
    "_levenshtein_distance_cached",
    "_is_fuzzy_match",
    "is_fuzzy_match",
    # Record helpers
    "extract_base_name",
    "is_legacy_name",
    "get_record_name",
    "get_record_vendor",
    "extract_domain_base_token",
    "get_record_field",
    "is_deprecated_by_field",
    "get_environment_field",
    "_extract_base_name",
    "_is_legacy_name",
    "_get_record_name",
    "_get_record_vendor",
    "_extract_domain_base_token",
    "_get_record_field",
    "_is_deprecated_by_field",
    "_get_environment_field",
    # Contains matching
    "is_valid_contains_match",
    "_is_valid_contains_match",
    # Disambiguation
    "disambiguate_matches",
    # Debug
    "log_match_debug",
    "_log_match_debug",
    # Plane correlator
    "correlate_to_plane",
    # Domain recovery
    "recover_domain_from_planes",
    "_recover_domain_from_planes",
    # Finance expander
    "expand_finance_to_include_all_vendor_records",
    "_expand_finance_to_include_all_vendor_records",
    # Main engine
    "correlate_entities_to_planes",
    "precompute_entity_data",
    "_precompute_entity_data",
]
