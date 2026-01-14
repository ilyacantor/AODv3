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

POLICY_MASTER_PATH = Path("config/policy_master.json")


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
        logger.error(f"Farm webhook notification failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending Farm webhook: {e}")
        return False


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
