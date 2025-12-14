#!/usr/bin/env python3
"""
Zombie Explain Script - Calls the zombie-explain endpoint and prints a compact summary.

Usage:
    python scripts/zombie_explain_from_farm_report.py --tenant FingerprintCorp --run run_d1daba1704c4

Or with custom keys:
    python scripts/zombie_explain_from_farm_report.py --tenant FingerprintCorp --run run_d1daba1704c4 --missed "mysqllegacy,salesforcecom" --extra "datadog,figma"
"""

import argparse
import httpx
import json
import sys
from collections import defaultdict


def call_zombie_explain(base_url: str, tenant_id: str, run_id: str, keys: list[str], window_days: int = 30) -> dict:
    """Call the zombie-explain endpoint"""
    url = f"{base_url}/api/debug/zombie-explain"
    payload = {
        "tenant_id": tenant_id,
        "run_id": run_id,
        "keys": keys,
        "window_days": window_days
    }
    
    response = httpx.post(url, json=payload, timeout=30.0)
    response.raise_for_status()
    return response.json()


def call_zombie_reconcile(base_url: str, tenant_id: str, run_id: str, 
                          expected_keys: list[str], extra_keys: list[str], 
                          window_days: int = 30) -> dict:
    """Call the zombie-reconcile endpoint"""
    url = f"{base_url}/api/debug/zombie-reconcile"
    payload = {
        "tenant_id": tenant_id,
        "run_id": run_id,
        "expected_zombie_keys": expected_keys,
        "extra_zombie_keys": extra_keys,
        "window_days": window_days
    }
    
    response = httpx.post(url, json=payload, timeout=30.0)
    response.raise_for_status()
    return response.json()


def print_compact_summary(result: dict, label: str = ""):
    """Print a compact summary grouped by reason codes"""
    print(f"\n{'='*60}")
    print(f"ZOMBIE EXPLAIN SUMMARY {label}")
    print(f"{'='*60}")
    print(f"Run: {result['run_id']}")
    print(f"Tenant: {result['tenant_id']}")
    print(f"Window: {result['window_days']} days")
    print()
    
    reason_groups = defaultdict(list)
    
    for exp in result['explanations']:
        decision = exp['zombie_decision']
        key = exp['key']
        
        if not exp['matched_asset_ids']:
            reason_code = "NO_MATCH"
        elif not exp['idp_present'] and not exp['cmdb_present']:
            reason_code = "NO_IDP_CMDB"
        elif exp['activity_within_window'] is True:
            reason_code = "HAS_ACTIVITY"
        elif exp['activity_within_window'] is False:
            reason_code = "STALE_ACTIVITY"
        elif exp['activity_within_window'] is None:
            reason_code = "NO_TIMESTAMPS"
        else:
            reason_code = "UNKNOWN"
        
        reason_groups[reason_code].append({
            "key": key,
            "decision": decision,
            "why": exp['why']
        })
    
    print("GROUPED BY REASON CODE:")
    print("-" * 40)
    
    for reason_code, items in sorted(reason_groups.items()):
        print(f"\n{reason_code}: {len(items)} keys")
        for item in items:
            print(f"  - {item['key']} -> {item['decision']}")
            for bullet in item['why'][:2]:
                print(f"      {bullet[:80]}...")
    
    print()
    print("RAW SUMMARY COUNTS:")
    print("-" * 40)
    for k, v in result['summary'].items():
        if v > 0:
            print(f"  {k}: {v}")


def print_full_explanation(exp: dict, label: str = ""):
    """Print full JSON explanation for one key"""
    print(f"\n{'='*60}")
    print(f"FULL EXPLANATION: {exp['key']} ({label})")
    print(f"{'='*60}")
    print(json.dumps(exp, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(description="Zombie Explain from Farm Report")
    parser.add_argument("--base-url", default="http://localhost:5000", help="AOD base URL")
    parser.add_argument("--tenant", required=True, help="Tenant ID")
    parser.add_argument("--run", required=True, help="Run ID")
    parser.add_argument("--missed", help="Comma-separated missed zombie keys from Farm")
    parser.add_argument("--extra", help="Comma-separated extra zombie keys in AOD")
    parser.add_argument("--window", type=int, default=30, help="Activity window in days")
    parser.add_argument("--full", action="store_true", help="Print full JSON for first missed and extra")
    
    args = parser.parse_args()
    
    missed_keys = args.missed.split(",") if args.missed else [
        "mysqllegacy", "salesforcecom", "zoomus", "githubcom", "admindashboard"
    ]
    extra_keys = args.extra.split(",") if args.extra else [
        "datadog", "billingapi", "microsoft365", "figma", "okta"
    ]
    
    all_keys = missed_keys + extra_keys
    
    print(f"Calling zombie-explain for {len(all_keys)} keys...")
    print(f"Missed (Farm expected): {missed_keys}")
    print(f"Extra (AOD found): {extra_keys}")
    
    try:
        result = call_zombie_explain(
            args.base_url, 
            args.tenant, 
            args.run, 
            all_keys,
            args.window
        )
        
        print_compact_summary(result, f"[{args.tenant}]")
        
        if args.full:
            missed_explanations = [e for e in result['explanations'] if e['key'] in missed_keys]
            extra_explanations = [e for e in result['explanations'] if e['key'] in extra_keys]
            
            if missed_explanations:
                print_full_explanation(missed_explanations[0], "MISSED ZOMBIE")
            if extra_explanations:
                print_full_explanation(extra_explanations[0], "EXTRA ZOMBIE")
        
        print("\n" + "="*60)
        print("RECONCILE REPORT")
        print("="*60)
        
        reconcile_result = call_zombie_reconcile(
            args.base_url,
            args.tenant,
            args.run,
            missed_keys,
            extra_keys,
            args.window
        )
        
        print(reconcile_result['compact_report'])
        
        if reconcile_result.get('sample_explanation'):
            print("\nSample explanation:")
            print(json.dumps(reconcile_result['sample_explanation'], indent=2))
        
    except httpx.HTTPStatusError as e:
        print(f"HTTP Error: {e.response.status_code} - {e.response.text}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
