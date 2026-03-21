"""
Resolve entity_id for triple conversion.

Entity_id is required for writing triples to the DCL triple store.
It identifies the business entity (e.g., Meridian, Cascadia) whose
discovery data is being recorded.

Resolution order:
1. Explicit parameter (from API request)
2. Snapshot metadata (from Farm)
3. AOD_DEFAULT_ENTITY_ID environment variable
4. FAIL LOUDLY — no silent fallback, no querying the triples table

This follows the same pattern as Farm's entity_id resolution
(manifest.target.entity_id → FARM_DEFAULT_ENTITY_ID → fail).
"""

import os
import logging

logger = logging.getLogger(__name__)


def resolve_entity_id(
    snapshot_data: dict | None = None,
    request_entity_id: str | None = None,
) -> str:
    """Resolve entity_id from available sources.

    Args:
        snapshot_data: Raw snapshot JSON (may contain meta.entity_id).
        request_entity_id: Explicit entity_id from the API request.

    Returns:
        Resolved entity_id string.

    Raises:
        ValueError: If no entity_id can be resolved from any source.
    """
    # 1. Explicit parameter takes priority
    if request_entity_id:
        return request_entity_id

    # 2. Snapshot metadata (Farm snapshots carry entity_id in meta)
    if snapshot_data:
        meta = snapshot_data.get("meta", {})
        snapshot_entity_id = meta.get("entity_id")
        if snapshot_entity_id:
            return snapshot_entity_id

    # 3. Environment variable fallback (same pattern as Farm's FARM_DEFAULT_ENTITY_ID)
    env_entity_id = os.environ.get("AOD_DEFAULT_ENTITY_ID")
    if env_entity_id:
        return env_entity_id

    # 4. Fail loudly — entity_id is required
    raise ValueError(
        "entity_id required for triple conversion but not provided. "
        "Set entity_id in the API request, in the snapshot meta.entity_id field, "
        "or in the AOD_DEFAULT_ENTITY_ID environment variable. "
        "Do NOT query the triples table to resolve entity_id — "
        "this is a banned anti-pattern (see maestra_platform_spec_v7.1 §10.1)."
    )
