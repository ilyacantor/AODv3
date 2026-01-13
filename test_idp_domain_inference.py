#!/usr/bin/env python3
"""
Test the enhanced _extract_idp_domain function with name-based domain inference.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from dataclasses import dataclass
from typing import Optional
from aod.pipeline.admission import _extract_idp_domain, _idp_domain_matches_entity
from aod.pipeline.vendor_inference import extract_registered_domain


# Mock IdPObject for testing
@dataclass
class MockIdPObject:
    name: str
    domain: Optional[str] = None
    has_sso: bool = False
    has_scim: bool = False
    idp_type: str = "application"
    raw_data: Optional[dict] = None


def test_idp_domain_inference():
    """Test domain inference from IdP record names."""

    print("=" * 80)
    print("TEST: IdP Domain Inference from Name")
    print("=" * 80)

    # Test cases from cyberhub_snapshot.json
    test_records = [
        ("TEAMDESK", None, "teamdesk.net"),
        ("Teamsuite", None, "teamsuite.cloud"),  # Should pick .cloud as canonical
        ("Corelabs", None, "corelabs.tech"),
        ("Probox", None, "probox.co"),
        ("Microsoft 365", None, "microsoft.com"),  # Product name alias
        ("Google Workspace", None, "google.com"),  # Product name alias
        ("AWS", None, "amazon.com"),  # Product name alias
    ]

    print("\n1. TEST DOMAIN INFERENCE")
    print("-" * 80)

    passed = 0
    failed = 0

    for name, domain_field, expected_domain in test_records:
        mock_record = MockIdPObject(name=name, domain=domain_field)

        extracted_domain = _extract_idp_domain(mock_record)

        print(f"\nIdP Record: {name}")
        print(f"  Domain field: {domain_field if domain_field else '(none)'}")
        print(f"  Expected inferred: {expected_domain}")
        print(f"  Actual extracted: {extracted_domain}")

        # Check if extracted domain belongs to the same vendor as expected
        # (might not be exact match due to canonical domain selection)
        from aod.pipeline.vendor_inference import infer_vendor_from_domain

        expected_vendor = infer_vendor_from_domain(expected_domain)
        extracted_vendor = infer_vendor_from_domain(extracted_domain) if extracted_domain else None

        if not extracted_domain:
            print(f"  ✗ FAIL: No domain extracted")
            failed += 1
        elif expected_vendor and extracted_vendor and expected_vendor.value == extracted_vendor.value:
            print(f"  ✓ PASS: Vendor match ({extracted_vendor.value})")
            passed += 1
        elif extracted_domain == expected_domain:
            print(f"  ✓ PASS: Exact domain match")
            passed += 1
        else:
            print(f"  ✗ FAIL: Vendor mismatch or wrong domain")
            failed += 1

    print("\n" + "=" * 80)
    print(f"Domain Inference: {passed} passed, {failed} failed")
    print("=" * 80)

    # Test cross-domain vendor matching with inferred domains
    print("\n2. TEST CROSS-DOMAIN VENDOR MATCHING WITH INFERRED DOMAINS")
    print("-" * 80)

    matching_tests = [
        # (IdP name, entity domain, should match)
        ("Teamsuite", "teamsuite.cloud", True),
        ("Teamsuite", "teamsuite.ai", True),
        ("TEAMDESK", "teamdesk.net", True),
        ("Corelabs", "corelabs.tech", True),
        ("Corelabs", "corelabs.app", True),
        ("Teamsuite", "microsoft.com", False),
    ]

    match_passed = 0
    match_failed = 0

    for idp_name, entity_domain, should_match in matching_tests:
        mock_record = MockIdPObject(name=idp_name, domain=None)

        # Extract IdP domain (will use name-based inference)
        idp_extracted = _extract_idp_domain(mock_record)
        entity_registered = extract_registered_domain(entity_domain)

        # Test matching
        actual_match = _idp_domain_matches_entity(idp_extracted, entity_registered, idp_name)

        print(f"\nIdP '{idp_name}' (inferred: {idp_extracted}) vs Entity '{entity_domain}'")
        print(f"  Expected: {should_match}, Actual: {actual_match}")

        if actual_match == should_match:
            print(f"  ✓ PASS")
            match_passed += 1
        else:
            print(f"  ✗ FAIL")
            match_failed += 1

    print("\n" + "=" * 80)
    print(f"Cross-Domain Matching: {match_passed} passed, {match_failed} failed")
    print("=" * 80)

    total_passed = passed + match_passed
    total_failed = failed + match_failed

    print(f"\n{'=' * 80}")
    print(f"TOTAL: {total_passed} passed, {total_failed} failed")
    print(f"{'=' * 80}")

    if total_failed > 0:
        print("\n⚠️  Some tests failed")
        return 1
    else:
        print("\n✓ All tests passed!")
        print("\nThe enhanced _extract_idp_domain now:")
        print("1. Infers domains from IdP record names via VENDOR_TO_DOMAIN")
        print("2. Enables vendor-based governance for name-only IdP matches")
        print("3. Should reduce Shadow FPs for teamsuite, corelabs, teamdesk")
        return 0


if __name__ == "__main__":
    sys.exit(test_idp_domain_inference())
