"""Centralized policy configuration for AOS Discover

All policy thresholds and limits should be defined here for consistency
and easy modification. Import from this module rather than hardcoding values.
"""


class PolicyConfig:
    """Policy thresholds that affect business logic decisions"""
    
    FINANCE_GAP_MONTHLY_THRESHOLD: float = 200.0
    """Minimum monthly spend (USD) required for FINANCE_GAP finding"""
    
    DISCOVERY_ACTIVITY_WINDOW_DAYS: int = 90
    """Number of days to consider for discovery activity"""
    
    MAX_OBSERVATION_SAMPLES: int = 2000
    """Maximum observation samples to store per run"""
    
    FUZZY_MATCH_MAX_DISTANCE: int = 2
    """Maximum edit distance for fuzzy name matching"""
    
    FUZZY_MATCH_MAX_RATIO: float = 0.20
    """Maximum edit distance ratio for fuzzy matching"""


class FindingPriority:
    """Triage priority thresholds"""
    
    P0_CONFIDENCE = "high"
    P0_MATERIALITY = "high"
    
    P1_MIN_CONFIDENCE = "med"
    P1_MIN_MATERIALITY = "med"


policy = PolicyConfig()
