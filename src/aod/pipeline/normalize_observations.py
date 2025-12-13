"""Stage 2: NormalizeObservations - Normalize names/domains and derive candidate entities"""

import re
from dataclasses import dataclass, field
from typing import Optional

from ..models.input_contracts import Observation


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
    
    - Normalize names/domains/hostnames
    - Derive candidate "system entities" from raw observations
    - Maintain provenance (observation IDs)
    - Merge observations that represent the same entity
    
    Args:
        observations: List of raw observations
        
    Returns:
        List of candidate entities with normalized identifiers
    """
    entities_by_canonical: dict[str, CandidateEntity] = {}
    
    for obs in sorted(observations, key=lambda o: o.observation_id):
        canonical_name = derive_canonical_name(obs)
        
        if not canonical_name:
            continue
        
        domain = normalize_domain(obs.domain) if obs.domain else None
        if not domain and obs.uri:
            domain = extract_domain_from_uri(obs.uri)
        
        hostname = obs.hostname.lower().strip() if obs.hostname else None
        uri = obs.uri.lower().strip() if obs.uri else None
        vendor = normalize_string(obs.vendor) if obs.vendor else None
        
        lookup_key = canonical_name
        if domain:
            lookup_key = f"{canonical_name}:{domain}"
        
        if lookup_key in entities_by_canonical:
            entity = entities_by_canonical[lookup_key]
            entity.observation_ids.append(obs.observation_id)
            if domain and not entity.domain:
                entity.domain = domain
            if hostname and not entity.hostname:
                entity.hostname = hostname
            if uri and not entity.uri:
                entity.uri = uri
            if vendor and not entity.vendor:
                entity.vendor = vendor
        else:
            entity = CandidateEntity(
                entity_id=f"entity:{obs.observation_id}",
                canonical_name=canonical_name,
                original_name=obs.name,
                domain=domain,
                hostname=hostname,
                uri=uri,
                vendor=vendor,
                observation_ids=[obs.observation_id],
                source=obs.source
            )
            entities_by_canonical[lookup_key] = entity
    
    return sorted(entities_by_canonical.values(), key=lambda e: e.canonical_name)
