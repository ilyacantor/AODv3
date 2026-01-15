"""
TLD Variant Isolation Tests (Jan 2026)

These tests verify that cross-TLD brand matches (e.g., netcloud.com vs netcloud.io)
are stored as relationship metadata only, NOT as identity merge.

Key invariants:
1. Entity identity = registered domain (eTLD+1) ONLY
2. Cross-TLD matches emit RelatedDomainVariant edges, not identity merge
3. Domain promotion is blocked for heuristic match methods
4. Late-binding merge is blocked when primary registered domains differ
"""

import pytest
import uuid
from dataclasses import dataclass
from typing import Optional

from src.aod.pipeline.correlate_entities import (
    RelatedDomainVariant,
    PlaneMatch,
    MatchStatus,
    HEURISTIC_MATCH_METHODS,
    CROSS_TLD_MATCH_METHODS,
    AUTHORITATIVE_MATCH_METHODS,
)
from src.aod.pipeline.admission import (
    PROMOTION_ALLOWED_MATCH_METHODS,
    PROMOTION_BLOCKED_MATCH_METHODS,
)
from src.aod.pipeline.asset_identity import (
    CROSS_TLD_MERGE_BLOCKED,
    _get_primary_registered_domain,
)
from src.aod.pipeline.vendor_inference import extract_registered_domain
from src.aod.models.output_contracts import Asset, AssetIdentifiers, LensStatuses, LensCoverage


class TestCrossTLDMatchMethodClassification:
    """Test that cross-domain brand matching is classified as heuristic"""
    
    def test_cross_domain_brand_is_heuristic(self):
        """cross_domain_brand must be in HEURISTIC_MATCH_METHODS"""
        assert "cross_domain_brand" in HEURISTIC_MATCH_METHODS
    
    def test_cross_domain_brand_in_cross_tld_methods(self):
        """cross_domain_brand must be in CROSS_TLD_MATCH_METHODS"""
        assert "cross_domain_brand" in CROSS_TLD_MATCH_METHODS
    
    def test_authoritative_methods_do_not_include_cross_domain(self):
        """Authoritative methods must NOT include cross-domain heuristics"""
        assert "cross_domain_brand" not in AUTHORITATIVE_MATCH_METHODS
        assert "fuzzy" not in AUTHORITATIVE_MATCH_METHODS
        assert "contains" not in AUTHORITATIVE_MATCH_METHODS
    
    def test_domain_uri_canonical_are_authoritative(self):
        """Domain, URI, canonical_name are authoritative match methods"""
        assert "domain" in AUTHORITATIVE_MATCH_METHODS
        assert "uri" in AUTHORITATIVE_MATCH_METHODS
        assert "canonical_name" in AUTHORITATIVE_MATCH_METHODS


class TestDomainPromotionBlocking:
    """Test that domain promotion is blocked for heuristic match methods"""
    
    def test_promotion_blocked_includes_heuristics(self):
        """PROMOTION_BLOCKED_MATCH_METHODS must include all heuristics"""
        for method in HEURISTIC_MATCH_METHODS:
            assert method in PROMOTION_BLOCKED_MATCH_METHODS, f"{method} not in PROMOTION_BLOCKED"
    
    def test_promotion_blocked_includes_cross_tld(self):
        """PROMOTION_BLOCKED_MATCH_METHODS must include cross-TLD methods"""
        for method in CROSS_TLD_MATCH_METHODS:
            assert method in PROMOTION_BLOCKED_MATCH_METHODS, f"{method} not in PROMOTION_BLOCKED"
    
    def test_promotion_allowed_is_authoritative(self):
        """PROMOTION_ALLOWED_MATCH_METHODS must include authoritative methods"""
        for method in AUTHORITATIVE_MATCH_METHODS:
            assert method in PROMOTION_ALLOWED_MATCH_METHODS, f"{method} not in PROMOTION_ALLOWED"
    
    def test_promotion_allowed_excludes_heuristics(self):
        """PROMOTION_ALLOWED_MATCH_METHODS must NOT include heuristics"""
        for method in HEURISTIC_MATCH_METHODS:
            assert method not in PROMOTION_ALLOWED_MATCH_METHODS, f"{method} in PROMOTION_ALLOWED"


class TestRelatedDomainVariant:
    """Test RelatedDomainVariant dataclass for cross-TLD relationships"""
    
    def test_related_domain_variant_creation(self):
        """RelatedDomainVariant must store cross-TLD relationship metadata"""
        variant = RelatedDomainVariant(
            entity_domain="netcloud.com",
            related_domain="netcloud.io",
            match_basis="first_token",
            record_id="cmdb-123",
            plane="cmdb"
        )
        assert variant.entity_domain == "netcloud.com"
        assert variant.related_domain == "netcloud.io"
        assert variant.match_basis == "first_token"
        assert variant.record_id == "cmdb-123"
        assert variant.plane == "cmdb"
    
    def test_plane_match_has_related_domain_variants_field(self):
        """PlaneMatch must have related_domain_variants field"""
        match = PlaneMatch(status=MatchStatus.UNMATCHED)
        assert hasattr(match, 'related_domain_variants')
        assert match.related_domain_variants == []
    
    def test_plane_match_with_variants(self):
        """PlaneMatch can store multiple RelatedDomainVariant records"""
        variant1 = RelatedDomainVariant(
            entity_domain="netcloud.com",
            related_domain="netcloud.io",
            match_basis="first_token",
            record_id="cmdb-123",
            plane="cmdb"
        )
        variant2 = RelatedDomainVariant(
            entity_domain="netcloud.com",
            related_domain="netcloud.co",
            match_basis="collapsed_brand",
            record_id="idp-456",
            plane="idp"
        )
        match = PlaneMatch(
            status=MatchStatus.UNMATCHED,
            related_domain_variants=[variant1, variant2]
        )
        assert len(match.related_domain_variants) == 2
        assert match.related_domain_variants[0].related_domain == "netcloud.io"
        assert match.related_domain_variants[1].related_domain == "netcloud.co"


class TestTLDVariantIsolation:
    """
    CRITICAL: Test that TLD variants remain distinct entities.
    
    netcloud.com and netcloud.io must NEVER be merged into the same entity,
    even if they share brand tokens. They should be separate assets with
    relationship metadata indicating the brand match.
    """
    
    @pytest.mark.parametrize("domain1,domain2,should_be_distinct", [
        ("netcloud.com", "netcloud.io", True),
        ("flowbase.com", "flowbase.ai", True),
        ("servicenow.com", "service-now.com", True),
        ("datadog.com", "datadoghq.com", True),
        ("stripe.com", "stripe.io", True),
        ("slack.com", "slack.com", False),
        ("app.slack.com", "api.slack.com", False),
    ])
    def test_tld_variants_have_different_registered_domains(
        self, domain1: str, domain2: str, should_be_distinct: bool
    ):
        """TLD variants must have different registered domains (and thus different entity_ids)"""
        reg1 = extract_registered_domain(domain1)
        reg2 = extract_registered_domain(domain2)
        
        if should_be_distinct:
            assert reg1 != reg2, f"{domain1} and {domain2} should have distinct registered domains"
        else:
            assert reg1 == reg2, f"{domain1} and {domain2} should have same registered domain"
    
    def test_cross_tld_merge_blocked_constant_exists(self):
        """CROSS_TLD_MERGE_BLOCKED reason code must be defined"""
        assert CROSS_TLD_MERGE_BLOCKED == "CROSS_TLD_MERGE_BLOCKED"


class TestPrimaryRegisteredDomain:
    """Test _get_primary_registered_domain helper for cross-TLD safety"""
    
    def _make_asset(self, name: str, domains: list[str]) -> Asset:
        """Helper to create test assets"""
        return Asset(
            asset_id=uuid.uuid4(),
            tenant_id="test-tenant",
            run_id="test-run",
            name=name,
            identifiers=AssetIdentifiers(domains=domains),
            lens_status=LensStatuses(),
            lens_coverage=LensCoverage(),
        )
    
    def test_primary_domain_is_first_valid(self):
        """Primary registered domain should be first valid domain"""
        asset = self._make_asset("NetCloud", ["netcloud.com", "netcloud.io"])
        primary = _get_primary_registered_domain(asset)
        assert primary == "netcloud.com"
    
    def test_primary_domain_extracts_registered(self):
        """Primary domain should be eTLD+1, not subdomain"""
        asset = self._make_asset("NetCloud", ["app.netcloud.com", "api.netcloud.io"])
        primary = _get_primary_registered_domain(asset)
        assert primary == "netcloud.com"
    
    def test_no_domains_returns_none(self):
        """Asset with no domains should return None for primary"""
        asset = self._make_asset("Unknown App", [])
        primary = _get_primary_registered_domain(asset)
        assert primary is None
    
    def test_assets_with_different_primaries_should_not_merge(self):
        """Two assets with different primary domains should NOT be merged"""
        asset1 = self._make_asset("NetCloud.com", ["netcloud.com"])
        asset2 = self._make_asset("NetCloud.io", ["netcloud.io"])
        
        primary1 = _get_primary_registered_domain(asset1)
        primary2 = _get_primary_registered_domain(asset2)
        
        assert primary1 != primary2, "Different TLD variants should have different primaries"


class TestPlaneNamePropagation:
    """Test that plane_name is properly passed to RelatedDomainVariant"""
    
    def test_related_domain_variant_has_plane_field(self):
        """RelatedDomainVariant should have plane field set by caller"""
        variant = RelatedDomainVariant(
            entity_domain="netcloud.com",
            related_domain="netcloud.io",
            match_basis="first_token",
            record_id="cmdb-123",
            plane="cmdb"
        )
        assert variant.plane == "cmdb"
    
    def test_plane_field_values(self):
        """Plane field should support all valid plane names"""
        valid_planes = ["idp", "cmdb", "cloud", "finance"]
        for plane in valid_planes:
            variant = RelatedDomainVariant(
                entity_domain="test.com",
                related_domain="test.io",
                match_basis="first_token",
                record_id="test-123",
                plane=plane
            )
            assert variant.plane == plane


class TestMatchQualityClassification:
    """Test match quality classification for governance decisions"""
    
    def test_domain_match_is_authoritative(self):
        """Domain match should be classified as authoritative"""
        match = PlaneMatch(
            status=MatchStatus.MATCHED,
            matched_ids=["cmdb-123"],
            match_method="domain"
        )
        assert match.is_authoritative
    
    def test_fuzzy_match_is_not_authoritative(self):
        """Fuzzy match should NOT be classified as authoritative"""
        match = PlaneMatch(
            status=MatchStatus.MATCHED,
            matched_ids=["cmdb-123"],
            match_method="fuzzy"
        )
        assert not match.is_authoritative
    
    def test_cross_domain_brand_is_not_authoritative(self):
        """cross_domain_brand match should NOT be classified as authoritative"""
        match = PlaneMatch(
            status=MatchStatus.MATCHED,
            matched_ids=["cmdb-123"],
            match_method="cross_domain_brand"
        )
        assert not match.is_authoritative
    
    def test_contains_is_not_authoritative(self):
        """contains match should NOT be classified as authoritative"""
        match = PlaneMatch(
            status=MatchStatus.MATCHED,
            matched_ids=["cmdb-123"],
            match_method="contains"
        )
        assert not match.is_authoritative
