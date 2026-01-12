#!/usr/bin/env python3
"""Debug vendor governance propagation for googleapis.com and office.com"""

import sys
sys.path.insert(0, 'src')

import json
from aod.pipeline.validate_snapshot import validate_snapshot
from aod.pipeline.normalize_observations import normalize_observations
from aod.pipeline.build_plane_indexes import build_plane_indexes
from aod.pipeline.correlate_entities import correlate_entities_to_planes
from aod.pipeline.vendor_governance import propagate_vendor_governance, get_effective_vendor

def main():
    with open('tests/fixtures/real_farm_snapshot.json', 'r') as f:
        snapshot_dict = json.load(f)

    snapshot = validate_snapshot(snapshot_dict, normalize=True, fallback_tenant_id='test', snapshot_id='test')
    observations = snapshot.planes.discovery.observations

    entities, _ = normalize_observations(observations)
    indexes = build_plane_indexes(snapshot.planes)
    correlations = correlate_entities_to_planes(entities, indexes)

    target_domains = ['googleapis.com', 'office.com']

    print("=" * 80)
    print("STEP 1: Find target entities")
    print("=" * 80)

    target_entities = []
    for entity in entities:
        if entity.domain and entity.domain.lower() in target_domains:
            target_entities.append(entity)
            vendor = get_effective_vendor(entity)
            print(f"\n✓ Found entity: {entity.domain}")
            print(f"  - entity_id: {entity.entity_id}")
            print(f"  - vendor: {entity.vendor}")
            print(f"  - effective_vendor: {vendor}")

    if not target_entities:
        print("\n❌ No target entities found")
        return

    print("\n" + "=" * 80)
    print("STEP 2: Check correlations")
    print("=" * 80)

    target_correlations = []
    for entity in target_entities:
        for corr in correlations:
            if corr.entity.entity_id == entity.entity_id:
                target_correlations.append(corr)
                print(f"\n✓ Correlation for {entity.domain}:")
                print(f"  - IdP status: {corr.idp.status}")
                print(f"  - CMDB status: {corr.cmdb.status}")
                print(f"  - IdP matches: {len(corr.idp.matched_records)}")
                print(f"  - CMDB matches: {len(corr.cmdb.matched_records)}")
                break

    print("\n" + "=" * 80)
    print("STEP 3: Check for vendor siblings with governance")
    print("=" * 80)

    # Build vendor groups
    vendor_groups = {}
    for corr in correlations:
        vendor = get_effective_vendor(corr.entity)
        if vendor:
            if vendor not in vendor_groups:
                vendor_groups[vendor] = []
            vendor_groups[vendor].append(corr)

    for entity in target_entities:
        vendor = get_effective_vendor(entity)
        if not vendor:
            print(f"\n❌ {entity.domain}: No vendor")
            continue

        print(f"\n{entity.domain} vendor: {vendor}")

        if vendor not in vendor_groups:
            print(f"  ❌ No vendor group found")
            continue

        siblings = vendor_groups[vendor]
        print(f"  ✓ Found {len(siblings)} entities with vendor={vendor}")

        # Find siblings with governance
        idp_sources = []
        cmdb_sources = []

        for sibling in siblings:
            from aod.pipeline.correlate_entities import MatchStatus
            if sibling.idp.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
                idp_sources.append(sibling.entity.domain or sibling.entity.canonical_name)
            if sibling.cmdb.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
                cmdb_sources.append(sibling.entity.domain or sibling.entity.canonical_name)

        if idp_sources:
            print(f"  ✓ IdP governance available from: {idp_sources[:5]}")
        else:
            print(f"  ❌ No IdP governance in vendor group")

        if cmdb_sources:
            print(f"  ✓ CMDB governance available from: {cmdb_sources[:5]}")
        else:
            print(f"  ❌ No CMDB governance in vendor group")

    print("\n" + "=" * 80)
    print("STEP 4: Run propagate_vendor_governance()")
    print("=" * 80)

    propagated = propagate_vendor_governance(correlations)

    print(f"\nTotal propagated governance entries: {len(propagated)}")

    for entity in target_entities:
        if entity.entity_id in propagated:
            prop = propagated[entity.entity_id]
            print(f"\n✓ {entity.domain} has propagated governance:")
            print(f"  - idp_present: {prop.idp_present}")
            print(f"  - cmdb_present: {prop.cmdb_present}")
            print(f"  - propagation_reason: {prop.propagation_reason}")
        else:
            print(f"\n❌ {entity.domain}: NO propagated governance entry")

if __name__ == '__main__':
    main()
