"""Farm reconciliation module - syncs AOD results back to Farm"""

import os
import httpx
import logging
from typing import Optional
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

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
    
    derived = compute_derived_classifications(assets, activity_window_days=30)
    
    # TRACE: Log derived classifications for debugging reconciliation
    logger.info(f"[RECONCILE-TRACE] snapshot_id={snapshot_id}")
    logger.info(f"[RECONCILE-TRACE] Total assets: {len(assets)}")
    logger.info(f"[RECONCILE-TRACE] Derived shadow_count={derived.shadow_count}, zombie_count={derived.zombie_count}, indeterminate={derived.indeterminate_count}")
    logger.info(f"[RECONCILE-TRACE] Shadow assets (vendor_keys): {[a.get('vendor_key', '') for a in derived.shadow_assets]}")
    logger.info(f"[RECONCILE-TRACE] Zombie assets (vendor_keys): {[a.get('vendor_key', '') for a in derived.zombie_assets]}")
    
    # Send vendor_key as canonical ID, with domain_key and display_name as evidence
    # vendor_key = internal canonical ID (e.g., 'yammer')
    # domain_key = legacy *com format for backward compatibility (e.g., 'yammercom')
    # domains = actual domain evidence if known
    shadow_asset_list = [
        {
            "vendor_key": a.get("vendor_key", ""),
            "domain_key": a.get("domain_key", ""),
            "domains": a.get("domains", []),
            "display_name": a.get("display_name", "")
        }
        for a in derived.shadow_assets[:10]
    ]
    zombie_asset_list = [
        {
            "vendor_key": a.get("vendor_key", ""),
            "domain_key": a.get("domain_key", ""),
            "domains": a.get("domains", []),
            "display_name": a.get("display_name", "")
        }
        for a in derived.zombie_assets[:10]
    ]
    
    high_severity_findings = [
        {
            "finding_type": f.finding_type.value,
            "severity": f.severity.value,
            "explanation": f.explanation[:200]
        }
        for f in findings
        if f.severity.value == "high"
    ][:10]
    
    # INVARIANT: summary counts MUST equal the actual payload list lengths (single source of truth)
    # Use the actual lists we're sending, not derived counts which may differ
    payload_shadow_count = len(shadow_asset_list)
    payload_zombie_count = len(zombie_asset_list)
    
    logger.info(f"[RECONCILE-TRACE] Payload counts: shadow={payload_shadow_count}, zombie={payload_zombie_count}")
    
    reconcile_payload = {
        "snapshot_id": snapshot_id,
        "tenant_id": run_log.tenant_id,
        "aod_run_id": run_log.run_id,
        "aod_status": run_log.status.value,
        "completed_at": run_log.completed_at.isoformat() if run_log.completed_at else now_pst().isoformat(),
        "aod_summary": {
            "observations_in": run_log.counts.observations_in,
            "candidates_out": run_log.counts.candidates_out,
            "assets_admitted": run_log.counts.assets_admitted,
            "artifacts_recorded": run_log.counts.artifacts_recorded,
            "rejected": run_log.counts.rejected,
            "ambiguous_matches": run_log.counts.ambiguous_matches,
            "findings_generated": run_log.counts.findings_generated,
            "shadow_count": payload_shadow_count,
            "zombie_count": payload_zombie_count
        },
        "aod_lists": {
            "shadow_assets": shadow_asset_list,
            "zombie_assets": zombie_asset_list,
            "high_severity_findings": high_severity_findings
        }
    }
    
    headers = {"Content-Type": "application/json"}
    
    shared_secret = os.environ.get("FARM_SHARED_SECRET")
    if shared_secret:
        headers["X-Farm-Shared-Secret"] = shared_secret
    
    reconcile_url = f"{base_url.rstrip('/')}/api/reconcile"
    
    # TRACE: Log the payload being sent to Farm
    logger.info(f"[RECONCILE-TRACE] Sending to Farm: {reconcile_url}")
    logger.info(f"[RECONCILE-TRACE] Payload aod_summary: {reconcile_payload['aod_summary']}")
    logger.info(f"[RECONCILE-TRACE] Payload aod_lists.shadow_assets: {reconcile_payload['aod_lists']['shadow_assets']}")
    logger.info(f"[RECONCILE-TRACE] Payload aod_lists.zombie_assets: {reconcile_payload['aod_lists']['zombie_assets']}")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                reconcile_url,
                json=reconcile_payload,
                headers=headers
            )
            
            # TRACE: Log Farm's response
            logger.info(f"[RECONCILE-TRACE] Farm response status: {response.status_code}")
            logger.info(f"[RECONCILE-TRACE] Farm response body: {response.text[:500] if response.text else '(empty)'}")
            
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
