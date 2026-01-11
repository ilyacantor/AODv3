"""Debug discovery admission for cloudflareinsights.com and tiktok.com"""
import sys
sys.path.insert(0, 'src')

import json
from aod.pipeline.pipeline_executor import run_pipeline_ephemeral

# Load snapshot
with open('tests/fixtures/real_farm_snapshot.json') as f:
    snapshot = json.load(f)

print("Running pipeline...")
result = run_pipeline_ephemeral(
    snapshot,
    run_id="discovery_debug",
    is_farm_source=True
)

check_domains = ['cloudflareinsights.com', 'tiktok.com']

print(f"\n{'='*80}")
print("DISCOVERY THRESHOLD DEBUG")
print(f"{'='*80}\n")

for domain in check_domains:
    print(f"=== {domain} ===")

    # Check if admitted
    found_asset = None
    for asset in result.assets:
        if domain in [d.lower() for d in asset.identifiers.domains]:
            found_asset = asset
            break

    if found_asset:
        print(f"✅ ADMITTED")
        print(f"   Discovery sources: {found_asset.discovery_sources}")
        print(f"   Admission reason: {found_asset.admission_reason}")
    else:
        print(f"❌ NOT ADMITTED")

        # Check observations in snapshot
        obs_count = 0
        sources = []
        for obs in snapshot['planes']['discovery']['observations']:
            if obs.get('domain') == domain:
                obs_count += 1
                sources.append(obs.get('source'))

        print(f"   Observations: {obs_count}")
        print(f"   Sources: {set(sources)}")
        print(f"   All sources: {sources}")

        # Check rejections
        for rej in result.rejections:
            if domain in str(rej).lower():
                print(f"   Rejection found: {rej}")
                break

    print()
