"""
Domain Merge Stage for Pipeline

Enforces the invariant: one asset per registered domain at materialization time.

Uses union-find (connected components) to merge entities that share overlapping 
registered domains, ensuring deterministic consolidation before admission.

Merge Rules:
- Governance: OR aggregation (cmdb_present/idp_present from ANY merged entity)
- Domains: Union of all registered domains from merged entities
- Evidence: Union of all evidence refs and observation IDs
- Activity: Latest activity timestamp wins
- Match status: Preserve both "matched" (any correlation) and "present" (governance-granting)
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
import logging

from .correlate_entities import CorrelationResult, PlaneMatch, MatchStatus, MatchQuality
from .normalize_observations import CandidateEntity
from .vendor_inference import extract_registered_domain
from .admission import _extract_all_domains_from_correlation

logger = logging.getLogger(__name__)


@dataclass
class MergedCorrelation:
    """A merged correlation result representing multiple entities with overlapping domains."""
    primary_entity: CandidateEntity
    merged_entity_ids: list[str]
    all_registered_domains: set[str]
    idp: PlaneMatch
    cmdb: PlaneMatch
    cloud: PlaneMatch
    finance: PlaneMatch
    idp_matched: bool = False
    cmdb_matched: bool = False
    idp_present: bool = False
    cmdb_present: bool = False
    merged_observation_ids: list[str] = field(default_factory=list)
    source_correlations: list[CorrelationResult] = field(default_factory=list)


class UnionFind:
    """Union-Find data structure for connected component detection."""
    
    def __init__(self):
        self.parent = {}
        self.rank = {}
    
    def find(self, x):
        if x not in self.parent:
            self.parent[x] = x
            self.rank[x] = 0
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]
    
    def union(self, x, y):
        px, py = self.find(x), self.find(y)
        if px == py:
            return
        if self.rank[px] < self.rank[py]:
            px, py = py, px
        self.parent[py] = px
        if self.rank[px] == self.rank[py]:
            self.rank[px] += 1


def _get_registered_domains_for_correlation(correlation: CorrelationResult) -> set[str]:
    """Extract all registered domains from a correlation result."""
    domains = set()
    
    if correlation.entity.domain:
        reg = extract_registered_domain(correlation.entity.domain)
        if reg:
            domains.add(reg)
    
    all_domains = _extract_all_domains_from_correlation(correlation)
    for d in all_domains:
        reg = extract_registered_domain(d)
        if reg:
            domains.add(reg)
    
    return domains


def _is_authoritative_match(plane_match: PlaneMatch) -> bool:
    """Check if a plane match grants governance (authoritative + matched)."""
    if plane_match.status not in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
        return False
    return plane_match.match_quality == MatchQuality.AUTHORITATIVE


def _is_any_match(plane_match: PlaneMatch) -> bool:
    """Check if a plane match exists (any method)."""
    return plane_match.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS)


def _merge_plane_match(matches: list[PlaneMatch]) -> PlaneMatch:
    """Merge multiple PlaneMatch objects, preserving the most complete info.
    
    Priority: 
    1. Matched > Ambiguous > Unmatched
    2. Authoritative > Heuristic (for governance decisions made separately)
    3. Combine all matched_ids and matched_records
    """
    if not matches:
        return PlaneMatch(status=MatchStatus.UNMATCHED)
    
    matched = [m for m in matches if m.status == MatchStatus.MATCHED]
    ambiguous = [m for m in matches if m.status == MatchStatus.AMBIGUOUS]
    
    if matched:
        best = matched[0]
        for m in matched:
            if m.match_quality == MatchQuality.AUTHORITATIVE:
                best = m
                break
    elif ambiguous:
        best = ambiguous[0]
    else:
        return PlaneMatch(status=MatchStatus.UNMATCHED)
    
    all_ids = set()
    all_records = []
    seen_record_ids = set()
    
    for m in matches:
        if m.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
            all_ids.update(m.matched_ids)
            for rec in m.matched_records:
                rec_id = getattr(rec, 'record_id', None)
                if rec_id and rec_id not in seen_record_ids:
                    seen_record_ids.add(rec_id)
                    all_records.append(rec)
    
    return PlaneMatch(
        status=best.status,
        matched_ids=list(all_ids),
        matched_records=all_records,
        match_method=best.match_method,
        match_key=best.match_key,
        ambiguity_code=best.ambiguity_code,
        disambiguation_detail=best.disambiguation_detail
    )


def merge_by_registered_domain(
    correlations: list[CorrelationResult]
) -> tuple[list[MergedCorrelation], dict[str, str]]:
    """
    Merge correlations that share overlapping registered domains.
    
    Uses union-find to find connected components where any shared registered domain
    links entities together. This ensures fastbox.com + fastbox.org entities 
    are merged if they share fastbox.org.
    
    Args:
        correlations: List of CorrelationResult objects from correlate_entities_to_planes
        
    Returns:
        Tuple of:
        - List of MergedCorrelation objects (one per connected component)
        - Domain-to-component mapping for assertion validation
    """
    if not correlations:
        return [], {}
    
    uf = UnionFind()
    entity_id_to_domains: dict[str, set[str]] = {}
    domain_to_entity_ids: dict[str, list[str]] = {}
    entity_id_to_correlation: dict[str, CorrelationResult] = {}
    
    for corr in correlations:
        entity_id = corr.entity.entity_id
        entity_id_to_correlation[entity_id] = corr
        
        domains = _get_registered_domains_for_correlation(corr)
        entity_id_to_domains[entity_id] = domains
        
        for domain in domains:
            if domain not in domain_to_entity_ids:
                domain_to_entity_ids[domain] = []
            domain_to_entity_ids[domain].append(entity_id)
    
    for domain, entity_ids in domain_to_entity_ids.items():
        if len(entity_ids) > 1:
            first = entity_ids[0]
            for other in entity_ids[1:]:
                uf.union(first, other)
    
    components: dict[str, list[str]] = {}
    for entity_id in entity_id_to_correlation:
        root = uf.find(entity_id)
        if root not in components:
            components[root] = []
        components[root].append(entity_id)
    
    merged_results = []
    domain_to_component: dict[str, str] = {}
    
    for component_id, entity_ids in components.items():
        corrs = [entity_id_to_correlation[eid] for eid in entity_ids]
        
        all_domains: set[str] = set()
        all_observation_ids: list[str] = []
        
        idp_matches = []
        cmdb_matches = []
        cloud_matches = []
        finance_matches = []
        
        idp_matched = False
        cmdb_matched = False
        idp_present = False
        cmdb_present = False
        
        for corr in corrs:
            all_domains.update(entity_id_to_domains.get(corr.entity.entity_id, set()))
            all_observation_ids.extend(corr.entity.observation_ids)
            
            idp_matches.append(corr.idp)
            cmdb_matches.append(corr.cmdb)
            cloud_matches.append(corr.cloud)
            finance_matches.append(corr.finance)
            
            if _is_any_match(corr.idp):
                idp_matched = True
            if _is_any_match(corr.cmdb):
                cmdb_matched = True
            if _is_authoritative_match(corr.idp):
                idp_present = True
            if _is_authoritative_match(corr.cmdb):
                cmdb_present = True
        
        primary = corrs[0].entity
        for corr in corrs:
            if corr.entity.domain:
                primary = corr.entity
                break
        
        merged_idp = _merge_plane_match(idp_matches)
        merged_cmdb = _merge_plane_match(cmdb_matches)
        merged_cloud = _merge_plane_match(cloud_matches)
        merged_finance = _merge_plane_match(finance_matches)
        
        for domain in all_domains:
            if domain in domain_to_component:
                logger.error(
                    f"INVARIANT VIOLATION: Domain {domain} appears in multiple components! "
                    f"Component {component_id} and {domain_to_component[domain]}"
                )
            domain_to_component[domain] = component_id
        
        merged = MergedCorrelation(
            primary_entity=primary,
            merged_entity_ids=entity_ids,
            all_registered_domains=all_domains,
            idp=merged_idp,
            cmdb=merged_cmdb,
            cloud=merged_cloud,
            finance=merged_finance,
            idp_matched=idp_matched,
            cmdb_matched=cmdb_matched,
            idp_present=idp_present,
            cmdb_present=cmdb_present,
            merged_observation_ids=list(set(all_observation_ids)),
            source_correlations=corrs
        )
        merged_results.append(merged)
        
        if len(entity_ids) > 1:
            logger.info(
                f"Merged {len(entity_ids)} entities by domain connectivity: "
                f"domains={sorted(all_domains)}, entity_ids={entity_ids}"
            )
    
    return merged_results, domain_to_component


def assert_domain_invariant(
    merged_correlations: list[MergedCorrelation],
    domain_to_component: dict[str, str]
) -> bool:
    """
    Assert the invariant: every registered domain appears in exactly one merged entity.
    
    This is a non-negotiable check that fails tests if violated.
    
    Args:
        merged_correlations: List of merged correlation results
        domain_to_component: Mapping from domain to component ID
        
    Returns:
        True if invariant holds, raises AssertionError otherwise
    """
    seen_domains: dict[str, str] = {}
    
    for merged in merged_correlations:
        component_id = merged.merged_entity_ids[0] if merged.merged_entity_ids else "unknown"
        
        for domain in merged.all_registered_domains:
            if domain in seen_domains:
                raise AssertionError(
                    f"DOMAIN INVARIANT VIOLATED: '{domain}' appears in multiple merged entities: "
                    f"component {seen_domains[domain]} and component {component_id}"
                )
            seen_domains[domain] = component_id
    
    return True


def convert_merged_to_correlation(merged: MergedCorrelation) -> CorrelationResult:
    """
    Convert a MergedCorrelation back to a CorrelationResult for admission.
    
    The resulting CorrelationResult has:
    - entity with combined observation_ids
    - merged plane matches
    - governance flags computed from OR aggregation
    """
    merged_entity = CandidateEntity(
        entity_id=merged.primary_entity.entity_id,
        canonical_name=merged.primary_entity.canonical_name,
        original_name=merged.primary_entity.original_name,
        domain=merged.primary_entity.domain,
        hostname=merged.primary_entity.hostname,
        uri=merged.primary_entity.uri,
        vendor=merged.primary_entity.vendor,
        vendor_hypothesis=merged.primary_entity.vendor_hypothesis,
        observation_ids=merged.merged_observation_ids,
        source=merged.primary_entity.source
    )
    
    return CorrelationResult(
        entity=merged_entity,
        idp=merged.idp,
        cmdb=merged.cmdb,
        cloud=merged.cloud,
        finance=merged.finance
    )
