"""Stage 2: NormalizeObservations - Normalize names/domains and derive candidate entities"""

import re
from dataclasses import dataclass, field
from typing import Optional

from ..models.input_contracts import Observation
from .vendor_inference import infer_vendor_from_domain, VendorHypothesisResult
from .domain_normalization import (
    normalize_hostname,
    derive_canonical_asset_key,
    looks_like_domain as canonical_looks_like_domain,
)


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


def normalize_string(s: str) -> str:
    """Normalize a string for matching: lowercase, strip whitespace, remove special chars"""
    if not s:
        return ""
    normalized = s.lower().strip()
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized


def normalize_domain(domain: str) -> str:
    """Normalize a domain for matching"""
    if not domain:
        return ""
    normalized = domain.lower().strip()
    normalized = normalized.removeprefix("www.")
    normalized = normalized.removeprefix("http://")
    normalized = normalized.removeprefix("https://")
    normalized = normalized.split("/")[0]
    return normalized


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


def derive_canonical_name(observation: Observation) -> str:
    """Derive a canonical name from an observation"""
    name = observation.name
    canonical = normalize_string(name)
    canonical = re.sub(r'\([^)]*\)', '', canonical).strip()
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


def normalize_observations(observations: list[Observation]) -> list[CandidateEntity]:
    """
    Normalize observations and derive candidate system entities.
    
    - Normalize names/domains/hostnames using canonical functions
    - Derive candidate "system entities" from raw observations
    - Maintain provenance (observation IDs)
    - Merge observations that represent the same entity
    - Domain-first keying: use eTLD+1 (registered domain) as canonical key
    
    INVARIANT: If any observation has a resolvable domain, the entity key
    MUST be the eTLD+1 (e.g., app.slack.com -> slack.com)
    
    Args:
        observations: List of raw observations
        
    Returns:
        List of candidate entities with normalized identifiers
    """
    entities_by_domain: dict[str, CandidateEntity] = {}
    entities_by_name: dict[str, CandidateEntity] = {}
    
    for obs in sorted(observations, key=lambda o: o.observation_id):
        canonical_name = derive_canonical_name(obs)
        
        if not canonical_name:
            continue
        
        raw_domain = None
        if obs.domain:
            raw_domain = obs.domain
        elif obs.uri:
            raw_domain = normalize_hostname(obs.uri)
        elif obs.hostname:
            raw_domain = normalize_hostname(obs.hostname)
        elif canonical_looks_like_domain(obs.name.lower().strip()):
            raw_domain = obs.name.lower().strip()
        
        domain = derive_canonical_asset_key(raw_domain) if raw_domain else None
        
        hostname = normalize_hostname(obs.hostname) if obs.hostname else None
        uri = obs.uri.lower().strip() if obs.uri else None
        vendor = normalize_string(obs.vendor) if obs.vendor else None
        
        existing_entity = None
        
        if domain:
            if domain in entities_by_domain:
                existing_entity = entities_by_domain[domain]
            else:
                base_name = _extract_base_name(domain)
                if canonical_name in entities_by_name:
                    existing_entity = entities_by_name[canonical_name]
                    del entities_by_name[canonical_name]
                elif base_name and base_name in entities_by_name:
                    existing_entity = entities_by_name[base_name]
                    del entities_by_name[base_name]
                
                if existing_entity:
                    existing_entity.domain = domain
                    if not existing_entity.vendor_hypothesis:
                        existing_entity.vendor_hypothesis = infer_vendor_from_domain(domain)
                    entities_by_domain[domain] = existing_entity
        else:
            if canonical_name in entities_by_name:
                existing_entity = entities_by_name[canonical_name]
        
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
                original_name=obs.name,
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
    
    all_entities = list(entities_by_domain.values()) + list(entities_by_name.values())
    return sorted(all_entities, key=lambda e: e.domain or e.canonical_name)


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
