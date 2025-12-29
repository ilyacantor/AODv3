"""
Identity Normalizer - Hybrid Identity Pipeline for domain normalization.

This module implements the Iron Dome refactoring plan, providing a single
source of truth for identity normalization across AOD.

The pipeline order is:
1. Sanitize: Strip protocols, paths, query params, ports
2. Iron Dome Check: Validate key integrity (reject internal hostnames)
3. Alias Map: Map known aliases to canonical domains
4. Extraction: Use tldextract for domain components
5. PaaS Logic: Preserve tenant subdomains for PaaS roots
"""

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import tldextract

from ..pipeline.normalize_observations import validate_key_integrity

logger = logging.getLogger(__name__)

_RULES_CACHE: Optional[dict] = None


def load_normalization_rules() -> dict:
    """
    Load and cache normalization rules from JSON configuration.
    
    Returns:
        Dictionary with 'policy.alias_map' and 'policy.paas_roots' keys
    """
    global _RULES_CACHE
    
    if _RULES_CACHE is not None:
        return _RULES_CACHE
    
    rules_path = Path(__file__).parent / "normalization_rules.json"
    
    try:
        with open(rules_path, "r") as f:
            data = json.load(f)
            # Support both flat and nested 'policy' structure
            policy = data.get("policy", data)
            _RULES_CACHE = {
                "alias_map": policy.get("alias_map", {}),
                "paas_roots": policy.get("paas_roots", [])
            }
            logger.debug("identity_normalizer.rules_loaded", extra={
                "alias_count": len(_RULES_CACHE["alias_map"]),
                "paas_count": len(_RULES_CACHE["paas_roots"])
            })
            return _RULES_CACHE
    except FileNotFoundError:
        logger.error("identity_normalizer.rules_not_found", extra={
            "path": str(rules_path)
        })
        _RULES_CACHE = {"alias_map": {}, "paas_roots": []}
        return _RULES_CACHE
    except json.JSONDecodeError as e:
        logger.error("identity_normalizer.rules_parse_error", extra={
            "error": str(e)
        })
        _RULES_CACHE = {"alias_map": {}, "paas_roots": []}
        return _RULES_CACHE


def clear_rules_cache() -> None:
    """Clear the cached normalization rules (useful for testing)."""
    global _RULES_CACHE
    _RULES_CACHE = None


class IdentityNormalizer:
    """
    Hybrid Identity Pipeline for domain normalization.
    
    This class implements a deterministic pipeline that:
    1. Sanitizes input (strips protocols, paths, query params, ports)
    2. Validates via Iron Dome (rejects internal hostnames without valid TLDs)
    3. Maps known aliases to canonical domains
    4. Extracts domain components using tldextract
    5. Applies PaaS logic to preserve tenant subdomains where appropriate
    
    Usage:
        normalizer = IdentityNormalizer()
        result = normalizer.normalize("https://api.zoom-video.com/login")
        # Returns: "zoom.us"
    """
    
    def __init__(self):
        """Initialize the normalizer and load rules."""
        self.rules = load_normalization_rules()
        self.alias_map: dict[str, str] = self.rules.get("alias_map", {})
        self.paas_roots: set[str] = set(self.rules.get("paas_roots", []))
    
    def normalize(self, raw_input: Optional[str]) -> Optional[str]:
        """
        Normalize a raw domain/URL input to its canonical form.
        
        Pipeline order:
        1. Sanitize: Strip protocols, paths, query params, ports
        2. Iron Dome Check: Validate key integrity
        3. Alias Map: Map known aliases
        4. Extraction: Use tldextract
        5. PaaS Logic: Preserve or collapse subdomains
        
        Args:
            raw_input: Raw domain, URL, or hostname to normalize
            
        Returns:
            Canonical domain string, or None if invalid/rejected
        """
        if not raw_input:
            return None
        
        sanitized = self._sanitize(raw_input)
        if not sanitized:
            return None
        
        is_valid, reason = validate_key_integrity(sanitized)
        if not is_valid:
            logger.debug("identity_normalizer.iron_dome_rejected", extra={
                "input": raw_input,
                "sanitized": sanitized,
                "reason": reason
            })
            return None
        
        if sanitized in self.alias_map:
            canonical = self.alias_map[sanitized]
            logger.debug("identity_normalizer.alias_matched", extra={
                "input": sanitized,
                "canonical": canonical
            })
            return canonical
        
        extracted = tldextract.extract(sanitized)
        
        if not extracted.domain or not extracted.suffix:
            return None
        
        registered_domain = f"{extracted.domain}.{extracted.suffix}"
        
        if registered_domain in self.alias_map:
            canonical = self.alias_map[registered_domain]
            logger.debug("identity_normalizer.alias_matched_registered", extra={
                "input": sanitized,
                "registered": registered_domain,
                "canonical": canonical
            })
            return canonical
        
        if registered_domain in self.paas_roots:
            if extracted.subdomain:
                full_domain = f"{extracted.subdomain}.{registered_domain}"
                logger.debug("identity_normalizer.paas_preserved", extra={
                    "input": sanitized,
                    "result": full_domain
                })
                return full_domain
            return registered_domain
        
        logger.debug("identity_normalizer.collapsed_to_root", extra={
            "input": sanitized,
            "result": registered_domain
        })
        return registered_domain
    
    def _sanitize(self, raw_input: str) -> Optional[str]:
        """
        Sanitize input by stripping protocols, paths, query params, and ports.
        
        Args:
            raw_input: Raw string input
            
        Returns:
            Sanitized lowercase domain, or None if empty
        """
        if not raw_input:
            return None
        
        value = raw_input.strip().lower()
        
        if "://" in value:
            try:
                parsed = urlparse(value)
                value = parsed.netloc or parsed.path.split("/")[0]
            except Exception:
                value = value.split("://", 1)[-1]
        
        value = value.split("/")[0]
        
        value = value.split("?")[0]
        
        value = value.split("#")[0]
        
        if ":" in value:
            host_part = value.rsplit(":", 1)
            if host_part[1].isdigit():
                value = host_part[0]
        
        value = value.strip(".")
        
        return value if value else None
    
    def reload_rules(self) -> None:
        """Reload normalization rules from disk."""
        clear_rules_cache()
        self.rules = load_normalization_rules()
        self.alias_map = self.rules.get("alias_map", {})
        self.paas_roots = set(self.rules.get("paas_roots", []))


@lru_cache(maxsize=10000)
def normalize_identity(raw_input: str) -> Optional[str]:
    """
    Convenience function to normalize a domain using a shared normalizer instance.
    
    This is a cached wrapper around IdentityNormalizer.normalize() for
    high-performance scenarios where the same domain is normalized repeatedly.
    
    Args:
        raw_input: Raw domain, URL, or hostname to normalize
        
    Returns:
        Canonical domain string, or None if invalid/rejected
    """
    normalizer = IdentityNormalizer()
    return normalizer.normalize(raw_input)
