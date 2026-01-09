"""Tests for Shadow/Zombie classification with timestamped activity signals"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

import sys
sys.path.insert(0, 'src')

from aod.models.output_contracts import (
    Asset, AssetType, Environment, LensStatus, LensStatuses, 
    LensCoverage, AssetIdentifiers, ActivityEvidence, ProvisioningStatus
)
from aod.pipeline.derived_classifications import (
    classify_shadow, classify_zombie, compute_derived_classifications
)


class TestShadowZombieTimestamps:
    """Test Shadow/Zombie classification with timestamped activity signals"""
    
    def test_zombie_managed_but_stale(self):
        """
        Zombie: Asset is in IdP (managed) but has stale activity (last_login_at old).
        
        Scenario: App exists in SSO but last login was 60 days ago.
        Expected: Classified as Zombie because activity is outside 30-day window.
        """
        stale_date = datetime.utcnow() - timedelta(days=60)
        
        asset = Asset(
            asset_id=uuid4(),
            tenant_id="test",
            run_id="test-run",
            name="Stale SSO App",
            asset_type=AssetType.SAAS,
            provisioning_status=ProvisioningStatus.REVIEW,
            lens_status=LensStatuses(
                idp=LensStatus.MATCHED,
                cmdb=LensStatus.UNMATCHED,
                cloud=LensStatus.UNMATCHED,
                finance=LensStatus.UNMATCHED
            ),
            lens_coverage=LensCoverage(
                idp=True,
                cmdb=False,
                cloud=False,
                finance=False
            ),
            activity_evidence=ActivityEvidence(
                idp_last_login_at=stale_date,
                latest_activity_at=stale_date
            ),
            evidence_refs=["idp:app1"],
            tags=["identity_managed"],
            admission_reason="IdP match with SSO enabled"
        )
        
        result = classify_zombie(asset, activity_window_days=30)
        
        assert result.is_classified is True
        assert result.is_indeterminate is False
        assert "Zombie" in result.reason
        assert "stale" in result.reason.lower()
    
    def test_shadow_paid_but_unmanaged(self):
        """
        Shadow: Asset discovered + active + ungoverned.
        
        Scenario: Discovered asset with recent activity, not in IdP or CMDB.
        Expected: Classified as Shadow IT.
        """
        recent_date = datetime.utcnow() - timedelta(days=5)
        
        asset = Asset(
            asset_id=uuid4(),
            tenant_id="test",
            run_id="test-run",
            name="Unmanaged Paid App",
            asset_type=AssetType.SAAS,
            identifiers=AssetIdentifiers(domains=["unmanagedapp.com"]),
            lens_status=LensStatuses(
                idp=LensStatus.UNMATCHED,
                cmdb=LensStatus.UNMATCHED,
                cloud=LensStatus.MATCHED,
                finance=LensStatus.MATCHED
            ),
            lens_coverage=LensCoverage(
                idp=False,
                cmdb=False,
                cloud=True,
                finance=True
            ),
            activity_evidence=ActivityEvidence(
                finance_last_transaction_at=recent_date,
                latest_activity_at=recent_date,
                discovery_observed_at=recent_date
            ),
            evidence_refs=["discovery:obs1", "finance:txn1"],
            tags=["finance_tracked"],
            admission_reason="Finance match: Recurring transaction"
        )
        
        result = classify_shadow(asset, activity_window_days=30)
        
        assert result.is_classified is True
        assert result.is_indeterminate is False
        assert "Shadow" in result.reason
    
    def test_not_zombie_when_recent_activity(self):
        """
        Not Zombie: Asset is in IdP AND has recent activity.
        
        Scenario: App exists in SSO and was used yesterday.
        Expected: Not a zombie.
        """
        recent_date = datetime.utcnow() - timedelta(days=1)
        
        asset = Asset(
            asset_id=uuid4(),
            tenant_id="test",
            run_id="test-run",
            name="Active SSO App",
            asset_type=AssetType.SAAS,
            provisioning_status=ProvisioningStatus.ACTIVE,
            lens_status=LensStatuses(
                idp=LensStatus.MATCHED,
                cmdb=LensStatus.UNMATCHED,
                cloud=LensStatus.UNMATCHED,
                finance=LensStatus.UNMATCHED
            ),
            lens_coverage=LensCoverage(
                idp=True,
                cmdb=False,
                cloud=False,
                finance=False
            ),
            activity_evidence=ActivityEvidence(
                idp_last_login_at=recent_date,
                latest_activity_at=recent_date
            ),
            evidence_refs=["idp:app1", "obs:1"],
            tags=["identity_managed"],
            admission_reason="IdP match with SSO enabled"
        )
        
        result = classify_zombie(asset, activity_window_days=30)
        
        assert result.is_classified is False
        assert result.is_indeterminate is False
        assert "active" in result.reason.lower() or "not zombie" in result.reason.lower()
    
    def test_not_shadow_when_in_idp(self):
        """
        Not Shadow: Asset is in IdP, even if has other evidence.
        
        Scenario: App exists in SSO, so it's not shadow IT.
        Expected: Not shadow.
        """
        recent_date = datetime.utcnow() - timedelta(days=5)
        
        asset = Asset(
            asset_id=uuid4(),
            tenant_id="test",
            run_id="test-run",
            name="Managed App",
            asset_type=AssetType.SAAS,
            provisioning_status=ProvisioningStatus.ACTIVE,
            lens_status=LensStatuses(
                idp=LensStatus.MATCHED,
                cmdb=LensStatus.UNMATCHED,
                cloud=LensStatus.UNMATCHED,
                finance=LensStatus.MATCHED
            ),
            lens_coverage=LensCoverage(
                idp=True,
                cmdb=False,
                cloud=False,
                finance=True
            ),
            activity_evidence=ActivityEvidence(
                finance_last_transaction_at=recent_date,
                latest_activity_at=recent_date
            ),
            evidence_refs=["idp:app1", "finance:txn1"],
            tags=["identity_managed", "finance_tracked"],
            admission_reason="IdP match; Finance match"
        )
        
        result = classify_shadow(asset, activity_window_days=30)
        
        assert result.is_classified is False
        assert "active" in result.reason.lower() or "not shadow" in result.reason.lower()
    
    def test_indeterminate_when_no_timestamps(self):
        """
        Indeterminate: Asset has no activity timestamps.
        
        Scenario: Asset exists but we have no timestamp data.
        Expected: With QUARANTINE status, classify_shadow returns classified=True (Shadow Block).
        The indeterminate logic is bypassed by Traffic Light status-based classification.
        """
        asset = Asset(
            asset_id=uuid4(),
            tenant_id="test",
            run_id="test-run",
            name="No Timestamp App",
            asset_type=AssetType.SAAS,
            provisioning_status=ProvisioningStatus.QUARANTINE,
            lens_status=LensStatuses(
                idp=LensStatus.UNMATCHED,
                cmdb=LensStatus.UNMATCHED,
                cloud=LensStatus.UNMATCHED,
                finance=LensStatus.MATCHED
            ),
            lens_coverage=LensCoverage(
                idp=False,
                cmdb=False,
                cloud=False,
                finance=True
            ),
            activity_evidence=ActivityEvidence(),
            evidence_refs=["finance:txn1"],
            tags=["finance_tracked"],
            admission_reason="Finance match"
        )
        
        result = classify_shadow(asset, activity_window_days=30)
        
        assert result.is_classified is True
        assert "Shadow" in result.reason or "quarantine" in result.reason.lower()
    
    def test_compute_derived_summary_counts(self):
        """
        Test compute_derived_classifications returns correct counts.
        
        Scenario:
        - 1 managed-but-stale asset (IdP matched, stale) → Zombie
        - 1 paid-for-but-unmanaged asset (finance, recent) → Shadow
        - 1 no-timestamp asset → Indeterminate
        
        Expected: 1 zombie, 1 shadow, 1 indeterminate
        """
        stale_date = datetime.utcnow() - timedelta(days=60)
        recent_date = datetime.utcnow() - timedelta(days=5)
        
        zombie_asset = Asset(
            asset_id=uuid4(),
            tenant_id="test",
            run_id="test-run",
            name="Zombie App",
            asset_type=AssetType.SAAS,
            identifiers=AssetIdentifiers(domains=["zombieapp.com"]),
            lens_status=LensStatuses(
                idp=LensStatus.MATCHED,
                cmdb=LensStatus.UNMATCHED,
                cloud=LensStatus.UNMATCHED,
                finance=LensStatus.MATCHED  # Zombie requires ongoing finance
            ),
            lens_coverage=LensCoverage(idp=True, cmdb=False, cloud=False, finance=True, discovery=True),
            activity_evidence=ActivityEvidence(
                idp_last_login_at=stale_date,
                latest_activity_at=stale_date
            ),
            evidence_refs=["idp:app1", "recurring_transaction:txn1"],  # Ongoing finance
            tags=["identity_managed"],
            admission_reason="IdP match with SSO enabled",
            provisioning_status=ProvisioningStatus.REVIEW,  # Zombie requires REVIEW status
            discovery_sources=["dns", "browser"]  # Single source of truth for discovery (lens_coverage.discovery must match)
        )
        
        shadow_asset = Asset(
            asset_id=uuid4(),
            tenant_id="test",
            run_id="test-run",
            name="Shadow App",
            asset_type=AssetType.SAAS,
            identifiers=AssetIdentifiers(domains=["shadowapp.com"]),
            lens_status=LensStatuses(
                idp=LensStatus.UNMATCHED,
                cmdb=LensStatus.UNMATCHED,
                cloud=LensStatus.MATCHED,
                finance=LensStatus.MATCHED
            ),
            lens_coverage=LensCoverage(idp=False, cmdb=False, cloud=True, finance=True, discovery=True),
            activity_evidence=ActivityEvidence(
                finance_last_transaction_at=recent_date,
                latest_activity_at=recent_date,
                discovery_observed_at=recent_date
            ),
            evidence_refs=["discovery:obs1", "finance:txn1"],
            tags=["finance_tracked"],
            admission_reason="Finance match: Recurring transaction",
            provisioning_status=ProvisioningStatus.QUARANTINE,  # Shadow requires QUARANTINE
            discovery_sources=["dns", "browser"]  # Single source of truth for discovery
        )
        
        indeterminate_asset = Asset(
            asset_id=uuid4(),
            tenant_id="test",
            run_id="test-run",
            name="Indeterminate App",
            asset_type=AssetType.SAAS,
            lens_status=LensStatuses(
                idp=LensStatus.UNMATCHED,
                cmdb=LensStatus.UNMATCHED,
                cloud=LensStatus.UNMATCHED,
                finance=LensStatus.MATCHED
            ),
            lens_coverage=LensCoverage(idp=False, cmdb=False, cloud=False, finance=True),
            activity_evidence=ActivityEvidence(),
            evidence_refs=["finance:txn2"],
            tags=["finance_tracked"],
            admission_reason="Finance match"
        )
        
        assets = [zombie_asset, shadow_asset, indeterminate_asset]
        summary = compute_derived_classifications(assets, activity_window_days=30)
        
        assert summary.zombie_count == 1
        assert summary.shadow_count == 1
        assert summary.indeterminate_count == 1
        
        assert len(summary.zombie_assets) == 1
        assert summary.zombie_assets[0]["name"] == "zombieapp.com"
        
        assert len(summary.shadow_assets) == 1
        assert summary.shadow_assets[0]["name"] == "shadowapp.com"
        
        assert summary.distribution.total_assets == 3
        assert summary.distribution.with_idp_match == 1
        assert summary.distribution.with_cmdb_match == 0
        assert summary.distribution.with_any_activity_timestamp == 2
        assert summary.distribution.with_activity_last_30_days == 1
    
    def test_configurable_activity_window(self):
        """
        Test that activity window is configurable.
        
        Scenario: Asset has activity 45 days ago.
        - With 30-day window: classified as Zombie (stale)
        - With 60-day window: not classified as Zombie (within window)
        """
        activity_date = datetime.utcnow() - timedelta(days=45)
        
        asset = Asset(
            asset_id=uuid4(),
            tenant_id="test",
            run_id="test-run",
            name="45-Day Old Activity App",
            asset_type=AssetType.SAAS,
            provisioning_status=ProvisioningStatus.REVIEW,
            lens_status=LensStatuses(
                idp=LensStatus.MATCHED,
                cmdb=LensStatus.UNMATCHED,
                cloud=LensStatus.UNMATCHED,
                finance=LensStatus.UNMATCHED
            ),
            lens_coverage=LensCoverage(idp=True, cmdb=False, cloud=False, finance=False),
            activity_evidence=ActivityEvidence(
                idp_last_login_at=activity_date,
                latest_activity_at=activity_date
            ),
            evidence_refs=["idp:app1"],
            tags=["identity_managed"],
            admission_reason="IdP match with SSO enabled"
        )
        
        result_30_day = classify_zombie(asset, activity_window_days=30)
        assert result_30_day.is_classified is True
        
        asset_active = Asset(
            asset_id=uuid4(),
            tenant_id="test",
            run_id="test-run",
            name="45-Day Old Activity App",
            asset_type=AssetType.SAAS,
            provisioning_status=ProvisioningStatus.ACTIVE,
            lens_status=LensStatuses(
                idp=LensStatus.MATCHED,
                cmdb=LensStatus.UNMATCHED,
                cloud=LensStatus.UNMATCHED,
                finance=LensStatus.UNMATCHED
            ),
            lens_coverage=LensCoverage(idp=True, cmdb=False, cloud=False, finance=False),
            activity_evidence=ActivityEvidence(
                idp_last_login_at=activity_date,
                latest_activity_at=activity_date
            ),
            evidence_refs=["idp:app1"],
            tags=["identity_managed"],
            admission_reason="IdP match with SSO enabled"
        )
        
        result_60_day = classify_zombie(asset_active, activity_window_days=60)
        assert result_60_day.is_classified is False


class TestZombieNoPresenceEvidence:
    """Test Zombie classification when no presence evidence exists"""
    
    def test_zombie_in_cmdb_no_evidence(self):
        """
        Zombie: Asset is in CMDB but has no activity timestamps.
        
        Scenario: CMDB says we have this app but no timestamped activity exists.
        Expected: With REVIEW status, classified as Zombie Review.
        """
        asset = Asset(
            asset_id=uuid4(),
            tenant_id="test",
            run_id="test-run",
            name="CMDB Only App",
            asset_type=AssetType.SAAS,
            provisioning_status=ProvisioningStatus.REVIEW,
            lens_status=LensStatuses(
                idp=LensStatus.UNMATCHED,
                cmdb=LensStatus.MATCHED,
                cloud=LensStatus.UNMATCHED,
                finance=LensStatus.UNMATCHED
            ),
            lens_coverage=LensCoverage(idp=False, cmdb=True, cloud=False, finance=False),
            activity_evidence=ActivityEvidence(),
            evidence_refs=[],
            tags=["cmdb_registered"],
            admission_reason="CMDB match: app in production"
        )
        
        result = classify_zombie(asset, activity_window_days=30)
        
        assert result.is_classified is True
        assert result.is_indeterminate is False
        assert "Zombie" in result.reason
    
    def test_zombie_idp_with_discovery_but_no_timestamps(self):
        """
        Zombie: Asset is in IdP with discovery observations but no timestamps.
        
        Scenario: SSO app has discovery observations but we don't know when.
        Expected: With REVIEW status, classified as Zombie Review.
        """
        asset = Asset(
            asset_id=uuid4(),
            tenant_id="test",
            run_id="test-run",
            name="IdP App No Timestamps",
            asset_type=AssetType.SAAS,
            provisioning_status=ProvisioningStatus.REVIEW,
            lens_status=LensStatuses(
                idp=LensStatus.MATCHED,
                cmdb=LensStatus.UNMATCHED,
                cloud=LensStatus.UNMATCHED,
                finance=LensStatus.UNMATCHED
            ),
            lens_coverage=LensCoverage(idp=True, cmdb=False, cloud=False, finance=False),
            activity_evidence=ActivityEvidence(),
            evidence_refs=["obs:1", "obs:2"],
            tags=["identity_managed"],
            admission_reason="IdP match with SSO enabled"
        )
        
        result = classify_zombie(asset, activity_window_days=30)
        
        assert result.is_classified is True
        assert result.is_indeterminate is False
        assert "Zombie" in result.reason


class TestDiscoverySourcesInvariant:
    """
    Regression tests for discovery_sources single-source-of-truth invariant.
    
    POLICY: discovery_sources is the canonical source for discovery presence.
    lens_coverage.discovery MUST equal bool(discovery_sources).
    This prevents split-brain where different code paths compute has_discovery differently.
    """
    
    def test_discovery_sources_matches_lens_coverage_discovery(self):
        """
        Invariant: lens_coverage.discovery == bool(discovery_sources)
        
        When discovery_sources is set, lens_coverage.discovery must be True.
        When discovery_sources is empty, lens_coverage.discovery must be False.
        """
        asset_with_discovery = Asset(
            asset_id=uuid4(),
            tenant_id="test",
            run_id="test-run",
            name="App With Discovery",
            asset_type=AssetType.SAAS,
            lens_status=LensStatuses(
                idp=LensStatus.UNMATCHED,
                cmdb=LensStatus.UNMATCHED,
                cloud=LensStatus.UNMATCHED,
                finance=LensStatus.UNMATCHED
            ),
            lens_coverage=LensCoverage(idp=False, cmdb=False, cloud=False, finance=False, discovery=True),
            activity_evidence=ActivityEvidence(),
            evidence_refs=["obs:1"],
            tags=[],
            admission_reason="Discovery",
            discovery_sources=["dns", "browser"]
        )
        
        asset_without_discovery = Asset(
            asset_id=uuid4(),
            tenant_id="test",
            run_id="test-run",
            name="App Without Discovery",
            asset_type=AssetType.SAAS,
            lens_status=LensStatuses(
                idp=LensStatus.MATCHED,
                cmdb=LensStatus.UNMATCHED,
                cloud=LensStatus.UNMATCHED,
                finance=LensStatus.UNMATCHED
            ),
            lens_coverage=LensCoverage(idp=True, cmdb=False, cloud=False, finance=False, discovery=False),
            activity_evidence=ActivityEvidence(),
            evidence_refs=["idp:1"],
            tags=[],
            admission_reason="IdP match",
            discovery_sources=[]
        )
        
        assert asset_with_discovery.lens_coverage.discovery == bool(asset_with_discovery.discovery_sources)
        assert asset_without_discovery.lens_coverage.discovery == bool(asset_without_discovery.discovery_sources)
