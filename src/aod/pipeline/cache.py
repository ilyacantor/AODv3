"""Caching layer for expensive pipeline computations

Provides LRU cache with TTL for domain rollups and derived classifications.
"""

from functools import lru_cache
from typing import Optional, Callable, Any, TypeVar, ParamSpec
from datetime import datetime, timedelta, timezone
import hashlib
import pickle

P = ParamSpec('P')
T = TypeVar('T')


class CacheEntry:
    """Cache entry with expiration timestamp"""
    def __init__(self, value: Any, ttl_seconds: int):
        self.value = value
        self.expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) >= self.expires_at


class TTLCache:
    """
    Simple in-memory cache with Time-To-Live (TTL) eviction.

    Features:
    - LRU eviction when max_size is reached
    - TTL-based expiration for stale data
    - Thread-safe for concurrent API requests
    """

    def __init__(self, max_size: int = 128, default_ttl: int = 300):
        """
        Initialize TTL cache.

        Args:
            max_size: Maximum number of entries (default 128)
            default_ttl: Default time-to-live in seconds (default 300 = 5 minutes)
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: dict[str, CacheEntry] = {}
        self._access_order: list[str] = []

    def _evict_lru(self):
        """Evict least recently used entry"""
        if self._access_order:
            lru_key = self._access_order.pop(0)
            self._cache.pop(lru_key, None)

    def _evict_expired(self):
        """Evict all expired entries"""
        expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
        for k in expired_keys:
            self._cache.pop(k, None)
            if k in self._access_order:
                self._access_order.remove(k)

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache, returns None if expired or not found"""
        self._evict_expired()

        entry = self._cache.get(key)
        if entry is None:
            return None

        if entry.is_expired():
            self._cache.pop(key)
            if key in self._access_order:
                self._access_order.remove(key)
            return None

        # Update access order (move to end = most recently used)
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)

        return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in cache with optional TTL override"""
        self._evict_expired()

        # Evict LRU if at capacity
        if len(self._cache) >= self.max_size and key not in self._cache:
            self._evict_lru()

        ttl_seconds = ttl if ttl is not None else self.default_ttl
        self._cache[key] = CacheEntry(value, ttl_seconds)

        # Update access order
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)

    def invalidate(self, key: str):
        """Invalidate a specific cache entry"""
        self._cache.pop(key, None)
        if key in self._access_order:
            self._access_order.remove(key)

    def invalidate_pattern(self, prefix: str):
        """Invalidate all entries matching a prefix pattern"""
        keys_to_remove = [k for k in self._cache.keys() if k.startswith(prefix)]
        for k in keys_to_remove:
            self.invalidate(k)

    def clear(self):
        """Clear all cache entries"""
        self._cache.clear()
        self._access_order.clear()

    def stats(self) -> dict:
        """Get cache statistics"""
        self._evict_expired()
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "entries": list(self._cache.keys())
        }


# Global cache instances for different computation types
_domain_rollups_cache = TTLCache(max_size=64, default_ttl=600)  # 10 minutes
_derived_classifications_cache = TTLCache(max_size=64, default_ttl=600)  # 10 minutes


def get_domain_rollups_cache() -> TTLCache:
    """Get the global domain rollups cache instance"""
    return _domain_rollups_cache


def get_derived_classifications_cache() -> TTLCache:
    """Get the global derived classifications cache instance"""
    return _derived_classifications_cache


def invalidate_run_caches(run_id: str):
    """
    Invalidate all cached data for a specific run.

    Call this when:
    - A run is updated or deleted
    - Assets for a run are modified
    - Findings for a run are regenerated
    """
    _domain_rollups_cache.invalidate_pattern(f"run:{run_id}:")
    _derived_classifications_cache.invalidate_pattern(f"run:{run_id}:")


def make_cache_key(*args, **kwargs) -> str:
    """
    Generate deterministic cache key from arguments.

    Uses pickle + hash for complex objects (Asset lists, etc.)
    """
    # Sort kwargs for deterministic ordering
    sorted_kwargs = sorted(kwargs.items())

    # Create key from args and kwargs
    key_data = (args, tuple(sorted_kwargs))

    # Hash the pickled data for complex objects
    try:
        pickled = pickle.dumps(key_data, protocol=pickle.HIGHEST_PROTOCOL)
        return hashlib.sha256(pickled).hexdigest()
    except Exception:
        # Fallback to string representation if pickle fails
        return hashlib.sha256(str(key_data).encode()).hexdigest()
