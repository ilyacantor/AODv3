"""
Stage 5: Admission (AAC) - Apply admission criteria to determine assets.

This module has been refactored from a 2600-line monolith into smaller,
focused modules for better testability and maintainability.

Public API:
- apply_admission_criteria: Main entry point for admission processing
- AdmissionResult: Result of admission evaluation
- build_idp_activity_map: Build IdP activity map for cross-IdP aggregation

Sub-modules:
- gates/: Admission gates for each plane (IdP, CMDB, Cloud, Finance, Discovery)
- domain_validation: Domain validation utilities
- domain_extraction: Domain extraction from correlation records
- activity: Activity timestamp extraction
- classification: Asset type and environment classification
- debug: Debug utilities for match info
- constants: Shared constants
"""

# Main entry point
from .asset_builder import apply_admission_criteria

# Result types
from .result_types import AdmissionResult, AdmissionEvidence, DomainGateResult, DiscoveryInvariantError

# Gates - individual admission checks
from .gates import (
    check_idp_admission,
    check_cmdb_admission,
    check_cloud_admission,
    check_finance_admission,
    check_discovery_admission,
    build_discovery_footprint,
    DiscoveryFootprint,
    has_recurring_finance_spend,
    is_non_canonical_idp_app,
)

# IdP helpers
from .idp_helpers import build_idp_activity_map, _extract_idp_domain, _idp_domain_matches_entity

# Domain validation
from .domain_validation import (
    is_banned_domain,
    is_corporate_root_domain,
    is_infrastructure_domain,
)

# Domain extraction
from .domain_extraction import (
    extract_cmdb_primary_domain,
    extract_cmdb_external_ref_domains,
    validate_cmdb_domain_for_identity,
    _extract_all_domains_from_correlation,
    _extract_domain_from_correlation,
)

# Activity extraction
from .activity import extract_activity_timestamps

# Classification
from .classification import determine_asset_type, determine_environment

# Debug utilities
from .debug import build_match_debug_info, build_lens_match_debug

# Constants (re-export commonly used ones)
from .constants import (
    PROMOTION_ALLOWED_MATCH_METHODS,
    PROMOTION_BLOCKED_MATCH_METHODS,
    VALID_CI_TYPES,
    VALID_LIFECYCLES,
    VALID_CLOUD_RESOURCE_TYPES,
    SSO_PROVIDER_DOMAINS,
    SOURCE_TO_PLANE,
    DISCOVERY_CORROBORATION_PLANES,
    FARM_CREDITED_DISCOVERY_SOURCES,
    USER_ACTIVITY_EXHAUST,
)

# For backwards compatibility - expose source_to_plane at module level
from .gates.discovery import source_to_plane

__all__ = [
    # Main API
    'apply_admission_criteria',
    'AdmissionResult',
    'AdmissionEvidence',
    'DomainGateResult',
    'DiscoveryInvariantError',

    # Gates
    'check_idp_admission',
    'check_cmdb_admission',
    'check_cloud_admission',
    'check_finance_admission',
    'check_discovery_admission',
    'build_discovery_footprint',
    'DiscoveryFootprint',
    'has_recurring_finance_spend',
    'is_non_canonical_idp_app',

    # IdP helpers
    'build_idp_activity_map',
    '_extract_idp_domain',
    '_idp_domain_matches_entity',

    # Domain validation
    'is_banned_domain',
    'is_corporate_root_domain',
    'is_infrastructure_domain',

    # Domain extraction
    'extract_cmdb_primary_domain',
    'extract_cmdb_external_ref_domains',
    'validate_cmdb_domain_for_identity',
    '_extract_all_domains_from_correlation',
    '_extract_domain_from_correlation',

    # Activity
    'extract_activity_timestamps',

    # Classification
    'determine_asset_type',
    'determine_environment',

    # Debug
    'build_match_debug_info',
    'build_lens_match_debug',

    # Constants
    'PROMOTION_ALLOWED_MATCH_METHODS',
    'PROMOTION_BLOCKED_MATCH_METHODS',
    'VALID_CI_TYPES',
    'VALID_LIFECYCLES',
    'VALID_CLOUD_RESOURCE_TYPES',
    'SSO_PROVIDER_DOMAINS',
    'SOURCE_TO_PLANE',
    'DISCOVERY_CORROBORATION_PLANES',
    'FARM_CREDITED_DISCOVERY_SOURCES',
    'USER_ACTIVITY_EXHAUST',
    'source_to_plane',
]
