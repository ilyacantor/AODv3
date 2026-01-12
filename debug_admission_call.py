#!/usr/bin/env python3
"""Debug admission call for googleapis.com and office.com"""

import sys
sys.path.insert(0, 'src')

import json
from aod.pipeline.validate_snapshot import validate_snapshot
from aod.pipeline.normalize_observations import normalize_observations
from aod.pipeline.build_plane_indexes import build_plane_indexes
from aod.pipeline.correlate_entities import correlate_entities_to_planes
from aod.pipeline.vendor_governance import propagate_vendor_governance
from aod.pipeline.admission import apply_admission_criteria, build_idp_activity_map

def main():
    with open('tests/fixtures/real_farm_snapshot.json', 'r') as f:
        snapshot_dict = json.load(f)

    snapshot = validate_snapshot(snapshot_dict, normalize=True, fallback_tenant_id='test', snapshot_id='test')
    observations = snapshot.planes.discovery.observations

    entities, _ = normalize_observations(observations)
    indexes = build_plane_indexes(snapshot.planes)
    correlations = correlate_entities_to_planes(entities, indexes)
    propagated = propagate_vendor_governance(correlations)
    idp_activity_map = build_idp_activity_map(indexes.idp.records)

    target_domains = ['googleapis.com', 'office.com']

    for entity in entities:
        if entity.domain and entity.domain.lower() in target_domains:
            print("=" * 80)
            print(f"Testing admission for: {entity.domain}")
            print("=" * 80)

            # Find correlation
            corr = None
            for c in correlations:
                if c.entity.entity_id == entity.entity_id:
                    corr = c
                    break

            if not corr:
                print(f"❌ No correlation found")
                continue

            # Get propagated governance
            prop_gov = propagated.get(entity.entity_id)
            prop_idp = prop_gov.idp_present if prop_gov else False
            prop_cmdb = prop_gov.cmdb_present if prop_gov else False
            prop_reason = prop_gov.propagation_reason if prop_gov else None

            print(f"\nPropagated governance:")
            print(f"  - prop_idp: {prop_idp}")
            print(f"  - prop_cmdb: {prop_cmdb}")
            print(f"  - prop_reason: {prop_reason}")

            # Get entity observations
            entity_observations = [obs for obs in observations if obs.observation_id in entity.observation_ids]
            print(f"\nObservations: {len(entity_observations)}")
            for obs in entity_observations:
                print(f"  - source={obs.source}, observed_at={obs.observed_at}")

            # Call admission
            admission_result = apply_admission_criteria(
                corr, 'test', 'test_run', 'test_snap', entity_observations,
                propagated_idp=prop_idp,
                propagated_cmdb=prop_cmdb,
                propagation_reason=prop_reason,
                idp_activity_map=idp_activity_map
            )

            print(f"\nAdmission result:")
            print(f"  - admitted: {admission_result.admitted}")
            print(f"  - provisioning_status: {admission_result.provisioning_status}")
            if not admission_result.admitted:
                print(f"  - rejection_reason: {admission_result.rejection_reason}")
            else:
                print(f"  - admission_reason: {admission_result.admission_reason}")

            print()

if __name__ == '__main__':
    main()
