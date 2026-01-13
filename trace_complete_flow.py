#!/usr/bin/env python3
"""
Complete trace: Follow teamdesk.net through the entire pipeline
to see where idp_governance_aligned gets set to False.
"""

import sys
import json
sys.path.insert(0, 'src')

from dataclasses import dataclass
from typing import Optional

# Mock objects for testing
@dataclass
class MockIdPObject:
    name: str
    domain: Optional[str] = None
    has_sso: bool = False
    has_scim: bool = False
    raw_data: Optional[dict] = None
    last_login_at: Optional[str] = None

print("="*80)
print("COMPLETE FLOW TRACE: teamdesk.net")
print("="*80)

# Load snapshot to get actual IdP record
with open('tests/fixtures/cyberhub_snapshot.json', 'r') as f:
    snapshot = json.load(f)

# Find TEAMDESK IdP record
teamdesk_idp = None
for idp in snapshot['planes']['idp']['objects']:
    if idp['name'] == 'TEAMDESK':
        teamdesk_idp = idp
        break

print("\n1. IdP RECORD FROM SNAPSHOT")
print("-"*80)
print(f"Name: {teamdesk_idp['name']}")
print(f"Domain field: {teamdesk_idp.get('domain', 'NONE')}")
print(f"Has SSO: {teamdesk_idp.get('has_sso', False)}")
print(f"Has SCIM: {teamdesk_idp.get('has_scim', False)}")

# Create mock IdP object
mock_idp = MockIdPObject(
    name=teamdesk_idp['name'],
    domain=teamdesk_idp.get('domain'),
    has_sso=teamdesk_idp.get('has_sso', False),
    has_scim=teamdesk_idp.get('has_scim', False),
    raw_data=teamdesk_idp.get('raw_data')
)

# Entity domain
entity_domain = "teamdesk.net"

print("\n2. ENTITY DOMAIN")
print("-"*80)
print(f"Domain: {entity_domain}")

# Now trace through the admission logic
from aod.pipeline.admission import (
    _extract_idp_domain,
    _idp_domain_matches_entity,
    extract_registered_domain
)

print("\n3. EXTRACT_ACTIVITY_TIMESTAMPS LOGIC")
print("-"*80)

# Line 1372: Extract IdP domain
print("Step 1: idp_registered_domain = _extract_idp_domain(record)")
idp_registered_domain = _extract_idp_domain(mock_idp)
print(f"  Result: {idp_registered_domain}")

# Line 1316: Get entity registered domain
print("\nStep 2: entity_registered_domain = extract_registered_domain(entity.domain)")
entity_registered_domain = extract_registered_domain(entity_domain)
print(f"  Result: {entity_registered_domain}")

# Line 1375-1377: Check domain alignment
print("\nStep 3: domain_aligned = _idp_domain_matches_entity(...)")
print(f"  Inputs:")
print(f"    idp_registered_domain: {idp_registered_domain}")
print(f"    entity_registered_domain: {entity_registered_domain}")
print(f"    idp_name: {mock_idp.name}")

domain_aligned = _idp_domain_matches_entity(
    idp_registered_domain,
    entity_registered_domain,
    mock_idp.name
)
print(f"  Result: {domain_aligned}")

# Line 1379-1380: Set idp_governance_aligned
print("\nStep 4: Determine idp_governance_aligned")
idp_governance_aligned = False

# Check SSO/SCIM first (line 1368-1370)
if mock_idp.has_sso or mock_idp.has_scim:
    idp_governance_aligned = True
    print(f"  SSO/SCIM detected → idp_governance_aligned = True")
else:
    print(f"  No SSO/SCIM")

# Check domain alignment (line 1379-1380)
if domain_aligned:
    idp_governance_aligned = True
    print(f"  domain_aligned = True → idp_governance_aligned = True")
else:
    print(f"  domain_aligned = False → idp_governance_aligned remains False")

print(f"\n  FINAL idp_governance_aligned: {idp_governance_aligned}")

# Now trace through reconcile logic
print("\n4. AOD_AGENT_RECONCILE LOGIC")
print("-"*80)

# Line 501-505: has_domain_aligned_idp
has_idp = True  # Assume we have IdP match
print(f"has_idp: {has_idp}")
print(f"idp_governance_aligned (from activity_evidence): {idp_governance_aligned}")

has_domain_aligned_idp = has_idp and idp_governance_aligned
print(f"\nLine 501-505: has_domain_aligned_idp = has_idp AND idp_governance_aligned")
print(f"  Result: {has_domain_aligned_idp}")

# Line 515: has_governance_strict
has_cmdb = False  # Assume no CMDB for this test
print(f"\nhas_cmdb: {has_cmdb}")

has_governance_strict = has_domain_aligned_idp or has_cmdb
print(f"\nLine 515: has_governance_strict = has_domain_aligned_idp OR has_cmdb")
print(f"  Result: {has_governance_strict}")

# Line 540-546: Shadow classification
has_recent_activity = True  # Assume recent activity
ungoverned = not has_governance_strict

print(f"\nhas_recent_activity: {has_recent_activity}")
print(f"ungoverned: {ungoverned}")

print(f"\nLine 540-546: Shadow classification")
print(f"  if ungoverned AND has_recent_activity:")
if ungoverned and has_recent_activity:
    print(f"    is_shadow = True ← THIS IS THE PROBLEM")
    print(f"    SHADOW_CLASSIFICATION reason code added")
else:
    print(f"    is_shadow = False (asset is clean)")

print("\n" + "="*80)
print("DIAGNOSIS")
print("="*80)

if idp_governance_aligned:
    print("✓ Our fix IS working: idp_governance_aligned = True")
    print("✓ Entity should be classified as CLEAN")
else:
    print("✗ Our fix is NOT working: idp_governance_aligned = False")
    print("✗ Entity will be classified as SHADOW")
    print("\nWhy is idp_governance_aligned False?")
    if not idp_registered_domain:
        print("  → _extract_idp_domain returned None")
        print("  → Our domain inference fix is not executing")
    elif not domain_aligned:
        print("  → _idp_domain_matches_entity returned False")
        print("  → Vendor-based matching is not working")
    else:
        print("  → Unknown reason")

print("="*80)
