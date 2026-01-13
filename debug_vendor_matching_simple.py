#!/usr/bin/env python3
"""
Simplified diagnostic script to debug vendor-based domain matching.

This script focuses on tracing why _idp_domain_matches_entity returns False
for domains that should match via vendor inference.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from aod.pipeline.normalize_observations import normalize_observations
from aod.pipeline.build_plane_indexes import build_plane_indexes
from aod.pipeline.correlate_entities import correlate_entities_to_planes
from aod.pipeline.admission import _extract_idp_domain, _idp_domain_matches_entity
from aod.pipeline.vendor_inference import (
    infer_vendor_from_domain,
    extract_registered_domain,
    DOMAIN_TO_VENDOR
)
from aod.core.input_snapshot import InputSnapshot
from aod.core.correlation import MatchStatus


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

    # Check for sibling domains
    print("\n2. CHECK VENDOR SIBLING DOMAINS")
    print("-" * 80)
    for domain in target_domains:
        if domain in DOMAIN_TO_VENDOR:
            vendor = DOMAIN_TO_VENDOR[domain]
            siblings = [d for d, v in DOMAIN_TO_VENDOR.items() if v == vendor]
            print(f"{domain} ({vendor}):")
            for sibling in siblings:
                print(f"  - {sibling}")

    # Load snapshot
    print(f"\n3. LOAD SNAPSHOT")
    print("-" * 80)
    with open(snapshot_path, 'r') as f:
        data = json.load(f)
    snapshot = InputSnapshot.from_dict(data)
    print(f"Loaded snapshot: {snapshot.meta.snapshot_id}")

    # Normalize
    print("\n4. NORMALIZE OBSERVATIONS")
    print("-" * 80)
    entities, rejected = normalize_observations(snapshot.planes.discovery.observations)
    target_entities = [e for e in entities if e.domain in target_domains]
    print(f"Found {len(target_entities)} target entities")
    for e in target_entities:
        print(f"  - {e.canonical_name} ({e.domain})")

    # Build indexes
    print("\n5. BUILD PLANE INDEXES")
    print("-" * 80)
    idp_index, cmdb_index, cloud_index, finance_index = build_plane_indexes(
        snapshot.planes.idp.objects,
        snapshot.planes.cmdb.ci_records,
        snapshot.planes.cloud.cloud_resources,
        snapshot.planes.finance.finance_records
    )

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
    print("\n" + "=" * 80)
    print("7. TRACE VENDOR-BASED DOMAIN MATCHING")
    print("=" * 80)

    for corr in target_corrs:
        entity = corr.entity
        print(f"\n{'=' * 80}")
        print(f"ENTITY: {entity.canonical_name}")
        print(f"Domain: {entity.domain}")
        print(f"{'=' * 80}")

        # Extract entity's registered domain
        entity_registered = extract_registered_domain(entity.domain)
        print(f"\nEntity Analysis:")
        print(f"  Raw domain: {entity.domain}")
        print(f"  Registered domain: {entity_registered}")

        # Check vendor inference for entity
        entity_vendor_result = infer_vendor_from_domain(entity.domain)
        if entity_vendor_result:
            print(f"  Vendor: {entity_vendor_result.value} (confidence: {entity_vendor_result.confidence})")
            print(f"  Basis: {entity_vendor_result.basis}")
        else:
            print(f"  Vendor: ⚠️  NONE (no vendor mapping)")

        # Check IdP matches
        print(f"\nIdP Correlation:")
        print(f"  Status: {corr.idp.status.value}")
        print(f"  Matched records: {len(corr.idp.matched_records)}")

        if not corr.idp.matched_records:
            print("  ⚠️  NO IdP MATCHES - Cannot have IdP governance")
            continue

        # Trace each IdP match
        for i, record in enumerate(corr.idp.matched_records, 1):
            print(f"\n  {'─' * 76}")
            print(f"  IdP Record #{i}: {record.name}")
            print(f"  {'─' * 76}")

            # Extract IdP domain
            idp_domain = _extract_idp_domain(record)
            print(f"    Raw domain: {idp_domain if idp_domain else '⚠️  NONE'}")

            if not idp_domain:
                print(f"    ⚠️  CRITICAL: IdP record has NO DOMAIN")
                print(f"    → _idp_domain_matches_entity will return False (no domain)")
                print(f"    → idp_governance_aligned = False (unless SSO/SCIM)")

                # Check SSO/SCIM
                print(f"\n    Checking SSO/SCIM flags:")
                print(f"      has_sso: {record.has_sso}")
                print(f"      has_scim: {record.has_scim}")
                if record.has_sso or record.has_scim:
                    print(f"      → idp_governance_aligned = True (SSO/SCIM compensates)")
                else:
                    print(f"      → idp_governance_aligned = False (no domain, no SSO/SCIM)")
                continue

            # Extract registered domain
            idp_registered = extract_registered_domain(idp_domain)
            print(f"    Registered domain: {idp_registered}")

            # Check vendor inference for IdP
            idp_vendor_result = infer_vendor_from_domain(idp_domain)
            if idp_vendor_result:
                print(f"    Vendor: {idp_vendor_result.value} (confidence: {idp_vendor_result.confidence})")
                print(f"    Basis: {idp_vendor_result.basis}")
            else:
                print(f"    Vendor: ⚠️  NONE (no vendor mapping)")

            # Test _idp_domain_matches_entity step-by-step
            print(f"\n    Tracing _idp_domain_matches_entity Logic:")
            print(f"    ──────────────────────────────────────────")

            # Step 1: Check if IdP has domain
            if not idp_registered:
                print(f"    Step 1: IdP has no registered domain → FALSE")
                actual_result = _idp_domain_matches_entity(idp_registered, entity_registered, record.name)
                print(f"\n    ✗ RESULT: {actual_result}")
                continue

            # Step 2: Check if entity has domain
            if not entity_registered:
                print(f"    Step 1: Entity has no registered domain → TRUE (allow)")
                actual_result = _idp_domain_matches_entity(idp_registered, entity_registered, record.name)
                print(f"\n    ✓ RESULT: {actual_result}")
                continue

            # Step 3: Exact domain match
            print(f"    Step 1: Check exact match")
            print(f"      '{idp_registered}' == '{entity_registered}'?")
            if idp_registered == entity_registered:
                print(f"      → TRUE (exact match)")
                actual_result = _idp_domain_matches_entity(idp_registered, entity_registered, record.name)
                print(f"\n    ✓ RESULT: {actual_result}")
                continue
            else:
                print(f"      → FALSE (different domains)")

            # Step 4: Vendor-based matching
            print(f"\n    Step 2: Check vendor-based match")
            print(f"      Entity vendor: {entity_vendor_result.value if entity_vendor_result else 'NONE'}")
            print(f"      IdP vendor: {idp_vendor_result.value if idp_vendor_result else 'NONE'}")

            if entity_vendor_result and idp_vendor_result:
                entity_vendor_lower = entity_vendor_result.value.lower()
                idp_vendor_lower = idp_vendor_result.value.lower()
                print(f"      Comparing: '{entity_vendor_lower}' == '{idp_vendor_lower}'?")

                if entity_vendor_lower == idp_vendor_lower:
                    print(f"      → TRUE (SAME VENDOR)")
                    actual_result = _idp_domain_matches_entity(idp_registered, entity_registered, record.name)
                    print(f"\n    ✓ RESULT: {actual_result}")
                else:
                    print(f"      → FALSE (different vendors)")
                    actual_result = _idp_domain_matches_entity(idp_registered, entity_registered, record.name)
                    print(f"\n    ✗ RESULT: {actual_result}")
            else:
                print(f"      → FALSE (one or both have no vendor mapping)")
                actual_result = _idp_domain_matches_entity(idp_registered, entity_registered, record.name)
                print(f"\n    ✗ RESULT: {actual_result}")

            # Check SSO/SCIM as fallback
            print(f"\n    Checking SSO/SCIM flags:")
            print(f"      has_sso: {record.has_sso}")
            print(f"      has_scim: {record.has_scim}")

            # Final governance determination
            print(f"\n    Final Governance Determination:")
            if record.has_sso or record.has_scim:
                print(f"      → idp_governance_aligned = TRUE (SSO/SCIM)")
            elif actual_result:
                print(f"      → idp_governance_aligned = TRUE (domain/vendor match)")
            else:
                print(f"      → idp_governance_aligned = FALSE ❌")
                print(f"      → Entity will be classified as SHADOW if active")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_vendor_matching_simple.py <snapshot_path>")
        sys.exit(1)

    debug_vendor_matching(sys.argv[1])
