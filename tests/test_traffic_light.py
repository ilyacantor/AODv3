"""
Test Traffic Light provisioning system for AOD Discover.

Traffic Light System:
- IGNORED: Hard rejection (invalid TLD, infrastructure domain) - dropped
- ACTIVE: Trusted (has IdP or CMDB) - flows to DCL
- REVIEW: Needs cleanup (CMDB but stale activity) - flagged for review
- QUARANTINE: Shadow IT (Cloud/Finance/Discovery but no IdP/CMDB) - blocked from DCL
"""

import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from src.aod.models.output_contracts import ProvisioningStatus
from src.aod.pipeline.admission import apply_admission_criteria, AdmissionResult
from src.aod.pipeline.correlate_entities import CorrelationResult, PlaneMatch, MatchStatus
from src.aod.pipeline.normalize_observations import CandidateEntity
from src.aod.models.input_contracts import (
    IdPObject, CMDBConfigItem, CloudResource, Observation
)


def make_entity(domain: str, name: str = None, vendor: str = None) -> CandidateEntity:
    """Create a test CandidateEntity with proper required fields."""
    entity_name = name or domain
    return CandidateEntity(
        entity_id=str(uuid4()),
        canonical_name=entity_name.lower(),
        original_name=entity_name,
        domain=domain,
        hostname=domain,
        vendor=vendor or ""
    )


def make_correlation(
    entity: CandidateEntity,
    idp_records: list = None,
    cmdb_records: list = None,
    cloud_records: list = None,
    finance_records: list = None
) -> CorrelationResult:
    """Create a test CorrelationResult with specified plane matches.
    
    Note: match_method='domain' is set for authoritative matching - this 
    ensures governance checks pass (is_authoritative=True).
    """
    return CorrelationResult(
        entity=entity,
        idp=PlaneMatch(
            status=MatchStatus.MATCHED if idp_records else MatchStatus.UNMATCHED,
            matched_records=idp_records or [],
            match_method='domain' if idp_records else None
        ),
        cmdb=PlaneMatch(
            status=MatchStatus.MATCHED if cmdb_records else MatchStatus.UNMATCHED,
            matched_records=cmdb_records or [],
            match_method='domain' if cmdb_records else None
        ),
        cloud=PlaneMatch(
            status=MatchStatus.MATCHED if cloud_records else MatchStatus.UNMATCHED,
            matched_records=cloud_records or [],
            match_method='domain' if cloud_records else None
        ),
        finance=PlaneMatch(
            status=MatchStatus.MATCHED if finance_records else MatchStatus.UNMATCHED,
            matched_records=finance_records or [],
            match_method='domain' if finance_records else None
        )
    )


def make_idp_object(name: str, has_sso: bool = True, domain: str = None) -> IdPObject:
    """Create a test IdP object.
    
    Note: domain is required for domain-aligned governance to pass.
    IdP records without a domain cannot assert governance per Jan 2026 policy.
    """
    return IdPObject(
        idp_id=str(uuid4()),
        name=name,
        idp_type="service_principal",
        has_sso=has_sso,
        has_scim=False,
        domain=domain
    )


def make_cmdb_item(name: str, ci_type: str = "application", lifecycle: str = "production") -> CMDBConfigItem:
    """Create a test CMDB config item."""
    return CMDBConfigItem(
        ci_id=str(uuid4()),
        name=name,
        ci_type=ci_type,
        lifecycle=lifecycle,
        owner="test-owner"
    )


def make_cloud_resource(name: str, resource_type: str = "ec2") -> CloudResource:
    """Create a test cloud resource."""
    return CloudResource(
        resource_id=str(uuid4()),
        name=name,
        resource_type=resource_type,
        provider="aws"
    )


def make_observation(domain: str, days_ago: int = 1, source: str = "dns") -> Observation:
    """Create a test observation with specified age and source."""
    return Observation(
        observation_id=str(uuid4()),
        name=domain,
        domain=domain,
        source=source,
        observed_at=datetime.now(timezone.utc) - timedelta(days=days_ago)
    )


def make_observations_multi_source(domain: str, days_ago: int = 1, sources: list[str] = None) -> list[Observation]:
    """
    Create multiple observations with different sources for discovery corroboration.
    
    Admission requires >= 2 distinct discovery sources for governance to admit.
    Default: dns + browser (2 sources)
    """
    sources = sources or ["dns", "browser"]
    return [
        Observation(
            observation_id=str(uuid4()),
            name=domain,
            domain=domain,
            source=source,
            observed_at=datetime.now(timezone.utc) - timedelta(days=days_ago)
        )
        for source in sources
    ]


class TestTrafficLightProvisioning:
    """Test the Traffic Light provisioning system."""
    
    def test_active_with_idp_governance(self):
        """
        TEST CASE 1: Asset with IdP governance should be ACTIVE.
        
        Scenario: Okta with IdP match (has_sso=True)
        Expected: provisioning_status = ACTIVE (flows to DCL)
        """
        entity = make_entity("okta.com", "Okta", "Okta")
        idp = make_idp_object("Okta SSO", has_sso=True, domain="okta.com")
        correlation = make_correlation(entity, idp_records=[idp])
        # Need >= 2 discovery sources for governance to admit
        observations = make_observations_multi_source("okta.com", days_ago=1)
        
        result = apply_admission_criteria(
            correlation=correlation,
            tenant_id="test-tenant",
            run_id="test-run",
            snapshot_id="test-snapshot",
            observations=observations
        )
        
        assert result.admitted is True
        assert result.provisioning_status == ProvisioningStatus.ACTIVE
        assert result.asset is not None
        assert result.asset.provisioning_status == ProvisioningStatus.ACTIVE
        assert "traffic_light:active" in result.asset.tags
    
    def test_active_with_cmdb_governance(self):
        """
        TEST CASE 2: Asset with CMDB governance should be ACTIVE.
        
        Scenario: Salesforce with CMDB match (ci_type=application, lifecycle=production)
        Expected: provisioning_status = ACTIVE (flows to DCL)
        """
        entity = make_entity("salesforce.com", "Salesforce", "Salesforce")
        cmdb = make_cmdb_item("Salesforce", ci_type="application", lifecycle="production")
        correlation = make_correlation(entity, cmdb_records=[cmdb])
        # Need >= 2 discovery sources for governance to admit
        observations = make_observations_multi_source("salesforce.com", days_ago=5)
        
        result = apply_admission_criteria(
            correlation=correlation,
            tenant_id="test-tenant",
            run_id="test-run",
            snapshot_id="test-snapshot",
            observations=observations
        )
        
        assert result.admitted is True
        assert result.provisioning_status == ProvisioningStatus.ACTIVE
        assert result.asset is not None
        assert result.asset.provisioning_status == ProvisioningStatus.ACTIVE
    
    def test_review_with_stale_cmdb(self):
        """
        TEST CASE 3: Asset with CMDB but stale activity should be REVIEW.
        
        Scenario: Jira with CMDB match but last activity >90 days ago
        Expected: provisioning_status = REVIEW (zombie candidate)
        """
        entity = make_entity("atlassian.com", "Jira", "Atlassian")
        cmdb = make_cmdb_item("Jira", ci_type="application", lifecycle="production")
        correlation = make_correlation(entity, cmdb_records=[cmdb])
        # Need >= 2 discovery sources for governance to admit (stale = 120 days ago)
        observations = make_observations_multi_source("atlassian.com", days_ago=120)
        
        result = apply_admission_criteria(
            correlation=correlation,
            tenant_id="test-tenant",
            run_id="test-run",
            snapshot_id="test-snapshot",
            observations=observations
        )
        
        assert result.admitted is True
        assert result.provisioning_status == ProvisioningStatus.REVIEW
        assert result.asset is not None
        assert result.asset.provisioning_status == ProvisioningStatus.REVIEW
        assert "traffic_light:review" in result.asset.tags
    
    def test_active_discovery_only_with_corroboration(self):
        """
        TEST CASE 4: Asset with discovery-only evidence + corroboration should be ACTIVE.
        
        Scenario: Notion with discovery sources from 2+ distinct planes but no IdP/CMDB
        Expected: provisioning_status = ACTIVE (corroborated discovery is trusted)
        
        Note: Discovery admission requires evidence from 2+ distinct planes (not sources).
        dns -> network plane, edr -> endpoint plane = 2 distinct planes
        
        Traffic Light rules: Discovery corroboration (2+ planes) = GREEN/ACTIVE
        """
        entity = make_entity("notion.so", "Notion", "Notion")
        entity.observation_ids = ["obs1", "obs2"]
        correlation = make_correlation(entity)
        observations = [
            make_observation("notion.so", days_ago=1, source="dns"),
            make_observation("notion.so", days_ago=2, source="edr")
        ]
        
        result = apply_admission_criteria(
            correlation=correlation,
            tenant_id="test-tenant",
            run_id="test-run",
            snapshot_id="test-snapshot",
            observations=observations
        )
        
        assert result.admitted is True
        assert result.provisioning_status == ProvisioningStatus.ACTIVE
        assert result.asset is not None
        assert result.asset.provisioning_status == ProvisioningStatus.ACTIVE
        assert "traffic_light:active" in result.asset.tags
    
    def test_active_cloud_with_discovery(self):
        """
        Asset with cloud evidence + discovery should be ACTIVE.
        
        Scenario: Cloud app discovered with network evidence
        Expected: provisioning_status = ACTIVE (cloud + discovery corroboration)
        
        Note: Cloud matches with any discovery evidence get ACTIVE status.
        """
        entity = make_entity("cloudapp.example.io", "Cloud App", "Cloud Provider")
        cloud = make_cloud_resource("Cloud Instance", resource_type="compute")
        correlation = make_correlation(entity, cloud_records=[cloud])
        observations = [make_observation("cloudapp.example.io", days_ago=1, source="cloud")]
        
        result = apply_admission_criteria(
            correlation=correlation,
            tenant_id="test-tenant",
            run_id="test-run",
            snapshot_id="test-snapshot",
            observations=observations
        )
        
        assert result.admitted is True
        assert result.provisioning_status == ProvisioningStatus.ACTIVE
    
    def test_blocked_infrastructure_domain(self):
        """
        BLOCKED: Infrastructure domains are policy-banned.
        
        Scenario: postgresql.org (infrastructure domain on banned list)
        Expected: admitted=False, provisioning_status = BLOCKED
        
        Note: Infrastructure domains are now in the banned list, so they get BLOCKED 
        status (policy-forbidden) rather than IGNORED.
        """
        entity = make_entity("postgresql.org", "PostgreSQL", "PostgreSQL")
        correlation = make_correlation(entity)
        observations = [make_observation("postgresql.org", days_ago=1)]
        
        result = apply_admission_criteria(
            correlation=correlation,
            tenant_id="test-tenant",
            run_id="test-run",
            snapshot_id="test-snapshot",
            observations=observations
        )
        
        assert result.admitted is False
        assert result.provisioning_status == ProvisioningStatus.BLOCKED
        assert result.rejection_reason is not None
        assert "BANNED_DOMAINS" in result.rejection_reason or "policy-forbidden" in result.rejection_reason
    
    def test_ignored_invalid_tld(self):
        """
        IGNORED: Invalid TLD (internal hostname) should be rejected.
        
        Scenario: auth-service (no valid TLD)
        Expected: admitted=False, provisioning_status = IGNORED
        """
        entity = make_entity("auth-service", "Auth Service", "")
        correlation = make_correlation(entity)
        observations = [make_observation("auth-service", days_ago=1)]
        
        result = apply_admission_criteria(
            correlation=correlation,
            tenant_id="test-tenant",
            run_id="test-run",
            snapshot_id="test-snapshot",
            observations=observations
        )
        
        assert result.admitted is False
        assert result.provisioning_status == ProvisioningStatus.IGNORED
        assert result.rejection_reason is not None
        assert "Invalid TLD" in result.rejection_reason


class TestTrafficLightPrecedence:
    """Test Traffic Light precedence rules."""
    
    def test_idp_overrides_cloud(self):
        """IdP governance should result in ACTIVE even with cloud-only corroboration."""
        entity = make_entity("slack.com", "Slack", "Slack")
        idp = make_idp_object("Slack", has_sso=True, domain="slack.com")
        cloud = make_cloud_resource("Slack Integration")
        correlation = make_correlation(entity, idp_records=[idp], cloud_records=[cloud])
        # Need >= 2 discovery sources for governance to admit
        observations = make_observations_multi_source("slack.com", days_ago=1)
        
        result = apply_admission_criteria(
            correlation=correlation,
            tenant_id="test-tenant",
            run_id="test-run",
            snapshot_id="test-snapshot",
            observations=observations
        )
        
        assert result.admitted is True
        assert result.provisioning_status == ProvisioningStatus.ACTIVE
    
    def test_idp_prevents_review_status(self):
        """IdP governance should result in ACTIVE even with stale CMDB activity."""
        entity = make_entity("workday.com", "Workday", "Workday")
        idp = make_idp_object("Workday SSO", has_sso=True, domain="workday.com")
        cmdb = make_cmdb_item("Workday", ci_type="application", lifecycle="production")
        correlation = make_correlation(entity, idp_records=[idp], cmdb_records=[cmdb])
        # Need >= 2 discovery sources for governance to admit (stale = 120 days ago)
        observations = make_observations_multi_source("workday.com", days_ago=120)
        
        result = apply_admission_criteria(
            correlation=correlation,
            tenant_id="test-tenant",
            run_id="test-run",
            snapshot_id="test-snapshot",
            observations=observations
        )
        
        assert result.admitted is True
        assert result.provisioning_status == ProvisioningStatus.ACTIVE


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
