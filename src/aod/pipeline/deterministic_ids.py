"""Deterministic ID generation for pipeline outputs"""

import hashlib
from uuid import UUID


def deterministic_uuid(snapshot_id: str, *components: str) -> UUID:
    """
    Generate a deterministic UUID from snapshot_id and content components.
    
    Uses SHA-256 hash truncated to 16 bytes for UUID.
    Same inputs always produce the same UUID.
    
    Args:
        snapshot_id: The snapshot identifier (run_id or snapshot_id from provenance)
        *components: Additional strings to include in hash (asset name, finding type, etc.)
        
    Returns:
        Deterministic UUID
    """
    content = "|".join([snapshot_id] + list(components))
    hash_bytes = hashlib.sha256(content.encode("utf-8")).digest()[:16]
    return UUID(bytes=hash_bytes)
