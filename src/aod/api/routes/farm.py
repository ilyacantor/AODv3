"""Farm-related route module with offline cache fallback.

Feb 2026: Added transparent cache layer for Farm resilience.
When Farm is up: normal flow + write-through cache update.
When Farm is down: serve from cache immediately, no blocking wait.
"""

import logging
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..schemas import TenantListResponse, SnapshotListResponse
from ..deps import get_farm_url, get_farm_client
from ...cache import (
    write_snapshot_list_cache,
    read_snapshot_list_cache,
    read_snapshot_cache,
    get_cache_meta,
    has_cached_snapshot,
    has_cached_snapshot_list,
)

logger = logging.getLogger(__name__)

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
    Falls back to cached snapshot list if Farm is unavailable.
    """
    farm_client = get_farm_client()
    if not farm_client:
        return _farm_error_response("NO_FARM_URL", "No Farm URL configured")

    result = await farm_client.list_snapshots("", limit=100)

    if result.success:
        snapshots = result.snapshots or []
        tenants = sorted(set(s.get("tenant_id", "") for s in snapshots if s.get("tenant_id")))
        return TenantListResponse(tenants=tenants, count=len(tenants))

    # Farm unavailable - try cache
    cached_list = read_snapshot_list_cache()
    if cached_list:
        tenants = sorted(set(s.get("tenant_id", "") for s in cached_list if s.get("tenant_id")))
        logger.info("farm.tenants.from_cache", extra={"count": len(tenants)})
        return TenantListResponse(tenants=tenants, count=len(tenants))

    return _farm_error_response(result.error_type, result.error)


@router.get("/all-snapshots")
async def list_all_farm_snapshots():
    """
    List all available snapshots from Farm (no tenant filter).

    Returns all snapshots sorted by created_at descending.
    If Farm is unavailable, serves from cache with offline_mode flag.
    """
    farm_client = get_farm_client()
    if not farm_client:
        return _farm_error_response("NO_FARM_URL", "No Farm URL configured")

    result = await farm_client.list_snapshots("", limit=100)

    if result.success:
        snapshots = result.snapshots or []
        # Write-through: update cache on every successful Farm fetch
        write_snapshot_list_cache(snapshots)
        return snapshots

    # Farm unavailable - fall back to cache
    cached_list = read_snapshot_list_cache()
    if cached_list:
        meta = get_cache_meta()
        cached_at = meta.get("cached_at", "unknown") if meta else "unknown"
        logger.info("farm.all_snapshots.from_cache", extra={
            "count": len(cached_list), "cached_at": cached_at
        })
        return JSONResponse(content={
            "snapshots": cached_list,
            "offline_mode": True,
            "cached_at": cached_at,
            "detail": "Farm unavailable. Showing cached snapshot list.",
        })

    return _farm_error_response(result.error_type, result.error)


@router.get("/snapshots")
async def list_farm_snapshots(tenant_id: str, size: Optional[str] = None):
    """
    List available snapshots from Farm for a tenant.

    Falls back to cached list filtered by tenant_id if Farm is unavailable.
    """
    farm_client = get_farm_client()
    if not farm_client:
        return _farm_error_response("NO_FARM_URL", "No Farm URL configured")

    result = await farm_client.list_snapshots(tenant_id, size=size)

    if result.success:
        snapshots = result.snapshots or []
        return SnapshotListResponse(
            snapshots=snapshots,
            count=len(snapshots)
        )

    # Farm unavailable - try cache filtered by tenant
    cached_list = read_snapshot_list_cache()
    if cached_list:
        filtered = [s for s in cached_list if s.get("tenant_id") == tenant_id]
        logger.info("farm.snapshots.from_cache", extra={
            "tenant_id": tenant_id, "count": len(filtered)
        })
        return SnapshotListResponse(
            snapshots=filtered,
            count=len(filtered)
        )

    return _farm_error_response(result.error_type, result.error)


@router.get("/snapshot")
async def get_farm_snapshot(snapshot_id: str, tenant_id: Optional[str] = None):
    """
    Fetch a specific snapshot from Farm.

    Falls back to cached snapshot if Farm is unavailable
    and cached snapshot matches the requested snapshot_id.
    """
    farm_client = get_farm_client()
    if not farm_client:
        return _farm_error_response("NO_FARM_URL", "No Farm URL configured")

    result = await farm_client.fetch_snapshot(snapshot_id)

    if result.success:
        return result.data

    # Farm unavailable - check if cached snapshot matches
    if has_cached_snapshot():
        meta = get_cache_meta()
        if meta and meta.get("snapshot_id") == snapshot_id:
            cached = read_snapshot_cache()
            if cached:
                logger.info("farm.snapshot.from_cache", extra={
                    "snapshot_id": snapshot_id
                })
                return cached

    if result.error_type == "FARM_SNAPSHOT_NOT_FOUND":
        return JSONResponse(status_code=404, content={"detail": "Not Found", "error": result.error})
    return _farm_error_response(result.error_type, result.error)


@router.get("/status")
async def get_farm_status():
    """
    Get Farm connection status and cache info.

    Fast probe (1s timeout) - doesn't block the UI.
    Returns whether Farm is reachable and what cache data is available.
    cache_available is true if EITHER snapshot OR snapshot_list cache exists.
    """
    farm_client = get_farm_client()

    farm_up = False
    if farm_client:
        farm_up = await farm_client.probe()

    cache_meta = get_cache_meta()
    # Cache is available if either snapshot or snapshot list is cached
    has_cache = has_cached_snapshot() or has_cached_snapshot_list()

    return {
        "farm_available": farm_up,
        "farm_url": get_farm_url(),
        "cache_available": has_cache,
        "cache_meta": cache_meta,
        "mode": "live" if farm_up else ("cached" if has_cache else "unavailable"),
    }
