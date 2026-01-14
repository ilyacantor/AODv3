"""
DEPRECATED: Legacy policy configuration for AOS Discover

WARNING: This module is DEPRECATED as of Jan 2026.
All policy values have been migrated to config/policy_master.json and are now
accessed via the centralized policy loader:

    from aod.core.policy import get_current_config
    config = get_current_config()
    
    # Activity windows
    config.activity_windows.default_activity_window_days
    
    # Finance thresholds
    config.finance_thresholds.minimum_spend
    config.finance_thresholds.finance_gap_monthly_threshold
    
    # Fuzzy matching
    config.fuzzy_matching.max_edit_distance
    config.fuzzy_matching.max_edit_ratio
    config.fuzzy_matching.min_name_length
    
    # Query limits
    config.query_limits.default_rejection_limit
    config.query_limits.default_query_limit

This file is kept for backward compatibility with any code that still imports
from it, but new code should use the centralized policy loader.
"""

import warnings


class PolicyConfig:
    """
    DEPRECATED: Policy thresholds that affect business logic decisions.
    
    Use get_current_config() from aod.core.policy instead.
    Values here are kept for backward compatibility but are no longer
    the source of truth. See config/policy_master.json.
    """

    # DEPRECATED: Use config.activity_windows.discovery_activity_window_days
    DISCOVERY_ACTIVITY_WINDOW_DAYS: int = 90
    """Number of days to consider for discovery activity (default for asset classification)"""

    # DEPRECATED: Use config.activity_windows.default_activity_window_days
    DEFAULT_ACTIVITY_WINDOW_DAYS: int = 90
    """Default activity window for shadow/zombie classification"""

    # DEPRECATED: Use config.finance_thresholds.finance_gap_monthly_threshold
    FINANCE_GAP_MONTHLY_THRESHOLD: float = 200.0
    """Minimum monthly spend (USD) required for FINANCE_GAP finding"""

    # DEPRECATED: Use config.finance_thresholds.finance_gap_annual_threshold
    FINANCE_GAP_ANNUAL_THRESHOLD: float = 2000.0
    """Minimum annual spend (USD) required for FINANCE_GAP finding"""

    # DEPRECATED: Use config.query_limits.max_observation_samples
    MAX_OBSERVATION_SAMPLES: int = 2000
    """Maximum observation samples to store per run"""

    # DEPRECATED: Use config.query_limits.default_rejection_limit
    DEFAULT_REJECTION_LIMIT: int = 1000
    """Default limit for rejection queries"""

    # DEPRECATED: Use config.query_limits.default_query_limit
    DEFAULT_QUERY_LIMIT: int = 1000
    """Default limit for general database queries"""

    # DEPRECATED: Use config.fuzzy_matching.max_edit_distance
    FUZZY_MATCH_MAX_DISTANCE: int = 2
    """Maximum edit distance for fuzzy name matching"""

    # DEPRECATED: Use config.fuzzy_matching.max_edit_ratio
    FUZZY_MATCH_MAX_RATIO: float = 0.20
    """Maximum edit distance ratio (distance/max_length) for fuzzy matching"""

    # DEPRECATED: Use config.fuzzy_matching.min_name_length
    MIN_NAME_LENGTH_FOR_FUZZY: int = 4
    """Minimum name length to apply fuzzy matching"""

    # DEPRECATED: Use config.vendor_inference.max_confidence
    VENDOR_HYPOTHESIS_MAX_CONFIDENCE: float = 0.9
    """Maximum confidence for vendor hypothesis inference (never fully authoritative)"""

    # DEPRECATED: Use config.admission_gates.min_discovery_sources_for_shadow
    MIN_DISCOVERY_SOURCES_FOR_SHADOW: int = 2
    """Minimum number of corroborating sources required for shadow classification"""


class FindingPriority:
    """Triage priority thresholds"""

    P0_CONFIDENCE = "high"
    P0_MATERIALITY = "high"

    P1_MIN_CONFIDENCE = "med"
    P1_MIN_MATERIALITY = "med"


policy = PolicyConfig()

