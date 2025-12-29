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
from .vendor_inference import infer_vendor_from_domain, VendorHypothesisResult, VENDOR_TO_DOMAIN
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
    2. obs.uri (extract domain) → IdentityNormalizer.normalize()
    3. obs.name (if looks like domain) → IdentityNormalizer.normalize()
    4. obs.name → VENDOR_TO_DOMAIN lookup → IdentityNormalizer.normalize()
    5. obs.vendor → VENDOR_TO_DOMAIN lookup → IdentityNormalizer.normalize()
    
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


def normalize_observations(observations: list[Observation]) -> tuple[list[CandidateEntity], list[dict]]:
    """
    Normalize observations and derive candidate system entities.
    
    ARCHITECTURE (Dec 2025 Iron Dome Refactor):
    This function uses resolve_domain_from_observation() as the SINGLE entry point
    for domain resolution. All entities with resolvable domains have:
    - entity_id = "entity:{normalized_domain}"
    - canonical_name = normalized_domain
    - domain = normalized_domain
    
    Base-token merging ensures name-only entities get REKEYED when a domain
    is discovered for the same product later.
    
    Args:
        observations: List of raw observations
        
    Returns:
        Tuple of (valid_entities, rejected_observations)
    """
    entities_by_domain: dict[str, CandidateEntity] = {}
    entities_by_name: dict[str, CandidateEntity] = {}
    entities_by_base_token: dict[str, CandidateEntity] = {}
    rejected: list[dict] = []
    
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
        
        hostname = obs.hostname.lower().strip() if obs.hostname else None
        uri = obs.uri.lower().strip() if obs.uri else None
        vendor = normalize_string(obs.vendor) if obs.vendor else None
        
        base_token = get_normalization_token(domain) if domain else get_normalization_token(canonical_name)
        
        existing_entity = None
        
        if domain:
            if domain in entities_by_domain:
                existing_entity = entities_by_domain[domain]
            elif base_token and base_token in entities_by_base_token:
                existing_by_token = entities_by_base_token[base_token]
                if not existing_by_token.domain:
                    existing_entity = existing_by_token
                    old_canonical = existing_entity.canonical_name
                    old_entity_id = existing_entity.entity_id
                    
                    existing_entity.domain = domain
                    existing_entity.vendor_hypothesis = infer_vendor_from_domain(domain)
                    existing_entity.entity_id = f"entity:{domain}"
                    existing_entity.canonical_name = domain
                    
                    entities_by_domain[domain] = existing_entity
                    
                    if old_canonical in entities_by_name:
                        del entities_by_name[old_canonical]
                    
                    entities_by_base_token[base_token] = existing_entity
                    
                    logger.debug("normalize.base_token_merge_rekey", extra={
                        "observation_id": obs.observation_id,
                        "base_token": base_token,
                        "domain": domain,
                        "old_entity_id": old_entity_id,
                        "new_entity_id": existing_entity.entity_id,
                        "absorbed_name": old_canonical
                    })
        else:
            if canonical_name in entities_by_name:
                existing_entity = entities_by_name[canonical_name]
            elif base_token and base_token in entities_by_base_token:
                existing_by_token = entities_by_base_token[base_token]
                if existing_by_token.domain:
                    existing_entity = existing_by_token
                    logger.debug("normalize.base_token_merge_into_domain", extra={
                        "observation_id": obs.observation_id,
                        "base_token": base_token,
                        "name": canonical_name,
                        "merged_into_domain": existing_by_token.domain
                    })
        
        if existing_entity:
            existing_entity.observation_ids.append(obs.observation_id)
            if hostname and not existing_entity.hostname:
                existing_entity.hostname = hostname
            if uri and not existing_entity.uri:
                existing_entity.uri = uri
            if vendor and not existing_entity.vendor:
                existing_entity.vendor = vendor
        else:
            vendor_hypothesis = infer_vendor_from_domain(domain) if domain else None
            
            if domain:
                entity_key = domain
                entity_canonical = domain
            else:
                entity_key = canonical_name
                entity_canonical = canonical_name
            
            entity = CandidateEntity(
                entity_id=f"entity:{entity_key}",
                canonical_name=entity_canonical,
                original_name=obs.name or "",
                domain=domain,
                hostname=hostname,
                uri=uri,
                vendor=vendor,
                vendor_hypothesis=vendor_hypothesis,
                observation_ids=[obs.observation_id],
                source=obs.source
            )
            if domain:
                entities_by_domain[domain] = entity
            else:
                entities_by_name[canonical_name] = entity
            
            if base_token and base_token not in entities_by_base_token:
                entities_by_base_token[base_token] = entity
    
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
        if tld in ('com', 'org', 'net', 'io', 'co', 'dev', 'app', 'us', 'cloud'):
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
