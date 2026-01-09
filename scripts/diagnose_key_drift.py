#!/usr/bin/env python3
"""
Diagnostic script to trace canonical key selection for assets.

Usage:
    python scripts/diagnose_key_drift.py <run_id> [keys...]

Example:
    python scripts/diagnose_key_drift.py run_123 amazon.com workers.dev probase.com
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aod.pipeline.derived_classifications import _resolve_domain_key
from aod.pipeline.vendor_inference import extract_registered_domain
from aod.models.output_contracts import Asset


def diagnose_asset(asset: Asset, target_keys: set[str]) -> dict | None:
    """Trace the canonical key selection for an asset."""
    domain_key, is_canonical, alias_keys = _resolve_domain_key(asset)
    
    all_domains = set(asset.identifiers.domains if asset.identifiers and asset.identifiers.domains else [])
    all_domains.add(domain_key)
    all_domains.update(alias_keys)
    
    matches_target = domain_key in target_keys or any(ak in target_keys for ak in alias_keys)
    has_target_in_evidence = any(tk in all_domains for tk in target_keys)
    
    if not matches_target and not has_target_in_evidence:
        return None
    
    observed_domains = list(asset.identifiers.domains[:5]) if asset.identifiers and asset.identifiers.domains else []
    
    candidate_registered = set()
    for d in (asset.identifiers.domains if asset.identifiers and asset.identifiers.domains else []):
        if d and "." in d:
            reg = extract_registered_domain(d.lower().strip())
            if reg:
                candidate_registered.add(reg)
    
    why_chosen = []
    if asset.identifiers and asset.identifiers.domains:
        first_domain = asset.identifiers.domains[0] if asset.identifiers.domains else None
        if first_domain:
            first_reg = extract_registered_domain(first_domain.lower().strip())
            why_chosen.append(f"first_domain={first_domain}")
            why_chosen.append(f"first_registered={first_reg}")
            why_chosen.append(f"chose_first_valid_registered_domain")
    
    return {
        "asset_id": str(asset.asset_id),
        "asset_name": asset.name,
        "observed_domains": observed_domains,
        "candidate_registered_domains": sorted(candidate_registered),
        "chosen_canonical_key": domain_key,
        "is_canonical": is_canonical,
        "why_chosen": why_chosen,
        "alias_keys": alias_keys,
        "target_in_evidence": has_target_in_evidence,
        "key_matches_target": matches_target,
        "drift_detected": has_target_in_evidence and not matches_target
    }


def load_assets_from_run(run_id: str) -> list[Asset]:
    """Load assets from a run's output file."""
    output_dir = Path("outputs")
    run_file = output_dir / f"run_{run_id}" / "assets.json"
    
    if not run_file.exists():
        for f in output_dir.glob(f"*{run_id}*/assets.json"):
            run_file = f
            break
    
    if not run_file.exists():
        print(f"Could not find assets.json for run {run_id}")
        return []
    
    with open(run_file) as f:
        data = json.load(f)
    
    assets = []
    for item in data.get("assets", data if isinstance(data, list) else []):
        try:
            assets.append(Asset.model_validate(item))
        except Exception as e:
            print(f"Warning: Could not parse asset: {e}")
    
    return assets


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/diagnose_key_drift.py <run_id> [keys...]")
        print("Example: python scripts/diagnose_key_drift.py run_123 amazon.com workers.dev")
        sys.exit(1)
    
    run_id = sys.argv[1]
    target_keys = set(sys.argv[2:]) if len(sys.argv) > 2 else {
        "amazon.com", "workers.dev", "probase.com", "fasthub.dev", "syncdesk.tech"
    }
    
    print(f"Diagnosing key drift for run: {run_id}")
    print(f"Target keys: {sorted(target_keys)}")
    print()
    
    assets = load_assets_from_run(run_id)
    print(f"Loaded {len(assets)} assets")
    print()
    
    found_diagnostics = []
    
    for asset in assets:
        diag = diagnose_asset(asset, target_keys)
        if diag:
            found_diagnostics.append(diag)
    
    if not found_diagnostics:
        print("No assets found matching target keys in evidence or canonical key")
        print("\nSearching for any asset containing target strings in domains/name...")
        
        for asset in assets:
            for target in target_keys:
                target_base = target.split(".")[0]
                name_match = target_base.lower() in asset.name.lower()
                domain_match = any(target_base.lower() in d.lower() for d in (asset.identifiers.domains if asset.identifiers else []))
                
                if name_match or domain_match:
                    diag = {
                        "asset_id": str(asset.asset_id),
                        "asset_name": asset.name,
                        "observed_domains": list(asset.identifiers.domains[:5]) if asset.identifiers and asset.identifiers.domains else [],
                        "match_reason": f"fuzzy match on '{target_base}'",
                        "target": target
                    }
                    found_diagnostics.append(diag)
                    break
    
    for diag in found_diagnostics:
        print("=" * 60)
        print(f"Asset: {diag.get('asset_name', 'unknown')}")
        print(f"  observed_domains (top 5): {diag.get('observed_domains', [])}")
        print(f"  candidate_registered_domains: {diag.get('candidate_registered_domains', [])}")
        print(f"  chosen_canonical_key: {diag.get('chosen_canonical_key', 'N/A')}")
        print(f"  is_canonical: {diag.get('is_canonical', 'N/A')}")
        print(f"  why_chosen: {diag.get('why_chosen', [])}")
        print(f"  alias_keys: {diag.get('alias_keys', [])}")
        if diag.get('drift_detected'):
            print(f"  *** DRIFT DETECTED: target in evidence but not canonical key ***")
        print()
    
    print(f"\nTotal diagnostics: {len(found_diagnostics)}")
    drift_count = sum(1 for d in found_diagnostics if d.get('drift_detected'))
    print(f"Drift detected: {drift_count}")


if __name__ == "__main__":
    main()
