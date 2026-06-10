"""Farm route module — Farm-first with per-tenant cache fallback.

Apr 2026 rewrite: Phase 2. Cache-first was the wrong-snapshot bug; cache is
now per-tenant keyed and used only as a fallback when Farm is unreachable.
The snapshot route requires tenant_id (422 if missing). force=true disables
the fallback — a refresh must fail loudly rather than return stale data.
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


def _farm_error_response(error_type: str, error: str, status: int = 503) -> JSONResponse:
    """Return standardized JSON error for Farm failures."""
    return JSONResponse(
        status_code=status,
        content={"ok": False, "error": error_type, "detail": error}
    )


@router.get("/url")
async def get_farm_url_endpoint():
    """Get the configured Farm URL"""
    farm_url = get_farm_url()
    return {"farm_url": farm_url}


@router.get("/tenants")
async def list_farm_tenants():
    """List available tenants from Farm. Always live — tenant enumeration has
    no per-tenant cache. On Farm failure, surface 503 (A1)."""
    farm_client = get_farm_client()
    if not farm_client:
        return _farm_error_response("NO_FARM_URL", "No Farm URL configured")

    result = await farm_client.list_snapshots("", limit=100)

    if result.success:
        snapshots = result.snapshots or []
        tenants = sorted(set(s.get("tenant_id", "") for s in snapshots if s.get("tenant_id")))
        # I2/I5: operators see the entity business key, never the tenant UUID.
        # Farm's snapshot rows carry entity_id (pre-split rows: entity==tenant).
        entity_labels = {}
        for s_row in snapshots:
            t = s_row.get("tenant_id", "")
            if t and t not in entity_labels:
                entity_labels[t] = s_row.get("entity_id") or t
        return TenantListResponse(tenants=tenants, count=len(tenants),
                                  entity_labels=entity_labels)

    return _farm_error_response(result.error_type, result.error)


@router.get("/all-snapshots")
async def list_all_farm_snapshots():
    """List all snapshots across tenants. Always live. On Farm failure, 503."""
    farm_client = get_farm_client()
    if not farm_client:
        return _farm_error_response("NO_FARM_URL", "No Farm URL configured")

    result = await farm_client.list_snapshots("", limit=100)

    if result.success:
        return result.snapshots or []

    return _farm_error_response(result.error_type, result.error)


@router.get("/snapshots")
async def list_farm_snapshots(tenant_id: str, size: Optional[str] = None, force: bool = False):
    """List snapshots for a tenant. Farm-first with per-tenant list cache fallback.

    - force=false (load): Farm-first. On Farm failure, return cached list
      for this tenant if it exists; otherwise 503.
    - force=true (refresh): Farm-only. On Farm failure, 503 — no fallback.
    """
    if not tenant_id:
        return _farm_error_response("MISSING_TENANT_ID", "tenant_id query param is required", 422)

    farm_client = get_farm_client()
    if not farm_client:
        return _farm_error_response("NO_FARM_URL", "No Farm URL configured")

    result = await farm_client.list_snapshots(tenant_id, size=size)

    if result.success:
        snapshots = result.snapshots or []
        write_snapshot_list_cache(tenant_id, snapshots)
        return SnapshotListResponse(snapshots=snapshots, count=len(snapshots))

    if not force:
        cached = read_snapshot_list_cache(tenant_id)
        if cached:
            logger.info("farm.snapshots.cache_fallback", extra={
                "tenant_id": tenant_id, "count": len(cached),
            })
            return SnapshotListResponse(snapshots=cached, count=len(cached))

    return _farm_error_response(result.error_type, result.error)


@router.get("/snapshot")
async def get_farm_snapshot(snapshot_id: str, tenant_id: str, force: bool = False):
    """Fetch a specific snapshot. tenant_id REQUIRED (422 if missing).

    Farm-first: fetch from Farm, write-through to per-tenant cache on success.
    - force=false: on Farm failure, return per-tenant cached snapshot if any.
    - force=true: on Farm failure, 503 — no fallback.
    """
    if not tenant_id:
        return _farm_error_response("MISSING_TENANT_ID", "tenant_id query param is required", 422)

    farm_client = get_farm_client()
    if not farm_client:
        return _farm_error_response("NO_FARM_URL", "No Farm URL configured")

    result = await farm_client.fetch_snapshot(snapshot_id)

    if result.success and result.data is not None:
        schema_valid, schema_error = validate_schema_version(result.data)
        if schema_valid:
            snapshot_meta = result.data.get("meta", {}) or {}
            write_snapshot_cache(
                tenant_id=tenant_id,
                snapshot_id=snapshot_id,
                snapshot_data=result.data,
                snapshot_name=snapshot_meta.get("name", snapshot_id),
            )
            upsert_snapshot_list_entry(
                tenant_id=tenant_id,
                snapshot_id=snapshot_id,
                created_at=snapshot_meta.get("created_at", ""),
                name=snapshot_meta.get("name", ""),
            )
        else:
            logger.warning("farm.snapshot.schema_invalid_no_cache_write", extra={
                "tenant_id": tenant_id, "snapshot_id": snapshot_id, "error": schema_error,
            })
        return result.data

    if not force and has_cached_snapshot(tenant_id):
        cached = read_snapshot_cache(tenant_id)
        if cached:
            meta = get_cache_meta(tenant_id) or {}
            logger.info("farm.snapshot.cache_fallback", extra={
                "tenant_id": tenant_id,
                "requested_snapshot_id": snapshot_id,
                "cached_snapshot_id": meta.get("snapshot_id"),
            })
            return cached

    if result.error_type == "FARM_SNAPSHOT_NOT_FOUND":
        return JSONResponse(status_code=404, content={"detail": "Not Found", "error": result.error})
    return _farm_error_response(result.error_type, result.error)


@router.get("/status")
async def get_farm_status(tenant_id: Optional[str] = None):
    """Farm connectivity + optional per-tenant cache info.

    10s probe (matches load timeout). If tenant_id provided, reports whether
    a cache exists for that tenant.
    """
    farm_client = get_farm_client()

    farm_up = False
    if farm_client:
        farm_up = await farm_client.probe()

    cache_meta = None
    has_cache = False
    if tenant_id:
        cache_meta = get_cache_meta(tenant_id)
        has_cache = has_cached_snapshot(tenant_id) or has_cached_snapshot_list(tenant_id)

    return {
        "farm_available": farm_up,
        "farm_url": get_farm_url(),
        "cache_available": has_cache,
        "cache_meta": cache_meta,
        "mode": "live" if farm_up else ("cached" if has_cache else "unavailable"),
    }
