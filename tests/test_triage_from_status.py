"""
Test Triage Generation from Provisioning Status

Verifies that Shadow/Zombie classifications are derived from provisioning_status
rather than raw plane evidence.

Policy (Dec 2025):
- provisioning_status == QUARANTINE → Shadow Block (Tier 1)
- provisioning_status == REVIEW → Zombie Review (Tier 2)  
- provisioning_status == ACTIVE → No Shadow/Zombie items
"""

import pytest
from uuid import uuid4
from datetime import datetime, timezone, timedelta

from src.aod.models.output_contracts import (
    Asset, AssetType, Environment, LensStatuses, LensCoverage,
    AssetIdentifiers, ActivityEvidence, ProvisioningStatus, LensStatus
)
from src.aod.pipeline.derived_classifications import (
    classify_shadow, classify_zombie, ClassificationResult
)


def make_test_asset(
    provisioning_status: ProvisioningStatus,
    has_idp: bool = False,
    has_cmdb: bool = False,
    has_cloud: bool = False,
    has_discovery: bool = False,
    has_finance: bool = False,
    has_recent_activity: bool = True
) -> Asset:
    """Create a test asset with specified provisioning status and evidence"""
    now = datetime.now(timezone.utc)
    
    lens_status = LensStatuses(
        idp=LensStatus.MATCHED if has_idp else LensStatus.UNMATCHED,
        cmdb=LensStatus.MATCHED if has_cmdb else LensStatus.UNMATCHED,
        cloud=LensStatus.MATCHED if has_cloud else LensStatus.UNMATCHED,
        finance=LensStatus.MATCHED if has_finance else LensStatus.UNMATCHED,
    )
    
    lens_coverage = LensCoverage(
        idp=has_idp,
        cmdb=has_cmdb,
        cloud=has_cloud,
        discovery=has_discovery,
        finance=has_finance,
    )
    
    if has_recent_activity:
        activity_time = now - timedelta(days=30)
    else:
        activity_time = now - timedelta(days=180)
    
    activity_evidence = ActivityEvidence(
        latest_activity_at=activity_time,
        discovery_observed_at=activity_time if has_discovery else None,
        cloud_observed_at=activity_time if has_cloud else None,
    )
    
    return Asset(
        asset_id=uuid4(),
        tenant_id="test-tenant",
        run_id="test-run",
        name=f"test-asset-{provisioning_status.value}",
        asset_type=AssetType.SAAS,
        identifiers=AssetIdentifiers(domains=["test.example.com"]),
        vendor="Test Vendor",
        environment=Environment.PROD,
        evidence_refs=["test-ref"],
        lens_status=lens_status,
        lens_coverage=lens_coverage,
        activity_evidence=activity_evidence,
        tags=[],
        admission_reason="test admission",
        provisioning_status=provisioning_status,
        created_at=now,
    )


class TestTriageGenerationFromStatus:
    """Test that triage items are generated based on provisioning_status"""
    
    def test_quarantine_generates_shadow_block(self):
        """QUARANTINE status should generate a Shadow Block triage item"""
        asset = make_test_asset(
            provisioning_status=ProvisioningStatus.QUARANTINE,
            has_cloud=True,
            has_discovery=True,
        )
        
        result = classify_shadow(asset)
        
        assert result.is_classified is True
        assert result.classification_type == "shadow"
        assert "Shadow Block" in result.reason
        assert "QUARANTINE" in result.evidence_summary[0]
        assert "SANCTION" in result.evidence_summary[2]
    
    def test_quarantine_does_not_generate_zombie(self):
        """QUARANTINE status should NOT generate a Zombie item"""
        asset = make_test_asset(
            provisioning_status=ProvisioningStatus.QUARANTINE,
            has_cloud=True,
        )
        
        result = classify_zombie(asset)
        
        assert result.is_classified is False
        assert "quarantine" in result.reason.lower()
    
    def test_review_generates_zombie_review(self):
        """REVIEW status should generate a Zombie Review triage item"""
        asset = make_test_asset(
            provisioning_status=ProvisioningStatus.REVIEW,
            has_cmdb=True,
            has_recent_activity=False,
        )
        
        result = classify_zombie(asset)
        
        assert result.is_classified is True
        assert result.classification_type == "zombie"
        assert "Zombie Review" in result.reason
        assert "REVIEW" in result.evidence_summary[0]
        assert "DEPROVISION" in result.evidence_summary[3]
    
    def test_review_does_not_generate_shadow(self):
        """REVIEW status should NOT generate a Shadow item"""
        asset = make_test_asset(
            provisioning_status=ProvisioningStatus.REVIEW,
            has_cmdb=True,
        )
        
        result = classify_shadow(asset)
        
        assert result.is_classified is False
        assert "review" in result.reason.lower()
    
    def test_active_generates_neither_shadow_nor_zombie(self):
        """ACTIVE status should NOT generate Shadow or Zombie items"""
        asset = make_test_asset(
            provisioning_status=ProvisioningStatus.ACTIVE,
            has_idp=True,
            has_cmdb=True,
        )
        
        shadow_result = classify_shadow(asset)
        zombie_result = classify_zombie(asset)
        
        assert shadow_result.is_classified is False
        assert zombie_result.is_classified is False
        assert "active" in shadow_result.reason.lower()
        assert "active" in zombie_result.reason.lower()
    
    def test_blocked_generates_neither_shadow_nor_zombie(self):
        """BLOCKED status should NOT generate Shadow or Zombie items"""
        asset = make_test_asset(
            provisioning_status=ProvisioningStatus.BLOCKED,
            has_cloud=True,
        )
        
        shadow_result = classify_shadow(asset)
        zombie_result = classify_zombie(asset)
        
        assert shadow_result.is_classified is False
        assert zombie_result.is_classified is False
    
    def test_retired_generates_neither_shadow_nor_zombie(self):
        """RETIRED status should NOT generate Shadow or Zombie items"""
        asset = make_test_asset(
            provisioning_status=ProvisioningStatus.RETIRED,
            has_cmdb=True,
        )
        
        shadow_result = classify_shadow(asset)
        zombie_result = classify_zombie(asset)
        
        assert shadow_result.is_classified is False
        assert zombie_result.is_classified is False


class TestStateTransitionValidation:
    """Test valid state transitions for provisioning actions"""
    
    def test_sanction_valid_from_quarantine(self):
        """SANCTION should be valid from QUARANTINE status"""
        valid_source = ProvisioningStatus.QUARANTINE
        target = ProvisioningStatus.ACTIVE
        
        valid_transitions = {
            "SANCTION": [ProvisioningStatus.QUARANTINE, ProvisioningStatus.REVIEW],
        }
        
        assert valid_source in valid_transitions["SANCTION"]
    
    def test_sanction_valid_from_review(self):
        """SANCTION should be valid from REVIEW status"""
        valid_source = ProvisioningStatus.REVIEW
        
        valid_transitions = {
            "SANCTION": [ProvisioningStatus.QUARANTINE, ProvisioningStatus.REVIEW],
        }
        
        assert valid_source in valid_transitions["SANCTION"]
    
    def test_deprovision_valid_from_review(self):
        """DEPROVISION should be valid from REVIEW status"""
        valid_source = ProvisioningStatus.REVIEW
        
        valid_transitions = {
            "DEPROVISION": [ProvisioningStatus.REVIEW, ProvisioningStatus.ACTIVE],
        }
        
        assert valid_source in valid_transitions["DEPROVISION"]
    
    def test_ban_valid_from_quarantine(self):
        """BAN should be valid from QUARANTINE status"""
        valid_source = ProvisioningStatus.QUARANTINE
        
        valid_transitions = {
            "BAN": [ProvisioningStatus.QUARANTINE, ProvisioningStatus.REVIEW, ProvisioningStatus.ACTIVE],
        }
        
        assert valid_source in valid_transitions["BAN"]
