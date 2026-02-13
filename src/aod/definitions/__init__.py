"""
Farm Definitions Module - Authoritative Vendor & Domain Registry.

AOD is a DUMB CONSUMER of vendor/domain definitions.
All authoritative definitions come from Farm and are cached locally.

This module provides:
- FarmDefinitions: Cached vendor/domain registry synced from Farm
- get_definitions(): Global accessor for cached definitions
- sync_from_farm(): Pull latest definitions from Farm

ARCHITECTURAL PRINCIPLE:
AOD should NOT maintain its own vendor_registry table.
That creates drift from Farm (the central brain).
Instead, AOD pulls the authoritative list from Farm and caches in memory/Redis.
"""

from .registry import (
    FarmDefinitions,
    VendorEntry,
    FabricVendorPatterns,
    SaaSRoutingEntry,
    get_definitions,
    sync_from_farm,
    clear_cache,
)

__all__ = [
    "FarmDefinitions",
    "VendorEntry",
    "FabricVendorPatterns",
    "SaaSRoutingEntry",
    "get_definitions",
    "sync_from_farm",
    "clear_cache",
]
