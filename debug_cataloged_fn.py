"""Debug specific cataloged FN domains through the pipeline"""
import sys
sys.path.insert(0, 'src')

import json
from aod.pipeline.pipeline_executor import run_pipeline_ephemeral

# Load snapshot
with open('tests/fixtures/real_farm_snapshot.json') as f:
    snapshot = json.load(f)

print("Running pipeline...")
run_id = "debug_test"
result = run_pipeline_ephemeral(
    snapshot,
    run_id=run_id,
    is_farm_source=True
)

if not result.success:
    print(f"❌ Pipeline failed: {result.error}")
    sys.exit(1)

# Check specific domains
check_domains = ['googleusercontent.com', 'sharepoint.com', 'worktech.tech']

print(f"\n{'='*80}")
print("CHECKING 3 DOMAINS WITH 2+ DISCOVERY SOURCES")
print(f"{'='*80}\n")

for domain in check_domains:
    print(f"=== {domain} ===")

    # Check if admitted as asset
    found_asset = None
    for asset in result.assets:
        if domain in [d.lower() for d in asset.identifiers.domains]:
            found_asset = asset
            break

    if found_asset:
        print(f"✅ ADMITTED as asset")
        print(f"   Asset ID: {found_asset.asset_id}")
        print(f"   Name: {found_asset.name}")
        print(f"   Discovery sources: {found_asset.discovery_sources}")
        print(f"   Admission reason: {found_asset.admission_reason}")
    else:
        print(f"❌ NOT ADMITTED")

        # Check rejections
        found_rejection = None
        for rejection in result.rejections:
            if domain.lower() in rejection.entity_key.lower():
                found_rejection = rejection
                break

        if found_rejection:
            print(f"   Rejected with reason: {found_rejection.reason}")
            print(f"   Entity key: {found_rejection.entity_key}")
        else:
            print(f"   Not found in rejections either - may not have been created as entity")

    print()
