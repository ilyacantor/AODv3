#!/usr/bin/env python3
"""
End-to-end test: Verify vendor-based governance works in full admission pipeline.

Tests the complete flow from snapshot → normalization → correlation → admission
to ensure our IdP domain inference fix actually prevents Shadow FPs.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from aod.pipeline.normalize_observations import normalize_observations
from aod.pipeline.build_plane_indexes import build_plane_indexes
from aod.pipeline.correlate_entities import correlate_entities_to_planes
from aod.pipeline.vendor_governance import propagate_vendor_governance
from aod.pipeline.admission import (
    apply_admission_criteria,
    build_idp_activity_map,
    _extract_idp_domain
)


def test_e2e_vendor_governance(snapshot_path: str):
    """Test end-to-end vendor-based governance."""

    target_domains = {
        'teamsuite.cloud': 'clean',
        'teamsuite.ai': 'clean',
        'corelabs.tech': 'clean',
        'teamdesk.net': 'clean',
        'probox.co': 'clean',
    }

    print("=" * 80)
    print("END-TO-END TEST: Vendor-Based Governance in Full Pipeline")
    print("=" * 80)

    # Load snapshot
    print("\n1. LOAD SNAPSHOT")
    print("-" * 80)
    with open(snapshot_path, 'r') as f:
        snapshot = json.load(f)

    # Convert to objects (we'll work with dicts for simplicity)
    meta = snapshot['meta']
    observations = snapshot['planes']['discovery']['observations']
    idp_objects = snapshot['planes']['idp']['objects']
    cmdb_records = snapshot['planes']['cmdb']['cis']
    cloud_resources = snapshot['planes']['cloud']['resources']
    finance_records = snapshot['planes']['finance']['records']

    print(f"Snapshot: {meta['snapshot_id']}")
    print(f"Tenant: {meta['tenant_id']}")
    print(f"Observations: {len(observations)}")
    print(f"IdP Objects: {len(idp_objects)}")

    # Check IdP records for target vendors
    print("\n2. VERIFY IDP RECORDS")
    print("-" * 80)
    target_idp_records = []
    for record in idp_objects:
        name = record.get('name', '').lower()
        if any(vendor in name for vendor in ['teamsuite', 'corelabs', 'teamdesk', 'probox']):
            target_idp_records.append(record)
            print(f"Found IdP: {record['name']}")
            print(f"  Domain field: {record.get('domain', 'NONE')}")
            print(f"  Has SSO: {record.get('has_sso', False)}")
            print(f"  Has SCIM: {record.get('has_scim', False)}")

    # Import the models properly
    from aod.models.input_contracts import (
        Observation, IdPObject, CMDBRecord, CloudResource, FinanceRecord
    )

    # Convert to proper objects
    print("\n3. NORMALIZE & BUILD INDEXES")
    print("-" * 80)
    obs_objects = [Observation.from_dict(o) for o in observations]
    idp_obs = [IdPObject.from_dict(i) for i in idp_objects]
    cmdb_obs = [CMDBRecord.from_dict(c) for c in cmdb_records]
    cloud_obs = [CloudResource.from_dict(r) for r in cloud_resources]
    finance_obs = [FinanceRecord.from_dict(f) for f in finance_records]

    entities, rejected = normalize_observations(obs_objects)
    print(f"Normalized: {len(entities)} entities, {len(rejected)} rejected")

    target_entities = [e for e in entities if e.domain in target_domains]
    print(f"Target entities: {len(target_entities)}")
    for e in target_entities:
        print(f"  - {e.canonical_name} ({e.domain})")

    # Build indexes
    idp_index, cmdb_index, cloud_index, finance_index = build_plane_indexes(
        idp_obs, cmdb_obs, cloud_obs, finance_obs
    )

    # Build IdP activity map
    idp_activity_map = build_idp_activity_map({r.name: r for r in idp_obs})

    print("\n4. CORRELATE ENTITIES")
    print("-" * 80)
    correlations = correlate_entities_to_planes(
        entities, idp_index, cmdb_index, cloud_index, finance_index
    )

    target_corrs = [c for c in correlations if c.entity.domain in target_domains]
    print(f"Target correlations: {len(target_corrs)}")

    # Propagate vendor governance
    print("\n5. PROPAGATE VENDOR GOVERNANCE")
    print("-" * 80)
    propagated_gov = propagate_vendor_governance(correlations)

    print("\n6. APPLY ADMISSION & CHECK CLASSIFICATIONS")
    print("=" * 80)

    results = []
    for corr in target_corrs:
        entity = corr.entity
        print(f"\n{'=' * 80}")
        print(f"Entity: {entity.canonical_name} ({entity.domain})")
        print(f"{'=' * 80}")

        # Check IdP correlation details
        print(f"\nIdP Correlation:")
        print(f"  Status: {corr.idp.status.value}")
        print(f"  Matched: {len(corr.idp.matched_records)}")

        if corr.idp.matched_records:
            for i, record in enumerate(corr.idp.matched_records, 1):
                print(f"\n  IdP Record #{i}: {record.name}")
                # Test domain extraction
                extracted_domain = _extract_idp_domain(record)
                print(f"    Extracted domain: {extracted_domain}")
                print(f"    Has SSO: {record.has_sso}")
                print(f"    Has SCIM: {record.has_scim}")

        # Get propagated governance
        prop_gov = propagated_gov.get(entity.entity_id)
        if prop_gov:
            print(f"\n  Propagated Governance:")
            print(f"    IdP: {prop_gov.has_idp_governance}")
            print(f"    CMDB: {prop_gov.has_cmdb_governance}")

        # Get observations for this entity
        entity_obs = [o for o in obs_objects if o.observation_id in entity.observation_ids]

        # Apply admission
        admission_result = apply_admission_criteria(
            correlation=corr,
            tenant_id=meta['tenant_id'],
            run_id=meta.get('run_id', 'test'),
            snapshot_id=meta['snapshot_id'],
            observations=entity_obs,
            propagated_idp=prop_gov.has_idp_governance if prop_gov else False,
            propagated_cmdb=prop_gov.has_cmdb_governance if prop_gov else False,
            propagation_reason=prop_gov.reason if prop_gov else None,
            idp_activity_map=idp_activity_map
        )

        print(f"\nAdmission Result:")
        print(f"  Admitted: {admission_result.admitted}")
        print(f"  Provisioning: {admission_result.provisioning_status}")

        if admission_result.asset:
            asset = admission_result.asset
            print(f"\n  Asset Classification:")
            print(f"    Governance status: {asset.derived_classifications.governance_status}")
            print(f"    Is shadow: {asset.derived_classifications.is_shadow}")
            print(f"    Is zombie: {asset.derived_classifications.is_zombie}")
            print(f"    IdP lens: {asset.lens_status.idp}")
            print(f"    CMDB lens: {asset.lens_status.cmdb}")

            expected_classification = target_domains[entity.domain]
            actual_is_shadow = asset.derived_classifications.is_shadow
            actual_is_zombie = asset.derived_classifications.is_zombie

            if expected_classification == 'clean':
                if actual_is_shadow:
                    print(f"\n  ✗ FAIL: Expected CLEAN, got SHADOW")
                    results.append(('FAIL', entity.domain, 'Expected clean, got shadow'))
                elif actual_is_zombie:
                    print(f"\n  ✗ FAIL: Expected CLEAN, got ZOMBIE")
                    results.append(('FAIL', entity.domain, 'Expected clean, got zombie'))
                else:
                    print(f"\n  ✓ PASS: Correctly classified as CLEAN")
                    results.append(('PASS', entity.domain, 'Correctly clean'))
            elif expected_classification == 'shadow':
                if actual_is_shadow:
                    print(f"\n  ✓ PASS: Correctly classified as SHADOW")
                    results.append(('PASS', entity.domain, 'Correctly shadow'))
                else:
                    print(f"\n  ✗ FAIL: Expected SHADOW, got CLEAN/ZOMBIE")
                    results.append(('FAIL', entity.domain, 'Expected shadow, got clean/zombie'))
        else:
            print(f"\n  ⚠️  NOT ADMITTED")
            results.append(('FAIL', entity.domain, 'Not admitted'))

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    passed = sum(1 for r in results if r[0] == 'PASS')
    failed = sum(1 for r in results if r[0] == 'FAIL')

    for status, domain, reason in results:
        symbol = '✓' if status == 'PASS' else '✗'
        print(f"{symbol} {domain:25s} - {reason}")

    print("\n" + "=" * 80)
    print(f"TOTAL: {passed} passed, {failed} failed")
    print("=" * 80)

    if failed > 0:
        print("\n⚠️  VENDOR-BASED GOVERNANCE NOT WORKING IN FULL PIPELINE")
        print("\nOur IdP domain inference fix is NOT preventing Shadow FPs.")
        print("The issue is likely in how idp_governance_aligned is determined")
        print("in extract_activity_timestamps() within admission.py")
        return 1
    else:
        print("\n✓ All tests passed!")
        print("\nVendor-based governance is working correctly in the full pipeline.")
        print("If production still shows Shadow FPs, the code hasn't been deployed yet.")
        return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_e2e_vendor_governance.py <snapshot_path>")
        sys.exit(1)

    sys.exit(test_e2e_vendor_governance(sys.argv[1]))
