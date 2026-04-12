"""
Snapshot Cache - Per-tenant file-based cache for Farm snapshot data.

Provides offline resilience when Farm is unavailable.
Cache is per-tenant keyed; reads require tenant_id match. Single-slot cache
(which silently leaked cross-tenant data on snapshot_id collision) is gone.

Cache location: data/cache/tenants/{tenant_id}/
  - snapshot.json       Full snapshot payload from Farm
  - meta.json           Metadata for UI display
  - snapshot_list.json  Per-tenant snapshot listing for dropdown
"""

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

CACHE_DIR = Path(os.getenv("SNAPSHOT_CACHE_DIR", "data/cache"))
_TENANTS_SUBDIR = "tenants"

_SNAPSHOT_FILE = "snapshot.json"
_META_FILE = "meta.json"
_LIST_FILE = "snapshot_list.json"

_TENANT_ID_RE = re.compile(r"^[0-9a-fA-F-]{8,64}$")


def _validate_tenant_id(tenant_id: str) -> str:
    if not tenant_id or not isinstance(tenant_id, str):
        raise ValueError(f"tenant_id must be a non-empty string, got {tenant_id!r}")
    try:
        uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        if not _TENANT_ID_RE.match(tenant_id):
            raise ValueError(f"tenant_id must be a UUID, got {tenant_id!r}")
    return tenant_id


def _tenant_dir(tenant_id: str) -> Path:
    tid = _validate_tenant_id(tenant_id)
    path = CACHE_DIR / _TENANTS_SUBDIR / tid
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_json(tenant_id: str, filename: str, data: Any) -> bool:
    path = _tenant_dir(tenant_id) / filename
    try:
        with open(path, "w") as f:
            json.dump(data, f)
        return True
    except OSError as e:
        logger.error("cache.write_failed", extra={"tenant_id": tenant_id, "file": filename, "error": str(e)})
        return False


def _read_json(tenant_id: str, filename: str) -> Optional[Any]:
    try:
        _validate_tenant_id(tenant_id)
    except ValueError:
        return None
    path = CACHE_DIR / _TENANTS_SUBDIR / tenant_id / filename
    if not path.exists():
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error("cache.read_failed", extra={"tenant_id": tenant_id, "file": filename, "error": str(e)})
        return None


# =========================================================================
# Snapshot Payload Cache (full snapshot for re-running discovery)
# =========================================================================

def write_snapshot_cache(
    tenant_id: str,
    snapshot_id: str,
    snapshot_data: Dict[str, Any],
    snapshot_name: str = "",
    asset_count: int = 0,
    finding_count: int = 0,
    discovery_id: str = "",
) -> bool:
    """Write a tenant's most recent Farm snapshot to cache (write-through)."""
    if not snapshot_id:
        raise ValueError("snapshot_id is required")
    meta = {
        "tenant_id": tenant_id,
        "snapshot_id": snapshot_id,
        "snapshot_name": snapshot_name or snapshot_id,
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "aod_discovery_id": discovery_id,
        "asset_count": asset_count,
        "finding_count": finding_count,
        "farm_generated_at": (
            snapshot_data.get("meta", {}).get("created_at")
            or snapshot_data.get("meta", {}).get("generated_at")
        ),
        "schema_version": snapshot_data.get("meta", {}).get("schema_version", "unknown"),
    }

    snapshot_ok = _write_json(tenant_id, _SNAPSHOT_FILE, snapshot_data)
    meta_ok = _write_json(tenant_id, _META_FILE, meta)

    if snapshot_ok and meta_ok:
        logger.info("cache.snapshot.written", extra={
            "tenant_id": tenant_id,
            "snapshot_id": snapshot_id,
            "asset_count": asset_count,
        })
    return snapshot_ok and meta_ok


def read_snapshot_cache(tenant_id: str) -> Optional[Dict[str, Any]]:
    """Return the most recent cached snapshot for this tenant, or None."""
    return _read_json(tenant_id, _SNAPSHOT_FILE)


def get_cache_meta(tenant_id: str) -> Optional[Dict[str, Any]]:
    """Return cache metadata (snapshot_id, cached_at, etc.) for this tenant."""
    return _read_json(tenant_id, _META_FILE)


def has_cached_snapshot(tenant_id: str) -> bool:
    """True iff a cached snapshot exists for this tenant."""
    try:
        _validate_tenant_id(tenant_id)
    except ValueError:
        return False
    return (CACHE_DIR / _TENANTS_SUBDIR / tenant_id / _SNAPSHOT_FILE).exists()


def has_cached_snapshot_list(tenant_id: str) -> bool:
    try:
        _validate_tenant_id(tenant_id)
    except ValueError:
        return False
    return (CACHE_DIR / _TENANTS_SUBDIR / tenant_id / _LIST_FILE).exists()


# =========================================================================
# Snapshot List Cache (per-tenant, for populating the dropdown offline)
# =========================================================================

def write_snapshot_list_cache(tenant_id: str, snapshots: List[Dict[str, Any]]) -> bool:
    """Cache the snapshot listing for this tenant from Farm."""
    cache_data = {
        "tenant_id": tenant_id,
        "snapshots": snapshots,
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "count": len(snapshots),
    }
    ok = _write_json(tenant_id, _LIST_FILE, cache_data)
    if ok:
        logger.info("cache.snapshot_list.written", extra={"tenant_id": tenant_id, "count": len(snapshots)})
    return ok


def upsert_snapshot_list_entry(
    tenant_id: str,
    snapshot_id: str,
    created_at: str,
    name: str = "",
) -> bool:
    """Prepend or replace a single snapshot in the tenant's list cache."""
    existing = _read_json(tenant_id, _LIST_FILE) or {"snapshots": []}
    snapshots = [s for s in existing.get("snapshots", []) if s.get("snapshot_id") != snapshot_id]
    snapshots.insert(0, {
        "snapshot_id": snapshot_id,
        "tenant_id": tenant_id,
        "created_at": created_at,
        "name": name,
    })
    return write_snapshot_list_cache(tenant_id, snapshots)


def read_snapshot_list_cache(tenant_id: str) -> Optional[List[Dict[str, Any]]]:
    """Read cached snapshot listing for this tenant."""
    data = _read_json(tenant_id, _LIST_FILE)
    if data and isinstance(data, dict):
        return data.get("snapshots")
    return None


# =========================================================================
# Cache Management
# =========================================================================

def clear_cache() -> None:
    """Clear all cached tenant snapshot data (used in tests)."""
    tenants_dir = CACHE_DIR / _TENANTS_SUBDIR
    if not tenants_dir.exists():
        return
    for tenant_path in tenants_dir.iterdir():
        if tenant_path.is_dir():
            for filename in [_SNAPSHOT_FILE, _META_FILE, _LIST_FILE]:
                f = tenant_path / filename
                if f.exists():
                    f.unlink()
    logger.info("cache.cleared")
