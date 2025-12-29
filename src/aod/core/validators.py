"""
Core validators for AOD - shared validation utilities.

This module contains validation functions that are used across multiple
pipeline stages and should not have dependencies on pipeline-level modules.
"""

import re
from functools import lru_cache
from typing import Optional, Tuple

import tldextract


@lru_cache(maxsize=10000)
def _cached_extract(domain: str) -> tldextract.ExtractResult:
    """Cached tldextract.extract() call for performance."""
    return tldextract.extract(domain)


def validate_key_integrity(key: Optional[str]) -> Tuple[bool, str]:
    """
    Iron Dome: Unified admission gate for key/domain validation.
    
    This function MUST be called for ALL evidence streams before entity creation.
    Nothing bypasses this check - Discovery, Finance, CMDB, IdP, Endpoint.
    
    Rules:
    1. If suffix is empty (internal hostname like 'auth-service', 'images694'), reject
    2. If key contains spaces or invalid characters, reject
    3. Must have a valid public TLD suffix (.com, .io, .org, etc.)
    
    Args:
        key: Domain or key to validate
        
    Returns:
        (is_valid, reason) tuple
    """
    if not key:
        return False, "Empty key"
    
    key = key.lower().strip()
    
    if ' ' in key or '\t' in key or '\n' in key:
        return False, f"Key contains whitespace: {key}"
    
    invalid_chars = re.search(r'[<>"\'\{\}\[\]\\]', key)
    if invalid_chars:
        return False, f"Key contains invalid characters: {key}"
    
    extracted = _cached_extract(key)
    
    if not extracted.suffix:
        return False, f"No valid TLD suffix (internal hostname): {key}"
    
    if not extracted.domain:
        return False, f"No domain component: {key}"
    
    return True, ""


def clear_validator_cache() -> None:
    """Clear the domain extraction cache (useful for testing)."""
    _cached_extract.cache_clear()
