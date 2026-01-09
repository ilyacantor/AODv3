"""Tests for Finance Anchoring - HAS_ONGOING_FINANCE excludes from Shadow IT"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

import sys
sys.path.insert(0, 'src')

from aod.models.output_contracts import (
    Asset, AssetType, LensStatus, LensStatuses, 
    LensCoverage, AssetIdentifiers, ActivityEvidence
)
from aod.pipeline.aod_agent_reconcile import compute_asset_reasons, classify_actual


def make_asset(
    has_idp: bool = False,
    has_cmdb: bool = False,
    has_finance: bool = False,
    has_cloud: bool = False,
    activity_days_ago: int = 5,
    evidence_refs: list[str] | None = None,
    domain: str = "testapp.com"
) -> Asset:
    """Helper to create test assets with specified governance states."""
    activity_date = datetime.utcnow() - timedelta(days=activity_days_ago)
    
    return Asset(
        asset_id=uuid4(),
        tenant_id="test",
        run_id="test-run",
        name="Test App",
        asset_type=AssetType.SAAS,
        identifiers=AssetIdentifiers(domains=[domain]),
        lens_status=LensStatuses(
            idp=LensStatus.MATCHED if has_idp else LensStatus.UNMATCHED,
            cmdb=LensStatus.MATCHED if has_cmdb else LensStatus.UNMATCHED,
            cloud=LensStatus.MATCHED if has_cloud else LensStatus.UNMATCHED,
            finance=LensStatus.MATCHED if has_finance else LensStatus.UNMATCHED
        ),
        lens_coverage=LensCoverage(
            idp=has_idp,
            cmdb=has_cmdb,
            cloud=has_cloud,
            finance=has_finance
        ),
        activity_evidence=ActivityEvidence(
            latest_activity_at=activity_date,
            discovery_observed_at=activity_date,
            finance_last_transaction_at=activity_date if has_finance else None
        ),
        evidence_refs=evidence_refs or ["discovery:obs1"],
        tags=[],
        admission_reason="Test admission"
    )


class TestFinanceAnchoringReasonCodes:
    """Test that HAS_ONGOING_FINANCE/NO_ONGOING_FINANCE reason codes are correctly computed"""
    
    def test_no_finance_evidence_yields_no_ongoing_finance(self):
        """Asset with no finance evidence should have NO_ONGOING_FINANCE"""
        asset = make_asset(
            has_idp=True,
            has_finance=False,
            evidence_refs=["discovery:obs1", "idp:app1"]
        )
        
        reasons, _ = compute_asset_reasons(asset)
        reason_values = [r.value for r in reasons]
        
        assert "NO_ONGOING_FINANCE" in reason_values
        assert "HAS_ONGOING_FINANCE" not in reason_values
    
    def test_onetime_finance_yields_no_ongoing_finance(self):
        """Asset with one-time finance (no recurring_ prefix) should have NO_ONGOING_FINANCE"""
        asset = make_asset(
            has_finance=True,
            evidence_refs=["discovery:obs1", "finance:contract123"]
        )
        
        reasons, _ = compute_asset_reasons(asset)
        reason_values = [r.value for r in reasons]
        
        assert "HAS_FINANCE" in reason_values
        assert "NO_ONGOING_FINANCE" in reason_values
        assert "HAS_ONGOING_FINANCE" not in reason_values
    
    def test_recurring_contract_yields_ongoing_finance(self):
        """Asset with recurring_contract: prefix should have HAS_ONGOING_FINANCE"""
        asset = make_asset(
            has_finance=True,
            evidence_refs=["discovery:obs1", "finance:contract123", "recurring_contract:contract123"]
        )
        
        reasons, _ = compute_asset_reasons(asset)
        reason_values = [r.value for r in reasons]
        
        assert "HAS_FINANCE" in reason_values
        assert "HAS_ONGOING_FINANCE" in reason_values
        assert "NO_ONGOING_FINANCE" not in reason_values
    
    def test_recurring_transaction_yields_ongoing_finance(self):
        """Asset with recurring_transaction: prefix should have HAS_ONGOING_FINANCE"""
        asset = make_asset(
            has_finance=True,
            evidence_refs=["discovery:obs1", "finance:txn456", "recurring_transaction:txn456"]
        )
        
        reasons, _ = compute_asset_reasons(asset)
        reason_values = [r.value for r in reasons]
        
        assert "HAS_FINANCE" in reason_values
        assert "HAS_ONGOING_FINANCE" in reason_values


class TestFinanceAnchoringClassification:
    """Test shadow classification per Governance Trinity policy.
    
    Finance does NOT equal governance. Only IdP/CMDB presence determines governance.
    Shadow = ungoverned + recent activity (regardless of finance).
    """
    
    def test_ungoverned_onetime_finance_is_shadow(self):
        """Ungoverned asset with one-time finance IS shadow"""
        asset = make_asset(
            has_idp=False,
            has_cmdb=False,
            has_finance=True,
            activity_days_ago=5,
            evidence_refs=["discovery:obs1", "finance:contract123"]
        )
        
        result = classify_actual(asset)
        reason_values = [r.value for r in result.reasons]
        
        assert result.is_shadow is True
        assert "SHADOW_CLASSIFICATION" in reason_values
        assert "FINANCIAL_ANCHOR_GOVERNANCE_GAP" not in reason_values
    
    def test_ungoverned_recurring_finance_is_shadow_with_governance_gap(self):
        """Ungoverned asset with recurring finance IS shadow - finance does NOT equal governance.
        
        Per Governance Trinity (Dec 2025): Shadow IT is defined by absence of explicit
        sanctioning (IdP/CMDB). Finance presence does NOT equal governance - you can pay
        for unsanctioned tools. There is no 'Grey IT' - binary classification only.
        """
        asset = make_asset(
            has_idp=False,
            has_cmdb=False,
            has_finance=True,
            activity_days_ago=5,
            evidence_refs=["discovery:obs1", "finance:contract123", "recurring_contract:contract123"]
        )
        
        result = classify_actual(asset)
        reason_values = [r.value for r in result.reasons]
        
        # IS shadow because ungoverned (no IdP/CMDB) + RECENT activity
        assert result.is_shadow is True
        assert "SHADOW_CLASSIFICATION" in reason_values
        # Also tagged with governance gap since it has ongoing finance
        assert "FINANCIAL_ANCHOR_GOVERNANCE_GAP" in reason_values
    
    def test_governed_with_idp_is_not_shadow(self):
        """Asset with IdP is never shadow regardless of finance"""
        asset = make_asset(
            has_idp=True,
            has_finance=True,
            activity_days_ago=5,
            evidence_refs=["discovery:obs1", "idp:app1", "finance:contract123"]
        )
        
        result = classify_actual(asset)
        reason_values = [r.value for r in result.reasons]
        
        assert result.is_shadow is False
        assert "SHADOW_CLASSIFICATION" not in reason_values
    
    def test_governed_with_cmdb_is_not_shadow(self):
        """Asset with CMDB is never shadow regardless of finance"""
        asset = make_asset(
            has_cmdb=True,
            activity_days_ago=5,
            evidence_refs=["discovery:obs1", "cmdb:ci1"]
        )
        
        result = classify_actual(asset)
        
        assert result.is_shadow is False


class TestFinanceAnchoringZombie:
    """Test that governed + finance + stale = zombie; finance-only + stale = parked"""
    
    def test_governed_recurring_finance_stale_is_zombie(self):
        """Asset with CMDB + recurring finance but stale activity IS zombie
        
        Zombie = governed (IdP/CMDB) + stale + ongoing finance
        Finance alone without governance = parked (not zombie)
        """
        asset = make_asset(
            has_cmdb=True,  # Governance is required for zombie
            has_finance=True,
            activity_days_ago=120,
            evidence_refs=["discovery:obs1", "discovery:obs2", "cmdb:ci1", "finance:contract123", "recurring_contract:contract123"]
        )
        
        result = classify_actual(asset)
        reason_values = [r.value for r in result.reasons]
        
        assert result.is_zombie is True
        assert "ZOMBIE_CLASSIFICATION" in reason_values
        assert result.is_shadow is False
    
    def test_finance_only_stale_is_parked_not_zombie(self):
        """Asset with finance only but stale = parked (no governance = no zombie)
        
        Per governance trinity: zombie requires IdP or CMDB governance
        """
        asset = make_asset(
            has_finance=True,
            activity_days_ago=120,
            evidence_refs=["discovery:obs1", "finance:contract123", "recurring_contract:contract123"]
        )
        
        result = classify_actual(asset)
        reason_values = [r.value for r in result.reasons]
        
        # Without governance, stale = parked (not zombie)
        assert result.is_zombie is False
        assert result.is_parked is True
        assert "PARKED_CLASSIFICATION" in reason_values
