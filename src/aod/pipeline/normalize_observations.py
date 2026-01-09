"""Stage 2: NormalizeObservations - Normalize names/domains and derive candidate entities

ARCHITECTURE (Dec 2025 Iron Dome Refactor):
This module uses IdentityNormalizer as the SINGLE SOURCE OF TRUTH for all domain normalization.

Key Design:
- resolve_domain_from_observation() is the ONLY entry point for domain resolution
- All domain sources (obs.domain, obs.uri, obs.name, VENDOR_TO_DOMAIN) flow through IdentityNormalizer
- Domain-first keying: entities with domains use domain as entity_id and canonical_name
- Base-token merging rekeys name-only entities when domain is discovered later
"""

import functools
import re
import logging
from dataclasses import dataclass, field
from typing import Optional

from ..core.identity_normalizer import IdentityNormalizer
from ..models.input_contracts import Observation
from .vendor_inference import infer_vendor_from_domain, VendorHypothesisResult, VENDOR_TO_DOMAIN, extract_registered_domain
from ..utils.normalization import get_normalization_token
from ..core.validators import validate_key_integrity as _core_validate_key_integrity

logger = logging.getLogger(__name__)

_NORMALIZER = IdentityNormalizer()


def validate_key_integrity(key: Optional[str]) -> tuple[bool, str]:
    """
    Iron Dome: Unified admission gate for key/domain validation.
    
    This is a wrapper for backward compatibility - delegates to core.validators.
    See core.validators.validate_key_integrity for full documentation.
    
    Args:
        key: Domain or key to validate
        
    Returns:
        (is_valid, reason) tuple
    """
    return _core_validate_key_integrity(key)


def resolve_domain_from_observation(obs: Observation) -> Optional[str]:
    """
    SINGLE SOURCE OF TRUTH for domain resolution from an observation.
    
    Tries all possible domain sources in priority order, normalizing each
    through IdentityNormalizer. Returns the FIRST valid normalized domain.
    
    Resolution order:
    1. obs.domain (if present) → IdentityNormalizer.normalize()
    2. obs.hostname (if present) → IdentityNormalizer.normalize()
    3. obs.uri (extract domain) → IdentityNormalizer.normalize()
    4. obs.name (if looks like domain) → IdentityNormalizer.normalize()
    5. obs.name → VENDOR_TO_DOMAIN lookup → IdentityNormalizer.normalize()
    6. obs.vendor → VENDOR_TO_DOMAIN lookup → IdentityNormalizer.normalize()
    
    Args:
        obs: Observation object to resolve domain for
        
    Returns:
        Normalized canonical domain, or None if no valid domain found
    """
    if obs.domain:
        normalized = _NORMALIZER.normalize(obs.domain)
        if normalized:
            logger.debug("resolve_domain.from_domain", extra={
                "observation_id": obs.observation_id,
                "raw": obs.domain,
                "normalized": normalized
            })
            return normalized
    
    if obs.hostname:
        normalized = _NORMALIZER.normalize(obs.hostname)
        if normalized:
            logger.debug("resolve_domain.from_hostname", extra={
                "observation_id": obs.observation_id,
                "raw": obs.hostname,
                "normalized": normalized
            })
            return normalized
    
    if obs.uri:
        normalized = _NORMALIZER.normalize(obs.uri)
        if normalized:
            logger.debug("resolve_domain.from_uri", extra={
                "observation_id": obs.observation_id,
                "raw": obs.uri,
                "normalized": normalized
            })
            return normalized
    
    if obs.name and _looks_like_domain(obs.name.lower().strip()):
        normalized = _NORMALIZER.normalize(obs.name)
        if normalized:
            logger.debug("resolve_domain.from_name_as_domain", extra={
                "observation_id": obs.observation_id,
                "raw": obs.name,
                "normalized": normalized
            })
            return normalized
    
    if obs.name:
        vendor_domain = _lookup_vendor_domain(obs.name)
        if vendor_domain:
            normalized = _NORMALIZER.normalize(vendor_domain)
            if normalized:
                logger.debug("resolve_domain.from_name_vendor_lookup", extra={
                    "observation_id": obs.observation_id,
                    "name": obs.name,
                    "vendor_domain": vendor_domain,
                    "normalized": normalized
                })
                return normalized
    
    if obs.vendor:
        vendor_domain = _lookup_vendor_domain(obs.vendor)
        if vendor_domain:
            normalized = _NORMALIZER.normalize(vendor_domain)
            if normalized:
                logger.debug("resolve_domain.from_vendor_lookup", extra={
                    "observation_id": obs.observation_id,
                    "vendor": obs.vendor,
                    "vendor_domain": vendor_domain,
                    "normalized": normalized
                })
                return normalized
    
    return None


def _lookup_vendor_domain(name: str) -> Optional[str]:
    """
    Attempt to resolve a product/vendor name to its canonical domain.
    
    Uses VENDOR_TO_DOMAIN mapping to convert names like:
    - "Okta" -> "okta.com"
    - "Okta (Legacy)" -> "okta.com"
    - "Workday" -> "workday.com"
    - "Microsoft 365" -> "microsoft.com"
    - "PagerDuty-prod" -> "pagerduty.com"
    
    Args:
        name: Raw product/vendor name
        
    Returns:
        Domain from VENDOR_TO_DOMAIN if found, None otherwise
    """
    if not name:
        return None
    
    normalized = name.lower().strip()
    
    normalized = re.sub(r'\s*\([^)]*\)', '', normalized).strip()
    
    env_suffixes = r'[-_]?(prod|production|prd|dev|development|staging|stg|stage|test|testing|tst|uat|qa|sandbox|sbx|demo|legacy|old|new)$'
    normalized = re.sub(env_suffixes, '', normalized, flags=re.IGNORECASE).strip()
    
    normalized = re.sub(r'[^\w\s-]', '', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    if normalized in VENDOR_TO_DOMAIN:
        return VENDOR_TO_DOMAIN[normalized]
    
    normalized_no_spaces = normalized.replace(' ', '').replace('-', '')
    if normalized_no_spaces in VENDOR_TO_DOMAIN:
        return VENDOR_TO_DOMAIN[normalized_no_spaces]
    
    for vendor_key, domain in VENDOR_TO_DOMAIN.items():
        if vendor_key in normalized or vendor_key in normalized_no_spaces:
            return domain
    
    normalized_underscores = normalized.replace(' ', '_')
    if normalized_underscores in VENDOR_TO_DOMAIN:
        return VENDOR_TO_DOMAIN[normalized_underscores]
    
    return None


def normalize_name_to_domain(name: str) -> Optional[str]:
    """
    Attempt to resolve a product name to its canonical domain.
    
    DEPRECATED: Use resolve_domain_from_observation() instead.
    This wrapper is kept for backward compatibility.
    """
    vendor_domain = _lookup_vendor_domain(name)
    if vendor_domain:
        return _NORMALIZER.normalize(vendor_domain)
    return None


@dataclass
class CandidateEntity:
    """A candidate system entity derived from observations"""
    entity_id: str
    canonical_name: str
    original_name: str
    domain: Optional[str] = None
    hostname: Optional[str] = None
    uri: Optional[str] = None
    vendor: Optional[str] = None
    vendor_hypothesis: Optional[VendorHypothesisResult] = None
    observation_ids: list[str] = field(default_factory=list)
    source: str = "discovery"
    
    def __hash__(self):
        return hash(self.entity_id)


@functools.lru_cache(maxsize=10000)
def normalize_string(s: str) -> str:
    """Normalize a string for matching: lowercase, strip whitespace, remove special chars"""
    if not s:
        return ""
    normalized = s.lower().strip()
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized


def normalize_domain(domain: str) -> str:
    """Normalize a domain using IdentityNormalizer.
    
    DEPRECATED: Use _NORMALIZER.normalize() directly or resolve_domain_from_observation().
    This wrapper is kept for backward compatibility.
    """
    if not domain:
        return ""
    result = _NORMALIZER.normalize(domain)
    return result if result else ""


def extract_domain_from_uri(uri: str) -> Optional[str]:
    """Extract and normalize domain from a URI using IdentityNormalizer."""
    if not uri:
        return None
    return _NORMALIZER.normalize(uri)


ENV_SUFFIXES = {
    "prod", "production", "prd",
    "dev", "development",
    "staging", "stg", "stage",
    "test", "testing", "tst",
    "uat", "qa",
    "sandbox", "sbx",
    "demo", "legacy", "old", "new",
}


def derive_canonical_name(observation: Observation) -> str:
    """Derive a canonical name from an observation (used when no domain available)"""
    name = observation.name or ""
    canonical = normalize_string(name)
    canonical = re.sub(r'\([^)]*\)', '', canonical).strip()
    
    env_pattern = r'[-_](' + '|'.join(ENV_SUFFIXES) + r')$'
    canonical = re.sub(env_pattern, '', canonical, flags=re.IGNORECASE)
    
    suffixes_to_remove = [
        "dashboard", "report", "calculator", "worksheet",
        "view", "saved query", "file", "spreadsheet"
    ]
    for suffix in suffixes_to_remove:
        if canonical.endswith(suffix):
            canonical = canonical[:-len(suffix)].strip()
    canonical = re.sub(r'[^\w\s-]', '', canonical)
    canonical = re.sub(r'\s+', ' ', canonical).strip()
    return canonical if canonical else normalize_string(name)


def choose_primary_key_from_observations(observations: list[Observation]) -> Optional[str]:
    """
    Score and choose the best primary key from multiple observations.
    
    Selection criteria (in priority order):
    1. Domain support count (how many observations mention this domain) - PRIMARY
    2. Source diversity (multiple distinct sources = higher confidence) - SECONDARY
    3. Domain length (shorter = more canonical, e.g., zoom.us vs zoom-video.com)
    4. Lexicographic order (deterministic tiebreaker)
    
    Returns the best registrable domain as primary key, or None if no domains found.
    
    INVARIANT: Once chosen, this key MUST NOT be changed downstream.
    """
    import os
    from collections import defaultdict
    from .vendor_inference import extract_registered_domain
    
    if not observations:
        return None
    
    domain_sources: dict[str, set[str]] = defaultdict(set)
    domain_counts: dict[str, int] = defaultdict(int)
    
    for obs in observations:
        domain = resolve_domain_from_observation(obs)
        if domain:
            registered = extract_registered_domain(domain)
            if registered:
                source = (obs.source or "unknown").lower().strip()
                domain_sources[registered].add(source)
                domain_counts[registered] += 1
    
    if not domain_counts:
        return None
    
    scored = []
    for domain, count in domain_counts.items():
        source_diversity = len(domain_sources[domain])
        scored.append((count, source_diversity, -len(domain), domain))
    
    scored.sort(reverse=True)
    
    if os.environ.get("AOD_DEBUG_KEYS"):
        logger.info("primary_key.selection", extra={
            "candidates": [{"domain": d, "sources": list(domain_sources[d]), "count": c} for d in domain_counts],
            "chosen": scored[0][3] if scored else None
        })
    
    return scored[0][3] if scored else None


def normalize_observations(observations: list[Observation]) -> tuple[list[CandidateEntity], list[dict]]:
    """
    Normalize observations and derive candidate system entities.
    
    ARCHITECTURE:
    - Observations with domains: Group by REGISTERED DOMAIN (eTLD+1)
    - Observations without domains (name-only): Try to merge with existing domain entities via base token
    
    This preserves the entity:domain relationship that Farm expects while still
    allowing name-only observations to merge with their domain counterparts.
    
    All entities with resolvable domains have:
    - entity_id = "entity:{normalized_domain}"
    - canonical_name = normalized_domain
    - domain = normalized_domain
    
    Args:
        observations: List of raw observations
        
    Returns:
        Tuple of (valid_entities, rejected_observations)
    """
    import os
    
    entities_by_domain: dict[str, CandidateEntity] = {}
    entities_by_name: dict[str, CandidateEntity] = {}
    rejected: list[dict] = []
    
    debug_keys = os.environ.get("AOD_DEBUG_KEYS")
    
    for obs in sorted(observations, key=lambda o: o.observation_id):
        domain = resolve_domain_from_observation(obs)
        canonical_name = derive_canonical_name(obs)
        
        if not canonical_name and domain:
            canonical_name = _extract_base_name(domain) or domain
        
        if not canonical_name and not domain:
            rejected.append({
                "observation_id": obs.observation_id,
                "name": obs.name,
                "domain": None,
                "reason": "Empty canonical name and no domain"
            })
            continue
        
        is_valid, rejection_reason = validate_key_integrity(domain)
        if not is_valid:
            rejected.append({
                "observation_id": obs.observation_id,
                "name": obs.name,
                "domain": domain,
                "reason": rejection_reason
            })
            logger.debug("normalize.iron_dome_rejected", extra={
                "observation_id": obs.observation_id,
                "name": obs.name,
                "domain": domain,
                "reason": rejection_reason
            })
            continue
        
        if domain:
            registered_domain = extract_registered_domain(domain)
            if not registered_domain:
                registered_domain = domain
            
            if registered_domain in entities_by_domain:
                entity = entities_by_domain[registered_domain]
                entity.observation_ids.append(obs.observation_id)
                if not entity.hostname and obs.hostname:
                    entity.hostname = obs.hostname.lower().strip()
                if not entity.uri and obs.uri:
                    entity.uri = obs.uri.lower().strip()
                if not entity.vendor and obs.vendor:
                    entity.vendor = normalize_string(obs.vendor)
            else:
                vendor_hypothesis = infer_vendor_from_domain(registered_domain)
                entity = CandidateEntity(
                    entity_id=f"entity:{registered_domain}",
                    canonical_name=registered_domain,
                    original_name=obs.name or "",
                    domain=registered_domain,
                    hostname=obs.hostname.lower().strip() if obs.hostname else None,
                    uri=obs.uri.lower().strip() if obs.uri else None,
                    vendor=normalize_string(obs.vendor) if obs.vendor else None,
                    vendor_hypothesis=vendor_hypothesis,
                    observation_ids=[obs.observation_id],
                    source=obs.source
                )
                entities_by_domain[registered_domain] = entity
                
                if debug_keys:
                    logger.info("normalize.domain_entity_created", extra={
                        "registered_domain": registered_domain,
                        "entity_id": entity.entity_id,
                        "observation_id": obs.observation_id
                    })
        else:
            base_token = get_normalization_token(canonical_name)
            
            merged = False
            if base_token:
                for domain_key, domain_entity in entities_by_domain.items():
                    domain_token = get_normalization_token(domain_key)
                    if domain_token == base_token:
                        domain_entity.observation_ids.append(obs.observation_id)
                        if not domain_entity.vendor and obs.vendor:
                            domain_entity.vendor = normalize_string(obs.vendor)
                        merged = True
                        if debug_keys:
                            logger.info("normalize.name_merged_to_domain", extra={
                                "canonical_name": canonical_name,
                                "merged_to_domain": domain_key,
                                "base_token": base_token
                            })
                        break
            
            if not merged:
                if canonical_name in entities_by_name:
                    entity = entities_by_name[canonical_name]
                    entity.observation_ids.append(obs.observation_id)
                    if not entity.vendor and obs.vendor:
                        entity.vendor = normalize_string(obs.vendor)
                else:
                    entity = CandidateEntity(
                        entity_id=f"entity:{canonical_name}",
                        canonical_name=canonical_name,
                        original_name=obs.name or "",
                        domain=None,
                        hostname=obs.hostname.lower().strip() if obs.hostname else None,
                        uri=obs.uri.lower().strip() if obs.uri else None,
                        vendor=normalize_string(obs.vendor) if obs.vendor else None,
                        vendor_hypothesis=None,
                        observation_ids=[obs.observation_id],
                        source=obs.source
                    )
                    entities_by_name[canonical_name] = entity
    
    for name_key, name_entity in list(entities_by_name.items()):
        base_token = get_normalization_token(name_key)
        if base_token:
            for domain_key, domain_entity in entities_by_domain.items():
                domain_token = get_normalization_token(domain_key)
                if domain_token == base_token:
                    domain_entity.observation_ids.extend(name_entity.observation_ids)
                    if not domain_entity.vendor and name_entity.vendor:
                        domain_entity.vendor = name_entity.vendor
                    del entities_by_name[name_key]
                    if debug_keys:
                        logger.info("normalize.late_name_merge", extra={
                            "name_key": name_key,
                            "merged_to_domain": domain_key,
                            "base_token": base_token
                        })
                    break
    
    all_entities = list(entities_by_domain.values()) + list(entities_by_name.values())
    
    if rejected:
        logger.info("normalize.iron_dome_summary", extra={
            "total_observations": len(observations),
            "valid_entities": len(all_entities),
            "rejected_count": len(rejected)
        })
    
    return sorted(all_entities, key=lambda e: e.domain or e.canonical_name), rejected


def _looks_like_domain(name: str) -> bool:
    """Check if a canonical name looks like a domain (e.g., 'slack.com')"""
    if not name:
        return False
    parts = name.split('.')
    if len(parts) >= 2:
        tld = parts[-1]
        if tld in (
            'com', 'org', 'net', 'io', 'co', 'dev', 'app', 'us', 'cloud',
            'ai', 'tech', 'biz', 'info', 'xyz', 'me', 'cc', 'tv', 'so',
            'gg', 'fm', 'ly', 'to', 'sh', 'in', 'uk', 'de', 'fr', 'jp',
            'ca', 'au', 'br', 'it', 'es', 'nl', 'ru', 'eu', 'pro', 'edu',
            'gov', 'mil', 'int', 'name'
        ):
            return True
    return False


def _extract_base_name(domain: str) -> Optional[str]:
    """Extract base name from domain (e.g., 'slack.com' -> 'slack')"""
    if not domain:
        return None
    parts = domain.split('.')
    if len(parts) >= 2:
        return parts[0]
    return None


def extract_base_token(value: str, is_domain: bool = False) -> Optional[str]:
    """
    Extract base token for cross-reference matching.
    
    This enables aggressive domain merging by creating a common key that allows
    matching between name-only entities and domain entities.
    
    NOTE: This function now uses the shared get_normalization_token() for consistency.
    
    Args:
        value: Domain string or product name
        is_domain: Retained for backward compatibility (same logic used for both)
        
    Returns:
        Lowercase base token for matching, or None if extraction fails
    """
    if not value:
        return None
    token = get_normalization_token(value)
    return token if token else None


def _merge_entity_data(target: CandidateEntity, source: CandidateEntity) -> None:
    """
    Merge data from source entity into target entity.
    
    Transfers observation_ids and fills in missing fields.
    Target entity is the "winner" (domain-backed entity).
    """
    for obs_id in source.observation_ids:
        if obs_id not in target.observation_ids:
            target.observation_ids.append(obs_id)
    
    if source.hostname and not target.hostname:
        target.hostname = source.hostname
    if source.uri and not target.uri:
        target.uri = source.uri
    if source.vendor and not target.vendor:
        target.vendor = source.vendor
    if source.original_name and not target.original_name:
        target.original_name = source.original_name
