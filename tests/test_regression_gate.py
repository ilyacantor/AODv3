"""
Tests for the regression gate module and trace-shadow-classification endpoint.
"""

import pytest
from src.aod.pipeline.regression_gate import (
    RegressionGateResult,
    validate_reconciliation_regression,
    find_reappearing_fixed_patterns,
    count_key_normalization_mismatches,
    ReconciliationBaseline,
    KNOWN_FIXED_PATTERNS
)


class TestRegressionGateValidation:
    """Test regression gate validation logic"""
    
    def test_passing_result_no_regressions(self):
        """Gate passes when metrics improve or stay stable"""
        reconcile_result = {
            "differences": [
                {"result": "matched", "asset_key": "slack.com"},
                {"result": "matched", "asset_key": "zoom.us"},
            ]
        }
        
        result = validate_reconciliation_regression(reconcile_result, baseline=None)
        
        assert result.passed is True
        assert len(result.failures) == 0
    
    def test_fails_on_increased_mismatches(self):
        """Gate fails when key mismatches increase from baseline"""
        from datetime import datetime, timezone
        
        reconcile_result = {
            "differences": [
                {"result": "missed", "asset_key": "app.slack.com", "rca_hint": "KEY_NORMALIZATION_MISMATCH"},
                {"result": "missed", "asset_key": "zoom.us", "rca_hint": "KEY_NORMALIZATION_MISMATCH"},
                {"result": "missed", "asset_key": "notion.so", "rca_hint": "KEY_NORMALIZATION_MISMATCH"},
            ]
        }
        baseline = ReconciliationBaseline(
            snapshot_id="test",
            timestamp=datetime.now(timezone.utc),
            matched_count=50,
            missed_count=5,
            key_normalization_mismatch_count=0
        )
        
        result = validate_reconciliation_regression(reconcile_result, baseline)
        
        assert result.passed is False
        assert any("KEY_NORMALIZATION_MISMATCH" in f for f in result.failures)
    
    def test_warns_on_missed_increase(self):
        """Gate warns when missed count increases"""
        from datetime import datetime, timezone
        
        reconcile_result = {
            "differences": [
                {"result": "missed", "asset_key": "new.service.com"},
                {"result": "missed", "asset_key": "another.service.com"},
            ]
        }
        baseline = ReconciliationBaseline(
            snapshot_id="test",
            timestamp=datetime.now(timezone.utc),
            matched_count=50,
            missed_count=0,
            key_normalization_mismatch_count=0
        )
        
        result = validate_reconciliation_regression(reconcile_result, baseline)
        
        assert len(result.warnings) > 0
    
    def test_no_baseline_uses_defaults(self):
        """Gate works without baseline (first run)"""
        reconcile_result = {
            "differences": [
                {"result": "matched", "asset_key": "example.com"},
            ]
        }
        
        result = validate_reconciliation_regression(reconcile_result, baseline=None)
        
        assert result.passed is True


class TestKeyNormalizationPatterns:
    """Test detection of known-fixed normalization patterns"""
    
    def test_detects_reappearing_fixed_patterns(self):
        """Detects reappearance of previously-fixed domain patterns"""
        differences = [
            {"result": "missed", "asset_key": "app.slack.com", "rca_hint": "KEY_NORMALIZATION_MISMATCH"},
        ]
        
        issues = find_reappearing_fixed_patterns(differences)
        
        assert len(issues) > 0
    
    def test_allows_matched_fixed_patterns(self):
        """Fixed patterns that match correctly don't trigger warnings"""
        differences = [
            {"result": "matched", "asset_key": "slack.com"},
            {"result": "matched", "asset_key": "zoom.us"},
        ]
        
        issues = find_reappearing_fixed_patterns(differences)
        
        assert len(issues) == 0
    
    def test_counts_key_normalization_mismatches(self):
        """Correctly counts KEY_NORMALIZATION_MISMATCH issues"""
        differences = [
            {"result": "missed", "asset_key": "a.com", "rca_hint": "KEY_NORMALIZATION_MISMATCH"},
            {"result": "missed", "asset_key": "b.com", "rca_hint": "KEY_NORMALIZATION_MISMATCH"},
            {"result": "missed", "asset_key": "c.com", "rca_hint": "OTHER_REASON"},
            {"result": "matched", "asset_key": "d.com"},
        ]
        
        count = count_key_normalization_mismatches(differences)
        
        assert count == 2


class TestClassifyActualIntegration:
    """Test that classify_actual produces correct keys for shadow/zombie"""
    
    def test_subdomain_key_preserved(self):
        """Subdomain keys should be preserved (not collapsed to registered domain)"""
        from src.aod.pipeline.aod_agent_reconcile import classify_actual, ReasonCode
        from src.aod.models.output_contracts import (
            Asset, AssetIdentifiers, LensStatuses, LensCoverage,
            ActivityEvidence, LensStatus, AssetType
        )
        import uuid
        from datetime import datetime, timezone, timedelta
        
        recent = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        
        asset = Asset(
            asset_id=uuid.uuid4(),
            tenant_id="test-tenant",
            run_id="test-run",
            name="login498.edge.com",
            asset_type=AssetType.SAAS,
            identifiers=AssetIdentifiers(
                domains=["login498.edge.com"],
                ips=[],
                hostnames=[],
                emails=[]
            ),
            lens_status=LensStatuses(
                idp=LensStatus.UNMATCHED,
                cmdb=LensStatus.UNMATCHED,
                cloud=LensStatus.UNMATCHED,
                finance=LensStatus.UNMATCHED
            ),
            lens_coverage=LensCoverage(
                idp=False, cmdb=False, cloud=False, finance=False, discovery=True
            ),
            activity_evidence=ActivityEvidence(
                discovery_observed_at=recent,
                latest_activity_at=recent
            ),
            evidence_refs=["discovery:crowdstrike"]
        )
        
        result = classify_actual(asset, activity_window_days=90, mode="sprawl")
        
        assert result.asset_key == "login498.edge.com", f"Expected subdomain key, got {result.asset_key}"
        assert result.is_shadow is True, "Should be classified as shadow"
    
    def test_shadow_requires_discovery_and_activity(self):
        """Shadow classification requires discovery evidence and recent activity"""
        from src.aod.pipeline.aod_agent_reconcile import classify_actual, ReasonCode
        from src.aod.models.output_contracts import (
            Asset, AssetIdentifiers, LensStatuses, LensCoverage,
            ActivityEvidence, LensStatus, AssetType
        )
        import uuid
        from datetime import datetime, timezone, timedelta
        
        stale = (datetime.now(timezone.utc) - timedelta(days=180)).isoformat()
        
        asset = Asset(
            asset_id=uuid.uuid4(),
            tenant_id="test-tenant",
            run_id="test-run",
            name="stale.example.com",
            asset_type=AssetType.SAAS,
            identifiers=AssetIdentifiers(
                domains=["stale.example.com"],
                ips=[],
                hostnames=[],
                emails=[]
            ),
            lens_status=LensStatuses(
                idp=LensStatus.UNMATCHED,
                cmdb=LensStatus.UNMATCHED,
                cloud=LensStatus.UNMATCHED,
                finance=LensStatus.UNMATCHED
            ),
            lens_coverage=LensCoverage(
                idp=False, cmdb=False, cloud=False, finance=False, discovery=True
            ),
            activity_evidence=ActivityEvidence(
                discovery_observed_at=stale,
                latest_activity_at=stale
            ),
            evidence_refs=["discovery:crowdstrike"]
        )
        
        result = classify_actual(asset, activity_window_days=90, mode="sprawl")
        
        assert result.is_shadow is False, "Stale asset should not be shadow"
    
    def test_governed_asset_not_shadow(self):
        """Asset with IdP or CMDB match should not be shadow"""
        from src.aod.pipeline.aod_agent_reconcile import classify_actual, ReasonCode
        from src.aod.models.output_contracts import (
            Asset, AssetIdentifiers, LensStatuses, LensCoverage,
            ActivityEvidence, LensStatus, AssetType
        )
        import uuid
        from datetime import datetime, timezone, timedelta
        
        recent = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        
        asset = Asset(
            asset_id=uuid.uuid4(),
            tenant_id="test-tenant",
            run_id="test-run",
            name="governed.example.com",
            asset_type=AssetType.SAAS,
            identifiers=AssetIdentifiers(
                domains=["governed.example.com"],
                ips=[],
                hostnames=[],
                emails=[]
            ),
            lens_status=LensStatuses(
                idp=LensStatus.MATCHED,
                cmdb=LensStatus.UNMATCHED,
                cloud=LensStatus.UNMATCHED,
                finance=LensStatus.UNMATCHED
            ),
            lens_coverage=LensCoverage(
                idp=True, cmdb=False, cloud=False, finance=False, discovery=True
            ),
            activity_evidence=ActivityEvidence(
                discovery_observed_at=recent,
                idp_last_login_at=recent,
                latest_activity_at=recent
            ),
            evidence_refs=["discovery:crowdstrike", "idp:okta"]
        )
        
        result = classify_actual(asset, activity_window_days=90, mode="sprawl")
        
        assert result.is_shadow is False, "Governed asset should not be shadow"
        assert ReasonCode.HAS_IDP in result.reasons
