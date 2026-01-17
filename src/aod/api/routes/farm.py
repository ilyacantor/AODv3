"""Farm-related route module with automatic dev/prod fallback"""

from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..schemas import TenantListResponse, SnapshotListResponse
from ...farm_url_resolver import fetch_from_farm

router = APIRouter(prefix="/farm")


@router.get("/url")
async def get_farm_url_endpoint():
    """Get the configured Farm URL mode and status"""
    from ...farm_url_resolver import get_farm_config
    config = get_farm_config()
    return {
        "mode": config.mode,
        "dev_url": config.dev_url or "(not configured)",
        "prod_url": config.prod_url,
    }


@router.get("/tenants")
async def list_farm_tenants():
    """
    List available tenants from Farm.
    
    Fetches all snapshots and extracts unique tenant_ids.
    Uses automatic fallback from dev to prod if dev is unavailable.
    """
    result = await fetch_from_farm("/api/snapshots?tenant_id=&limit=100")
    
    if not result.ok:
        return JSONResponse(
            status_code=200,
            content={
                "tenants": [],
                "count": 0,
                "warning": result.warning or "Farm unavailable",
                "error": result.error,
                "mode": result.mode,
                "attempted": result.attempted,
            }
        )
    
    snapshots = result.data if isinstance(result.data, list) else []
    tenants = sorted(set(s.get("tenant_id", "") for s in snapshots if s.get("tenant_id")))
    
    response_data: dict = {
        "tenants": tenants,
        "count": len(tenants),
    }
    
    if result.warning:
        response_data["warning"] = result.warning
    if result.used_url:
        response_data["source"] = result.used_url
    
    return response_data


@router.get("/all-snapshots")
async def list_all_farm_snapshots():
    """
    List all available snapshots from Farm (no tenant filter).
    
    Returns all snapshots sorted by created_at descending (most recent first).
    Uses automatic fallback from dev to prod if dev is unavailable.
    """
    result = await fetch_from_farm("/api/snapshots?tenant_id=&limit=100")
    
    if not result.ok:
        return JSONResponse(
            status_code=200,
            content={
                "snapshots": [],
                "warning": result.warning or "Farm unavailable",
                "error": result.error,
                "mode": result.mode,
                "attempted": result.attempted,
            }
        )
    
    snapshots = result.data if isinstance(result.data, list) else []
    
    response_data: dict = {
        "snapshots": snapshots,
    }
    
    if result.warning:
        response_data["warning"] = result.warning
    if result.used_url:
        response_data["source"] = result.used_url
    
    return response_data


@router.get("/snapshots", response_model=SnapshotListResponse)
async def list_farm_snapshots(tenant_id: str, size: Optional[str] = None):
    """
    List available snapshots from Farm for a tenant.
    
    Args:
        tenant_id: The tenant to filter snapshots by
        size: Optional size filter (small, medium, large)
    """
    path = f"/api/snapshots?tenant_id={tenant_id}&limit=20"
    if size:
        path += f"&size={size}"
    
    result = await fetch_from_farm(path)
    
    if not result.ok:
        return JSONResponse(
            status_code=200,
            content={
                "snapshots": [],
                "count": 0,
                "warning": result.warning or "Farm unavailable",
                "error": result.error,
                "mode": result.mode,
                "attempted": result.attempted,
            }
        )
    
    snapshots = result.data if isinstance(result.data, list) else []
    
    if result.warning:
        return JSONResponse(
            status_code=200,
            content={
                "snapshots": snapshots,
                "count": len(snapshots),
                "warning": result.warning,
                "source": result.used_url,
            }
        )
    
    return SnapshotListResponse(
        snapshots=snapshots,
        count=len(snapshots)
    )
