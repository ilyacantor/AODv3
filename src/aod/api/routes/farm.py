"""Farm-related route module with cache-first page loads.

Apr 2026: Cache-first on page load. The four read endpoints return the
last known cached state immediately without contacting Farm, and are
write-through on the Farm path so successful fetches keep the cache
fresh. The Refresh button passes force=true to bypass the cache and
re-pull from Farm; on force, a Farm failure is surfaced as 503 — no
silent fallback.
"""

import logging
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..schemas import TenantListResponse, SnapshotListResponse
from ..deps import get_farm_url, get_farm_client
from ...cache import (
    write_snapshot_cache,
    write_snapshot_list_cache,
    upsert_snapshot_list_entry,
    read_snapshot_list_cache,
    read_snapshot_cache,
    get_cache_meta,
    has_cached_snapshot,
    has_cached_snapshot_list,
)
from ...farm_client import validate_schema_version

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
async def list_farm_tenants(force: bool = False):
    """
    List available tenants from Farm.

    Cache-first: if the snapshot list cache has data and force is false,
    returns tenants from cache immediately without contacting Farm.
    Only calls Farm when cache is empty or force=true is passed (e.g. from
    the Refresh button). On Farm failure, surface loudly as 503 — no
    silent fallback to DB.
    """
    # Cache-first: page load returns immediately from cache, no Farm call
    if not force:
        cached_list = read_snapshot_list_cache()
        if cached_list:
            tenants = sorted(set(s.get("tenant_id", "") for s in cached_list if s.get("tenant_id")))
            logger.info("farm.tenants.cache_first_hit", extra={"count": len(tenants)})
            return TenantListResponse(tenants=tenants, count=len(tenants))

    farm_client = get_farm_client()
    if not farm_client:
        return _farm_error_response("NO_FARM_URL", "No Farm URL configured")

    result = await farm_client.list_snapshots("", limit=100)

    if result.success:
        snapshots = result.snapshots or []
        # Write-through: keep the cache fresh on every successful Farm fetch
        write_snapshot_list_cache(snapshots)
        tenants = sorted(set(s.get("tenant_id", "") for s in snapshots if s.get("tenant_id")))
        return TenantListResponse(tenants=tenants, count=len(tenants))

    # Farm failed — surface loud. The snapshot-list cache was checked at the
    # top of the function; if we got here with a cache miss, the operator
    # sees Farm-offline state rather than synthesized data.
    return _farm_error_response(result.error_type, result.error)


@router.get("/all-snapshots")
async def list_all_farm_snapshots(force: bool = False):
    """
    List all available snapshots from Farm (no tenant filter).

    Cache-first: returns cached snapshot list immediately on page load.
    Only contacts Farm when cache is empty or force=true. On force, the
    successful Farm response is written through to the cache.
    """
    # Cache-first: page load returns the last known list instantly
    if not force:
        cached_list = read_snapshot_list_cache()
        if cached_list:
            logger.info("farm.all_snapshots.cache_first_hit", extra={"count": len(cached_list)})
            return cached_list

    farm_client = get_farm_client()
    if not farm_client:
        return _farm_error_response("NO_FARM_URL", "No Farm URL configured")

    result = await farm_client.list_snapshots("", limit=100)

    if result.success:
        snapshots = result.snapshots or []
        # Write-through: update cache on every successful Farm fetch
        write_snapshot_list_cache(snapshots)
        return snapshots

    # force=true bypasses cache on both directions - raise loud
    # Non-force only reaches here on cache-miss, so no cache fallback to offer
    return _farm_error_response(result.error_type, result.error)


@router.get("/snapshots")
async def list_farm_snapshots(tenant_id: str, size: Optional[str] = None, force: bool = False):
    """
    List available snapshots from Farm for a tenant.

    Cache-first: returns the cached snapshot list filtered by tenant_id
    on page load. Only contacts Farm when cache is empty, the tenant is
    not represented in the cache, or force=true.
    """
    # Cache-first: page load returns filtered cached list instantly
    if not force:
        cached_list = read_snapshot_list_cache()
        if cached_list:
            filtered = [s for s in cached_list if s.get("tenant_id") == tenant_id]
            if filtered:
                logger.info("farm.snapshots.cache_first_hit", extra={
                    "tenant_id": tenant_id, "count": len(filtered)
                })
                return SnapshotListResponse(snapshots=filtered, count=len(filtered))

    farm_client = get_farm_client()
    if not farm_client:
        return _farm_error_response("NO_FARM_URL", "No Farm URL configured")

    result = await farm_client.list_snapshots(tenant_id, size=size)

    if result.success:
        snapshots = result.snapshots or []
        # Write-through: upsert each returned snapshot into the list cache
        # so this tenant's entries are fresh without dropping other tenants.
        # Never overwrite the whole list — that would clobber other tenants.
        for s in snapshots:
            snap_id = s.get("snapshot_id") or s.get("id")
            if not snap_id:
                continue
            upsert_snapshot_list_entry(
                snapshot_id=snap_id,
                tenant_id=s.get("tenant_id", tenant_id),
                created_at=s.get("created_at", ""),
                name=s.get("name", ""),
            )
        return SnapshotListResponse(
            snapshots=snapshots,
            count=len(snapshots)
        )

    # force=true bypasses cache on both directions - raise loud
    # Non-force only reaches here on cache-miss, so no cache fallback to offer
    return _farm_error_response(result.error_type, result.error)


@router.get("/snapshot")
async def get_farm_snapshot(snapshot_id: str, tenant_id: Optional[str] = None, force: bool = False):
    """
    Fetch a specific snapshot from Farm.

    Cache-first: if the cached snapshot matches the requested snapshot_id
    and force is false, returns from cache immediately without contacting
    Farm. Only calls Farm on cache mismatch or force=true. Falls back to
    cache if Farm is unavailable and the cached snapshot matches.
    """
    # Cache-first: page load returns cached snapshot instantly on match
    if not force and has_cached_snapshot():
        meta = get_cache_meta()
        if meta and meta.get("snapshot_id") == snapshot_id:
            cached = read_snapshot_cache()
            if cached:
                logger.info("farm.snapshot.cache_first_hit", extra={
                    "snapshot_id": snapshot_id
                })
                return cached

    farm_client = get_farm_client()
    if not farm_client:
        return _farm_error_response("NO_FARM_URL", "No Farm URL configured")

    result = await farm_client.fetch_snapshot(snapshot_id)

    if result.success and result.data is not None:
        # Write-through: replace cached snapshot blob, but ONLY after schema
        # validation passes. A partial or invalid response must never overwrite
        # a good cache — existing cache is the fallback when Farm is degraded.
        schema_valid, schema_error = validate_schema_version(result.data)
        if schema_valid:
            snapshot_meta = result.data.get("meta", {})
            write_snapshot_cache(
                snapshot_data=result.data,
                snapshot_id=snapshot_id,
                snapshot_name=snapshot_meta.get("name", snapshot_id),
                tenant_id=snapshot_meta.get("tenant_id") or (tenant_id or ""),
                # counts left at defaults (0) — they reflect discovery output,
                # not snapshot content. They'll be populated when discovery runs
                # against this snapshot via create_run_from_farm.
            )
            # Keep the list cache consistent so the dropdown reflects this
            # snapshot without another Farm round trip.
            upsert_snapshot_list_entry(
                snapshot_id=snapshot_id,
                tenant_id=snapshot_meta.get("tenant_id") or (tenant_id or ""),
                created_at=snapshot_meta.get("created_at", ""),
                name=snapshot_meta.get("name", ""),
            )
        else:
            logger.warning("farm.snapshot.schema_invalid_no_cache_write", extra={
                "snapshot_id": snapshot_id, "error": schema_error
            })
        return result.data

    # force=true bypasses cache on both directions - raise loud
    # Non-force only reaches here on cache-miss, so no cache fallback to offer
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
    has_cache = has_cached_snapshot() or has_cached_snapshot_list()

    return {
        "farm_available": farm_up,
        "farm_url": get_farm_url(),
        "cache_available": has_cache,
        "cache_meta": cache_meta,
        "mode": "live" if farm_up else ("cached" if has_cache else "unavailable"),
    }
