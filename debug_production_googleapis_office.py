#!/usr/bin/env python3
"""
Debug script to investigate why googleapis.com and office.com aren't being admitted in production.

This script traces the entire admission pipeline for these domains to identify where the breakdown occurs.
"""

import sys
sys.path.insert(0, 'src')

import json
from pathlib import Path

from aod.pipeline.validate_snapshot import validate_snapshot
from aod.pipeline.normalize_observations import normalize_observations
from aod.pipeline.build_plane_indexes import build_plane_indexes
from aod.pipeline.correlate_entities import correlate_entities_to_planes
from aod.pipeline.vendor_governance import propagate_vendor_governance
from aod.pipeline.admission import apply_admission_criteria, build_idp_activity_map
from aod.pipeline.pipeline_executor import _build_policy_asset_data
from aod.core.policy import PolicyEngine, get_current_config


def analyze_snapshot(snapshot_path: str):
    """Analyze a snapshot to understand why googleapis.com and office.com aren't admitted."""

    print(f"Loading snapshot from: {snapshot_path}")
    with open(snapshot_path, 'r') as f:
        snapshot_dict = json.load(f)

    snapshot = validate_snapshot(snapshot_dict, normalize=True, fallback_tenant_id='test', snapshot_id='test')
    observations = snapshot.planes.discovery.observations

    print(f"Total observations: {len(observations)}")
    print(f"Total IdP objects: {len(snapshot.planes.idp.objects)}")
    print(f"Total CMDB CIs: {len(snapshot.planes.cmdb.cis)}")

    # Stage 1: Normalize observations
    entities, _ = normalize_observations(observations)
    print(f"\nTotal normalized entities: {len(entities)}")

    # Stage 2: Build plane indexes
    indexes = build_plane_indexes(snapshot.planes)
    idp_activity_map = build_idp_activity_map(indexes.idp.records)

    # Stage 3: Correlate entities
    correlations = correlate_entities_to_planes(entities, indexes)
    correlation_by_entity = {c.entity.entity_id: c for c in correlations}

    # Stage 4: Vendor governance propagation
    propagated = propagate_vendor_governance(correlations)

    print(f"\nTotal vendor governance propagations: {len(propagated)}")

    # Target domains to investigate
    target_domains = ['googleapis.com', 'office.com']

    for target_domain in target_domains:
        print("\n" + "=" * 80)
        print(f"INVESTIGATING: {target_domain}")
        print("=" * 80)

        # Find entities matching this domain
        matching_entities = [e for e in entities if e.domain and target_domain.lower() in e.domain.lower()]

        if not matching_entities:
            print(f"❌ No entities found with domain containing '{target_domain}'")

            # Check if domain exists in observations
            matching_obs = [o for o in observations if o.domain and target_domain.lower() in o.domain.lower()]
            if matching_obs:
                print(f"⚠️  Found {len(matching_obs)} observations with domain, but no entities created")
                for obs in matching_obs[:3]:
                    print(f"    - obs: domain={obs.domain}, name={obs.name}, source={obs.source}")
            continue

        print(f"✅ Found {len(matching_entities)} matching entities:")

        for entity in matching_entities:
            print(f"\n--- Entity: {entity.original_name} ---")
            print(f"  entity_id: {entity.entity_id}")
            print(f"  domain: {entity.domain}")
            print(f"  vendor: {entity.vendor}")
            print(f"  observation_ids: {len(entity.observation_ids)}")

            # Get observations for this entity
            entity_obs = [o for o in observations if o.observation_id in entity.observation_ids]
            print(f"  observations: {len(entity_obs)}")
            for obs in entity_obs[:5]:
                print(f"    - source={obs.source}, observed_at={obs.observed_at}")

            # Get correlation
            corr = correlation_by_entity.get(entity.entity_id)
            if not corr:
                print("  ❌ No correlation found")
                continue

            print(f"\n  Correlation Status:")
            print(f"    - IdP: {corr.idp.status.value} (matches: {len(corr.idp.matched_records)})")
            if corr.idp.matched_records:
                for rec in corr.idp.matched_records[:3]:
                    print(f"      • {rec.name} (has_sso={getattr(rec, 'has_sso', None)}, has_scim={getattr(rec, 'has_scim', None)})")

            print(f"    - CMDB: {corr.cmdb.status.value} (matches: {len(corr.cmdb.matched_records)})")
            if corr.cmdb.matched_records:
                for rec in corr.cmdb.matched_records[:3]:
                    print(f"      • {rec.name} (ci_type={getattr(rec, 'ci_type', None)}, lifecycle={getattr(rec, 'lifecycle', None)})")

            print(f"    - Cloud: {corr.cloud.status.value} (matches: {len(corr.cloud.matched_records)})")
            print(f"    - Finance: {corr.finance.status.value} (matches: {len(corr.finance.matched_records)})")

            # Check vendor governance propagation
            prop_gov = propagated.get(entity.entity_id)
            if prop_gov:
                print(f"\n  Vendor Governance Propagated:")
                print(f"    - idp_present: {prop_gov.idp_present}")
                print(f"    - cmdb_present: {prop_gov.cmdb_present}")
                print(f"    - has_sso: {prop_gov.has_sso}")
                print(f"    - has_scim: {prop_gov.has_scim}")
                print(f"    - idp_type: {prop_gov.idp_type}")
                print(f"    - ci_type: {prop_gov.ci_type}")
                print(f"    - lifecycle: {prop_gov.lifecycle}")
                print(f"    - source_entity: {prop_gov.source_entity}")
                print(f"    - reason: {prop_gov.propagation_reason}")
            else:
                print(f"\n  ❌ No vendor governance propagated")

            # Test admission.py
            print(f"\n  Admission Evaluation:")
            admission_result = apply_admission_criteria(
                corr, 'test', 'test', 'test', entity_obs,
                propagated_idp=prop_gov.idp_present if prop_gov else False,
                propagated_cmdb=prop_gov.cmdb_present if prop_gov else False,
                propagation_reason=prop_gov.propagation_reason if prop_gov else None,
                idp_activity_map=idp_activity_map
            )

            print(f"    - admitted: {admission_result.admitted}")
            print(f"    - provisioning_status: {admission_result.provisioning_status}")
            if admission_result.admitted:
                print(f"    - admission_reason: {admission_result.admission_reason}")
                print(f"    - asset created: {admission_result.asset is not None}")
            else:
                print(f"    - rejection_reason: {admission_result.rejection_reason}")

            # Test policy engine
            print(f"\n  Policy Engine Evaluation:")
            policy_config = get_current_config()
            policy_engine = PolicyEngine(policy_config)

            policy_asset_data = _build_policy_asset_data(
                entity, corr, entity_obs,
                propagated_gov=prop_gov
            )

            print(f"    Policy asset data:")
            print(f"      - in_idp: {policy_asset_data.get('in_idp')}")
            print(f"      - in_cmdb: {policy_asset_data.get('in_cmdb')}")
            print(f"      - has_sso: {policy_asset_data.get('has_sso')}")
            print(f"      - has_scim: {policy_asset_data.get('has_scim')}")
            print(f"      - ci_type: {policy_asset_data.get('ci_type')}")
            print(f"      - lifecycle: {policy_asset_data.get('lifecycle')}")
            print(f"      - discovery_planes_count: {policy_asset_data.get('discovery_planes_count')}")
            print(f"      - is_active: {policy_asset_data.get('is_active')}")

            policy_decision = policy_engine.evaluate(policy_asset_data)

            print(f"\n    Policy decision:")
            print(f"      - admitted: {policy_decision.admitted}")
            if policy_decision.admitted:
                print(f"      - admission_reason: {policy_decision.admission_reason}")
                print(f"      - classification: {policy_decision.classification}")
            else:
                print(f"      - rejection_reason: {policy_decision.rejection_reason}")
            print(f"      - reason_codes: {policy_decision.reason_codes}")

            # Check for vendor entities that might be providing governance
            print(f"\n  Vendor Analysis:")
            if entity.vendor:
                print(f"    Entity has vendor tag: {entity.vendor}")

                # Find other entities with same vendor
                same_vendor_entities = [e for e in entities if e.vendor and e.vendor.lower() == entity.vendor.lower()]
                print(f"    Found {len(same_vendor_entities)} entities with vendor '{entity.vendor}':")

                for ve in same_vendor_entities[:5]:
                    ve_corr = correlation_by_entity.get(ve.entity_id)
                    if ve_corr:
                        has_idp = ve_corr.idp.matched_records
                        has_cmdb = ve_corr.cmdb.matched_records
                        if has_idp or has_cmdb:
                            print(f"      • {ve.original_name} (domain={ve.domain})")
                            if has_idp:
                                print(f"        - IdP: {[r.name for r in ve_corr.idp.matched_records[:2]]}")
                            if has_cmdb:
                                print(f"        - CMDB: {[r.name for r in ve_corr.cmdb.matched_records[:2]]}")
            else:
                print(f"    ❌ Entity has NO vendor tag")

                # Try to infer vendor from domain
                from aod.pipeline.vendor_governance import get_effective_vendor
                inferred_vendor = get_effective_vendor(entity)
                if inferred_vendor:
                    print(f"    ℹ️  Inferred vendor from domain: {inferred_vendor}")

                    # Find other entities with same inferred vendor
                    same_vendor_entities = []
                    for e in entities:
                        e_vendor = get_effective_vendor(e)
                        if e_vendor and e_vendor.lower() == inferred_vendor.lower():
                            same_vendor_entities.append(e)

                    print(f"    Found {len(same_vendor_entities)} entities with inferred vendor '{inferred_vendor}':")
                    for ve in same_vendor_entities[:5]:
                        ve_corr = correlation_by_entity.get(ve.entity_id)
                        if ve_corr:
                            has_idp = ve_corr.idp.matched_records
                            has_cmdb = ve_corr.cmdb.matched_records
                            if has_idp or has_cmdb:
                                print(f"      • {ve.original_name} (domain={ve.domain})")
                                if has_idp:
                                    print(f"        - IdP: {[r.name for r in ve_corr.idp.matched_records[:2]]}")
                                if has_cmdb:
                                    print(f"        - CMDB: {[r.name for r in ve_corr.cmdb.matched_records[:2]]}")
                else:
                    print(f"    ❌ Could not infer vendor from domain")


def main():
    # Check if a snapshot path was provided
    if len(sys.argv) > 1:
        snapshot_path = sys.argv[1]
    else:
        # Default to test fixture
        snapshot_path = 'tests/fixtures/real_farm_snapshot.json'

    if not Path(snapshot_path).exists():
        print(f"❌ Snapshot not found: {snapshot_path}")
        print("\nUsage: python debug_production_googleapis_office.py [snapshot_path]")
        print("Example: python debug_production_googleapis_office.py production_snapshot.json")
        sys.exit(1)

    analyze_snapshot(snapshot_path)


if __name__ == '__main__':
    main()
