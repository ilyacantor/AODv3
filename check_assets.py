#!/usr/bin/env python3
"""Check if googleapis.com and office.com are in the assets list"""

import sys
sys.path.insert(0, 'src')

import json
from aod.pipeline.pipeline_executor import run_pipeline_ephemeral

with open('tests/fixtures/real_farm_snapshot.json', 'r') as f:
    snapshot = json.load(f)

print("Running pipeline...")
result = run_pipeline_ephemeral(
    snapshot,
    run_id="check_assets",
    is_farm_source=True
)

if not result.success:
    print(f"❌ Pipeline failed: {result.error}")
    sys.exit(1)

print(f"\nTotal assets: {len(result.assets)}")
print(f"Total rejections: {len(result.rejections)}")

# Check if googleapis.com is in assets
googleapis_assets = [a for a in result.assets if 'googleapis' in a.name.lower() or
                     (a.identifiers and a.identifiers.domains and
                      any('googleapis' in d.lower() for d in a.identifiers.domains))]

print(f"\n==================== googleapis.com assets ====================")
if googleapis_assets:
    for asset in googleapis_assets:
        print(f"  - Name: {asset.name}")
        print(f"    Domains: {asset.identifiers.domains if asset.identifiers else []}")
        print(f"    Provisioning status: {asset.provisioning_status}")
        print(f"    Admission reason: {asset.admission_reason}")
else:
    print("  ❌ NO googleapis.com assets found")

# Check if googleapis.com is in rejections
googleapis_rejections = [r for r in result.rejections if 'googleapis' in str(r).lower()]
if googleapis_rejections:
    print(f"\n  Found in rejections:")
    for rej in googleapis_rejections:
        print(f"    - {rej}")

# Check if office.com is in assets
office_assets = [a for a in result.assets if 'office.com' in a.name.lower() or
                 (a.identifiers and a.identifiers.domains and
                  any('office.com' in d.lower() for d in a.identifiers.domains))]

print(f"\n==================== office.com assets ====================")
if office_assets:
    for asset in office_assets:
        print(f"  - Name: {asset.name}")
        print(f"    Domains: {asset.identifiers.domains if asset.identifiers else []}")
        print(f"    Provisioning status: {asset.provisioning_status}")
        print(f"    Admission reason: {asset.admission_reason}")
else:
    print("  ❌ NO office.com assets found")

# Check if office.com is in rejections
office_rejections = [r for r in result.rejections if 'office.com' in str(r).lower()]
if office_rejections:
    print(f"\n  Found in rejections:")
    for rej in office_rejections:
        print(f"    - {rej}")

# Check if awsstatic.com is in assets
awsstatic_assets = [a for a in result.assets if 'awsstatic' in a.name.lower() or
                 (a.identifiers and a.identifiers.domains and
                  any('awsstatic' in d.lower() for d in a.identifiers.domains))]

print(f"\n==================== awsstatic.com assets ====================")
if awsstatic_assets:
    for asset in awsstatic_assets:
        print(f"  - Name: {asset.name}")
        print(f"    Domains: {asset.identifiers.domains if asset.identifiers else []}")
        print(f"    Provisioning status: {asset.provisioning_status}")
        print(f"    Admission reason: {asset.admission_reason}")
else:
    print("  ❌ NO awsstatic.com assets found")

# Check if awsstatic.com is in rejections
awsstatic_rejections = [r for r in result.rejections if 'awsstatic' in str(r).lower()]
if awsstatic_rejections:
    print(f"\n  Found in rejections:")
    for rej in awsstatic_rejections:
        print(f"    - {rej}")

# Check for amazon.com assets
amazon_assets = [a for a in result.assets if 'amazon' in a.name.lower() or 'aws' in a.name.lower() or
                 (a.identifiers and a.identifiers.domains and
                  any('amazon' in d.lower() or 'aws' in d.lower() for d in a.identifiers.domains))]

print(f"\n==================== amazon/aws assets ====================")
for asset in amazon_assets[:5]:
    print(f"  - Name: {asset.name}")
    print(f"    Domains: {asset.identifiers.domains if asset.identifiers else []}")
    print(f"    Provisioning status: {asset.provisioning_status}")
