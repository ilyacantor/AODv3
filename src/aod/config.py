"""Centralized policy configuration for AOS Discover

All policy thresholds and limits should be defined here for consistency
and easy modification. Import from this module rather than hardcoding values.
"""


class PolicyConfig:
    """Policy thresholds that affect business logic decisions"""

    # Activity and Time Windows
    DISCOVERY_ACTIVITY_WINDOW_DAYS: int = 90
    """Number of days to consider for discovery activity (default for asset classification)"""

    DEFAULT_ACTIVITY_WINDOW_DAYS: int = 90
    """Default activity window for shadow/zombie classification"""

    # Finance Thresholds
    FINANCE_GAP_MONTHLY_THRESHOLD: float = 200.0
    """Minimum monthly spend (USD) required for FINANCE_GAP finding"""

    FINANCE_GAP_ANNUAL_THRESHOLD: float = 2000.0
    """Minimum annual spend (USD) required for FINANCE_GAP finding"""

    # Query and Storage Limits
    MAX_OBSERVATION_SAMPLES: int = 2000
    """Maximum observation samples to store per run"""

    DEFAULT_REJECTION_LIMIT: int = 1000
    """Default limit for rejection queries"""

    DEFAULT_QUERY_LIMIT: int = 1000
    """Default limit for general database queries"""

    # Fuzzy Matching and Correlation
    FUZZY_MATCH_MAX_DISTANCE: int = 2
    """Maximum edit distance for fuzzy name matching"""

    FUZZY_MATCH_MAX_RATIO: float = 0.20
    """Maximum edit distance ratio (distance/max_length) for fuzzy matching"""

    MIN_NAME_LENGTH_FOR_FUZZY: int = 4
    """Minimum name length to apply fuzzy matching"""

    # Vendor Inference
    VENDOR_HYPOTHESIS_MAX_CONFIDENCE: float = 0.9
    """Maximum confidence for vendor hypothesis inference (never fully authoritative)"""

    # Discovery Requirements
    MIN_DISCOVERY_SOURCES_FOR_SHADOW: int = 2
    """Minimum number of corroborating sources required for shadow classification"""


class FindingPriority:
    """Triage priority thresholds"""

    P0_CONFIDENCE = "high"
    P0_MATERIALITY = "high"

    P1_MIN_CONFIDENCE = "med"
    P1_MIN_MATERIALITY = "med"


policy = PolicyConfig()

