"""Farm-related route module"""

from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..schemas import TenantListResponse, SnapshotListResponse
from ..deps import get_farm_url, get_farm_client

router = APIRouter(prefix="/farm")


def _farm_error_response(error_type: str, error: str) -> JSONResponse:
    """Return standardized JSON error for Farm failures."""
    return JSONResponse(
        status_code=503,
        content={"ok": False, "error": error_type, "detail": error}
    )


@router.get("/url")
async def get_farm_url_endpoint():
    """Get the configured Farm URL"""
    farm_url = get_farm_url()
    return {"farm_url": farm_url}


@router.get("/tenants")
async def list_farm_tenants():
    """
    List available tenants from Farm.
    
    Fetches all snapshots and extracts unique tenant_ids.
    """
    farm_client = get_farm_client()
    if not farm_client:
        return _farm_error_response("NO_FARM_URL", "No Farm URL configured")
    
    result = await farm_client.list_snapshots("", limit=100)
    
    if not result.success:
        return _farm_error_response(result.error_type, result.error)
    
    snapshots = result.snapshots or []
    tenants = sorted(set(s.get("tenant_id", "") for s in snapshots if s.get("tenant_id")))
    return TenantListResponse(tenants=tenants, count=len(tenants))


@router.get("/all-snapshots")
async def list_all_farm_snapshots():
    """
    List all available snapshots from Farm (no tenant filter).
    
    Returns all snapshots sorted by created_at descending (most recent first).
    Used to find the latest snapshot across all tenants.
    """
    farm_client = get_farm_client()
    if not farm_client:
        return _farm_error_response("NO_FARM_URL", "No Farm URL configured")
    
    result = await farm_client.list_snapshots("", limit=100)
    
    if not result.success:
        return _farm_error_response(result.error_type, result.error)
    
    snapshots = result.snapshots or []
    return snapshots


@router.get("/snapshots")
async def list_farm_snapshots(tenant_id: str, size: Optional[str] = None):
    """
    List available snapshots from Farm for a tenant.
    
    Proxies to Farm /api/snapshots?tenant_id=<tenant>&limit=20&size=<size>
    Returns metadata list with snapshot_id, tenant_id, created_at, schema_version.
    
    Args:
        tenant_id: The tenant to filter snapshots by
        size: Optional size filter (small, medium, large)
    """
    farm_client = get_farm_client()
    if not farm_client:
        return _farm_error_response("NO_FARM_URL", "No Farm URL configured")
    
    result = await farm_client.list_snapshots(tenant_id, size=size)
    
    if not result.success:
        return _farm_error_response(result.error_type, result.error)
    
    snapshots = result.snapshots or []
    return SnapshotListResponse(
        snapshots=snapshots,
        count=len(snapshots)
    )


@router.get("/snapshot")
async def get_farm_snapshot(snapshot_id: str, tenant_id: Optional[str] = None):
    """
    Fetch a specific snapshot from Farm.
    
    Args:
        snapshot_id: The snapshot ID to fetch
        tenant_id: Optional tenant ID (not used by Farm, included for frontend compatibility)
    
    Returns:
        The full snapshot data from Farm
    """
    farm_client = get_farm_client()
    if not farm_client:
        return _farm_error_response("NO_FARM_URL", "No Farm URL configured")
    
    result = await farm_client.fetch_snapshot(snapshot_id)
    
    if not result.success:
        if result.error_type == "FARM_SNAPSHOT_NOT_FOUND":
            return JSONResponse(status_code=404, content={"detail": "Not Found", "error": result.error})
        return _farm_error_response(result.error_type, result.error)
    
    return result.data
