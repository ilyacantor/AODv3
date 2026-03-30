"""
Policy Configuration API.

Exposes the current policy configuration so that Farm (and other consumers)
can fetch and align with AOD's rules.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException

from ...core.policy import get_current_config, reload_config, save_config

router = APIRouter(prefix="/policy", tags=["policy"])
logger = logging.getLogger(__name__)

# Anchor to project root (src/../config) so path works regardless of cwd
POLICY_MASTER_PATH = Path(__file__).resolve().parents[4] / "config" / "policy_master.json"


async def _notify_farm_webhook(webhook_url: str, config_dict: dict) -> bool:
    """Send policy change notification to Farm webhook."""
    if not webhook_url:
        logger.warning("Farm webhook URL is empty, skipping notification")
        return False
    
    payload = {
        "event": "policy_changed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": config_dict
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(webhook_url, json=payload)
            response.raise_for_status()
            logger.info(f"Farm webhook notification sent successfully to {webhook_url}")
            return True
    except httpx.HTTPError as e:
        raise RuntimeError(f"Farm webhook notification failed: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Unexpected error sending Farm webhook: {e}") from e


@router.get("/config")
async def get_policy_config() -> dict:
    """
    Get the current policy configuration.
    
    Farm fetches this endpoint before simulation to ensure
    it uses the same thresholds and exclusion lists as AOD.
    
    Returns:
        Complete policy configuration including:
        - admission: Gate thresholds (minimum_spend, noise_floor, zombie_window_days)
        - scope: Mode toggles (include_infra, treat_directory_as_idp)
        - exclusions: Mutable customer exclusion list
        - seed_exclusions: Immutable seed lists (corporate_root_domains, infrastructure_domains)
    """
    config = get_current_config()
    return config.to_dict()


@router.post("/reload")
async def reload_policy_config() -> dict:
    """
    Hot-reload the policy configuration from disk.
    
    Call this after updating config/policy.json to pick up changes
    without restarting the server.
    
    Returns:
        The newly loaded policy configuration
    """
    config = reload_config()
    return {
        "status": "reloaded",
        "config": config.to_dict()
    }


@router.get("/master")
async def get_policy_master() -> dict:
    """
    Get the full policy_master.json content including metadata.
    
    Returns the raw JSON structure with type, min, max, description,
    and ui_label for each setting - suitable for UI rendering.
    
    Returns:
        Full policy master configuration with metadata
    """
    if not POLICY_MASTER_PATH.exists():
        raise HTTPException(status_code=404, detail="Policy master file not found")
    
    try:
        with open(POLICY_MASTER_PATH) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Invalid JSON in policy master: {e}")
    except IOError as e:
        raise HTTPException(status_code=500, detail=f"Error reading policy master: {e}")


@router.get("/manifest")
async def get_policy_manifest(scan_session_id: str | None = None) -> dict:
    """
    Get a versioned policy manifest for a DiscoveryScan session.
    
    Exports policy_master.json into a manifest format suitable for downstream
    consumers (AAM, Farm, etc.). The manifest includes all governance rules
    extracted from the policy configuration.
    
    Args:
        scan_session_id: Optional DiscoveryScan session ID to associate with manifest.
                        If provided, links this manifest to a specific scan session.
    
    Returns:
        Policy manifest containing:
        - manifest_version: Version of the manifest format
        - policy_version: Version from policy_master.json
        - generated_at: ISO timestamp of when manifest was generated
        - scan_session_id: Associated DiscoveryScan session (if provided)
        - governance_rules: All governance rules (admission_gates, idp_governance,
          scope_toggles, infrastructure_domain_handling, finance_thresholds,
          activity_windows, connection_policy)
    """
    from ...core.policy.manifest import PolicyManifestBuilder
    
    try:
        builder = PolicyManifestBuilder()
        return builder.build_manifest(scan_session_id=scan_session_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error building policy manifest: {e}")
        raise HTTPException(status_code=500, detail=f"Error building policy manifest: {e}")


def _deep_merge(base: dict, updates: dict) -> dict:
    """Deep merge updates into base dictionary."""
    result = base.copy()
    for key, value in updates.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _extract_value(setting: Any) -> Any:
    """Extract value from a setting dict or return as-is."""
    if isinstance(setting, dict) and "value" in setting:
        return setting["value"]
    return setting


@router.put("/master")
async def update_policy_master(
    updates: dict,
    background_tasks: BackgroundTasks
) -> dict:
    """
    Update the policy master configuration.
    
    Accepts partial updates - only sections/fields provided are updated.
    Triggers Farm webhook notification if auto_notify_on_change is true.
    
    Args:
        updates: Partial update dictionary with sections/settings to update
    
    Returns:
        The updated policy master configuration
    """
    if not POLICY_MASTER_PATH.exists():
        raise HTTPException(status_code=404, detail="Policy master file not found")
    
    try:
        with open(POLICY_MASTER_PATH) as f:
            current_data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"Error reading policy master: {e}")
    
    merged_data = _deep_merge(current_data, updates)
    merged_data["last_modified"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    try:
        with open(POLICY_MASTER_PATH, "w") as f:
            json.dump(merged_data, f, indent=2)
    except IOError as e:
        raise HTTPException(status_code=500, detail=f"Error saving policy master: {e}")
    
    reload_config()
    
    farm_sync = merged_data.get("farm_sync", {})
    auto_notify = _extract_value(farm_sync.get("auto_notify_on_change", {}))
    webhook_url = _extract_value(farm_sync.get("webhook_url", {}))
    
    if auto_notify and webhook_url:
        background_tasks.add_task(_notify_farm_webhook, webhook_url, merged_data)
        logger.info("Scheduled Farm webhook notification in background")
    
    return merged_data


@router.post("/notify-farm")
async def notify_farm() -> dict:
    """
    Manually trigger Farm notification with current policy config.
    
    Reads webhook_url from current config and sends POST to Farm
    with the current policy configuration.
    
    Returns:
        Success/failure status of the notification
    """
    config = get_current_config()
    webhook_url = config.farm_sync.webhook_url
    
    if not webhook_url:
        raise HTTPException(
            status_code=400,
            detail="Farm webhook URL is not configured. Set farm_sync.webhook_url in policy_master.json"
        )
    
    if not POLICY_MASTER_PATH.exists():
        raise HTTPException(status_code=404, detail="Policy master file not found")
    
    try:
        with open(POLICY_MASTER_PATH) as f:
            config_dict = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"Error reading policy master: {e}")
    
    success = await _notify_farm_webhook(webhook_url, config_dict)
    
    if success:
        return {
            "status": "success",
            "message": f"Farm notification sent to {webhook_url}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    else:
        return {
            "status": "failed",
            "message": f"Failed to send notification to {webhook_url}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@router.get("/impact")
async def get_policy_impact(run_id: str | None = None) -> dict:
    """
    Get the impact of current policy configuration on a specific run.
    
    Shows which domains are being blocked/rejected by each policy rule
    and how many assets are affected. This helps operators understand
    the real-world effect of their policy settings.
    
    Args:
        run_id: Optional run ID. If not provided, uses the latest run.
    
    Returns:
        Policy impact summary including blocked domains by policy rule
    """
    from ...db.database import get_db_direct
    
    db = await get_db_direct()
    
    if not run_id:
        runs = await db.get_all_runs()
        if not runs:
            return {
                "status": "no_runs",
                "message": "No runs available to analyze policy impact"
            }
        runs.sort(key=lambda r: r.started_at or "", reverse=True)
        run_id = runs[0].run_id
    
    run = await db.get_run(run_id)
    if not run:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    rejections, total = await db.get_rejections_by_run(run_id, limit=2000)
    
    policy_impact = {
        "shared_infrastructure": {"count": 0, "domains": []},
        "vendor_root_portals": {"count": 0, "domains": []},
        "dev_build_infrastructure": {"count": 0, "domains": []},
        "custom_exclusions": {"count": 0, "domains": []},
        "admission_gates": {"count": 0, "domains": []},
        "other": {"count": 0, "domains": []}
    }
    
    for rej in rejections:
        reason_detail = rej.get("reason_detail", "") or ""
        entity_key = rej.get("entity_key", "")
        entity_name = rej.get("entity_name", "")
        
        if entity_key.startswith("entity:"):
            domain = entity_key[7:]
        else:
            domain = entity_name
        
        domain_info = {"domain": domain, "name": entity_name, "detail": reason_detail}
        reason_upper = reason_detail.upper()
        
        if "SHARED_INFRASTRUCTURE" in reason_upper or "CDN" in reason_upper or "STATIC_HOST" in reason_upper:
            policy_impact["shared_infrastructure"]["count"] += 1
            policy_impact["shared_infrastructure"]["domains"].append(domain_info)
        elif "VENDOR_PORTAL" in reason_upper or "VENDOR_ROOT" in reason_upper:
            policy_impact["vendor_root_portals"]["count"] += 1
            policy_impact["vendor_root_portals"]["domains"].append(domain_info)
        elif "DEV_BUILD" in reason_upper or "BUILD_INFRASTRUCTURE" in reason_upper:
            policy_impact["dev_build_infrastructure"]["count"] += 1
            policy_impact["dev_build_infrastructure"]["domains"].append(domain_info)
        elif "BANNED_DOMAINS" in reason_upper or "INFRASTRUCTURE" in reason_upper:
            policy_impact["shared_infrastructure"]["count"] += 1
            policy_impact["shared_infrastructure"]["domains"].append(domain_info)
        elif "CUSTOM" in reason_upper or "EXCLUSION" in reason_upper:
            policy_impact["custom_exclusions"]["count"] += 1
            policy_impact["custom_exclusions"]["domains"].append(domain_info)
        elif any(gate in reason_upper for gate in ["NOISE_FLOOR", "MINIMUM_SPEND", "ADMISSION", "GATE"]):
            policy_impact["admission_gates"]["count"] += 1
            policy_impact["admission_gates"]["domains"].append(domain_info)
        else:
            policy_impact["other"]["count"] += 1
            policy_impact["other"]["domains"].append(domain_info)
    
    for category in policy_impact.values():
        category["domains"] = category["domains"][:50]
    
    config = get_current_config()
    
    idh = config.infrastructure_domain_handling
    return {
        "aod_discovery_id": run_id,
        "run_status": run.status.value,
        "total_rejections": total,
        "policy_impact": policy_impact,
        "current_policy": {
            "shared_infrastructure_count": len(idh.shared_infrastructure_domains) if idh else 0,
            "vendor_portals_count": len(idh.vendor_root_portals) if idh else 0,
            "dev_build_count": len(idh.dev_build_infrastructure) if idh else 0,
            "custom_exclusions_count": len(config.custom_exclusions_config.domains) if config.custom_exclusions_config else 0
        }
    }
