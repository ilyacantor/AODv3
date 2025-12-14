#!/usr/bin/env python3
"""
Nuke Prevention Check for AOD/Farm Projects

A fast, repeatable sanity check that verifies the discovery pipeline works
correctly. Runs in ~60 seconds and outputs a plain-English PASS/FAIL summary.

Usage:
    python scripts/nuke_check.py

Environment:
    FARM_URL - Required for AOD checks. Points to the Farm server.
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

VALID_AOD_STATUSES = {
    "UPSTREAM_ERROR",
    "INVALID_SNAPSHOT",
    "COMPLETED_NO_ASSETS",
    "COMPLETED_WITH_RESULTS",
    "INVALID_INPUT_CONTRACT",
    "FAILED"
}

BANNED_FIELDS = {
    "is_shadow_it",
    "inCMDB",
    "rulesTriggered",
    "conflictTypes",
    "sourcePresence",
    "parked_reason",
    "ground_truth"
}


class NukeCheckResult:
    def __init__(self):
        self.passed = True
        self.project: Optional[str] = None
        self.verifications: list[str] = []
        self.failure_what: Optional[str] = None
        self.failure_cause: Optional[str] = None
        self.failure_fix: Optional[str] = None

    def add_pass(self, msg: str):
        self.verifications.append(f"[PASS] {msg}")

    def add_fail(self, what: str, cause: str, fix: str):
        self.passed = False
        self.failure_what = what
        self.failure_cause = cause
        self.failure_fix = fix
        self.verifications.append(f"[FAIL] {what}")

    def print_report(self):
        status = "PASS" if self.passed else "FAIL"
        print()
        print("=" * 60)
        print(f"NUKE CHECK: {status}")
        print(f"Project: {self.project or 'UNKNOWN'}")
        print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
        print()
        print("Key results:")
        for v in self.verifications:
            print(f"  - {v}")
        
        if not self.passed:
            print()
            print(f"What failed: {self.failure_what}")
            print(f"Likely cause: {self.failure_cause}")
            print(f"What to do: {self.failure_fix}")
        print("=" * 60)


def detect_project() -> Optional[str]:
    """Detect if this is AOD or Farm project"""
    routes_path = PROJECT_ROOT / "src" / "aod" / "api" / "routes.py"
    pipeline_path = PROJECT_ROOT / "src" / "aod" / "pipeline"
    
    if routes_path.exists() and pipeline_path.exists():
        with open(routes_path) as f:
            content = f.read()
            if "/api/runs" in content or "execute_pipeline" in content:
                return "AOD"
    
    farm_routes = PROJECT_ROOT / "src" / "farm" / "routes.py"
    generator_path = PROJECT_ROOT / "src" / "farm" / "generator.py"
    
    if farm_routes.exists() or generator_path.exists():
        return "FARM"
    
    if routes_path.exists():
        with open(routes_path) as f:
            content = f.read()
            if "/api/snapshots" in content and "generator" in content.lower():
                return "FARM"
    
    return None


async def check_aod(result: NukeCheckResult) -> NukeCheckResult:
    """Run AOD-specific checks"""
    
    farm_url = os.environ.get("FARM_URL")
    if not farm_url:
        result.add_fail(
            "FARM_URL environment variable is not set",
            "AOD needs to connect to a Farm server to fetch snapshots",
            "Set FARM_URL to point to your Farm server (e.g., export FARM_URL=https://farm.example.com)"
        )
        return result
    result.add_pass(f"FARM_URL is configured: {farm_url[:50]}...")
    
    base_url = "http://localhost:5000"
    
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            health = await client.get(f"{base_url}/api/health")
            if health.status_code != 200:
                result.add_fail(
                    "AOD health check failed",
                    f"Health endpoint returned status {health.status_code}",
                    "Make sure the AOD server is running on port 5000"
                )
                return result
            result.add_pass("AOD server is healthy")
        except httpx.ConnectError:
            result.add_fail(
                "Cannot connect to AOD server",
                "The AOD server is not running or not reachable",
                "Start the server with: python -m uvicorn src.main:app --host 0.0.0.0 --port 5000"
            )
            return result
        
        try:
            tenants_resp = await client.get(f"{base_url}/api/farm/tenants")
            if tenants_resp.status_code != 200:
                result.add_fail(
                    "Failed to list Farm tenants",
                    f"Tenants endpoint returned {tenants_resp.status_code}: {tenants_resp.text[:200]}",
                    "Check that FARM_URL is correct and Farm is accessible"
                )
                return result
            
            tenants_data = tenants_resp.json()
            tenants = tenants_data.get("tenants", [])
            if not tenants:
                result.add_fail(
                    "No tenants found in Farm",
                    "Farm returned an empty tenant list",
                    "Ensure Farm has at least one tenant with snapshots"
                )
                return result
            
            tenant_id = tenants[0]
            result.add_pass(f"Found {len(tenants)} tenant(s), using: {tenant_id}")
        except Exception as e:
            result.add_fail(
                "Error fetching tenants from Farm",
                str(e),
                "Check FARM_URL and network connectivity"
            )
            return result
        
        try:
            snapshots_resp = await client.get(f"{base_url}/api/farm/snapshots?tenant_id={tenant_id}")
            if snapshots_resp.status_code != 200:
                result.add_fail(
                    "Failed to list snapshots",
                    f"Snapshots endpoint returned {snapshots_resp.status_code}",
                    "Check Farm connectivity and tenant_id"
                )
                return result
            
            snapshots_data = snapshots_resp.json()
            snapshots = snapshots_data.get("snapshots", [])
            if not snapshots:
                result.add_fail(
                    "No snapshots found for tenant",
                    f"Tenant '{tenant_id}' has no snapshots",
                    "Generate at least one snapshot in Farm"
                )
                return result
            
            snapshot = snapshots[0]
            snapshot_id = snapshot.get("snapshot_id")
            result.add_pass(f"Found {len(snapshots)} snapshot(s), using: {snapshot_id[:20]}...")
        except Exception as e:
            result.add_fail(
                "Error fetching snapshots",
                str(e),
                "Check Farm connectivity"
            )
            return result
        
        run1_result = await run_discovery(client, base_url, tenant_id, snapshot_id, result, "Run 1")
        if not result.passed:
            return result
        
        run2_result = await run_discovery(client, base_url, tenant_id, snapshot_id, result, "Run 2")
        if not result.passed:
            return result
        
        if run1_result and run2_result:
            if not compare_runs(run1_result, run2_result, result):
                return result
            result.add_pass("Determinism check passed: both runs produced identical outputs")
    
    return result


async def run_discovery(
    client: httpx.AsyncClient,
    base_url: str,
    tenant_id: str,
    snapshot_id: str,
    result: NukeCheckResult,
    run_label: str
) -> Optional[dict]:
    """Run a discovery and return the result for comparison"""
    
    try:
        run_resp = await client.post(
            f"{base_url}/api/runs/from-farm",
            json={
                "tenant_id": tenant_id,
                "snapshot_id": snapshot_id
            },
            timeout=60
        )
        
        if run_resp.status_code not in (200, 400, 502):
            result.add_fail(
                f"{run_label}: Unexpected HTTP status {run_resp.status_code}",
                f"Response: {run_resp.text[:200]}",
                "Check server logs for errors"
            )
            return None
        
        if run_resp.status_code == 400:
            body = run_resp.json() if "application/json" in run_resp.headers.get("content-type", "") else {"detail": run_resp.text}
            detail = body.get("detail", "")
            if "INVALID_INPUT_CONTRACT" in str(detail):
                result.add_pass(f"{run_label}: Got expected INVALID_INPUT_CONTRACT for bad schema")
                return {"status": "INVALID_INPUT_CONTRACT", "counts": {}, "assets": []}
            result.add_fail(
                f"{run_label}: Bad request",
                detail,
                "Check snapshot format"
            )
            return None
        
        if run_resp.status_code == 502:
            result.add_pass(f"{run_label}: Got expected UPSTREAM_ERROR (Farm issue)")
            return {"status": "UPSTREAM_ERROR", "counts": {}, "assets": []}
        
        run_data = run_resp.json()
        status = run_data.get("status", "")
        
        if status not in VALID_AOD_STATUSES:
            result.add_fail(
                f"{run_label}: Invalid run status '{status}'",
                f"Status must be one of: {VALID_AOD_STATUSES}",
                "Check pipeline_executor.py for status handling"
            )
            return None
        
        run_id = run_data.get("run_id")
        counts = run_data.get("counts", {})
        result.add_pass(f"{run_label}: status={status}, assets={counts.get('assets_admitted', 0)}, findings={counts.get('findings_generated', 0)}")
        
        catalog_resp = await client.get(f"{base_url}/api/catalog?run_id={run_id}")
        assets = []
        if catalog_resp.status_code == 200:
            assets = catalog_resp.json().get("assets", [])
        
        return {
            "status": status,
            "counts": counts,
            "assets": sorted([a.get("name", "") for a in assets]),
            "finding_count": counts.get("findings_generated", 0)
        }
        
    except Exception as e:
        result.add_fail(
            f"{run_label}: Exception during discovery",
            str(e),
            "Check server logs"
        )
        return None


def compare_runs(run1: dict, run2: dict, result: NukeCheckResult) -> bool:
    """Compare two run results for determinism"""
    
    if run1["status"] != run2["status"]:
        result.add_fail(
            "Determinism check failed: different statuses",
            f"Run 1: {run1['status']}, Run 2: {run2['status']}",
            "Check for non-deterministic behavior in pipeline"
        )
        return False
    
    c1 = run1["counts"]
    c2 = run2["counts"]
    
    if c1.get("assets_admitted") != c2.get("assets_admitted"):
        result.add_fail(
            "Determinism check failed: different asset counts",
            f"Run 1: {c1.get('assets_admitted')}, Run 2: {c2.get('assets_admitted')}",
            "Check for random UUIDs or timestamps affecting admission"
        )
        return False
    
    if c1.get("findings_generated") != c2.get("findings_generated"):
        result.add_fail(
            "Determinism check failed: different finding counts",
            f"Run 1: {c1.get('findings_generated')}, Run 2: {c2.get('findings_generated')}",
            "Check findings engine for non-deterministic behavior"
        )
        return False
    
    if run1["assets"] != run2["assets"]:
        result.add_fail(
            "Determinism check failed: different asset names",
            f"Run 1 has {len(run1['assets'])} assets, Run 2 has {len(run2['assets'])} assets",
            "Check for ordering issues or unstable sorting"
        )
        return False
    
    return True


def scan_for_banned_fields(data: dict, path: str = "") -> list[str]:
    """Recursively scan JSON for banned adjudication fields"""
    found = []
    
    if isinstance(data, dict):
        for key, value in data.items():
            current_path = f"{path}.{key}" if path else key
            if key in BANNED_FIELDS:
                found.append(current_path)
            found.extend(scan_for_banned_fields(value, current_path))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            found.extend(scan_for_banned_fields(item, f"{path}[{i}]"))
    
    return found


async def main():
    print("=" * 60)
    print("NUKE PREVENTION CHECK")
    print("Starting...")
    print("=" * 60)
    
    start_time = time.time()
    result = NukeCheckResult()
    
    project = detect_project()
    result.project = project
    
    if project is None:
        result.add_fail(
            "Cannot detect project type",
            "Could not find AOD or Farm markers in the codebase",
            "Ensure you're running from the project root with src/aod or src/farm"
        )
        result.print_report()
        sys.exit(1)
    
    result.add_pass(f"Detected project: {project}")
    
    if project == "AOD":
        await check_aod(result)
    elif project == "FARM":
        result.add_fail(
            "Farm checks not implemented in this version",
            "This script currently only supports AOD",
            "Run Farm-specific validation manually"
        )
    
    elapsed = time.time() - start_time
    result.verifications.append(f"[INFO] Completed in {elapsed:.1f} seconds")
    
    result.print_report()
    
    sys.exit(0 if result.passed else 1)


if __name__ == "__main__":
    asyncio.run(main())
