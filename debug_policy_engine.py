#!/usr/bin/env python3
"""Debug policy engine evaluation for googleapis.com and office.com"""

import sys
sys.path.insert(0, 'src')

import json
from aod.pipeline.validate_snapshot import validate_snapshot
from aod.pipeline.normalize_observations import normalize_observations
from aod.pipeline.build_plane_indexes import build_plane_indexes
from aod.pipeline.correlate_entities import correlate_entities_to_planes
from aod.pipeline.vendor_governance import propagate_vendor_governance
from aod.pipeline.pipeline_executor import _build_policy_asset_data
from aod.core.policy import PolicyEngine, get_current_config

def main():
    with open('tests/fixtures/real_farm_snapshot.json', 'r') as f:
        snapshot_dict = json.load(f)

    snapshot = validate_snapshot(snapshot_dict, normalize=True, fallback_tenant_id='test', snapshot_id='test')
    observations = snapshot.planes.discovery.observations

    entities, _ = normalize_observations(observations)
    indexes = build_plane_indexes(snapshot.planes)
    correlations = correlate_entities_to_planes(entities, indexes)
    propagated = propagate_vendor_governance(correlations)

    target_domains = ['googleapis.com', 'office.com']

    config = get_current_config()
    policy_engine = PolicyEngine(config)

    for entity in entities:
        if entity.domain and entity.domain.lower() in target_domains:
            print("=" * 80)
            print(f"Testing policy engine for: {entity.domain}")
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

            print(f"\nPropagated governance object:")
            if prop_gov:
                print(f"  - idp_present: {prop_gov.idp_present}")
                print(f"  - cmdb_present: {prop_gov.cmdb_present}")
                print(f"  - has_sso: {prop_gov.has_sso}")
                print(f"  - has_scim: {prop_gov.has_scim}")
                print(f"  - idp_type: {prop_gov.idp_type}")
                print(f"  - ci_type: {prop_gov.ci_type}")
                print(f"  - lifecycle: {prop_gov.lifecycle}")
                print(f"  - propagation_reason: {prop_gov.propagation_reason}")
            else:
                print("  - NO propagated governance")

            # Get entity observations
            entity_observations = [obs for obs in observations if obs.observation_id in entity.observation_ids]

            # Build policy asset data
            policy_asset_data = _build_policy_asset_data(
                entity, corr, entity_observations,
                propagated_gov=prop_gov
            )

            print(f"\nPolicy asset data:")
            print(f"  - in_idp: {policy_asset_data.get('in_idp')}")
            print(f"  - in_cmdb: {policy_asset_data.get('in_cmdb')}")
            print(f"  - in_cloud: {policy_asset_data.get('in_cloud')}")
            print(f"  - has_sso: {policy_asset_data.get('has_sso')}")
            print(f"  - has_scim: {policy_asset_data.get('has_scim')}")
            print(f"  - is_service_principal: {policy_asset_data.get('is_service_principal')}")
            print(f"  - ci_type: {policy_asset_data.get('ci_type')}")
            print(f"  - lifecycle: {policy_asset_data.get('lifecycle')}")
            print(f"  - discovery_planes_count: {policy_asset_data.get('discovery_planes_count')}")
            print(f"  - is_active: {policy_asset_data.get('is_active')}")

            # Call policy engine
            policy_decision = policy_engine.evaluate(policy_asset_data)

            print(f"\nPolicy engine decision:")
            print(f"  - admitted: {policy_decision.admitted}")
            if policy_decision.admitted:
                print(f"  - admission_reason: {policy_decision.admission_reason}")
                print(f"  - classification: {policy_decision.classification}")
            else:
                print(f"  - rejection_reason: {policy_decision.rejection_reason}")
            print(f"  - reason_codes: {policy_decision.reason_codes}")

            print()

if __name__ == '__main__':
    main()
