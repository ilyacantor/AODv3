"""Farm reconciliation module - syncs AOD results back to Farm"""

import os
import httpx
from typing import Optional, Any
from datetime import datetime, timezone, timedelta

PST = timezone(timedelta(hours=-8))

def now_pst() -> datetime:
    return datetime.now(PST)

from .models.output_contracts import RunLog, Asset, Finding, SyncStatus
from .pipeline.aod_agent_reconcile import emit_actual_results


def build_reconcile_payload(
    run_log: RunLog,
    assets: list[Asset],
    findings: list[Finding],
    snapshot_id: str,
    rejections: list[dict] | None = None,
    mode: str = "sprawl"
) -> dict[str, Any]:
    """
    Build the reconcile payload for Farm.
    
    SINGLE SOURCE OF TRUTH for payload structure.
    Used by both reconcile_to_farm() and /api/runs/{run_id}/reconcile-payload endpoint.
    
    Args:
        run_log: The completed run log
        assets: List of admitted assets
        findings: List of generated findings
        snapshot_id: The source snapshot ID
        rejections: Optional list of rejected candidates
        mode: Reconciliation mode - "sprawl" (SaaS only) or "infra" (all assets)
    
    Returns:
        The reconcile payload dict ready to be sent to Farm or returned via API
    """
    actual_results = emit_actual_results(
        run_id=run_log.run_id,
        assets=assets,
        activity_window_days=90,
        rejections=rejections,
        mode=mode
    )
    
    high_severity_findings = [
        f"{f.finding_type.value}: {f.explanation[:150]}"
        for f in findings
        if f.severity.value == "high"
    ][:10]
    
    aod_callback_url = os.environ.get("REPLIT_DEV_DOMAIN", "")
    if aod_callback_url and not aod_callback_url.startswith("http"):
        aod_callback_url = f"https://{aod_callback_url}"
    
    asset_summaries = {}
    for key, reasons in actual_results.actual_reasons.items():
        details = actual_results.asset_details.get(key, {})
        decision = actual_results.admission_actual.get(key, "unknown")
        
        reason_codes = reasons if reasons else ["NO_REASON_DATA"]
        
        asset_summaries[key] = {
            "aod_decision": decision,
            "aod_reason_codes": reason_codes,
            "is_shadow": details.get("is_shadow", False),
            "is_zombie": details.get("is_zombie", False),
            "evidence_summary": details.get("evidence_summary", {})
        }
    
    shadow_asset_keys = sorted([k for k, v in asset_summaries.items() if v.get("is_shadow")])
    zombie_asset_keys = sorted([k for k, v in asset_summaries.items() if v.get("is_zombie")])
    
    return {
        "payload_version": 2,
        "has_asset_summaries": len(asset_summaries) > 0,
        "asset_summaries_count": len(asset_summaries),
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
            "shadow_count": len(shadow_asset_keys),
            "zombie_count": len(zombie_asset_keys)
        },
        "shadow_asset_keys": shadow_asset_keys,
        "zombie_asset_keys": zombie_asset_keys,
        "asset_summaries": asset_summaries,
        "aod_lists": {
            "shadow_asset_keys_sample": shadow_asset_keys[:10],
            "zombie_asset_keys_sample": zombie_asset_keys[:10],
            "high_severity_findings": high_severity_findings,
            "actual_reason_codes": actual_results.actual_reasons,
            "asset_summaries": asset_summaries
        }
    }


async def reconcile_to_farm(
    run_log: RunLog,
    assets: list[Asset],
    findings: list[Finding],
    snapshot_id: str,
    farm_url: Optional[str] = None,
    rejections: list[dict] | None = None,
    mode: str = "sprawl"
) -> tuple[bool, Optional[str]]:
    """
    Reconcile AOD results back to Farm.
    
    POSTs a summary of the run results to {FARM_URL}/api/reconcile
    
    Uses build_reconcile_payload() which is the single source of truth for
    payload structure, shared with the /api/runs/{run_id}/reconcile-payload endpoint.
    
    Args:
        run_log: The completed run log
        assets: List of admitted assets
        findings: List of generated findings
        snapshot_id: The source snapshot ID
        farm_url: Optional Farm URL override (uses FARM_URL env var if not provided)
        rejections: Optional list of rejected candidates
        mode: Reconciliation mode - "sprawl" (SaaS only) or "infra" (all assets)
    
    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    base_url = farm_url or os.environ.get("FARM_URL")
    if not base_url:
        return False, "No Farm URL configured"
    
    reconcile_payload = build_reconcile_payload(
        run_log=run_log,
        assets=assets,
        findings=findings,
        snapshot_id=snapshot_id,
        rejections=rejections,
        mode=mode
    )
    
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
