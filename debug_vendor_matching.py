#!/usr/bin/env python3
"""
Diagnostic script to debug vendor-based domain matching.

This script traces why idp_governance_aligned is False for domains
that should have vendor-based governance via our recent fixes.

Focus: teamsuite.cloud, teamsuite.ai, corelabs.tech, teamdesk.net, probox.co
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
    evaluate_admission,
    _extract_idp_domain,
    _idp_domain_matches_entity
)
from aod.pipeline.vendor_inference import (
    infer_vendor_from_domain,
    extract_registered_domain,
    DOMAIN_TO_VENDOR
)
from aod.core.input_snapshot import InputSnapshot


def debug_vendor_matching(snapshot_path: str):
    """Debug vendor-based domain matching for problematic domains."""

    target_domains = [
        'teamsuite.cloud', 'teamsuite.ai', 'corelabs.tech',
        'teamdesk.net', 'probox.co'
    ]

    print("=" * 80)
    print("DIAGNOSTIC: Vendor-Based Domain Matching")
    print("=" * 80)

    # First, verify vendor mappings are loaded
    print("\n1. VERIFY VENDOR MAPPINGS")
    print("-" * 80)
    for domain in target_domains:
        if domain in DOMAIN_TO_VENDOR:
            print(f"✓ {domain} → {DOMAIN_TO_VENDOR[domain]}")
        else:
            print(f"✗ {domain} NOT FOUND in DOMAIN_TO_VENDOR")

    # Load snapshot
    print(f"\n2. LOAD SNAPSHOT")
    print("-" * 80)
    with open(snapshot_path, 'r') as f:
        data = json.load(f)
    snapshot = InputSnapshot.from_dict(data)
    print(f"Loaded snapshot: {snapshot.meta.snapshot_id}")

    # Normalize
    print("\n3. NORMALIZE OBSERVATIONS")
    print("-" * 80)
    entities, rejected = normalize_observations(snapshot.planes.discovery.observations)
    target_entities = [e for e in entities if e.domain in target_domains]
    print(f"Found {len(target_entities)} target entities")

    # Build indexes
    print("\n4. BUILD PLANE INDEXES")
    print("-" * 80)
    idp_index, cmdb_index, cloud_index, finance_index = build_plane_indexes(
        snapshot.planes.idp.objects,
        snapshot.planes.cmdb.ci_records,
        snapshot.planes.cloud.cloud_resources,
        snapshot.planes.finance.finance_records
    )

    # Check IdP index for target domains and their vendor siblings
    print("\n5. IDP INDEX - DOMAIN COVERAGE")
    print("-" * 80)
    for domain in target_domains:
        print(f"\n{domain}:")
        # Check exact domain
        if domain in idp_index.domain_index:
            records = idp_index.domain_index[domain]
            print(f"  ✓ Exact match: {len(records)} IdP records")
            for r in records:
                print(f"    - {r.name}")
        else:
            print(f"  ✗ No exact domain match")

        # Check vendor siblings
        if domain in DOMAIN_TO_VENDOR:
            vendor = DOMAIN_TO_VENDOR[domain]
            sibling_domains = [d for d, v in DOMAIN_TO_VENDOR.items() if v == vendor and d != domain]
            print(f"  Vendor: {vendor}")
            print(f"  Sibling domains: {sibling_domains}")
            for sibling in sibling_domains:
                if sibling in idp_index.domain_index:
                    records = idp_index.domain_index[sibling]
                    print(f"    ✓ {sibling}: {len(records)} IdP records")
                    for r in records:
                        print(f"      - {r.name}")

    # Correlate
    print("\n6. CORRELATE ENTITIES")
    print("-" * 80)
    correlations = correlate_entities_to_planes(
        entities,
        idp_index,
        cmdb_index,
        cloud_index,
        finance_index
    )

    target_corrs = [c for c in correlations if c.entity.domain in target_domains]
    print(f"Found {len(target_corrs)} target correlations")

    # CRITICAL: Trace vendor-based domain matching
    print("\n7. TRACE VENDOR-BASED DOMAIN MATCHING")
    print("=" * 80)

    for corr in target_corrs:
        entity = corr.entity
        print(f"\n{'=' * 80}")
        print(f"Entity: {entity.canonical_name}")
        print(f"Domain: {entity.domain}")
        print(f"Entity ID: {entity.entity_id}")
        print(f"{'=' * 80}")

        # Extract entity's registered domain
        entity_registered = extract_registered_domain(entity.domain)
        print(f"\n  Entity registered domain: {entity_registered}")

        # Check vendor inference for entity
        entity_vendor_result = infer_vendor_from_domain(entity.domain)
        if entity_vendor_result:
            print(f"  Entity vendor: {entity_vendor_result.value} (confidence: {entity_vendor_result.confidence})")
        else:
            print(f"  Entity vendor: None")

        # Check IdP matches
        print(f"\n  IdP Status: {corr.idp.status.value}")
        print(f"  IdP Matched Records: {len(corr.idp.matched_records)}")

        if not corr.idp.matched_records:
            print("  ⚠️  NO IdP MATCHES - Cannot have vendor-based governance")
            continue

        for i, record in enumerate(corr.idp.matched_records, 1):
            print(f"\n  --- IdP Record #{i}: {record.name} ---")

            # Extract IdP domain
            idp_domain = _extract_idp_domain(record)
            print(f"    IdP domain (raw): {idp_domain}")

            if not idp_domain:
                print(f"    ⚠️  IdP record has NO DOMAIN - _idp_domain_matches_entity will return False")
                continue

            # Extract registered domain
            idp_registered = extract_registered_domain(idp_domain)
            print(f"    IdP registered domain: {idp_registered}")

            # Check vendor inference for IdP
            idp_vendor_result = infer_vendor_from_domain(idp_domain)
            if idp_vendor_result:
                print(f"    IdP vendor: {idp_vendor_result.value} (confidence: {idp_vendor_result.confidence})")
            else:
                print(f"    IdP vendor: None")

            # Test _idp_domain_matches_entity
            print(f"\n    Testing _idp_domain_matches_entity:")
            print(f"      Input: idp_registered={idp_registered}, entity_registered={entity_registered}")

            # Step through the logic
            if not idp_registered:
                print(f"      → Result: False (IdP has no domain)")
                continue

            if not entity_registered:
                print(f"      → Result: True (entity has no domain)")
                continue

            if idp_registered == entity_registered:
                print(f"      → Result: True (exact domain match)")
                continue

            # Vendor matching logic
            print(f"      → No exact match, checking vendor-based matching...")
            print(f"      → Entity vendor result: {entity_vendor_result}")
            print(f"      → IdP vendor result: {idp_vendor_result}")

            if entity_vendor_result and idp_vendor_result:
                entity_vendor_lower = entity_vendor_result.value.lower()
                idp_vendor_lower = idp_vendor_result.value.lower()
                print(f"      → Comparing: '{entity_vendor_lower}' == '{idp_vendor_lower}'")

                if entity_vendor_lower == idp_vendor_lower:
                    print(f"      → Result: True (SAME VENDOR MATCH)")
                else:
                    print(f"      → Result: False (different vendors)")
            else:
                print(f"      → Result: False (one or both have no vendor mapping)")

            # Actually call the function
            actual_result = _idp_domain_matches_entity(idp_registered, entity_registered, record.name)
            print(f"\n    Actual function result: {actual_result}")

            # Check SSO/SCIM flags
            print(f"\n    SSO/SCIM Flags:")
            print(f"      has_sso: {record.has_sso}")
            print(f"      has_scim: {record.has_scim}")

            # Determine governance alignment
            governance_aligned = False
            if record.has_sso or record.has_scim:
                governance_aligned = True
                print(f"      → idp_governance_aligned: True (SSO/SCIM)")
            elif actual_result:
                governance_aligned = True
                print(f"      → idp_governance_aligned: True (domain/vendor match)")
            else:
                print(f"      → idp_governance_aligned: False (no match)")

        # Run actual admission
        print(f"\n  {'=' * 40}")
        print(f"  RUNNING ADMISSION EVALUATION")
        print(f"  {'=' * 40}")

        propagated = propagate_vendor_governance(correlations)
        prop_gov = propagated.get(entity.entity_id)

        admission = evaluate_admission(
            candidate=entity,
            correlation=corr,
            observations=[o for o in snapshot.planes.discovery.observations if o.observation_id in entity.observation_ids],
            propagated_gov=prop_gov,
            snapshot_id=snapshot.meta.snapshot_id,
            run_id=snapshot.meta.run_id,
            tenant_id=snapshot.meta.tenant_id
        )

        print(f"\n  Admission Result:")
        print(f"    Admitted: {admission.admitted}")
        print(f"    Provisioning status: {admission.provisioning_status}")

        if admission.asset:
            asset = admission.asset
            print(f"    Asset Classification:")
            print(f"      lens_status.idp: {asset.lens_status.idp}")
            print(f"      lens_status.cmdb: {asset.lens_status.cmdb}")
            print(f"      lens_coverage.idp: {asset.lens_coverage.idp}")
            print(f"      lens_coverage.cmdb: {asset.lens_coverage.cmdb}")
            print(f"      is_shadow: {asset.derived_classifications.is_shadow}")
            print(f"      governance_status: {asset.derived_classifications.governance_status}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_vendor_matching.py <snapshot_path>")
        sys.exit(1)

    debug_vendor_matching(sys.argv[1])
