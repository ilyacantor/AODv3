#!/usr/bin/env python3
"""
Debug script to investigate teamsuite.cloud/org classification issue.

Farm says: teamsuite.cloud has IdP governance (CLEAN)
AOD says: teamsuite.cloud is shadow IT (no IdP match)

This script traces the full pipeline to understand the mismatch.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from aod.pipeline.normalize_observations import normalize_observations
from aod.pipeline.build_plane_indexes import build_plane_indexes
from aod.pipeline.correlate_entities import correlate_entities
from aod.pipeline.vendor_governance import propagate_vendor_governance
from aod.pipeline.admission import evaluate_admission
from aod.core.input_snapshot import InputSnapshot


def analyze_snapshot(snapshot_path: str):
    """Analyze teamsuite domains in the snapshot."""
    print(f"Loading snapshot from: {snapshot_path}")

    with open(snapshot_path, 'r') as f:
        data = json.load(f)

    snapshot = InputSnapshot.from_dict(data)

    # Stage 1: Normalize observations
    print("\n" + "=" * 80)
    print("STAGE 1: Normalize Observations")
    print("=" * 80)

    entities, rejected = normalize_observations(snapshot.planes.discovery.observations)

    # Find teamsuite entities
    teamsuite_entities = [e for e in entities if 'teamsuite' in (e.domain or '').lower() or 'teamsuite' in e.canonical_name.lower()]

    print(f"\nFound {len(teamsuite_entities)} teamsuite entities:")
    for entity in teamsuite_entities:
        print(f"\n  Entity: {entity.canonical_name}")
        print(f"    entity_id: {entity.entity_id}")
        print(f"    domain: {entity.domain}")
        print(f"    vendor: {entity.vendor}")
        print(f"    vendor_hypothesis: {entity.vendor_hypothesis}")
        print(f"    observations: {len(entity.observation_ids)}")

    # Stage 2: Build plane indexes
    print("\n" + "=" * 80)
    print("STAGE 2: Build Plane Indexes")
    print("=" * 80)

    idp_index, cmdb_index, cloud_index, finance_index = build_plane_indexes(
        snapshot.planes.idp.objects,
        snapshot.planes.cmdb.ci_records,
        snapshot.planes.cloud.cloud_resources,
        snapshot.planes.finance.finance_records
    )

    # Check IdP index for teamsuite
    print("\nIdP Index - searching for teamsuite:")
    for domain, records in idp_index.domain_index.items():
        if 'teamsuite' in domain.lower():
            print(f"  Domain: {domain}")
            print(f"    Records: {[r.name for r in records]}")

    for name, records in idp_index.name_index.items():
        if 'teamsuite' in name.lower():
            print(f"  Name: {name}")
            print(f"    Records: {[r.name for r in records]}")

    # Stage 3: Correlate entities
    print("\n" + "=" * 80)
    print("STAGE 3: Correlate Entities")
    print("=" * 80)

    correlations = correlate_entities(
        entities,
        idp_index,
        cmdb_index,
        cloud_index,
        finance_index
    )

    # Find teamsuite correlations
    teamsuite_corrs = [c for c in correlations if 'teamsuite' in (c.entity.domain or '').lower() or 'teamsuite' in c.entity.canonical_name.lower()]

    print(f"\nFound {len(teamsuite_corrs)} teamsuite correlations:")
    for corr in teamsuite_corrs:
        print(f"\n  Entity: {corr.entity.canonical_name}")
        print(f"    entity_id: {corr.entity.entity_id}")
        print(f"    domain: {corr.entity.domain}")
        print(f"    IdP status: {corr.idp.status.value} (matches: {len(corr.idp.matched_records)})")
        if corr.idp.matched_records:
            for record in corr.idp.matched_records:
                print(f"      - {record.name} (domain: {getattr(record, 'domain', None)})")
        print(f"    CMDB status: {corr.cmdb.status.value} (matches: {len(corr.cmdb.matched_records)})")
        print(f"    Cloud status: {corr.cloud.status.value}")
        print(f"    Finance status: {corr.finance.status.value}")

    # Stage 4: Vendor governance
    print("\n" + "=" * 80)
    print("STAGE 4: Vendor Governance Propagation")
    print("=" * 80)

    propagated = propagate_vendor_governance(correlations)

    for corr in teamsuite_corrs:
        if corr.entity.entity_id in propagated:
            prop = propagated[corr.entity.entity_id]
            print(f"\n  Entity: {corr.entity.canonical_name}")
            print(f"    Propagated IdP: {prop.idp_present}")
            print(f"    Propagated CMDB: {prop.cmdb_present}")
            print(f"    Source: {prop.source_entity}")
            print(f"    Reason: {prop.propagation_reason}")
        else:
            print(f"\n  Entity: {corr.entity.canonical_name}")
            print(f"    ❌ No vendor governance propagated")

    # Stage 5: Admission evaluation
    print("\n" + "=" * 80)
    print("STAGE 5: Admission Evaluation")
    print("=" * 80)

    for corr in teamsuite_corrs:
        prop_gov = propagated.get(corr.entity.entity_id)

        # Get admission result
        admission = evaluate_admission(
            candidate=corr.entity,
            correlation=corr,
            observations=[o for o in snapshot.planes.discovery.observations if o.observation_id in corr.entity.observation_ids],
            propagated_gov=prop_gov,
            snapshot_id=snapshot.meta.snapshot_id,
            run_id=snapshot.meta.run_id,
            tenant_id=snapshot.meta.tenant_id
        )

        print(f"\n  Entity: {corr.entity.canonical_name}")
        print(f"    Admitted: {admission.admitted}")
        print(f"    Provisioning status: {admission.provisioning_status}")
        print(f"    Admission reason: {admission.admission_reason}")

        if admission.asset:
            asset = admission.asset
            print(f"    Classification:")
            print(f"      - lens_status.idp: {asset.lens_status.idp}")
            print(f"      - lens_status.cmdb: {asset.lens_status.cmdb}")
            print(f"      - lens_coverage.idp: {asset.lens_coverage.idp}")
            print(f"      - lens_coverage.cmdb: {asset.lens_coverage.cmdb}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_teamsuite.py <snapshot_path>")
        sys.exit(1)

    analyze_snapshot(sys.argv[1])
