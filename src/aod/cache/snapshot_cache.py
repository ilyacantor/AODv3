"""
Snapshot Cache - File-based cache for Farm snapshot data.

Provides offline resilience when Farm is unavailable.
Cache is written on every successful discovery run from Farm.
Cache is read as fallback when Farm is unreachable.

Cache location: data/cache/ (configurable via SNAPSHOT_CACHE_DIR)
Files:
  - latest_snapshot.json   Full snapshot payload from Farm
  - latest_meta.json       Metadata for UI display
  - snapshot_list.json     Snapshot listing for dropdown

Design decisions:
  - File-based, not DB: Survives DB resets, easy to inspect/debug
  - Single snapshot only: Not a growing collection
  - Write-through: When Farm is up, cache is transparently updated
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

CACHE_DIR = Path(os.getenv("SNAPSHOT_CACHE_DIR", "data/cache"))

_SNAPSHOT_FILE = "latest_snapshot.json"
_META_FILE = "latest_meta.json"
_LIST_FILE = "snapshot_list.json"


def _ensure_cache_dir() -> Path:
    """Ensure cache directory exists."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR


def _write_json(filename: str, data: Any) -> bool:
    """Write JSON data to cache file. Returns True on success."""
    try:
        path = _ensure_cache_dir() / filename
        with open(path, "w") as f:
            json.dump(data, f)
        return True
    except Exception as e:
        logger.error("cache.write_failed", extra={"file": filename, "error": str(e)})
        return False


def _read_json(filename: str) -> Optional[Any]:
    """Read JSON data from cache file. Returns None if not found."""
    path = CACHE_DIR / filename
    if not path.exists():
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error("cache.read_failed", extra={"file": filename, "error": str(e)})
        return None


# =========================================================================
# Snapshot Payload Cache (full snapshot for re-running discovery)
# =========================================================================

def write_snapshot_cache(
    snapshot_data: Dict[str, Any],
    snapshot_id: str,
    snapshot_name: str = "",
    tenant_id: str = "",
    asset_count: int = 0,
    finding_count: int = 0,
    run_id: str = "",
) -> bool:
    """
    Cache a snapshot after successful Farm-sourced discovery.

    Args:
        snapshot_data: Full snapshot payload (exactly what Farm returned)
        snapshot_id: Farm snapshot ID
        snapshot_name: Human-readable snapshot name
        tenant_id: Tenant ID
        asset_count: Assets discovered in this run
        finding_count: Findings generated in this run
        run_id: The discovery run_id

    Returns:
        True if cache was written successfully
    """
    meta = {
        "snapshot_id": snapshot_id,
        "snapshot_name": snapshot_name or snapshot_id,
        "tenant_id": tenant_id,
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "discovery_run_id": run_id,
        "asset_count": asset_count,
        "finding_count": finding_count,
        "farm_generated_at": (
            snapshot_data.get("meta", {}).get("created_at")
            or snapshot_data.get("meta", {}).get("generated_at")
        ),
        "schema_version": snapshot_data.get("meta", {}).get("schema_version", "unknown"),
    }

    snapshot_ok = _write_json(_SNAPSHOT_FILE, snapshot_data)
    meta_ok = _write_json(_META_FILE, meta)

    if snapshot_ok and meta_ok:
        logger.info("cache.snapshot.written", extra={
            "snapshot_id": snapshot_id,
            "tenant_id": tenant_id,
            "asset_count": asset_count,
        })
    return snapshot_ok and meta_ok


def read_snapshot_cache() -> Optional[Dict[str, Any]]:
    """
    Read cached snapshot payload.

    Returns None if no cache exists.
    """
    return _read_json(_SNAPSHOT_FILE)


def get_cache_meta() -> Optional[Dict[str, Any]]:
    """
    Read cache metadata (snapshot_id, cached_at, etc.).

    Returns None if no cache exists.
    """
    return _read_json(_META_FILE)


def has_cached_snapshot() -> bool:
    """Check if a cached snapshot exists."""
    return (CACHE_DIR / _SNAPSHOT_FILE).exists()


def has_cached_snapshot_list() -> bool:
    """Check if a cached snapshot list exists (for tenant dropdown)."""
    return (CACHE_DIR / _LIST_FILE).exists()


# =========================================================================
# Snapshot List Cache (for populating the dropdown in offline mode)
# =========================================================================

def write_snapshot_list_cache(snapshots: List[Dict[str, Any]]) -> bool:
    """
    Cache the snapshot listing from Farm.

    Written every time we successfully list snapshots from Farm.
    Used to populate the dropdown when Farm is unavailable.
    """
    cache_data = {
        "snapshots": snapshots,
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "count": len(snapshots),
    }
    ok = _write_json(_LIST_FILE, cache_data)
    if ok:
        logger.info("cache.snapshot_list.written", extra={"count": len(snapshots)})
    return ok


def upsert_snapshot_list_entry(
    snapshot_id: str,
    tenant_id: str,
    created_at: str,
    name: str = "",
) -> bool:
    """Update or prepend a single snapshot in the list cache.

    Called after a successful discovery run so the list cache stays
    consistent with the runs DB without an extra Farm round trip.
    """
    existing = _read_json(_LIST_FILE) or {"snapshots": [], "cached_at": None, "count": 0}
    snapshots = [s for s in existing.get("snapshots", []) if s.get("snapshot_id") != snapshot_id]
    snapshots.insert(0, {
        "snapshot_id": snapshot_id,
        "tenant_id": tenant_id,
        "created_at": created_at,
        "name": name,
    })
    return write_snapshot_list_cache(snapshots)


def read_snapshot_list_cache() -> Optional[List[Dict[str, Any]]]:
    """
    Read cached snapshot listing.

    Returns None if no cache exists.
    """
    data = _read_json(_LIST_FILE)
    if data and isinstance(data, dict):
        return data.get("snapshots")
    return None


# =========================================================================
# Cache Management
# =========================================================================

def clear_cache() -> None:
    """Clear all cached snapshot data (for testing)."""
    for filename in [_SNAPSHOT_FILE, _META_FILE, _LIST_FILE]:
        path = CACHE_DIR / filename
        if path.exists():
            path.unlink()
    logger.info("cache.cleared")
