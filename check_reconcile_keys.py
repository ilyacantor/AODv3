#!/usr/bin/env python3
"""Check what keys are generated for googleapis.com and office.com in reconciliation"""

import sys
sys.path.insert(0, 'src')

import json
from aod.pipeline.pipeline_executor import run_pipeline_ephemeral
from aod.pipeline.aod_agent_reconcile import emit_actual_results

with open('tests/fixtures/real_farm_snapshot.json', 'r') as f:
    snapshot = json.load(f)

print("Running pipeline...")
result = run_pipeline_ephemeral(
    snapshot,
    run_id="check_keys",
    is_farm_source=True
)

if not result.success:
    print(f"❌ Pipeline failed: {result.error}")
    sys.exit(1)

print("Emitting results...")
actual_results = emit_actual_results(
    run_id="check_keys",
    assets=result.assets,
    activity_window_days=90,
    rejections=result.rejections,
    mode="sprawl",
    snapshot_as_of=result.snapshot_as_of
)

print(f"\nTotal keys in admission_actual: {len(actual_results.admission_actual)}")
print(f"Total admitted: {len([v for v in actual_results.admission_actual.values() if v == 'admitted'])}")
print(f"Total rejected: {len([v for v in actual_results.admission_actual.values() if v == 'rejected'])}")

# Check if googleapis.com is in admission_actual
googleapis_keys = [k for k in actual_results.admission_actual.keys() if 'googleapis' in k.lower() or 'google.com' in k.lower()]

print(f"\n==================== googleapis keys ====================")
if googleapis_keys:
    for key in googleapis_keys:
        status = actual_results.admission_actual[key]
        print(f"  - Key: {key}")
        print(f"    Status: {status}")
        if key in actual_results.asset_details:
            details = actual_results.asset_details[key]
            print(f"    Name: {details.get('name')}")
            print(f"    Alias keys: {details.get('alias_keys', [])}")
            print(f"    Is shadow: {details.get('is_shadow')}")
            print(f"    Is zombie: {details.get('is_zombie')}")
else:
    print("  ❌ NO googleapis keys found in admission_actual")

# Check if office.com is in admission_actual
office_keys = [k for k in actual_results.admission_actual.keys() if 'office' in k.lower()]

print(f"\n==================== office.com keys ====================")
if office_keys:
    for key in office_keys:
        status = actual_results.admission_actual[key]
        print(f"  - Key: {key}")
        print(f"    Status: {status}")
        if key in actual_results.asset_details:
            details = actual_results.asset_details[key]
            print(f"    Name: {details.get('name')}")
            print(f"    Alias keys: {details.get('alias_keys', [])}")
            print(f"    Is shadow: {details.get('is_shadow')}")
            print(f"    Is zombie: {details.get('is_zombie')}")
else:
    print("  ❌ NO office.com keys found in admission_actual")

# Check what keys ARE being used for Google and Microsoft
google_keys = [k for k in actual_results.admission_actual.keys() if 'google' in k.lower()]
microsoft_keys = [k for k in actual_results.admission_actual.keys() if 'microsoft' in k.lower()]

print(f"\n==================== All Google-related keys ====================")
for key in google_keys[:10]:
    print(f"  - {key}: {actual_results.admission_actual[key]}")

print(f"\n==================== All Microsoft-related keys ====================")
for key in microsoft_keys[:10]:
    print(f"  - {key}: {actual_results.admission_actual[key]}")
