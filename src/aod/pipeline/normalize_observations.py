"""Stage 2: NormalizeObservations - Normalize names/domains and derive candidate entities"""

import functools
import re
import logging
from dataclasses import dataclass, field
from typing import Optional

from .domain_cache import extract_domain

from ..models.input_contracts import Observation
from .vendor_inference import infer_vendor_from_domain, VendorHypothesisResult, VENDOR_TO_DOMAIN
from ..utils.normalization import get_normalization_token

logger = logging.getLogger(__name__)


def validate_key_integrity(key: Optional[str]) -> tuple[bool, str]:
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
    
    extracted = extract_domain(key)
    
    if not extracted.suffix:
        return False, f"No valid TLD suffix (internal hostname): {key}"
    
    if not extracted.domain:
        return False, f"No domain component: {key}"
    
    return True, ""


def normalize_name_to_domain(name: str) -> Optional[str]:
    """
    Attempt to resolve a product name to its canonical domain.
    
    Uses VENDOR_TO_DOMAIN mapping to convert product names like:
    - "Okta" -> "okta.com"
    - "Okta (Legacy)" -> "okta.com"
    - "Workday" -> "workday.com"
    - "Microsoft 365" -> "microsoft.com"
    - "PagerDuty-prod" -> "pagerduty.com"
    
    This normalization MUST happen BEFORE the validate_key_integrity check.
    Strips common suffixes like (Legacy), -prod, -dev etc. before matching.
    
    Args:
        name: Raw product/vendor name
        
    Returns:
        Canonical domain if found, None otherwise
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
    """Normalize a domain for matching.
    
    Dec 2025 Fix: Use extract_registered_domain() to strip ALL subdomains
    (not just www.) to ensure domains like api.primebox.io → primebox.io.
    This fixes KEY_NORMALIZATION_MISMATCH errors where discovery subdomains
    don't match the Farm's canonical base domain.
    """
    if not domain:
        return ""
    
    # Clean up the domain first
    normalized = domain.lower().strip()
    normalized = normalized.removeprefix("http://")
    normalized = normalized.removeprefix("https://")
    normalized = normalized.split("/")[0]  # Remove path
    normalized = normalized.split(":")[0]  # Remove port
    
    if not normalized:
        return ""
    
    # Use extract_registered_domain to get the eTLD+1 (base domain)
    # This strips ALL subdomains: api.primebox.io → primebox.io
    from .vendor_inference import extract_registered_domain
    registered = extract_registered_domain(normalized)
    
    # Fall back to original if extraction fails (e.g., IP addresses, localhost)
    return registered if registered else normalized


def extract_domain_from_uri(uri: str) -> Optional[str]:
    """Extract domain from a URI"""
    if not uri:
        return None
    uri = uri.lower().strip()
    uri = uri.removeprefix("http://")
    uri = uri.removeprefix("https://")
    parts = uri.split("/")
    if parts:
        domain = parts[0].split(":")[0]
        return normalize_domain(domain)
    return None


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
    """Derive a canonical name from an observation"""
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
    
    IRON DOME: All entities MUST pass validate_key_integrity() before creation.
    Internal hostnames (no valid TLD) are rejected at this stage.
    
    - Normalize names/domains/hostnames
    - Derive candidate "system entities" from raw observations
    - Apply validate_key_integrity() to filter invalid entities
    - Maintain provenance (observation IDs)
    - Merge observations that represent the same entity
    - Domain-first keying: if entity has domain, use domain as canonical key
    
    Args:
        observations: List of raw observations
        
    Returns:
        Tuple of (valid_entities, rejected_observations)
        - valid_entities: List of candidate entities with normalized identifiers
        - rejected_observations: List of rejected observations with reasons
    """
    entities_by_domain: dict[str, CandidateEntity] = {}
    entities_by_name: dict[str, CandidateEntity] = {}
    entities_by_base_token: dict[str, CandidateEntity] = {}
    rejected: list[dict] = []
    
    for obs in sorted(observations, key=lambda o: o.observation_id):
        domain = normalize_domain(obs.domain) if obs.domain else None
        if not domain and obs.uri:
            domain = extract_domain_from_uri(obs.uri)
        if not domain and obs.name and _looks_like_domain(obs.name.lower().strip()):
            domain = normalize_domain(obs.name.lower().strip())
        
        canonical_name = derive_canonical_name(obs)
        
        if not canonical_name and domain:
            canonical_name = _extract_base_name(domain) or domain
        
        if not canonical_name:
            rejected.append({
                "observation_id": obs.observation_id,
                "name": obs.name,
                "domain": domain,
                "reason": "Empty canonical name and no domain"
            })
            continue
        
        if not domain and obs.name:
            resolved_domain = normalize_name_to_domain(obs.name)
            if resolved_domain:
                domain = resolved_domain
                logger.debug("normalize.product_name_resolved", extra={
                    "observation_id": obs.observation_id,
                    "name": obs.name,
                    "resolved_domain": domain
                })
        
        if not domain:
            if obs.vendor:
                resolved_domain = normalize_name_to_domain(obs.vendor)
                if resolved_domain:
                    domain = resolved_domain
                    logger.debug("normalize.vendor_name_resolved", extra={
                        "observation_id": obs.observation_id,
                        "vendor": obs.vendor,
                        "resolved_domain": domain
                    })
        
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
        
        # Use get_normalization_token for consistent base token extraction
        # This ensures "Airtable" (name) and "airtable.com" (domain) produce the same token
        base_token = get_normalization_token(domain) if domain else get_normalization_token(canonical_name)
        
        existing_entity = None
        
        if domain:
            if domain in entities_by_domain:
                existing_entity = entities_by_domain[domain]
            elif base_token and base_token in entities_by_base_token:
                existing_by_token = entities_by_base_token[base_token]
                if not existing_by_token.domain:
                    existing_entity = existing_by_token
                    existing_entity.domain = domain
                    existing_entity.vendor_hypothesis = infer_vendor_from_domain(domain)
                    entities_by_domain[domain] = existing_entity
                    if existing_entity.canonical_name in entities_by_name:
                        del entities_by_name[existing_entity.canonical_name]
                    logger.debug("normalize.base_token_merge_domain_wins", extra={
                        "observation_id": obs.observation_id,
                        "base_token": base_token,
                        "domain": domain,
                        "absorbed_name": existing_entity.canonical_name
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
            entity = CandidateEntity(
                entity_id=f"entity:{obs.observation_id}",
                canonical_name=canonical_name,
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
    
    For domains: "airtable.com" → "airtable"
    For names: "Airtable" → "airtable", "Airtable (Legacy)" → "airtable"
    
    NOTE: This function now uses the shared get_normalization_token() for consistency
    across the codebase. The is_domain parameter is retained for backward compatibility
    but the same token extraction logic is used for both.
    
    Args:
        value: Domain string or product name
        is_domain: Retained for backward compatibility (same logic used for both)
        
    Returns:
        Lowercase base token for matching, or None if extraction fails
    """
    if not value:
        return None
    
    # Use the shared get_normalization_token() for consistent token extraction
    # This ensures domains and names that represent the same product
    # produce the same token (e.g., "airtable.com" and "Airtable" both -> "airtable")
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
