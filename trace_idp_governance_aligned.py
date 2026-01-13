#!/usr/bin/env python3
"""
Diagnostic: Trace idp_governance_aligned flag through full admission pipeline.

This will show us exactly why idp_governance_aligned is False for our target entities.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

# Patch the extract_activity_timestamps function to add debug logging
original_extract = None

def debug_extract_activity_timestamps(correlation, entity, observations=None, idp_activity_map=None, propagated_idp=False):
    """Wrapper that adds debug logging."""
    from aod.pipeline.admission import (
        _extract_idp_domain,
        _idp_domain_matches_entity,
        extract_registered_domain,
        MatchStatus
    )
    from aod.models.input_contracts import IdPObject

    target_domains = ['teamsuite.cloud', 'teamsuite.ai', 'corelabs.tech', 'teamdesk.net', 'probox.co']

    if entity.domain in target_domains:
        print(f"\n{'='*80}")
        print(f"DEBUG: extract_activity_timestamps for {entity.canonical_name} ({entity.domain})")
        print(f"{'='*80}")

        entity_registered_domain = extract_registered_domain(entity.domain) if entity.domain else None
        print(f"Entity registered domain: {entity_registered_domain}")

        print(f"\nIdP correlation status: {correlation.idp.status.value}")
        print(f"IdP matched records: {len(correlation.idp.matched_records)}")

        idp_governance_aligned = False

        if correlation.idp.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
            for i, record in enumerate(correlation.idp.matched_records, 1):
                if isinstance(record, IdPObject):
                    print(f"\n  IdP Record #{i}: {record.name}")
                    print(f"    has_sso: {record.has_sso}")
                    print(f"    has_scim: {record.has_scim}")

                    # Check SSO/SCIM first
                    if record.has_sso or record.has_scim:
                        print(f"    → SSO/SCIM detected, setting idp_governance_aligned=True")
                        idp_governance_aligned = True

                    # Extract IdP domain
                    idp_registered_domain = _extract_idp_domain(record)
                    print(f"    _extract_idp_domain result: {idp_registered_domain}")

                    # Check domain alignment
                    domain_aligned = _idp_domain_matches_entity(
                        idp_registered_domain, entity_registered_domain, record.name
                    )
                    print(f"    _idp_domain_matches_entity({idp_registered_domain}, {entity_registered_domain}): {domain_aligned}")

                    if domain_aligned:
                        print(f"    → Domain aligned, setting idp_governance_aligned=True")
                        idp_governance_aligned = True
                    elif not (record.has_sso or record.has_scim):
                        print(f"    → NOT domain aligned, NO SSO/SCIM, skipping activity inheritance")

        print(f"\nFINAL idp_governance_aligned: {idp_governance_aligned}")
        print(f"{'='*80}\n")

    # Call original function
    return original_extract(correlation, entity, observations, idp_activity_map, propagated_idp)


# Monkey patch
from aod.pipeline import admission
original_extract = admission.extract_activity_timestamps
admission.extract_activity_timestamps = debug_extract_activity_timestamps

# Now run the actual pipeline
from aod.models.input_contracts import Planes, Meta
from aod.pipeline.normalize_observations import normalize_observations
from aod.pipeline.build_plane_indexes import build_plane_indexes
from aod.pipeline.correlate_entities import correlate_entities_to_planes
from aod.pipeline.vendor_governance import propagate_vendor_governance
from aod.pipeline.admission import apply_admission_criteria, build_idp_activity_map


def run_diagnostic(snapshot_path: str):
    """Run full pipeline with debug instrumentation."""

    print("="*80)
    print("DIAGNOSTIC: Tracing idp_governance_aligned through admission pipeline")
    print("="*80)

    # Load snapshot
    with open(snapshot_path, 'r') as f:
        data = json.load(f)

    # Build Planes object
    planes_dict = data['planes']
    meta_dict = data['meta']

    # Convert to proper types (simplified - using dict access)
    from aod.models.input_contracts import (
        Observation, IdPObject, CMDBRecord, CloudResource,
        FinanceVendor, FinanceContract, FinanceTransaction
    )

    observations = [Observation.model_validate(o) for o in planes_dict['discovery']['observations']]
    idp_objects = [IdPObject.model_validate(i) for i in planes_dict['idp']['objects']]
    cmdb_records = [CMDBRecord.model_validate(c) for c in planes_dict['cmdb']['cis']]
    cloud_resources = [CloudResource.model_validate(r) for r in planes_dict['cloud']['resources']]

    # Finance plane
    finance_vendors = [FinanceVendor.model_validate(v) for v in planes_dict['finance']['vendors']]
    finance_contracts = [FinanceContract.model_validate(c) for c in planes_dict['finance']['contracts']]
    finance_transactions = [FinanceTransaction.model_validate(t) for t in planes_dict['finance']['transactions']]

    print(f"\nLoaded snapshot: {meta_dict['snapshot_id']}")
    print(f"Observations: {len(observations)}")
    print(f"IdP objects: {len(idp_objects)}")

    # Normalize
    print("\nNormalizing observations...")
    entities, rejected = normalize_observations(observations)
    print(f"Entities: {len(entities)}, Rejected: {len(rejected)}")

    target_domains = ['teamsuite.cloud', 'teamsuite.ai', 'corelabs.tech', 'teamdesk.net', 'probox.co']
    target_entities = [e for e in entities if e.domain in target_domains]
    print(f"Target entities: {len(target_entities)}")

    # Build indexes using Planes structure
    from aod.models.input_contracts import (
        IdPPlane, CMDBPlane, CloudPlane, FinancePlane,
        Planes, Meta as MetaModel
    )

    planes = Planes(
        discovery={'observations': observations},
        idp=IdPPlane(objects=idp_objects),
        cmdb=CMDBPlane(cis=cmdb_records),
        cloud=CloudPlane(resources=cloud_resources),
        finance=FinancePlane(
            vendors=finance_vendors,
            contracts=finance_contracts,
            transactions=finance_transactions
        ),
        endpoint={},
        network={},
        security={}
    )

    print("\nBuilding plane indexes...")
    indexes = build_plane_indexes(planes)

    # Correlate
    print("\nCorrelating entities...")
    correlations = correlate_entities_to_planes(
        entities,
        indexes.idp,
        indexes.cmdb,
        indexes.cloud,
        indexes.finance
    )

    target_corrs = [c for c in correlations if c.entity.domain in target_domains]
    print(f"Target correlations: {len(target_corrs)}")

    # Propagate vendor governance
    print("\nPropagating vendor governance...")
    propagated_gov = propagate_vendor_governance(correlations)

    # Build IdP activity map
    idp_activity_map = build_idp_activity_map({r.name: r for r in idp_objects})

    # Apply admission (this will trigger our debug wrapper)
    print("\nApplying admission criteria...\n")
    for corr in target_corrs:
        entity = corr.entity
        entity_obs = [o for o in observations if o.observation_id in entity.observation_ids]
        prop_gov = propagated_gov.get(entity.entity_id)

        result = apply_admission_criteria(
            correlation=corr,
            tenant_id=meta_dict['tenant_id'],
            run_id=meta_dict.get('run_id', 'test'),
            snapshot_id=meta_dict['snapshot_id'],
            observations=entity_obs,
            propagated_idp=prop_gov.has_idp_governance if prop_gov else False,
            propagated_cmdb=prop_gov.has_cmdb_governance if prop_gov else False,
            propagation_reason=prop_gov.reason if prop_gov else None,
            idp_activity_map=idp_activity_map
        )

        if result.asset:
            asset = result.asset
            print(f"  Asset {asset.name}:")
            print(f"    activity_evidence: {asset.activity_evidence}")
            if asset.activity_evidence:
                print(f"    idp_governance_aligned: {asset.activity_evidence.idp_governance_aligned}")
            print(f"    Admitted: {result.admitted}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python trace_idp_governance_aligned.py <snapshot_path>")
        sys.exit(1)

    run_diagnostic(sys.argv[1])
