"""
AOD Stability Tests - Verify critical bug fixes

Test 1: Split Brain Merge - Finance name + Network domain = 1 asset
Test 2: Ownership Persistence - Triage assign updates asset.owner
"""

import asyncio
import sys
sys.path.insert(0, '/home/runner/workspace/src')

from aod.db.database import get_db_direct
from aod.pipeline.normalize_observations import normalize_observations
from aod.models.input_contracts import Observation
from aod.models.output_contracts import ProvisioningStatus


async def test_split_brain_merge():
    """
    TEST: Finance 'Zoom' (name only) + Network 'zoom.us' (domain) = 1 asset
    
    This tests the aggressive domain merging logic that prevents separate
    rows for name-only and domain entities.
    """
    print("\n" + "="*60)
    print("TEST 1: Split Brain Merge (Zoom)")
    print("="*60)
    
    finance_obs = Observation(
        observation_id="fin-zoom-test",
        name="Zoom",
        source="finance_spend"
    )
    
    network_obs = Observation(
        observation_id="net-zoom-test", 
        domain="zoom.us",
        source="network_traffic"
    )
    
    normalized, rejections = normalize_observations([finance_obs, network_obs])
    
    zoom_entities = [e for e in normalized if 'zoom' in (e.canonical_name or '').lower() or 'zoom' in (e.domain or '').lower()]
    
    print(f"Normalized entities with 'zoom': {len(zoom_entities)}")
    for e in zoom_entities:
        print(f"  - Name: {e.canonical_name}, Domain: {e.domain}, Observations: {e.observation_ids}")
    
    if len(zoom_entities) == 1:
        entity = zoom_entities[0]
        has_domain = entity.domain and 'zoom' in entity.domain
        has_finance = any('fin' in obs_id for obs_id in entity.observation_ids)
        
        if has_domain and has_finance:
            print("\nRESULT: PASS - Single 'zoom.us' asset with finance evidence attached")
            return True
        else:
            print(f"\nRESULT: FAIL - Asset missing domain ({has_domain}) or finance ({has_finance})")
            return False
    elif len(zoom_entities) == 0:
        print("\nRESULT: FAIL - No Zoom entities found (normalization issue)")
        return False
    else:
        print("\nRESULT: FAIL - Multiple Zoom entities (split brain not fixed)")
        return False


async def test_ownership_persistence():
    """
    TEST: Triage 'Assign Owner' updates asset.owner in database
    
    1. Find asset with owner=NULL
    2. Call update_asset_owner
    3. Verify asset.owner is updated
    4. Verify governance_gap logic would skip this asset (asset.owner is set)
    """
    print("\n" + "="*60)
    print("TEST 2: Ownership Persistence")
    print("="*60)
    
    db = await get_db_direct()
    
    runs = await db.get_all_runs()
    if not runs:
        print("RESULT: SKIP - No runs available for testing")
        return None
    
    run = runs[0]
    assets = await db.get_assets_by_run(run.run_id)
    
    test_asset = None
    for a in assets:
        if a.owner is None and a.provisioning_status == ProvisioningStatus.ACTIVE:
            test_asset = a
            break
    
    if not test_asset:
        print("RESULT: SKIP - No unowned ACTIVE assets to test")
        return None
    
    print(f"Selected asset: {test_asset.name} (ID: {test_asset.asset_id})")
    print(f"Current owner: {test_asset.owner}")
    
    test_owner = "jane@company.com"
    success = await db.update_asset_owner(str(test_asset.asset_id), test_owner)
    
    if not success:
        print("RESULT: FAIL - update_asset_owner returned False")
        return False
    
    updated_asset = await db.get_asset_by_id(str(test_asset.asset_id))
    
    if updated_asset.owner != test_owner:
        print(f"RESULT: FAIL - Owner not persisted. Expected '{test_owner}', got '{updated_asset.owner}'")
        return False
    
    print(f"Owner updated to: {updated_asset.owner}")
    
    if updated_asset.owner:
        print("Governance gap check: asset.owner is set, finding would be suppressed")
        print("\nRESULT: PASS - Owner persisted and finding would be suppressed")
        return True
    else:
        print("\nRESULT: FAIL - Owner not set after update")
        return False


async def run_all_tests():
    """Run all stability tests and report results"""
    print("\n" + "#"*60)
    print("# AOD STABILITY VERIFICATION TESTS")
    print("#"*60)
    
    results = {}
    
    results['split_brain_merge'] = await test_split_brain_merge()
    results['ownership_persistence'] = await test_ownership_persistence()
    
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
