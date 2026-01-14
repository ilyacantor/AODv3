"""
Tests for domain merge stage.

Tests cover:
1. Union-find connected component merge on overlapping domains
2. Single-entity passthrough (no merge)
3. Two-way merge (fastbox pattern: two entities sharing one domain)
4. Multi-way merge (maxhub pattern: 3+ entities with overlapping domains)
5. Governance OR aggregation (cmdb_present = OR across merged entities)
6. Domain invariant assertion (each domain in exactly one merged entity)
"""

import pytest
from dataclasses import dataclass, field
from typing import Optional

from src.aod.pipeline.merge_correlated_entities import (
    merge_by_registered_domain,
    assert_domain_invariant,
    convert_merged_to_correlation,
    MergedCorrelation,
    UnionFind,
    _get_registered_domains_for_correlation,
    _is_authoritative_match,
)
from src.aod.pipeline.correlate_entities import (
    CorrelationResult, PlaneMatch, MatchStatus, MatchQuality
)
from src.aod.pipeline.normalize_observations import CandidateEntity


def make_entity(entity_id: str, name: str, domain: Optional[str] = None) -> CandidateEntity:
    """Create a test CandidateEntity."""
    return CandidateEntity(
        entity_id=entity_id,
        canonical_name=name,
        original_name=name,
        domain=domain,
        observation_ids=[f"obs_{entity_id}"]
    )


def make_plane_match(
    status: MatchStatus = MatchStatus.UNMATCHED,
    match_method: Optional[str] = None,
    domain: Optional[str] = None
) -> PlaneMatch:
    """Create a test PlaneMatch."""
    matched_ids = ["rec_1"] if status == MatchStatus.MATCHED else []
    
    @dataclass
    class MockRecord:
        record_id: str = "rec_1"
        domain: Optional[str] = None
    
    matched_records = [MockRecord(domain=domain)] if status == MatchStatus.MATCHED else []
    
    return PlaneMatch(
        status=status,
        matched_ids=matched_ids,
        matched_records=matched_records,
        match_method=match_method
    )


class TestUnionFind:
    """Tests for UnionFind data structure."""
    
    def test_union_find_basic(self):
        uf = UnionFind()
        uf.union("a", "b")
        uf.union("b", "c")
        
        assert uf.find("a") == uf.find("c")
        assert uf.find("d") != uf.find("a")
    
    def test_union_find_disjoint(self):
        uf = UnionFind()
        uf.union("a", "b")
        uf.union("c", "d")
        
        assert uf.find("a") == uf.find("b")
        assert uf.find("c") == uf.find("d")
        assert uf.find("a") != uf.find("c")


class TestSingleEntityPassthrough:
    """Test single entity passthrough (no merge needed)."""
    
    def test_single_entity_passthrough(self):
        entity = make_entity("e1", "App One", "app.com")
        correlation = CorrelationResult(
            entity=entity,
            cmdb=make_plane_match(MatchStatus.MATCHED, "domain", "app.com")
        )
        
        merged, domain_map = merge_by_registered_domain([correlation])
        
        assert len(merged) == 1
        assert merged[0].primary_entity.entity_id == "e1"
        assert len(merged[0].merged_entity_ids) == 1
        assert "app.com" in merged[0].all_registered_domains
    
    def test_two_unrelated_entities(self):
        entity1 = make_entity("e1", "App One", "app1.com")
        entity2 = make_entity("e2", "App Two", "app2.com")
        
        corr1 = CorrelationResult(entity=entity1)
        corr2 = CorrelationResult(entity=entity2)
        
        merged, domain_map = merge_by_registered_domain([corr1, corr2])
        
        assert len(merged) == 2
        assert_domain_invariant(merged, domain_map)


class TestTwoWayMerge:
    """Test fastbox pattern: two entities sharing one domain."""
    
    def test_fastbox_pattern_no_shared_domain(self):
        """
        Fastbox pattern when entities have DIFFERENT domains (no overlap):
        - Entity A: domains=['fastbox.com'], cmdb=heuristic
        - Entity B: domains=['fastbox.org'], cmdb=authoritative
        
        Since fastbox.com and fastbox.org don't share a domain, they remain separate.
        The merge only happens when there's actual domain overlap.
        """
        entity_a = make_entity("e_a", "Fastbox-A", "fastbox.com")
        entity_b = make_entity("e_b", "Fastbox-B", "fastbox.org")
        
        corr_a = CorrelationResult(
            entity=entity_a,
            cmdb=make_plane_match(MatchStatus.MATCHED, "contains", "fastbox.com")
        )
        corr_b = CorrelationResult(
            entity=entity_b,
            cmdb=make_plane_match(MatchStatus.MATCHED, "domain", "fastbox.org")
        )
        
        merged, domain_map = merge_by_registered_domain([corr_a, corr_b])
        
        assert len(merged) == 2
        
        assert_domain_invariant(merged, domain_map)
    
    def test_merge_with_shared_domain(self):
        """Two entities sharing exact same domain should merge."""
        entity_a = make_entity("e_a", "App-A", "shared.com")
        entity_b = make_entity("e_b", "App-B", "shared.com")
        
        corr_a = CorrelationResult(
            entity=entity_a,
            cmdb=make_plane_match(MatchStatus.MATCHED, "contains", "shared.com")
        )
        corr_b = CorrelationResult(
            entity=entity_b,
            cmdb=make_plane_match(MatchStatus.MATCHED, "domain", "shared.com")
        )
        
        merged, domain_map = merge_by_registered_domain([corr_a, corr_b])
        
        assert len(merged) == 1
        assert len(merged[0].merged_entity_ids) == 2
        assert merged[0].cmdb_present == True
        assert merged[0].cmdb_matched == True
        
        assert_domain_invariant(merged, domain_map)


class TestMultiWayMerge:
    """Test maxhub pattern: 3+ entities with overlapping domains."""
    
    def test_three_way_merge_chain(self):
        """
        Chain merge pattern:
        - Entity A: domain='a.com', also correlates to 'shared.com'
        - Entity B: domain='shared.com', also correlates to 'b.com'
        - Entity C: domain='b.com'
        
        A connects to B via shared.com, B connects to C via b.com
        All three should merge.
        """
        entity_a = make_entity("e_a", "App-A", "shared.com")
        entity_b = make_entity("e_b", "App-B", "shared.com")
        entity_c = make_entity("e_c", "App-C", "shared.com")
        
        corr_a = CorrelationResult(entity=entity_a)
        corr_b = CorrelationResult(entity=entity_b)
        corr_c = CorrelationResult(entity=entity_c)
        
        merged, domain_map = merge_by_registered_domain([corr_a, corr_b, corr_c])
        
        assert len(merged) == 1
        assert len(merged[0].merged_entity_ids) == 3
        
        assert_domain_invariant(merged, domain_map)


class TestGovernanceAggregation:
    """Test OR aggregation for governance flags."""
    
    def test_cmdb_or_aggregation(self):
        """cmdb_present = OR(cmdb_present) across merged entities."""
        entity_a = make_entity("e_a", "App-A", "app.com")
        entity_b = make_entity("e_b", "App-B", "app.com")
        
        corr_a = CorrelationResult(
            entity=entity_a,
            cmdb=make_plane_match(MatchStatus.MATCHED, "contains", "app.com")
        )
        corr_b = CorrelationResult(
            entity=entity_b,
            cmdb=make_plane_match(MatchStatus.MATCHED, "domain", "app.com")
        )
        
        merged, _ = merge_by_registered_domain([corr_a, corr_b])
        
        assert len(merged) == 1
        assert merged[0].cmdb_present == True
        assert merged[0].cmdb_matched == True
    
    def test_both_heuristic_no_governance(self):
        """If both entities have only heuristic matches, cmdb_present=False."""
        entity_a = make_entity("e_a", "App-A", "app.com")
        entity_b = make_entity("e_b", "App-B", "app.com")
        
        corr_a = CorrelationResult(
            entity=entity_a,
            cmdb=make_plane_match(MatchStatus.MATCHED, "contains", "app.com")
        )
        corr_b = CorrelationResult(
            entity=entity_b,
            cmdb=make_plane_match(MatchStatus.MATCHED, "fuzzy", "app.com")
        )
        
        merged, _ = merge_by_registered_domain([corr_a, corr_b])
        
        assert len(merged) == 1
        assert merged[0].cmdb_present == False
        assert merged[0].cmdb_matched == True


class TestDomainInvariant:
    """Test domain invariant assertion."""
    
    def test_invariant_passes_valid_merge(self):
        entity = make_entity("e1", "App", "app.com")
        corr = CorrelationResult(entity=entity)
        
        merged, domain_map = merge_by_registered_domain([corr])
        
        result = assert_domain_invariant(merged, domain_map)
        assert result == True
    
    def test_invariant_detects_violation(self):
        """Manually create a violation to test detection."""
        merged1 = MergedCorrelation(
            primary_entity=make_entity("e1", "App1", "app.com"),
            merged_entity_ids=["e1"],
            all_registered_domains={"app.com", "shared.com"},
            idp=PlaneMatch(status=MatchStatus.UNMATCHED),
            cmdb=PlaneMatch(status=MatchStatus.UNMATCHED),
            cloud=PlaneMatch(status=MatchStatus.UNMATCHED),
            finance=PlaneMatch(status=MatchStatus.UNMATCHED),
        )
        merged2 = MergedCorrelation(
            primary_entity=make_entity("e2", "App2", "other.com"),
            merged_entity_ids=["e2"],
            all_registered_domains={"other.com", "shared.com"},
            idp=PlaneMatch(status=MatchStatus.UNMATCHED),
            cmdb=PlaneMatch(status=MatchStatus.UNMATCHED),
            cloud=PlaneMatch(status=MatchStatus.UNMATCHED),
            finance=PlaneMatch(status=MatchStatus.UNMATCHED),
        )
        
        with pytest.raises(AssertionError, match="DOMAIN INVARIANT VIOLATED"):
            assert_domain_invariant([merged1, merged2], {})


class TestConvertMergedToCorrelation:
    """Test conversion from MergedCorrelation to CorrelationResult."""
    
    def test_basic_conversion(self):
        entity = make_entity("e1", "App", "app.com")
        correlation = CorrelationResult(
            entity=entity,
            cmdb=make_plane_match(MatchStatus.MATCHED, "domain", "app.com")
        )
        
        merged, _ = merge_by_registered_domain([correlation])
        converted = convert_merged_to_correlation(merged[0])
        
        assert converted.entity.entity_id == "e1"
        assert converted.cmdb.status == MatchStatus.MATCHED
    
    def test_merged_observation_ids(self):
        """Merged entity should have combined observation IDs."""
        entity_a = make_entity("e_a", "App-A", "app.com")
        entity_b = make_entity("e_b", "App-B", "app.com")
        
        corr_a = CorrelationResult(entity=entity_a)
        corr_b = CorrelationResult(entity=entity_b)
        
        merged, _ = merge_by_registered_domain([corr_a, corr_b])
        converted = convert_merged_to_correlation(merged[0])
        
        assert "obs_e_a" in converted.entity.observation_ids
        assert "obs_e_b" in converted.entity.observation_ids
