"""
Diagnostic test for Zombie False Positives

Tests the specific FP zombies from the reconciliation report to understand
why AOD emits STALE_ACTIVITY when Farm expects RECENT_ACTIVITY.
"""
import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4

import sys
sys.path.insert(0, 'src')

from aod.models.output_contracts import (
    Asset, AssetType, LensStatus, LensStatuses,
    LensCoverage, AssetIdentifiers, ActivityEvidence, ProvisioningStatus
)
from aod.pipeline.aod_agent_reconcile import compute_asset_reasons, classify_actual
from aod.pipeline.derived_classifications import get_activity_status, ActivityStatus


class TestZombieFPDiagnostic:
    """
    Diagnose why STALE_ACTIVITY is emitted for assets Farm expects RECENT.
    
    FP Zombie examples from report:
    - flexsuite.net, flexfy.ai, smartspace.dev, proapp.app, smartspace.ai
    - workapp.tech, maxflow.com, cloudworks.dev, teamapp.ai, openflow.io, primehub.io
    
    All have: Farm RECENT_ACTIVITY, AOD STALE_ACTIVITY
    """
    
    def test_activity_status_with_snapshot_as_of(self):
        """
        Test that activity status is calculated against snapshot time, not wall-clock.
        """
        snapshot_time = datetime(2025, 10, 1, tzinfo=timezone.utc)
        
        recent_within_snapshot = datetime(2025, 9, 15, tzinfo=timezone.utc)
        stale_even_at_snapshot = datetime(2025, 6, 1, tzinfo=timezone.utc)
        
        status_recent = get_activity_status(
            recent_within_snapshot,
            activity_window_days=90,
            snapshot_as_of=snapshot_time
        )
        assert status_recent == ActivityStatus.RECENT, f"Expected RECENT, got {status_recent}"
        
        status_stale = get_activity_status(
            stale_even_at_snapshot,
            activity_window_days=90,
            snapshot_as_of=snapshot_time
        )
        assert status_stale == ActivityStatus.STALE, f"Expected STALE, got {status_stale}"
        
        status_recent_without_snapshot = get_activity_status(
            recent_within_snapshot,
            activity_window_days=90,
            snapshot_as_of=None
        )
        assert status_recent_without_snapshot == ActivityStatus.STALE, \
            "Without snapshot_as_of, old activity should be STALE relative to wall-clock now"
    
    def test_compute_asset_reasons_uses_snapshot_as_of(self):
        """
        Test that compute_asset_reasons uses snapshot_as_of correctly.
        """
        snapshot_time = datetime(2025, 10, 1, tzinfo=timezone.utc)
        activity_time = datetime(2025, 9, 15, tzinfo=timezone.utc)
        
        asset = Asset(
            asset_id=uuid4(),
            tenant_id="test",
            aod_discovery_id="test-run",
            name="Test App",
            asset_type=AssetType.SAAS,
            identifiers=AssetIdentifiers(domains=["testapp.com"]),
            lens_status=LensStatuses(
                idp=LensStatus.MATCHED,
                cmdb=LensStatus.MATCHED,
                cloud=LensStatus.UNMATCHED,
                finance=LensStatus.MATCHED
            ),
            lens_coverage=LensCoverage(idp=True, cmdb=True, cloud=False, finance=True),
            activity_evidence=ActivityEvidence(
                latest_activity_at=activity_time,
                discovery_observed_at=activity_time
            ),
            evidence_refs=["discovery:browser:obs1", "idp:app1", "cmdb:ci1"],
            tags=["identity_managed"],
            admission_reason="IdP and CMDB match"
        )
        
        reasons_with_snapshot, evidence_with = compute_asset_reasons(
            asset, activity_window_days=90, snapshot_as_of=snapshot_time
        )
        
        reasons_without_snapshot, evidence_without = compute_asset_reasons(
            asset, activity_window_days=90, snapshot_as_of=None
        )
        
        reason_values_with = [r.value for r in reasons_with_snapshot]
        reason_values_without = [r.value for r in reasons_without_snapshot]
        
        print(f"\n=== With snapshot_as_of ({snapshot_time.isoformat()}) ===")
        print(f"  activity_evidence.latest_activity_at: {activity_time.isoformat()}")
        print(f"  reasons: {reason_values_with}")
        print(f"  evidence.activity: {evidence_with.get('activity')}")
        print(f"  evidence.snapshot_as_of: {evidence_with.get('snapshot_as_of')}")
        print(f"  evidence.activity_cutoff: {evidence_with.get('activity_cutoff')}")
        
        print(f"\n=== Without snapshot_as_of (wall-clock now) ===")
        print(f"  reasons: {reason_values_without}")
        print(f"  evidence.activity: {evidence_without.get('activity')}")
        print(f"  evidence.snapshot_as_of: {evidence_without.get('snapshot_as_of')}")
        
        assert "RECENT_ACTIVITY" in reason_values_with, \
            f"With snapshot_as_of, expected RECENT_ACTIVITY, got {reason_values_with}"
        
        assert "STALE_ACTIVITY" in reason_values_without, \
            f"Without snapshot_as_of, expected STALE_ACTIVITY for old activity, got {reason_values_without}"
    
    def test_classify_actual_uses_snapshot_as_of(self):
        """
        Test that classify_actual correctly passes snapshot_as_of through.
        """
        snapshot_time = datetime(2025, 10, 1, tzinfo=timezone.utc)
        activity_time = datetime(2025, 9, 15, tzinfo=timezone.utc)
        
        asset = Asset(
            asset_id=uuid4(),
            tenant_id="test",
            aod_discovery_id="test-run",
            name="testapp.com",
            asset_type=AssetType.SAAS,
            identifiers=AssetIdentifiers(domains=["testapp.com"]),
            lens_status=LensStatuses(
                idp=LensStatus.MATCHED,
                cmdb=LensStatus.MATCHED,
                cloud=LensStatus.UNMATCHED,
                finance=LensStatus.MATCHED
            ),
            lens_coverage=LensCoverage(idp=True, cmdb=True, cloud=False, finance=True),
            activity_evidence=ActivityEvidence(
                latest_activity_at=activity_time,
                discovery_observed_at=activity_time
            ),
            evidence_refs=["discovery:browser:obs1", "idp:app1", "cmdb:ci1", "recurring_contract:cont1"],
            tags=["identity_managed"],
            admission_reason="IdP and CMDB match"
        )
        
        result_with = classify_actual(asset, activity_window_days=90, snapshot_as_of=snapshot_time)
        result_without = classify_actual(asset, activity_window_days=90, snapshot_as_of=None)
        
        reason_values_with = [r.value for r in result_with.reasons]
        reason_values_without = [r.value for r in result_without.reasons]
        
        print(f"\n=== classify_actual with snapshot_as_of ===")
        print(f"  is_zombie: {result_with.is_zombie}")
        print(f"  reasons: {reason_values_with}")
        
        print(f"\n=== classify_actual without snapshot_as_of ===")
        print(f"  is_zombie: {result_without.is_zombie}")
        print(f"  reasons: {reason_values_without}")
        
        assert result_with.is_zombie is False, \
            f"With snapshot_as_of, governed+recent should NOT be zombie, got is_zombie={result_with.is_zombie}"
        
        assert result_without.is_zombie is True, \
            f"Without snapshot_as_of, governed+stale should be zombie, got is_zombie={result_without.is_zombie}"


class TestActivityTimestampExtraction:
    """
    Test that activity timestamps are correctly extracted from evidence.
    
    The issue might be that latest_activity_at is not being set correctly
    during pipeline execution.
    """
    
    def test_activity_evidence_fields(self):
        """
        Verify ActivityEvidence correctly tracks all activity timestamps.
        """
        now = datetime.now(timezone.utc)
        
        idp_time = now - timedelta(days=10)
        discovery_time = now - timedelta(days=5)
        finance_time = now - timedelta(days=3)
        cloud_time = now - timedelta(days=7)
        
        evidence = ActivityEvidence(
            idp_last_login_at=idp_time,
            discovery_observed_at=discovery_time,
            finance_last_transaction_at=finance_time,
            cloud_last_seen_at=cloud_time,
            latest_activity_at=max(idp_time, discovery_time, finance_time, cloud_time)
        )
        
        assert evidence.latest_activity_at == finance_time, \
            f"Expected {finance_time}, got {evidence.latest_activity_at}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
