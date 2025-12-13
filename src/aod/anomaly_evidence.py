"""
Evidence-based anomaly detection and risk scoring.

Replaces numeric anomaly_score from Farm with concrete evidence indicators.
Risk scores are derived deterministically from validated evidence.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

VALID_INDICATOR_TYPES = {
    "unusual_access_patterns",
    "data_volume_spike",
    "off_hours_activity",
    "auth_fail_storm",
    "latency_regression",
    "permission_escalation",
    "geo_anomaly",
    "rate_limit_breach"
}

INDICATOR_WEIGHTS = {
    "unusual_access_patterns": {"low": 0.2, "medium": 0.45, "high": 0.75},
    "data_volume_spike": {"low": 0.15, "medium": 0.4, "high": 0.7},
    "off_hours_activity": {"low": 0.1, "medium": 0.3, "high": 0.5},
    "auth_fail_storm": {"low": 0.25, "medium": 0.5, "high": 0.8},
    "latency_regression": {"low": 0.1, "medium": 0.25, "high": 0.45},
    "permission_escalation": {"low": 0.3, "medium": 0.55, "high": 0.85},
    "geo_anomaly": {"low": 0.2, "medium": 0.45, "high": 0.7},
    "rate_limit_breach": {"low": 0.15, "medium": 0.35, "high": 0.6}
}

DEFAULT_SEVERITY = "medium"
EVIDENCE_DECAY_DAYS = 7


def validate_indicator(indicator: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    Validate a single anomaly indicator.
    
    Required fields:
    - indicator_type: must be in VALID_INDICATOR_TYPES
    - observed_at: ISO timestamp of when the anomaly was observed
    - evidence: dict with supporting data
    
    Returns (is_valid, error_message)
    """
    if not isinstance(indicator, dict):
        return False, "Indicator must be a dictionary"
    
    indicator_type = indicator.get("indicator_type")
    if not indicator_type:
        return False, "Missing indicator_type"
    if indicator_type not in VALID_INDICATOR_TYPES:
        return False, f"Invalid indicator_type: {indicator_type}"
    
    observed_at = indicator.get("observed_at")
    if not observed_at:
        return False, "Missing observed_at timestamp"
    
    evidence = indicator.get("evidence")
    if not isinstance(evidence, dict) or len(evidence) == 0:
        return False, "Evidence must be a non-empty dictionary"
    
    return True, None


def normalize_indicators(raw_indicators: List[Any]) -> List[Dict[str, Any]]:
    """
    Validate and normalize a list of anomaly indicators.
    Invalid indicators are filtered out (fail closed).
    """
    if not isinstance(raw_indicators, list):
        return []
    
    normalized = []
    for indicator in raw_indicators:
        is_valid, error = validate_indicator(indicator)
        if is_valid:
            normalized.append({
                "indicator_type": indicator["indicator_type"],
                "severity": indicator.get("severity", DEFAULT_SEVERITY),
                "observed_at": indicator["observed_at"],
                "evidence": indicator["evidence"]
            })
    
    return normalized


def is_indicator_fresh(indicator: Dict[str, Any], max_age_days: int = EVIDENCE_DECAY_DAYS) -> bool:
    """Check if an indicator is within the freshness window."""
    observed_at = indicator.get("observed_at")
    if not observed_at:
        return False
    
    try:
        if isinstance(observed_at, str):
            obs_time = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        else:
            obs_time = observed_at
        
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        return obs_time >= cutoff
    except (ValueError, TypeError):
        return False


def calculate_risk_score(indicators: List[Dict[str, Any]]) -> float:
    """
    Calculate evidence-based risk score from validated indicators.
    
    Uses formula: risk_score = 1 - Π(1 - weight_i)
    This means multiple indicators compound but cap at 1.0
    
    Only fresh indicators (within EVIDENCE_DECAY_DAYS) contribute.
    """
    if not indicators:
        return 0.0
    
    fresh_indicators = [ind for ind in indicators if is_indicator_fresh(ind)]
    if not fresh_indicators:
        return 0.0
    
    survival_product = 1.0
    for indicator in fresh_indicators:
        indicator_type = indicator.get("indicator_type", "")
        severity = indicator.get("severity", DEFAULT_SEVERITY)
        
        weights = INDICATOR_WEIGHTS.get(indicator_type, {})
        weight = weights.get(severity, 0.3) if severity else 0.3
        
        survival_product *= (1 - weight)
    
    risk_score = 1 - survival_product
    return round(risk_score, 3)


def derive_ops_risk_finding(indicators: List[Dict[str, Any]], risk_score: float) -> Optional[Dict[str, Any]]:
    """
    Derive ops_risk finding from evidence-based indicators.
    
    Thresholds:
    - risk_score >= 0.7: critical severity
    - risk_score >= 0.35: warn severity
    - risk_score < 0.35: no finding
    
    Returns finding dict or None if no finding should be emitted.
    """
    if risk_score < 0.35:
        return None
    
    fresh_indicators = [ind for ind in indicators if is_indicator_fresh(ind)]
    if not fresh_indicators:
        return None
    
    indicator_types = list(set(ind["indicator_type"] for ind in fresh_indicators))
    indicator_count = len(fresh_indicators)
    
    severity = "critical" if risk_score >= 0.7 else "warn"
    
    return {
        "finding_type": "ops_risk",
        "rule_id": "OPS_EVIDENCE_BASED",
        "severity": severity,
        "description": f"Operational risk detected ({indicator_count} indicator(s): {', '.join(indicator_types)})",
        "evidence": {
            "risk_score": risk_score,
            "indicator_count": indicator_count,
            "indicator_types": indicator_types,
            "indicators": fresh_indicators
        }
    }


def extract_anomaly_evidence(signals: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract and process anomaly evidence from Farm signals.
    
    Ignores any numeric anomaly_score.
    Only processes concrete anomaly_indicators.
    
    Returns dict with:
    - indicators: list of validated indicators
    - risk_score: derived evidence-based score
    - has_evidence: boolean
    """
    raw_indicators = signals.get("anomaly_indicators", [])
    
    normalized = normalize_indicators(raw_indicators)
    risk_score = calculate_risk_score(normalized)
    
    return {
        "indicators": normalized,
        "risk_score": risk_score,
        "has_evidence": len(normalized) > 0
    }
