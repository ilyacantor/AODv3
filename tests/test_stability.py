"""
AOD Stability Tests - Verify critical bug fixes

Test 1: Split Brain Merge - Finance name + Network domain = 1 asset
Test 2: Ownership Persistence - Triage assign updates asset.owner
Test 3: Status-Based Suppression - QUARANTINE assets don't get secondary findings
"""

import asyncio
import pytest
import sys
from uuid import uuid4
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aod.db.database import get_db_direct
from aod.pipeline.normalize_observations import normalize_observations, CandidateEntity
from aod.pipeline.findings.engine import generate_findings
from aod.pipeline.correlate_entities import CorrelationResult
from aod.pipeline.build_plane_indexes import PlaneIndexes
from aod.models.input_contracts import Observation
from aod.models.output_contracts import (
    ProvisioningStatus, Asset, AssetType, AssetIdentifiers,
    Environment, LensStatuses, LensCoverage, ActivityEvidence
)


@pytest.mark.asyncio
async def test_split_brain_merge():
    """
    TEST: Multiple observations for same domain merge = 1 entity
    
    This tests the aggressive domain merging logic that prevents separate
    rows for entities with the same registered domain.
    
    Note: Post-Category5 fix, observations must have domain evidence to be admitted.
    Finance-only observations without domains are rejected by normalize_observations
    (they go through the correlation phase instead).
    """
    print("\n" + "="*60)
    print("TEST 1: Split Brain Merge (Zoom)")
    print("="*60)
    
    network_obs1 = Observation(
        observation_id="net-zoom-1",
        name="Zoom Meeting",
        domain="zoom.us",
        source="network_traffic"
    )
    
    network_obs2 = Observation(
        observation_id="net-zoom-2", 
        domain="zoom.us",
        source="dns"
    )
    
    normalized, rejections = normalize_observations([network_obs1, network_obs2])
    
    zoom_entities = [e for e in normalized if 'zoom' in (e.canonical_name or '').lower() or 'zoom' in (e.domain or '').lower()]
    
    print(f"Normalized entities with 'zoom': {len(zoom_entities)}")
    for e in zoom_entities:
        print(f"  - Name: {e.canonical_name}, Domain: {e.domain}, Observations: {e.observation_ids}")
    
    if len(zoom_entities) == 1:
        entity = zoom_entities[0]
        has_domain = entity.domain and 'zoom' in entity.domain
        has_both_obs = len(entity.observation_ids) == 2
        
        if has_domain and has_both_obs:
            print("\nRESULT: PASS - Single 'zoom.us' entity with both observations merged")
            assert True
            return True
        else:
            print(f"\nRESULT: FAIL - Entity missing domain ({has_domain}) or not all observations merged ({has_both_obs})")
            assert False, f"Entity missing domain ({has_domain}) or not all observations merged ({has_both_obs})"
            return False
    elif len(zoom_entities) == 0:
        print("\nRESULT: FAIL - No Zoom entities found (normalization issue)")
        assert False, "No Zoom entities found (normalization issue)"
        return False
    else:
        print("\nRESULT: FAIL - Multiple Zoom entities (split brain not fixed)")
        assert False, "Multiple Zoom entities (split brain not fixed)"
        return False


@pytest.mark.asyncio
async def test_ownership_persistence(pg_db_with_cleanup):
    """
    TEST: Triage 'Assign Owner' updates asset.owner in database

    Seeds a pipeline run to create assets, then tests ownership update.
    """
    from aod.pipeline.pipeline_executor import execute_pipeline
    from datetime import datetime

    db, track = pg_db_with_cleanup
    run_id = f"test_ownership_{uuid4().hex[:8]}"
    track(run_id)

    # Seed: run pipeline to create assets with owner=NULL
    # Use domain-aligned IdP + CMDB data to guarantee admission
    snapshot = {
        "meta": {"tenant_id": "t1", "run_id": run_id, "generated_at": "2024-01-01T00:00:00Z"},
        "planes": {
            "discovery": {"observations": [
                {"observation_id": "o1", "name": "Salesforce", "source": "proxy", "domain": "salesforce.com"},
                {"observation_id": "o2", "name": "Slack", "source": "proxy", "domain": "slack.com"}
            ]},
            "idp": {"objects": [
                {"idp_id": "idp-1", "name": "Salesforce", "has_sso": True, "canonical_domain": "salesforce.com"},
                {"idp_id": "idp-2", "name": "Slack", "has_sso": True, "canonical_domain": "slack.com"}
            ]},
            "cmdb": {"cis": [
                {"ci_id": "ci-1", "name": "Salesforce CRM", "ci_type": "application", "lifecycle": "production", "environment": "prod", "canonical_domain": "salesforce.com"},
                {"ci_id": "ci-2", "name": "Slack", "ci_type": "application", "lifecycle": "production", "environment": "prod", "canonical_domain": "slack.com"}
            ]},
            "cloud": {"resources": []},
            "endpoint": {"devices": [], "installed_apps": []},
            "network": {"dns": [], "proxy": [], "certs": []},
            "finance": {"vendors": [], "contracts": [], "transactions": []}
        }
    }

    result = await execute_pipeline(snapshot, db, run_id=run_id, started_at=datetime.utcnow())
    assert result.success, f"Pipeline seed failed: {result.error}"

    assets = await db.get_assets_by_run(run_id)
    assert len(assets) > 0, "Pipeline should produce at least one asset"

    # Find an asset with no owner
    test_asset = next((a for a in assets if a.owner is None), None)
    assert test_asset is not None, "Should have at least one unowned asset"

    # Update ownership
    test_owner = "jane@company.com"
    success = await db.update_asset_owner(str(test_asset.asset_id), test_owner)
    assert success, "update_asset_owner should return True"

    # Verify persistence
    updated_asset = await db.get_asset_by_id(str(test_asset.asset_id))
    assert updated_asset is not None, "Asset should still exist after update"
    assert updated_asset.owner == test_owner, f"Owner should be '{test_owner}', got '{updated_asset.owner}'"


@pytest.mark.asyncio
async def test_status_based_suppression():
    """
    TEST: QUARANTINE assets only get primary triage item, NOT secondary findings

    1. Create a QUARANTINE asset with owner=NULL
    2. Run findings engine
    3. ASSERT: No governance_gap, cmdb_gap, etc. findings for this asset
    """
    test_asset_id = uuid4()
    quarantine_asset = Asset(
        asset_id=test_asset_id,
        tenant_id="test-tenant",
        aod_discovery_id="test-run",
        name="dropbox",
        asset_type=AssetType.SAAS,
        identifiers=AssetIdentifiers(
            domains=["dropbox.com"],
            emails=[],
            ip_addresses=[],
            mac_addresses=[],
            hostnames=[]
        ),
        vendor=None,
        vendor_hypothesis=None,
        environment=Environment.PROD,
        evidence_refs=["discovery-dropbox"],
        lens_status=LensStatuses(),
        lens_coverage=LensCoverage(),
        activity_evidence=ActivityEvidence(),
        tags=[],
        admission_reason="discovered_active",
        provisioning_status=ProvisioningStatus.QUARANTINE,
        has_critical_gap=False,
        owner=None
    )

    test_entity = CandidateEntity(
        entity_id="dropbox-test-entity",
        canonical_name="dropbox",
        original_name="Dropbox",
        domain="dropbox.com",
        observation_ids=["discovery-dropbox"],
        source="discovery"
    )
    test_correlation = CorrelationResult(
        entity=test_entity
    )

    empty_indexes = PlaneIndexes()

    findings = generate_findings(
        assets=[quarantine_asset],
        correlations=[test_correlation],
        indexes=empty_indexes,
        tenant_id="test-tenant",
        run_id="test-run",
        snapshot_id="test-snapshot"
    )

    asset_findings = [f for f in findings if f.asset_id == test_asset_id]

    assert len(asset_findings) == 0, (
        f"QUARANTINE asset should get 0 secondary findings, got {len(asset_findings)}: "
        f"{[f.finding_type.value for f in asset_findings]}"
    )


async def run_all_tests():
    """Run all stability tests and report results"""
    print("\n" + "#"*60)
    print("# AOD STABILITY VERIFICATION TESTS")
    print("#"*60)
    
    results = {}
    
    results['split_brain_merge'] = await test_split_brain_merge()
    results['ownership_persistence'] = await test_ownership_persistence()
    results['status_based_suppression'] = await test_status_based_suppression()
    
    print("\n" + "="*60)
    print("STABILITY TEST REPORT")
    print("="*60)
    
    for test_name, result in results.items():
        if result is True:
            status = "PASS"
        elif result is False:
            status = "FAIL"
        else:
            status = "SKIP"
        print(f"  {test_name}: {status}")
    
    print("="*60)
    
    all_passed = all(r is True or r is None for r in results.values())
    any_failed = any(r is False for r in results.values())
    
    if any_failed:
        print("\nOVERALL: FAIL - Some tests failed, fixes required")
        return False
    elif all_passed:
        print("\nOVERALL: PASS - All tests passed")
        return True
    else:
        print("\nOVERALL: PARTIAL - Some tests skipped")
        return True


if __name__ == "__main__":
    result = asyncio.run(run_all_tests())
    sys.exit(0 if result else 1)
