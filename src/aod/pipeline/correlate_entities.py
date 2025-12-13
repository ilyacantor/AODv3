"""Stage 4: CorrelateEntitiesToPlanes - Real-world simple matcher"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from .normalize_observations import CandidateEntity, normalize_string
from .build_plane_indexes import PlaneIndexes, PlaneIndex


class MatchStatus(str, Enum):
    """Match status for correlation"""
    MATCHED = "matched"
    AMBIGUOUS = "ambiguous"
    UNMATCHED = "unmatched"


@dataclass
class PlaneMatch:
    """Match result for a single plane"""
    status: MatchStatus
    matched_ids: list[str] = field(default_factory=list)
    matched_records: list[Any] = field(default_factory=list)
    match_method: Optional[str] = None


@dataclass
class CorrelationResult:
    """Correlation result for an entity across all planes"""
    entity: CandidateEntity
    idp: PlaneMatch = field(default_factory=lambda: PlaneMatch(status=MatchStatus.UNMATCHED))
    cmdb: PlaneMatch = field(default_factory=lambda: PlaneMatch(status=MatchStatus.UNMATCHED))
    cloud: PlaneMatch = field(default_factory=lambda: PlaneMatch(status=MatchStatus.UNMATCHED))
    finance: PlaneMatch = field(default_factory=lambda: PlaneMatch(status=MatchStatus.UNMATCHED))
    
    def all_evidence_refs(self) -> list[str]:
        """Get all evidence references from matched planes"""
        refs = list(self.entity.observation_ids)
        for plane_match in [self.idp, self.cmdb, self.cloud, self.finance]:
            if plane_match.status == MatchStatus.MATCHED:
                refs.extend(plane_match.matched_ids)
        return refs


def correlate_to_plane(
    entity: CandidateEntity,
    plane_index: PlaneIndex,
    use_domain: bool = True,
    use_uri: bool = False
) -> PlaneMatch:
    """
    Correlate an entity to a plane using three-pass matching.
    
    Pass 1: Domain match (if applicable)
    Pass 2: Exact canonical normalized name match
    Pass 3: Unique contains match (strict; if >1 candidate → ambiguous)
    
    Returns matched/ambiguous/unmatched plus evidence refs.
    """
    matched_ids: list[str] = []
    match_method: Optional[str] = None
    
    if use_domain and entity.domain and plane_index.by_domain:
        domain_matches = plane_index.by_domain.get(entity.domain, [])
        if len(domain_matches) == 1:
            return PlaneMatch(
                status=MatchStatus.MATCHED,
                matched_ids=domain_matches,
                matched_records=[plane_index.records.get(mid) for mid in domain_matches],
                match_method="domain"
            )
        elif len(domain_matches) > 1:
            return PlaneMatch(
                status=MatchStatus.AMBIGUOUS,
                matched_ids=domain_matches,
                matched_records=[plane_index.records.get(mid) for mid in domain_matches],
                match_method="domain"
            )
    
    if use_uri and entity.uri and plane_index.by_uri:
        uri_matches = plane_index.by_uri.get(entity.uri.lower().strip(), [])
        if len(uri_matches) == 1:
            return PlaneMatch(
                status=MatchStatus.MATCHED,
                matched_ids=uri_matches,
                matched_records=[plane_index.records.get(mid) for mid in uri_matches],
                match_method="uri"
            )
        elif len(uri_matches) > 1:
            return PlaneMatch(
                status=MatchStatus.AMBIGUOUS,
                matched_ids=uri_matches,
                matched_records=[plane_index.records.get(mid) for mid in uri_matches],
                match_method="uri"
            )
    
    canonical = entity.canonical_name
    name_matches = plane_index.by_canonical_name.get(canonical, [])
    if len(name_matches) == 1:
        return PlaneMatch(
            status=MatchStatus.MATCHED,
            matched_ids=name_matches,
            matched_records=[plane_index.records.get(mid) for mid in name_matches],
            match_method="canonical_name"
        )
    elif len(name_matches) > 1:
        return PlaneMatch(
            status=MatchStatus.AMBIGUOUS,
            matched_ids=name_matches,
            matched_records=[plane_index.records.get(mid) for mid in name_matches],
            match_method="canonical_name"
        )
    
    contains_matches: list[str] = []
    for indexed_name, record_ids in plane_index.by_canonical_name.items():
        if canonical in indexed_name or indexed_name in canonical:
            contains_matches.extend(record_ids)
    
    contains_matches = list(set(contains_matches))
    
    if len(contains_matches) == 1:
        return PlaneMatch(
            status=MatchStatus.MATCHED,
            matched_ids=contains_matches,
            matched_records=[plane_index.records.get(mid) for mid in contains_matches],
            match_method="contains"
        )
    elif len(contains_matches) > 1:
        return PlaneMatch(
            status=MatchStatus.AMBIGUOUS,
            matched_ids=contains_matches,
            matched_records=[plane_index.records.get(mid) for mid in contains_matches],
            match_method="contains"
        )
    
    if entity.vendor and plane_index.by_vendor_product:
        vendor_key = normalize_string(entity.vendor)
        vendor_matches = plane_index.by_vendor_product.get(vendor_key, [])
        if len(vendor_matches) == 1:
            return PlaneMatch(
                status=MatchStatus.MATCHED,
                matched_ids=vendor_matches,
                matched_records=[plane_index.records.get(mid) for mid in vendor_matches],
                match_method="vendor"
            )
        elif len(vendor_matches) > 1:
            return PlaneMatch(
                status=MatchStatus.AMBIGUOUS,
                matched_ids=vendor_matches,
                matched_records=[plane_index.records.get(mid) for mid in vendor_matches],
                match_method="vendor"
            )
    
    return PlaneMatch(status=MatchStatus.UNMATCHED)


def correlate_entities_to_planes(
    entities: list[CandidateEntity],
    indexes: PlaneIndexes
) -> list[CorrelationResult]:
    """
    Correlate all entities to all planes.
    
    Per plane, per entity:
    - Pass 1: domain match (if applicable)
    - Pass 2: exact canonical normalized name match
    - Pass 3: unique contains match (strict; if >1 candidate → ambiguous)
    
    Returns matched/ambiguous/unmatched plus evidence refs.
    No shared IDs across planes. No truth keys.
    
    Args:
        entities: Candidate entities from normalization stage
        indexes: Plane indexes from indexing stage
        
    Returns:
        List of correlation results for each entity
    """
    results = []
    
    for entity in sorted(entities, key=lambda e: e.entity_id):
        result = CorrelationResult(entity=entity)
        
        result.idp = correlate_to_plane(entity, indexes.idp, use_domain=True)
        result.cmdb = correlate_to_plane(entity, indexes.cmdb, use_domain=False)
        result.cloud = correlate_to_plane(entity, indexes.cloud, use_domain=False, use_uri=True)
        result.finance = correlate_to_plane(entity, indexes.finance, use_domain=False)
        
        results.append(result)
    
    return results
