#!/usr/bin/env python3
"""
Simple trace: Test _extract_idp_domain and _idp_domain_matches_entity
with actual snapshot data to verify our fix works.
"""

import sys
import json
from dataclasses import dataclass
from typing import Optional

sys.path.insert(0, 'src')

from aod.pipeline.admission import _extract_idp_domain, _idp_domain_matches_entity
from aod.pipeline.vendor_inference import extract_registered_domain, infer_vendor_from_domain


# Mock IdPObject
@dataclass
class MockIdPObject:
    name: str
    domain: Optional[str] = None
    has_sso: bool = False
    has_scim: bool = False
    raw_data: Optional[dict] = None


# Test pairs: (entity_domain, idp_name, idp_domain_field, expected_result)
test_cases = [
    ("teamsuite.cloud", "Teamsuite", None, True, "Same domain family via vendor"),
    ("teamsuite.ai", "Teamsuite", None, True, "Cross-domain vendor match"),
    ("corelabs.tech", "Corelabs", None, True, "Same domain"),
    ("corelabs.app", "Corelabs", None, True, "Cross-domain vendor match"),
    ("teamdesk.net", "TEAMDESK", None, True, "Same domain"),
    ("probox.co", "Probox", None, True, "Same domain"),
]

print("="*80)
print("SIMPLE TRACE: Testing _extract_idp_domain and _idp_domain_matches_entity")
print("="*80)

print("\nTest Cases:")
print("-"*80)

all_pass = True

for entity_domain, idp_name, idp_domain_field, expected_match, description in test_cases:
    print(f"\nTest: {description}")
    print(f"  Entity domain: {entity_domain}")
    print(f"  IdP name: {idp_name}")
    print(f"  IdP domain field: {idp_domain_field if idp_domain_field else 'None'}")

    # Create mock IdP record
    mock_idp = MockIdPObject(name=idp_name, domain=idp_domain_field)

    # Step 1: Extract IdP domain (should infer from name if domain field is None)
    extracted_idp_domain = _extract_idp_domain(mock_idp)
    print(f"  → _extract_idp_domain result: {extracted_idp_domain}")

    if not extracted_idp_domain and idp_domain_field is None:
        print(f"  ✗ FAIL: Domain inference from name failed!")
        all_pass = False
        continue

    # Step 2: Get entity registered domain
    entity_registered = extract_registered_domain(entity_domain)
    print(f"  → Entity registered: {entity_registered}")

    # Step 3: Test domain matching
    domain_matches = _idp_domain_matches_entity(extracted_idp_domain, entity_registered, idp_name)
    print(f"  → _idp_domain_matches_entity result: {domain_matches}")

    # Check if result matches expectation
    if domain_matches == expected_match:
        print(f"  ✓ PASS")
    else:
        print(f"  ✗ FAIL: Expected {expected_match}, got {domain_matches}")
        all_pass = False

        # Debug vendor matching
        if extracted_idp_domain:
            idp_vendor = infer_vendor_from_domain(extracted_idp_domain)
            entity_vendor = infer_vendor_from_domain(entity_domain)
            print(f"    Debug: IdP vendor = {idp_vendor.value if idp_vendor else 'None'}")
            print(f"    Debug: Entity vendor = {entity_vendor.value if entity_vendor else 'None'}")

print("\n" + "="*80)
if all_pass:
    print("✓ ALL TESTS PASSED")
    print("\nOur fix IS working correctly.")
    print("If production still shows Shadow FPs, check:")
    print("1. Is production code actually deployed from this branch?")
    print("2. Is there a caching issue?")
    print("3. Is the AOD run using old results?")
else:
    print("✗ SOME TESTS FAILED")
    print("\nOur fix has a bug that needs to be addressed.")
print("="*80)
