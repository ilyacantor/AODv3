#!/usr/bin/env python3
"""
Minimal diagnostic to test vendor-based domain matching logic.

Tests the core _idp_domain_matches_entity function with problematic domain pairs.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from aod.pipeline.admission import _idp_domain_matches_entity
from aod.pipeline.vendor_inference import (
    infer_vendor_from_domain,
    extract_registered_domain,
    DOMAIN_TO_VENDOR
)


def test_domain_pairs():
    """Test vendor-based matching for problematic domain pairs."""

    print("=" * 80)
    print("MINIMAL DIAGNOSTIC: Vendor-Based Domain Matching")
    print("=" * 80)

    # Test cases: (entity_domain, idp_domain, expected_match, reason)
    test_cases = [
        # TeamSuite cross-domain matches
        ("teamsuite.cloud", "teamsuite.org", True, "Same vendor (TeamSuite)"),
        ("teamsuite.cloud", "teamsuite.ai", True, "Same vendor (TeamSuite)"),
        ("teamsuite.ai", "teamsuite.org", True, "Same vendor (TeamSuite)"),

        # CoreLabs cross-domain matches
        ("corelabs.tech", "corelabs.app", True, "Same vendor (CoreLabs)"),

        # TeamDesk (single domain - should match itself)
        ("teamdesk.net", "teamdesk.net", True, "Exact domain match"),

        # Negative cases
        ("teamsuite.cloud", "microsoft.com", False, "Different vendors"),
        ("corelabs.tech", "google.com", False, "Different vendors"),

        # Edge cases
        ("unmapped.com", "another.com", False, "Both unmapped"),
        ("teamsuite.cloud", "unmapped.com", False, "Entity mapped, IdP unmapped"),
    ]

    print("\n1. VERIFY VENDOR MAPPINGS")
    print("-" * 80)

    unique_domains = set()
    for entity_domain, idp_domain, _, _ in test_cases:
        unique_domains.add(entity_domain)
        unique_domains.add(idp_domain)

    for domain in sorted(unique_domains):
        if domain in DOMAIN_TO_VENDOR:
            print(f"✓ {domain:30s} → {DOMAIN_TO_VENDOR[domain]}")
        else:
            print(f"✗ {domain:30s} → (not mapped)")

    print("\n2. TEST VENDOR-BASED DOMAIN MATCHING")
    print("=" * 80)

    passed = 0
    failed = 0

    for entity_domain, idp_domain, expected_match, reason in test_cases:
        print(f"\nTest: {entity_domain} vs {idp_domain}")
        print(f"Expected: {expected_match} ({reason})")
        print("-" * 80)

        # Extract registered domains
        entity_registered = extract_registered_domain(entity_domain)
        idp_registered = extract_registered_domain(idp_domain)
        print(f"  Entity registered: {entity_registered}")
        print(f"  IdP registered:    {idp_registered}")

        # Infer vendors
        entity_vendor_result = infer_vendor_from_domain(entity_domain)
        idp_vendor_result = infer_vendor_from_domain(idp_domain)

        if entity_vendor_result:
            print(f"  Entity vendor:     {entity_vendor_result.value} (conf: {entity_vendor_result.confidence})")
        else:
            print(f"  Entity vendor:     None")

        if idp_vendor_result:
            print(f"  IdP vendor:        {idp_vendor_result.value} (conf: {idp_vendor_result.confidence})")
        else:
            print(f"  IdP vendor:        None")

        # Test the matching function
        actual_match = _idp_domain_matches_entity(idp_registered, entity_registered, f"test-{idp_domain}")

        print(f"\n  Result: {actual_match}")

        if actual_match == expected_match:
            print(f"  ✓ PASS")
            passed += 1
        else:
            print(f"  ✗ FAIL - Expected {expected_match}, got {actual_match}")
            failed += 1

    print("\n" + "=" * 80)
    print(f"SUMMARY: {passed} passed, {failed} failed")
    print("=" * 80)

    if failed > 0:
        print("\n⚠️  VENDOR-BASED MATCHING IS BROKEN")
        print("The _idp_domain_matches_entity function is not correctly matching")
        print("cross-domain entities from the same vendor.")
        return 1
    else:
        print("\n✓ All vendor-based matching tests passed")
        print("The logic is working correctly in isolation.")
        print("\nIf production still shows Shadow FPs, the issue must be:")
        print("1. IdP records have no domain field (returns None)")
        print("2. Code not deployed to production")
        print("3. Different code path being used")
        return 0


if __name__ == "__main__":
    sys.exit(test_domain_pairs())
