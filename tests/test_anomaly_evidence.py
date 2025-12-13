"""Tests for evidence-based anomaly detection and risk scoring."""

import pytest
from datetime import datetime, timezone, timedelta

from src.aod.anomaly_evidence import (
    validate_indicator,
    normalize_indicators,
    calculate_risk_score,
    derive_ops_risk_finding,
    extract_anomaly_evidence,
    VALID_INDICATOR_TYPES
)


class TestValidateIndicator:
    def test_valid_indicator(self):
        indicator = {
            "indicator_type": "unusual_access_patterns",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "evidence": {"user_count": 150, "baseline": 50}
        }
        is_valid, error = validate_indicator(indicator)
        assert is_valid is True
        assert error is None
    
    def test_invalid_missing_type(self):
        indicator = {
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "evidence": {"user_count": 150}
        }
        is_valid, error = validate_indicator(indicator)
        assert is_valid is False
        assert "Missing indicator_type" in error
    
    def test_invalid_unknown_type(self):
        indicator = {
            "indicator_type": "unknown_anomaly",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "evidence": {"data": "test"}
        }
        is_valid, error = validate_indicator(indicator)
        assert is_valid is False
        assert "Invalid indicator_type" in error
    
    def test_invalid_missing_timestamp(self):
        indicator = {
            "indicator_type": "data_volume_spike",
            "evidence": {"volume": 1000}
        }
        is_valid, error = validate_indicator(indicator)
        assert is_valid is False
        assert "Missing observed_at" in error
    
    def test_invalid_empty_evidence(self):
        indicator = {
            "indicator_type": "off_hours_activity",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "evidence": {}
        }
        is_valid, error = validate_indicator(indicator)
        assert is_valid is False
        assert "non-empty dictionary" in error
    
    def test_invalid_not_dict(self):
        is_valid, error = validate_indicator("not a dict")
        assert is_valid is False
        assert "must be a dictionary" in error


class TestNormalizeIndicators:
    def test_normalize_valid_indicators(self):
        raw = [
            {
                "indicator_type": "auth_fail_storm",
                "severity": "high",
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "evidence": {"failed_attempts": 500}
            },
            {
                "indicator_type": "geo_anomaly",
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "evidence": {"source_country": "XX"}
            }
        ]
        normalized = normalize_indicators(raw)
        assert len(normalized) == 2
        assert normalized[0]["severity"] == "high"
        assert normalized[1]["severity"] == "medium"
    
    def test_normalize_filters_invalid(self):
        raw = [
            {
                "indicator_type": "auth_fail_storm",
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "evidence": {"failed_attempts": 500}
            },
            {"invalid": "indicator"},
            None,
            "not a dict"
        ]
        normalized = normalize_indicators(raw)
        assert len(normalized) == 1
    
    def test_normalize_not_list_returns_empty(self):
        assert normalize_indicators("not a list") == []
        assert normalize_indicators(None) == []
        assert normalize_indicators({}) == []


class TestCalculateRiskScore:
    def test_empty_indicators_zero_score(self):
        assert calculate_risk_score([]) == 0.0
    
    def test_single_medium_indicator(self):
        indicators = [{
            "indicator_type": "unusual_access_patterns",
            "severity": "medium",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "evidence": {"data": "test"}
        }]
        score = calculate_risk_score(indicators)
        assert 0.4 <= score <= 0.5
    
    def test_single_high_indicator(self):
        indicators = [{
            "indicator_type": "permission_escalation",
            "severity": "high",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "evidence": {"data": "test"}
        }]
        score = calculate_risk_score(indicators)
        assert score >= 0.8
    
    def test_multiple_indicators_compound(self):
        indicators = [
            {
                "indicator_type": "unusual_access_patterns",
                "severity": "medium",
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "evidence": {"data": "test"}
            },
            {
                "indicator_type": "off_hours_activity",
                "severity": "medium",
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "evidence": {"data": "test"}
            }
        ]
        score = calculate_risk_score(indicators)
        assert score > 0.5
    
    def test_stale_indicators_ignored(self):
        old_time = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        indicators = [{
            "indicator_type": "auth_fail_storm",
            "severity": "high",
            "observed_at": old_time,
            "evidence": {"data": "test"}
        }]
        score = calculate_risk_score(indicators)
        assert score == 0.0


class TestDeriveOpsRiskFinding:
    def test_no_finding_below_threshold(self):
        indicators = [{
            "indicator_type": "off_hours_activity",
            "severity": "low",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "evidence": {"data": "test"}
        }]
        finding = derive_ops_risk_finding(indicators, 0.1)
        assert finding is None
    
    def test_warn_finding_medium_risk(self):
        indicators = [{
            "indicator_type": "unusual_access_patterns",
            "severity": "medium",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "evidence": {"data": "test"}
        }]
        finding = derive_ops_risk_finding(indicators, 0.45)
        assert finding is not None
        assert finding["severity"] == "warn"
        assert finding["finding_type"] == "ops_risk"
    
    def test_critical_finding_high_risk(self):
        indicators = [{
            "indicator_type": "permission_escalation",
            "severity": "high",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "evidence": {"data": "test"}
        }]
        finding = derive_ops_risk_finding(indicators, 0.85)
        assert finding is not None
        assert finding["severity"] == "critical"
    
    def test_finding_includes_evidence(self):
        indicators = [{
            "indicator_type": "auth_fail_storm",
            "severity": "high",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "evidence": {"failed_attempts": 500}
        }]
        finding = derive_ops_risk_finding(indicators, 0.8)
        assert "evidence" in finding
        assert "indicator_types" in finding["evidence"]
        assert "auth_fail_storm" in finding["evidence"]["indicator_types"]


class TestExtractAnomalyEvidence:
    def test_no_indicators_returns_empty(self):
        signals = {"other_field": "value"}
        result = extract_anomaly_evidence(signals)
        assert result["indicators"] == []
        assert result["risk_score"] == 0.0
        assert result["has_evidence"] is False
    
    def test_with_valid_indicators(self):
        signals = {
            "anomaly_indicators": [{
                "indicator_type": "data_volume_spike",
                "severity": "high",
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "evidence": {"volume_gb": 500}
            }]
        }
        result = extract_anomaly_evidence(signals)
        assert len(result["indicators"]) == 1
        assert result["risk_score"] > 0
        assert result["has_evidence"] is True
    
    def test_ignores_numeric_anomaly_score(self):
        signals = {
            "anomaly_score": 0.9,
            "anomaly_indicators": []
        }
        result = extract_anomaly_evidence(signals)
        assert result["risk_score"] == 0.0
        assert result["has_evidence"] is False


class TestIndicatorTypes:
    def test_all_indicator_types_exist(self):
        expected = {
            "unusual_access_patterns",
            "data_volume_spike", 
            "off_hours_activity",
            "auth_fail_storm",
            "latency_regression",
            "permission_escalation",
            "geo_anomaly",
            "rate_limit_breach"
        }
        assert VALID_INDICATOR_TYPES == expected
