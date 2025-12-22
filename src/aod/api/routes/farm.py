"""Farm-related route module"""

import os
from typing import Optional

from fastapi import APIRouter, HTTPException

from ..schemas import TenantListResponse, SnapshotListResponse
from ..deps import get_farm_url
from ...farm_client import FarmClient

router = APIRouter(prefix="/farm")


@router.get("/url")
async def get_farm_url_endpoint():
    """Get the configured Farm URL"""
    farm_url = os.environ.get("FARM_URL")
    return {"farm_url": farm_url}


@router.get("/tenants", response_model=TenantListResponse)
async def list_farm_tenants():
    """
    List available tenants from Farm.
    
    Fetches all snapshots and extracts unique tenant_ids.
    """
    farm_url = os.environ.get("FARM_URL")
    if not farm_url:
        raise HTTPException(status_code=400, detail="No Farm URL configured. Set FARM_URL environment variable.")
    
    farm_client = FarmClient(farm_url)
    result = await farm_client.list_snapshots("", limit=100)
    
    if not result.success:
        raise HTTPException(
            status_code=502,
            detail=f"{result.error_type}: {result.error}"
        )
    
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
    farm_url = os.environ.get("FARM_URL")
    if not farm_url:
        raise HTTPException(status_code=400, detail="No Farm URL configured. Set FARM_URL environment variable.")
    
    farm_client = FarmClient(farm_url)
    result = await farm_client.list_snapshots("", limit=100)
    
    if not result.success:
        raise HTTPException(
            status_code=502,
            detail=f"{result.error_type}: {result.error}"
        )
    
    snapshots = result.snapshots or []
    return snapshots


@router.get("/snapshots", response_model=SnapshotListResponse)
async def list_farm_snapshots(tenant_id: str, size: Optional[str] = None):
    """
    List available snapshots from Farm for a tenant.
    
    Proxies to {FARM_URL}/api/snapshots?tenant_id=<tenant>&limit=20&size=<size>
    Returns metadata list with snapshot_id, tenant_id, created_at, schema_version.
    
    Args:
        tenant_id: The tenant to filter snapshots by
        size: Optional size filter (small, medium, large)
    """
    farm_url = os.environ.get("FARM_URL")
    if not farm_url:
        raise HTTPException(status_code=400, detail="No Farm URL configured. Set FARM_URL environment variable.")
    
    farm_client = FarmClient(farm_url)
    result = await farm_client.list_snapshots(tenant_id, size=size)
    
    if not result.success:
        raise HTTPException(
            status_code=502,
            detail=f"{result.error_type}: {result.error}"
        )
    
    snapshots = result.snapshots or []
    return SnapshotListResponse(
        snapshots=snapshots,
        count=len(snapshots)
    )
