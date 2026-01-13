#!/usr/bin/env python3
"""
Final diagnostic: Import actual modules and trace through real code path
to see if there's any difference between test and production.
"""

import sys
import json
sys.path.insert(0, 'src')

# Force fresh imports
for mod in list(sys.modules.keys()):
    if 'aod' in mod:
        del sys.modules[mod]

# Now import
from aod.models.input_contracts import IdPObject
from aod.pipeline.admission import _extract_idp_domain, _idp_domain_matches_entity, extract_registered_domain

print("="*80)
print("FINAL DIAGNOSTIC: Using Real IdPObject from Pydantic Models")
print("="*80)

# Load snapshot
with open('tests/fixtures/cyberhub_snapshot.json', 'r') as f:
    snapshot = json.load(f)

# Find TEAMDESK IdP record
teamdesk_dict = None
for record in snapshot['planes']['idp']['objects']:
    if record['name'] == 'TEAMDESK':
        teamdesk_dict = record
        break

print("\n1. RAW IdP RECORD FROM SNAPSHOT")
print("-"*80)
print(f"Raw dict: {json.dumps(teamdesk_dict, indent=2)}")

print("\n2. CONVERT TO IdPObject (Pydantic model)")
print("-"*80)
try:
    idp_record = IdPObject.model_validate(teamdesk_dict)
    print(f"✓ Successfully created IdPObject")
    print(f"  name: {idp_record.name}")
    print(f"  domain: {idp_record.domain}")
    print(f"  has_sso: {idp_record.has_sso}")
    print(f"  has_scim: {idp_record.has_scim}")
except Exception as e:
    print(f"✗ Failed to create IdPObject: {e}")
    sys.exit(1)

print("\n3. CALL _extract_idp_domain")
print("-"*80)
try:
    extracted_domain = _extract_idp_domain(idp_record)
    print(f"Result: {extracted_domain}")

    if extracted_domain == "teamdesk.net":
        print(f"✓ CORRECT - extracted teamdesk.net")
    else:
        print(f"✗ WRONG - expected teamdesk.net, got {extracted_domain}")
except Exception as e:
    print(f"✗ Exception: {e}")
    import traceback
    traceback.print_exc()

print("\n4. TEST DOMAIN MATCHING")
print("-"*80)
entity_domain = "teamdesk.net"
entity_registered = extract_registered_domain(entity_domain)
print(f"Entity registered: {entity_registered}")

if extracted_domain:
    matches = _idp_domain_matches_entity(extracted_domain, entity_registered, idp_record.name)
    print(f"_idp_domain_matches_entity result: {matches}")

    if matches:
        print(f"✓ DOMAINS MATCH - idp_governance_aligned should be TRUE")
    else:
        print(f"✗ DOMAINS DON'T MATCH - idp_governance_aligned will be FALSE")

print("\n5. CONCLUSION")
print("="*80)
if extracted_domain == "teamdesk.net" and matches:
    print("✓ ALL TESTS PASS")
    print("\nThe fix IS working with real Pydantic models.")
    print("If production still fails, the issue must be:")
    print("1. Production is using a different snapshot with different data")
    print("2. Production has different IdP record structure")
    print("3. There's an environment-specific issue (Docker, deployment, etc.)")
else:
    print("✗ TEST FAILED")
    print("\nThere IS a bug in the fix!")

