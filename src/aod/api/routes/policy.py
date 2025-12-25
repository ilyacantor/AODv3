"""
Policy Configuration API.

Exposes the current policy configuration so that Farm (and other consumers)
can fetch and align with AOD's rules.
"""

from fastapi import APIRouter

from ...core.policy import get_current_config, reload_config

router = APIRouter(prefix="/policy", tags=["policy"])


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
