"""Check for key mismatches between Farm expectations and AOD output"""
import sys
sys.path.insert(0, 'src')

import json
from aod.pipeline.pipeline_executor import run_pipeline_ephemeral
from aod.pipeline.aod_agent_reconcile import emit_actual_results

# Load snapshot and expected outcomes
with open('tests/fixtures/real_farm_snapshot.json') as f:
    snapshot = json.load(f)

with open('tests/fixtures/golden_expected_outcomes.json') as f:
    expected = json.load(f)

print("Running pipeline...")
result = run_pipeline_ephemeral(
    snapshot,
    run_id="key_check",
    is_farm_source=True
)

print("Emitting results...")
actual_results = emit_actual_results(
    run_id="key_check",
    assets=result.assets,
    activity_window_days=90,
    rejections=result.rejections,
    mode="sprawl",
    snapshot_as_of=result.snapshot_as_of
)

# Get expected cataloged
expected_cataloged = set(expected.get("expected_cataloged", []))

# Get actual cataloged keys
actual_cataloged_keys = set(
    k for k, v in actual_results.admission_actual.items()
    if v == "admitted"
)

# Check the 9 cataloged FN
cataloged_fn = expected_cataloged - actual_cataloged_keys

print(f"\n{'='*80}")
print(f"CATALOGED FN ANALYSIS - Key Matching")
print(f"{'='*80}\n")

print(f"Total cataloged FN: {len(cataloged_fn)}")
print(f"Cataloged FN domains: {sorted(cataloged_fn)}\n")

# For each FN, check if we have an asset with that domain but under a different key
for fn_domain in sorted(cataloged_fn):
    print(f"=== {fn_domain} ===")

    # Search for assets with this domain
    found_assets = []
    for asset in result.assets:
        asset_domains = [d.lower() for d in asset.identifiers.domains]
        if fn_domain.lower() in asset_domains:
            found_assets.append(asset)

    if found_assets:
        print(f"✅ Found {len(found_assets)} asset(s) with this domain:")
        for asset in found_assets:
            # Find this asset's key in actual_results
            asset_key = None
            for k, v in actual_results.admission_actual.items():
                if v == "admitted":
                    # Check if this key matches this asset
                    # The key should be the primary domain (first in domains list)
                    primary_domain = asset.identifiers.domains[0].lower()
                    if k.lower() == primary_domain:
                        asset_key = k
                        break

            print(f"   Primary domain: {asset.identifiers.domains[0]}")
            print(f"   All domains: {asset.identifiers.domains}")
            print(f"   Asset key in actual_results: {asset_key}")
            print(f"   Name: {asset.name}")

            if fn_domain.lower() != asset.identifiers.domains[0].lower():
                print(f"   ⚠️  KEY MISMATCH: Farm expects key '{fn_domain}' but AOD uses '{asset.identifiers.domains[0]}'")
    else:
        print(f"❌ No asset found with this domain")

    print()
