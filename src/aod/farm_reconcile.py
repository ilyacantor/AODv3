"""Farm reconciliation module - syncs AOD results back to Farm"""

import os
import httpx
from typing import Optional
from datetime import datetime, timezone, timedelta

PST = timezone(timedelta(hours=-8))

def now_pst() -> datetime:
    return datetime.now(PST)

from .models.output_contracts import RunLog, Asset, Finding, SyncStatus
from .pipeline.derived_classifications import compute_derived_classifications


async def reconcile_to_farm(
    run_log: RunLog,
    assets: list[Asset],
    findings: list[Finding],
    snapshot_id: str,
    farm_url: Optional[str] = None
) -> tuple[bool, Optional[str]]:
    """
    Reconcile AOD results back to Farm.
    
    POSTs a summary of the run results to {FARM_URL}/api/reconcile
    
    Args:
        run_log: The completed run log
        assets: List of admitted assets
        findings: List of generated findings
        snapshot_id: The source snapshot ID
        farm_url: Optional Farm URL override (uses FARM_URL env var if not provided)
    
    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    base_url = farm_url or os.environ.get("FARM_URL")
    if not base_url:
        return False, "No Farm URL configured"
    
    derived = compute_derived_classifications(assets, activity_window_days=90)
    
    def get_asset_key(asset) -> str:
        """Get canonical reconciliation key for an asset (registered domain preferred)"""
        domains = []
        name = ""
        
        if isinstance(asset, dict):
            identifiers = asset.get("identifiers", {})
            if isinstance(identifiers, dict):
                domains = identifiers.get("domains", [])
            elif hasattr(identifiers, "domains"):
                domains = identifiers.domains or []
            name = asset.get("name", "")
        else:
            identifiers = getattr(asset, "identifiers", None)
            if identifiers:
                if hasattr(identifiers, "domains"):
                    domains = identifiers.domains or []
                elif isinstance(identifiers, dict):
                    domains = identifiers.get("domains", [])
            name = getattr(asset, "name", "")
        
        if domains and len(domains) > 0:
            return domains[0].lower()
        return name.lower().replace(" ", "_")
    
    shadow_asset_keys = [get_asset_key(a) for a in derived.shadow_assets]
    zombie_asset_keys = [get_asset_key(a) for a in derived.zombie_assets]
    
    def get_reason_codes(asset: dict) -> list[str]:
        """Generate canonical reason codes for an asset"""
        codes = []
        lens_coverage = asset.get("lens_coverage", {})
        activity_evidence = asset.get("activity_evidence", {})
        
        if lens_coverage.get("idp"):
            codes.append("HAS_IDP")
        else:
            codes.append("NO_IDP")
        
        if lens_coverage.get("cmdb"):
            codes.append("HAS_CMDB")
        else:
            codes.append("NO_CMDB")
        
        if lens_coverage.get("finance"):
            codes.append("HAS_FINANCE")
        else:
            codes.append("NO_FINANCE")
        
        if lens_coverage.get("cloud"):
            codes.append("HAS_CLOUD")
        else:
            codes.append("NO_CLOUD")
        
        if lens_coverage.get("discovery"):
            codes.append("HAS_DISCOVERY")
        else:
            codes.append("NO_DISCOVERY")
        
        latest_activity = activity_evidence.get("latest_activity_at")
        if latest_activity:
            codes.append("HAS_ACTIVITY_TIMESTAMP")
        else:
            codes.append("NO_ACTIVITY_TIMESTAMPS")
        
        return codes
    
    actual_reasons: dict[str, list[str]] = {}
    for asset in derived.shadow_assets:
        key = get_asset_key(asset)
        codes = get_reason_codes(asset)
        codes.append("SHADOW_CLASSIFICATION")
        actual_reasons[key] = codes
    
    for asset in derived.zombie_assets:
        key = get_asset_key(asset)
        codes = get_reason_codes(asset)
        codes.append("ZOMBIE_CLASSIFICATION")
        actual_reasons[key] = codes
    
    high_severity_findings = [
        f"{f.finding_type.value}: {f.explanation[:150]}"
        for f in findings
        if f.severity.value == "high"
    ][:10]
    
    aod_callback_url = os.environ.get("REPLIT_DEV_DOMAIN", "")
    if aod_callback_url and not aod_callback_url.startswith("http"):
        aod_callback_url = f"https://{aod_callback_url}"
    
    reconcile_payload = {
        "snapshot_id": snapshot_id,
        "tenant_id": run_log.tenant_id,
        "aod_run_id": run_log.run_id,
        "aod_status": run_log.status.value,
        "aod_callback_url": aod_callback_url,
        "completed_at": run_log.completed_at.isoformat() if run_log.completed_at else now_pst().isoformat(),
        "aod_summary": {
            "observations_in": run_log.counts.observations_in,
            "candidates_out": run_log.counts.candidates_out,
            "assets_admitted": run_log.counts.assets_admitted,
            "artifacts_recorded": run_log.counts.artifacts_recorded,
            "rejected": run_log.counts.rejected,
            "ambiguous_matches": run_log.counts.ambiguous_matches,
            "findings_generated": run_log.counts.findings_generated,
            "shadow_count": derived.shadow_count,
            "zombie_count": derived.zombie_count
        },
        "shadow_asset_keys": shadow_asset_keys,
        "zombie_asset_keys": zombie_asset_keys,
        "aod_lists": {
            "shadow_asset_keys_sample": shadow_asset_keys[:10],
            "zombie_asset_keys_sample": zombie_asset_keys[:10],
            "high_severity_findings": high_severity_findings,
            "actual_reason_codes": actual_reasons
        }
    }
    
    headers = {"Content-Type": "application/json"}
    
    shared_secret = os.environ.get("FARM_SHARED_SECRET")
    if shared_secret:
        headers["X-Farm-Shared-Secret"] = shared_secret
    
    reconcile_url = f"{base_url.rstrip('/')}/api/reconcile"
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                reconcile_url,
                json=reconcile_payload,
                headers=headers
            )
            
            if response.status_code in (200, 201, 202, 204):
                return True, None
            else:
                error_text = response.text[:200] if response.text else f"HTTP {response.status_code}"
                return False, f"Farm returned {response.status_code}: {error_text}"
                
    except httpx.ConnectError as e:
        return False, f"Connection error: {str(e)[:100]}"
    except httpx.TimeoutException:
        return False, "Request timed out"
    except Exception as e:
        return False, f"Unexpected error: {str(e)[:100]}"
