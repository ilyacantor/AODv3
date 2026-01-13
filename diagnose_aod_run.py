#!/usr/bin/env python3
"""
Diagnostic: Check if AOD run results show evidence of our fix.

This will analyze the actual AOD run output to see if idp_governance_aligned
is set correctly for our target domains.
"""

import sys
import json

def diagnose_aod_run(aod_output_path: str):
    """
    Analyze AOD run output to check if our fix was applied.

    Args:
        aod_output_path: Path to AOD run output JSON (assets.json or similar)
    """

    print("="*80)
    print("DIAGNOSTIC: Checking if AOD run has our vendor governance fix")
    print("="*80)

    with open(aod_output_path, 'r') as f:
        data = json.load(f)

    # Look for our target domains in the assets
    target_domains = {
        'teamdesk.net',
        'corelabs.tech',
        'teamsuite.cloud',
        'teamsuite.ai',
        'probox.co'
    }

    # Try different possible structures
    assets = []
    if isinstance(data, list):
        assets = data
    elif 'assets' in data:
        assets = data['assets']
    elif 'cataloged' in data:
        assets = data['cataloged']

    print(f"\nFound {len(assets)} assets in AOD output")

    found_targets = []
    for asset in assets:
        # Get domain from asset
        domain = None
        if 'identifiers' in asset and 'domain' in asset['identifiers']:
            domain = asset['identifiers']['domain']
        elif 'domain' in asset:
            domain = asset['domain']
        elif 'name' in asset:
            # Try to extract from name
            name = asset['name'].lower()
            for target in target_domains:
                if target in name:
                    domain = target
                    break

        if domain in target_domains:
            found_targets.append((domain, asset))

    print(f"Found {len(found_targets)} target domain assets")

    if not found_targets:
        print("\n⚠️  WARNING: No target domains found in AOD output")
        print("This could mean:")
        print("1. AOD rejected these entities (not admitted)")
        print("2. They're in a different output file")
        print("3. The JSON structure is different than expected")
        return

    print("\nAnalyzing target assets:")
    print("-"*80)

    for domain, asset in found_targets:
        print(f"\nDomain: {domain}")

        # Check for activity_evidence
        if 'activity_evidence' not in asset:
            print("  ✗ NO activity_evidence field (old code structure?)")
            continue

        activity_ev = asset['activity_evidence']

        # Check idp_governance_aligned flag
        if 'idp_governance_aligned' not in activity_ev:
            print("  ✗ NO idp_governance_aligned field (old code, pre-Jan 2026)")
            continue

        idp_gov_aligned = activity_ev['idp_governance_aligned']
        print(f"  idp_governance_aligned: {idp_gov_aligned}")

        # Check derived classifications
        if 'derived_classifications' in asset:
            derived = asset['derived_classifications']
            is_shadow = derived.get('is_shadow', False)
            is_zombie = derived.get('is_zombie', False)
            gov_status = derived.get('governance_status', 'unknown')

            print(f"  is_shadow: {is_shadow}")
            print(f"  is_zombie: {is_zombie}")
            print(f"  governance_status: {gov_status}")

            # Diagnose
            if idp_gov_aligned and is_shadow:
                print("  ⚠️  BUG: idp_governance_aligned=True but classified as shadow!")
            elif idp_gov_aligned and not is_shadow:
                print("  ✓ CORRECT: idp_governance_aligned=True → not shadow")
            elif not idp_gov_aligned and is_shadow:
                print("  ✗ ISSUE: idp_governance_aligned=False → classified as shadow")
                print("     This means our fix is NOT being applied in this AOD run")
            elif not idp_gov_aligned and not is_shadow:
                print("  ? UNCLEAR: idp_governance_aligned=False but not shadow (other governance?)")

        # Check lens status
        if 'lens_status' in asset:
            lens = asset['lens_status']
            print(f"  lens_status.idp: {lens.get('idp', 'unknown')}")
            print(f"  lens_status.cmdb: {lens.get('cmdb', 'unknown')}")

    print("\n" + "="*80)
    print("CONCLUSION")
    print("="*80)

    issues = [a for d, a in found_targets
              if 'activity_evidence' in a
              and not a['activity_evidence'].get('idp_governance_aligned', False)
              and a.get('derived_classifications', {}).get('is_shadow', False)]

    if issues:
        print(f"✗ {len(issues)} assets show idp_governance_aligned=False + is_shadow=True")
        print("This indicates the AOD run was executed with OLD CODE (before our fix)")
        print("\nTo fix:")
        print("1. Ensure branch claude/analyze-key-normalization-X7VDd is deployed")
        print("2. Clear any Python cache: rm -rf **/__pycache__")
        print("3. Execute a NEW AOD run")
        print("4. Run reconciliation against the NEW run")
    else:
        print("✓ All target assets show correct idp_governance_aligned values")
        print("The fix is working in this AOD run!")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python diagnose_aod_run.py <aod_output.json>")
        print("\nProvide the path to AOD run output (assets.json, cataloged.json, etc)")
        sys.exit(1)

    diagnose_aod_run(sys.argv[1])
