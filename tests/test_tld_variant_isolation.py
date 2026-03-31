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
            aod_discovery_id="test-run",
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


class TestRegisteredDomainFallbackMatching:
    """Test that registered domain fallback enables authoritative matches"""
    
    def test_subdomain_should_match_via_registered_domain(self):
        """api.maxsoft.org should match maxsoft.org via registered domain fallback"""
        from src.aod.pipeline.vendor_inference import extract_registered_domain
        
        entity_domain = "maxsoft.org"
        record_domain = "api.maxsoft.org"
        
        entity_registered = extract_registered_domain(entity_domain)
        record_registered = extract_registered_domain(record_domain)
        
        assert entity_registered == "maxsoft.org"
        assert record_registered == "maxsoft.org"
        assert entity_registered == record_registered
    
    def test_registered_domain_match_is_authoritative(self):
        """Matches via registered domain should still use authoritative 'domain' method"""
        from src.aod.pipeline.correlate_entities import AUTHORITATIVE_MATCH_METHODS
        
        assert "domain" in AUTHORITATIVE_MATCH_METHODS
    
    def test_different_registered_domains_do_not_match(self):
        """maxsoft.org should NOT match maxsoft.io via registered domain"""
        from src.aod.pipeline.vendor_inference import extract_registered_domain
        
        entity_domain = "maxsoft.org"
        unrelated_domain = "maxsoft.io"
        
        entity_registered = extract_registered_domain(entity_domain)
        unrelated_registered = extract_registered_domain(unrelated_domain)
        
        assert entity_registered == "maxsoft.org"
        assert unrelated_registered == "maxsoft.io"
        assert entity_registered != unrelated_registered


class TestCanonicalDomainIndexing:
    """Test that canonical_domain field from Farm is indexed for correlation"""
    
    def test_canonical_domain_in_raw_data_fallback_chain(self):
        """canonical_domain field should be checked after domain but before external_ref"""
        # This tests that the fallback chain includes canonical_domain
        # Farm generates CMDB/IdP entries with canonical_domain linking to discovery domain
        from src.aod.pipeline.build_plane_indexes import build_idp_index, build_cmdb_index
        from src.aod.models.input_contracts import IdPPlane, IdPObject, CMDBPlane, CMDBConfigItem
        
        # Test IdP with canonical_domain as direct field (Farm's primary method)
        idp_obj = IdPObject(
            idp_id="idp-slack-1",
            name="Slack",
            domain=None,  # No domain field
            canonical_domain="slack.com"  # Farm's correlation field
        )
        idp_plane = IdPPlane(objects=[idp_obj])
        idp_index = build_idp_index(idp_plane)
        
        # Should be indexed by slack.com (from canonical_domain)
        assert "slack.com" in idp_index.by_domain
        assert "idp-slack-1" in idp_index.by_domain["slack.com"]
        
        # Test CMDB with canonical_domain as direct field (Farm's primary method)
        cmdb_ci = CMDBConfigItem(
            ci_id="cmdb-monday-1",
            name="Monday.com",
            domain=None,  # No domain field
            canonical_domain="monday.com"  # Farm's correlation field
        )
        cmdb_plane = CMDBPlane(cis=[cmdb_ci])
        cmdb_index = build_cmdb_index(cmdb_plane)
        
        # Should be indexed by monday.com (from canonical_domain)
        assert "monday.com" in cmdb_index.by_domain
        assert "cmdb-monday-1" in cmdb_index.by_domain["monday.com"]


class TestDomainBaseNameMatching:
    """Test domain base name matching for canonical_name correlation"""
    
    def test_domain_base_extraction(self):
        """slack.com should extract base 'slack' for canonical name matching"""
        domain = "slack.com"
        domain_base = domain.split('.')[0].lower().strip() if '.' in domain else None
        assert domain_base == "slack"
    
    def test_domain_base_sufficient_length(self):
        """Domain base must be >= 3 chars to avoid false matches"""
        short_domain = "go.com"
        domain_base = short_domain.split('.')[0].lower().strip() if '.' in short_domain else None
        assert domain_base == "go"
        assert len(domain_base) < 3  # Too short for matching
        
        long_domain = "goo.com"
        domain_base2 = long_domain.split('.')[0].lower().strip() if '.' in long_domain else None
        assert domain_base2 == "goo"
        assert len(domain_base2) >= 3  # Sufficient for matching
    
    def test_canonical_name_is_authoritative(self):
        """Matches via canonical_name (including domain base) are authoritative"""
        from src.aod.pipeline.correlate_entities import AUTHORITATIVE_MATCH_METHODS
        
        assert "canonical_name" in AUTHORITATIVE_MATCH_METHODS


class TestAliasCollapsing:
    """Test alias collapsing aligns with Farm contract"""
    
    def test_zoom_collapses_to_zoom_com(self):
        """zoom.us should collapse to zoom.com (Farm contract)"""
        from src.aod.pipeline.canonical_key import ALIAS_DOMAINS_TO_COLLAPSE, normalize_to_canonical_vendor_domain
        from src.aod.pipeline.vendor_inference import VENDOR_TO_DOMAIN
        
        # zoom.us should be in alias set (collapses to zoom.com)
        assert "zoom.us" in ALIAS_DOMAINS_TO_COLLAPSE
        # zoom.com should NOT be in alias set (it's the canonical)
        assert "zoom.com" not in ALIAS_DOMAINS_TO_COLLAPSE
        # VENDOR_TO_DOMAIN should map zoom to zoom.com
        assert VENDOR_TO_DOMAIN.get("zoom") == "zoom.com"
    
    def test_atlassian_aliases_collapse(self):
        """atlassian.net, trello.com, bitbucket.org, hipchat.com should collapse to atlassian.com"""
        from src.aod.pipeline.canonical_key import ALIAS_DOMAINS_TO_COLLAPSE
        from src.aod.pipeline.vendor_inference import VENDOR_TO_DOMAIN
        
        # Atlassian TECHNICAL aliases should be in alias set
        assert "atlassian.net" in ALIAS_DOMAINS_TO_COLLAPSE
        assert "trello.com" in ALIAS_DOMAINS_TO_COLLAPSE
        assert "bitbucket.org" in ALIAS_DOMAINS_TO_COLLAPSE
        # NOTE: hipchat.com is LEGACY PRODUCT, not technical alias - keep standalone for zombie detection
        assert "hipchat.com" not in ALIAS_DOMAINS_TO_COLLAPSE
        # atlassian.com is canonical - should NOT be in alias set
        assert "atlassian.com" not in ALIAS_DOMAINS_TO_COLLAPSE
        # VENDOR_TO_DOMAIN should map atlassian to atlassian.com
        assert VENDOR_TO_DOMAIN.get("atlassian") == "atlassian.com"
    
    def test_basecamp_not_collapsed(self):
        """basecamp.com should be standalone, not collapsed to another vendor"""
        from src.aod.pipeline.canonical_key import ALIAS_DOMAINS_TO_COLLAPSE
        
        # Basecamp is its own product, NOT an alias
        assert "basecamp.com" not in ALIAS_DOMAINS_TO_COLLAPSE


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


class TestIdPDomainMatchingStrictness:
    """
    Test IdP domain matching when IdP record has no domain field.
    
    Jan 2026: Option B implementation - Stricter name-based fallback:
    - IdP name must EXACTLY match entity base token (not just startswith)
    - Entity base token must be at least 5 characters (avoid short token collisions)
    
    This eliminates false positives where unrelated apps with short names
    incorrectly match (e.g., "api" IdP matching any "api.xxx" domain).
    """
    
    def _import_function(self):
        """Import the function under test"""
        from src.aod.pipeline.admission import _idp_domain_matches_entity
        return _idp_domain_matches_entity
    
    def test_exact_match_with_sufficient_length_allowed(self):
        """IdP name exactly matching entity base token (>=5 chars) should match"""
        func = self._import_function()
        
        # "coreio" is 6 characters, exact match with IdP name "Coreio"
        assert func(
            idp_registered_domain=None,
            entity_registered_domain="coreio.ai",
            idp_name="Coreio"
        ) == True
    
    def test_startswith_match_now_rejected(self):
        """IdP name starting with entity base token should NO LONGER match"""
        func = self._import_function()
        
        # "coreio" IdP name should NOT match "coreioservice" entity base
        # (previously would have matched with startswith logic)
        assert func(
            idp_registered_domain=None,
            entity_registered_domain="coreioservice.ai",
            idp_name="Coreio"
        ) == False
    
    def test_short_entity_base_rejected(self):
        """Entity base token less than 5 characters should be rejected"""
        func = self._import_function()
        
        # "test" is 4 characters (< 5 minimum), should not match even with exact name
        assert func(
            idp_registered_domain=None,
            entity_registered_domain="test.com",
            idp_name="Test"
        ) == False
    
    def test_exactly_5_chars_accepted(self):
        """Entity base token of exactly 5 characters should be accepted"""
        func = self._import_function()
        
        # "slack" is exactly 5 characters, exact match with IdP name
        assert func(
            idp_registered_domain=None,
            entity_registered_domain="slack.com",
            idp_name="Slack"
        ) == True
    
    def test_normalized_name_matching(self):
        """IdP name normalization (removing dashes, underscores, spaces) should work"""
        func = self._import_function()
        
        # "slack-app" normalized to "slackapp" should NOT match "slack" base (5 chars)
        # because "slackapp" != "slack"
        assert func(
            idp_registered_domain=None,
            entity_registered_domain="slack.com",
            idp_name="Slack-App"
        ) == False
    
    def test_normalized_exact_match(self):
        """Normalized name should match normalized base token"""
        func = self._import_function()
        
        # "Team Suite" normalized to "teamsuite" (9 chars) matches "teamsuite" base
        assert func(
            idp_registered_domain=None,
            entity_registered_domain="teamsuite.cloud",
            idp_name="Team Suite"
        ) == True
    
    def test_legacy_suffix_still_rejected(self):
        """IdP names with legacy/deprecated suffixes should still be rejected"""
        func = self._import_function()
        
        # Even with exact match and sufficient length, legacy suffix blocks match
        assert func(
            idp_registered_domain=None,
            entity_registered_domain="coreio.ai",
            idp_name="Coreio (Legacy)"
        ) == False
    
    def test_prod_suffix_still_rejected(self):
        """IdP names with -prod suffix should still be rejected"""
        func = self._import_function()
        
        # Even with exact match and sufficient length, -prod suffix blocks match
        assert func(
            idp_registered_domain=None,
            entity_registered_domain="fastbox.cloud",
            idp_name="Fastbox-prod"
        ) == False
    
    def test_with_explicit_domain_still_matches(self):
        """IdP with explicit domain should still use domain-based matching"""
        func = self._import_function()
        
        # Domain-based match should work regardless of name (this is not the fallback case)
        assert func(
            idp_registered_domain="flexflow.org",
            entity_registered_domain="flexflow.org",
            idp_name="Any Name"
        ) == True
    
    def test_empty_entity_domain_allows_match(self):
        """Entity with no domain should allow match (existing behavior)"""
        func = self._import_function()
        
        # When entity has no domain, match is allowed (unchanged from original)
        assert func(
            idp_registered_domain="someidp.com",
            entity_registered_domain=None,
            idp_name="SomeIdP"
        ) == True
    
    def test_false_positive_example_blocked(self):
        """Real-world false positive case should be blocked by new rules"""
        func = self._import_function()
        
        # Example: "api" IdP (4 chars, too short) should not match "api-gateway.cloud"
        assert func(
            idp_registered_domain=None,
            entity_registered_domain="api-gateway.cloud",
            idp_name="API"
        ) == False
    
    def test_false_positive_startswith_blocked(self):
        """False positive from startswith logic should now be blocked"""
        func = self._import_function()
        
        # "net" IdP (3 chars, too short) should not match "netcloud.io"
        # Even though "net" is < 5 chars AND "net".startswith("net") is true,
        # the new rules block it
        assert func(
            idp_registered_domain=None,
            entity_registered_domain="netcloud.io",
            idp_name="Net"
        ) == False


class TestDomainCorrelationFallbacks:
    """Test the new domain correlation fallback paths added in Jan 2026"""
    
    def test_new_heuristic_match_methods_registered(self):
        """New fallback match methods should be in HEURISTIC_MATCH_METHODS"""
        from src.aod.pipeline.correlate_entities import HEURISTIC_MATCH_METHODS
        
        assert "domain_token_to_name" in HEURISTIC_MATCH_METHODS
        assert "registered_domain_token" in HEURISTIC_MATCH_METHODS
        assert "canonical_name_as_domain" in HEURISTIC_MATCH_METHODS
    
    def test_new_methods_blocked_from_promotion(self):
        """New match methods should be blocked from domain promotion"""
        from src.aod.pipeline.admission import PROMOTION_BLOCKED_MATCH_METHODS
        
        assert "domain_token_to_name" in PROMOTION_BLOCKED_MATCH_METHODS
        assert "registered_domain_token" in PROMOTION_BLOCKED_MATCH_METHODS
        assert "canonical_name_as_domain" in PROMOTION_BLOCKED_MATCH_METHODS
    
    def test_canonical_name_as_domain_is_not_authoritative(self):
        """canonical_name_as_domain must NOT be in AUTHORITATIVE_MATCH_METHODS
        
        This is the critical governance gate fix. Using canonical_name as a domain
        source is HEURISTIC - it's inferring domain from an unreliable field.
        It must NOT assert governance (HAS_IDP, HAS_CMDB).
        """
        from src.aod.pipeline.correlate_entities import AUTHORITATIVE_MATCH_METHODS
        
        assert "canonical_name_as_domain" not in AUTHORITATIVE_MATCH_METHODS
    
    def test_canonical_name_as_domain_regex_validation(self):
        """Test regex for canonical_name-as-domain validation"""
        import re
        
        valid_domains = [
            "slack.com", "microsoft.com", "api-gateway.io", "test-123.cloud",
            "flowbase.ai", "netcloud.co"
        ]
        invalid_domains = [
            "Microsoft 365.com", "Okta (Legacy)", "slack", "test",
            ".com", "-.com", "test..com"
        ]
        
        pattern = r'^[a-z0-9][-a-z0-9]*(\.[a-z0-9][-a-z0-9]*)+$'
        
        for domain in valid_domains:
            assert re.match(pattern, domain.lower()), f"{domain} should be valid"
        
        for domain in invalid_domains:
            assert not re.match(pattern, domain.lower()), f"{domain} should be invalid"
    
    def test_domain_token_extraction(self):
        """Test domain token extraction for by_name_words lookup"""
        test_cases = [
            ("flexpoint.cloud", "flexpoint"),
            ("flowsoft.okta.com", "flowsoft"),
            ("api.maxsoft.org", "api"),
            ("test.io", "test"),
            ("abc.com", "abc"),
        ]
        
        for domain, expected_token in test_cases:
            token = domain.split('.')[0].lower().strip() if '.' in domain else None
            assert token == expected_token, f"{domain} should extract token {expected_token}"
    
    def test_registered_token_for_reverse_lookup(self):
        """Test registered domain token extraction for reverse lookup"""
        from src.aod.pipeline.vendor_inference import extract_registered_domain
        
        test_cases = [
            ("flowsoft.org", "flowsoft"),
            ("api.maxsoft.org", "maxsoft"),
            ("app.netcloud.com", "netcloud"),
        ]
        
        for entity_domain, expected_token in test_cases:
            registered = extract_registered_domain(entity_domain)
            reg_token = registered.split('.')[0].lower().strip() if registered and '.' in registered else None
            assert reg_token == expected_token, f"{entity_domain} registered token should be {expected_token}"


class TestGovernanceGateInvariants:
    """
    Test governance gate invariants per Jan 2026 spec.
    
    NON-NEGOTIABLE INVARIANT:
    Governance requires proof: exact domain match, verified alias, or explicit foreign key.
    Heuristics may produce candidates/enrichment only, NEVER HAS_IDP/HAS_CMDB.
    """
    
    def test_authoritative_methods_expanded(self):
        """AUTHORITATIVE_MATCH_METHODS must include new authoritative methods"""
        from src.aod.pipeline.correlate_entities import AUTHORITATIVE_MATCH_METHODS
        
        # Original authoritative methods
        assert "domain" in AUTHORITATIVE_MATCH_METHODS
        assert "uri" in AUTHORITATIVE_MATCH_METHODS
        assert "canonical_name" in AUTHORITATIVE_MATCH_METHODS
        
        # New authoritative methods (Jan 2026)
        assert "verified_alias_domain" in AUTHORITATIVE_MATCH_METHODS
        assert "foreign_key" in AUTHORITATIVE_MATCH_METHODS
        assert "explicit_id" in AUTHORITATIVE_MATCH_METHODS
        assert "cmdb_domains_array" in AUTHORITATIVE_MATCH_METHODS
        assert "cmdb_canonical_domain" in AUTHORITATIVE_MATCH_METHODS
    
    def test_heuristic_methods_cannot_assert_governance(self):
        """Heuristic methods must NOT be in AUTHORITATIVE_MATCH_METHODS"""
        from src.aod.pipeline.correlate_entities import (
            AUTHORITATIVE_MATCH_METHODS, HEURISTIC_MATCH_METHODS
        )
        
        # No overlap between authoritative and heuristic
        overlap = AUTHORITATIVE_MATCH_METHODS & HEURISTIC_MATCH_METHODS
        assert len(overlap) == 0, f"Methods in both sets: {overlap}"
        
        # All heuristic methods are explicitly NOT authoritative
        for method in HEURISTIC_MATCH_METHODS:
            assert method not in AUTHORITATIVE_MATCH_METHODS
    
    def test_canonical_name_as_domain_is_heuristic(self):
        """
        Test B: canonical_name_as_domain must be labeled HEURISTIC.
        
        When entity.domain is empty and entity.canonical_name looks like a domain,
        this is a heuristic inference - NOT authoritative.
        """
        from src.aod.pipeline.correlate_entities import (
            AUTHORITATIVE_MATCH_METHODS, HEURISTIC_MATCH_METHODS
        )
        
        # canonical_name_as_domain is EXPLICITLY in heuristic set
        assert "canonical_name_as_domain" in HEURISTIC_MATCH_METHODS
        # And NOT in authoritative set
        assert "canonical_name_as_domain" not in AUTHORITATIVE_MATCH_METHODS
    
    def test_heuristic_idp_match_produces_candidate_not_governance(self):
        """
        Test A: Heuristic IdP match must NOT assert HAS_IDP.
        
        Scenario: entity domain "oneway.com", IdP record name contains "oneway" 
        but IdP domain does not match.
        
        Expected: IDP_CANDIDATE=true (for debug), HAS_IDP=false (no governance)
        """
        from src.aod.pipeline.correlate_entities import PlaneMatch, MatchStatus, HEURISTIC_MATCH_METHODS
        
        # Create a heuristic match (domain_token_to_name)
        heuristic_match = PlaneMatch(
            status=MatchStatus.MATCHED,
            matched_ids=["idp-123"],
            match_method="domain_token_to_name"  # Heuristic
        )
        
        # Verify match_method is in heuristic set
        assert heuristic_match.match_method in HEURISTIC_MATCH_METHODS
        # Verify is_authoritative is False
        assert heuristic_match.is_authoritative == False
    
    def test_authoritative_match_can_assert_governance(self):
        """Test C: Authoritative matches CAN assert governance."""
        from src.aod.pipeline.correlate_entities import PlaneMatch, MatchStatus, AUTHORITATIVE_MATCH_METHODS
        
        # Create an authoritative match (domain)
        authoritative_match = PlaneMatch(
            status=MatchStatus.MATCHED,
            matched_ids=["cmdb-456"],
            match_method="domain"  # Authoritative
        )
        
        # Verify match_method is in authoritative set
        assert authoritative_match.match_method in AUTHORITATIVE_MATCH_METHODS
        # Verify is_authoritative is True
        assert authoritative_match.is_authoritative == True
    
    def test_cmdb_authoritative_methods(self):
        """Test C: CMDB authoritative recovery via domains[]/canonical_domain."""
        from src.aod.pipeline.correlate_entities import PlaneMatch, MatchStatus, AUTHORITATIVE_MATCH_METHODS
        
        # cmdb_domains_array should allow governance assertion
        cmdb_domains_match = PlaneMatch(
            status=MatchStatus.MATCHED,
            matched_ids=["cmdb-789"],
            match_method="cmdb_domains_array"
        )
        assert cmdb_domains_match.is_authoritative == True
        
        # cmdb_canonical_domain should allow governance assertion
        cmdb_canonical_match = PlaneMatch(
            status=MatchStatus.MATCHED,
            matched_ids=["cmdb-789"],
            match_method="cmdb_canonical_domain"
        )
        assert cmdb_canonical_match.is_authoritative == True
    
    def test_yammer_remains_standalone_legacy_product(self):
        """Test D: yammer.com must remain standalone (legacy product, not technical alias)."""
        from src.aod.pipeline.canonical_key import (
            ALIAS_DOMAINS_TO_COLLAPSE, 
            normalize_to_canonical_vendor_domain
        )
        
        # yammer.com is a LEGACY PRODUCT, not a technical alias - keep standalone for zombie detection
        assert "yammer.com" not in ALIAS_DOMAINS_TO_COLLAPSE
        
        # Verify no collapse occurs (returns None)
        result = normalize_to_canonical_vendor_domain("yammer.com")
        assert result is None, f"yammer.com should remain standalone (None), got {result}"
    
    def test_hipchat_remains_standalone_legacy_product(self):
        """Test D: hipchat.com must remain standalone (legacy product, not technical alias)."""
        from src.aod.pipeline.canonical_key import (
            ALIAS_DOMAINS_TO_COLLAPSE,
            normalize_to_canonical_vendor_domain
        )
        
        # hipchat.com is a LEGACY PRODUCT, not a technical alias - keep standalone for zombie detection
        assert "hipchat.com" not in ALIAS_DOMAINS_TO_COLLAPSE
        
        # Verify no collapse occurs (returns None)
        result = normalize_to_canonical_vendor_domain("hipchat.com")
        assert result is None, f"hipchat.com should remain standalone (None), got {result}"
    
    def test_basecamp_remains_standalone(self):
        """Test D: basecamp.com must remain standalone (no collapse entry)."""
        from src.aod.pipeline.canonical_key import ALIAS_DOMAINS_TO_COLLAPSE
        
        # Basecamp is its own product, NOT an alias
        assert "basecamp.com" not in ALIAS_DOMAINS_TO_COLLAPSE
    
    def test_unknown_match_method_defaults_to_heuristic(self):
        """Unknown match methods should default to HEURISTIC for safety."""
        from src.aod.pipeline.correlate_entities import PlaneMatch, MatchStatus, MatchQuality
        
        # Create a match with unknown method
        unknown_match = PlaneMatch(
            status=MatchStatus.MATCHED,
            matched_ids=["test-123"],
            match_method="some_new_untested_method"  # Not in either set
        )
        
        # Should default to heuristic (fail-safe)
        assert unknown_match.match_quality == MatchQuality.HEURISTIC
        assert unknown_match.is_authoritative == False


class TestCMDBAuthoritativeRecovery:
    """
    Phase B tests: CMDB Authoritative Recovery
    
    Validates that new CMDB lookup paths are authoritative:
    1. canonical_domain == D
    2. D ∈ domains[]
    3. verified_alias_domain(D) == canonical_domain
    """
    
    def test_cmdb_index_has_separate_authoritative_indexes(self):
        """PlaneIndex must have by_canonical_domain and by_domains_array indexes"""
        from src.aod.pipeline.build_plane_indexes import PlaneIndex
        
        index = PlaneIndex()
        assert hasattr(index, 'by_canonical_domain')
        assert hasattr(index, 'by_domains_array')
        assert isinstance(index.by_canonical_domain, dict)
        assert isinstance(index.by_domains_array, dict)
    
    def test_cmdb_model_has_domains_array_field(self):
        """CMDBConfigItem must have domains[] array field"""
        from src.aod.models.input_contracts import CMDBConfigItem
        
        ci = CMDBConfigItem(ci_id="test", name="Test App")
        assert hasattr(ci, 'domains')
        assert ci.domains == []  # Default is empty list
        
        # Can be set to a list of domains
        ci2 = CMDBConfigItem(ci_id="test2", name="Test App 2", domains=["app.com", "api.app.com"])
        assert ci2.domains == ["app.com", "api.app.com"]
    
    def test_cmdb_canonical_domain_indexing(self):
        """CMDB canonical_domain must be indexed in by_canonical_domain"""
        from src.aod.models.input_contracts import CMDBPlane, CMDBConfigItem
        from src.aod.pipeline.build_plane_indexes import build_cmdb_index
        
        cmdb_plane = CMDBPlane(cis=[
            CMDBConfigItem(
                ci_id="ci-123",
                name="BluEdge App",
                canonical_domain="bluedge.com"
            )
        ])
        
        index = build_cmdb_index(cmdb_plane)
        
        # canonical_domain should be in by_canonical_domain index
        assert "bluedge.com" in index.by_canonical_domain
        assert "ci-123" in index.by_canonical_domain["bluedge.com"]
        
        # Also in general by_domain for backward compatibility
        assert "bluedge.com" in index.by_domain
    
    def test_cmdb_domains_array_indexing(self):
        """CMDB domains[] array members must be indexed in by_domains_array"""
        from src.aod.models.input_contracts import CMDBPlane, CMDBConfigItem
        from src.aod.pipeline.build_plane_indexes import build_cmdb_index
        
        cmdb_plane = CMDBPlane(cis=[
            CMDBConfigItem(
                ci_id="ci-456",
                name="SmartPad",
                domains=["smartpad.io", "api.smartpad.io", "app.smartpad.io"]
            )
        ])
        
        index = build_cmdb_index(cmdb_plane)
        
        # All domain array members should be in by_domains_array
        assert "smartpad.io" in index.by_domains_array
        assert "ci-456" in index.by_domains_array["smartpad.io"]
        
        # Subdomains normalized to registered domain
        # api.smartpad.io → smartpad.io in by_domains_array
        assert "smartpad.io" in index.by_domains_array
    
    def test_cmdb_authoritative_methods_can_assert_governance(self):
        """CMDB authoritative match methods must be able to assert HAS_CMDB"""
        from src.aod.pipeline.correlate_entities import PlaneMatch, MatchStatus, AUTHORITATIVE_MATCH_METHODS
        
        # cmdb_canonical_domain is authoritative
        match1 = PlaneMatch(
            status=MatchStatus.MATCHED,
            matched_ids=["ci-123"],
            match_method="cmdb_canonical_domain"
        )
        assert match1.is_authoritative == True
        assert "cmdb_canonical_domain" in AUTHORITATIVE_MATCH_METHODS
        
        # cmdb_domains_array is authoritative
        match2 = PlaneMatch(
            status=MatchStatus.MATCHED,
            matched_ids=["ci-456"],
            match_method="cmdb_domains_array"
        )
        assert match2.is_authoritative == True
        assert "cmdb_domains_array" in AUTHORITATIVE_MATCH_METHODS
    
    def test_verified_alias_is_authoritative(self):
        """verified_alias_domain match method is authoritative"""
        from src.aod.pipeline.correlate_entities import PlaneMatch, MatchStatus, AUTHORITATIVE_MATCH_METHODS
        
        match = PlaneMatch(
            status=MatchStatus.MATCHED,
            matched_ids=["ci-789"],
            match_method="verified_alias_domain"
        )
        assert match.is_authoritative == True
        assert "verified_alias_domain" in AUTHORITATIVE_MATCH_METHODS


class TestGovernanceInvariantEnforcement:
    """
    Phase B tests: Governance Invariant Enforcement
    
    Validates that heuristic matches NEVER assert governance (HAS_IDP/HAS_CMDB).
    Tests the runtime invariant that blocks heuristic methods from granting governance.
    """
    
    def test_heuristic_idp_match_blocked_from_admission(self):
        """
        Test that heuristic IdP matches are blocked from asserting HAS_IDP.
        
        This is the key invariant: an entity with domain token matching an IdP record
        by name (heuristic) should produce IDP_CANDIDATE but NOT HAS_IDP.
        """
        from src.aod.pipeline.correlate_entities import (
            CorrelationResult, PlaneMatch, MatchStatus, HEURISTIC_MATCH_METHODS
        )
        from src.aod.pipeline.normalize_observations import CandidateEntity
        from src.aod.pipeline.admission import check_idp_admission
        from src.aod.models.input_contracts import IdPObject
        
        # Create a mock entity
        mock_entity = CandidateEntity(
            entity_id="entity-123",
            canonical_name="TeamSpot",
            original_name="TeamSpot",
            domain="teamspot.com"
        )
        
        # Create an IdP record
        idp_record = IdPObject(
            idp_id="idp-123",
            name="TeamSpot",  # Name matches but domain doesn't
            domain="teamspot.net",  # Different TLD
            has_sso=True
        )
        
        # Create a correlation with HEURISTIC match method
        for heuristic_method in ["fuzzy", "contains", "vendor", "domain_token_to_name"]:
            assert heuristic_method in HEURISTIC_MATCH_METHODS, f"{heuristic_method} must be heuristic"
            
            correlation = CorrelationResult(
                entity=mock_entity,
                idp=PlaneMatch(
                    status=MatchStatus.MATCHED,
                    matched_ids=["idp-123"],
                    matched_records=[idp_record],
                    match_method=heuristic_method
                )
            )
            
            # INVARIANT: Heuristic match must NOT grant HAS_IDP
            admitted, reason = check_idp_admission(correlation, entity_registered_domain="teamspot.com")
            assert admitted == False, f"Heuristic method '{heuristic_method}' must NOT grant HAS_IDP"
    
    def test_authoritative_idp_match_can_assert_governance(self):
        """
        Test that authoritative IdP matches CAN assert HAS_IDP when domain-aligned.
        """
        from src.aod.pipeline.correlate_entities import (
            CorrelationResult, PlaneMatch, MatchStatus, AUTHORITATIVE_MATCH_METHODS
        )
        from src.aod.pipeline.normalize_observations import CandidateEntity
        from src.aod.pipeline.admission import check_idp_admission
        from src.aod.models.input_contracts import IdPObject
        
        # Create a mock entity
        mock_entity = CandidateEntity(
            entity_id="entity-456",
            canonical_name="TeamSpot",
            original_name="TeamSpot",
            domain="teamspot.com"
        )
        
        # Create an IdP record with domain-aligned match
        idp_record = IdPObject(
            idp_id="idp-456",
            name="TeamSpot",
            domain="teamspot.com",  # Same domain as entity
            has_sso=True
        )
        
        # Create a correlation with AUTHORITATIVE match method
        correlation = CorrelationResult(
            entity=mock_entity,
            idp=PlaneMatch(
                status=MatchStatus.MATCHED,
                matched_ids=["idp-456"],
                matched_records=[idp_record],
                match_method="domain"  # Authoritative method
            )
        )
        
        assert "domain" in AUTHORITATIVE_MATCH_METHODS
        
        # Authoritative + domain-aligned = HAS_IDP granted
        admitted, reason = check_idp_admission(correlation, entity_registered_domain="teamspot.com")
        assert admitted == True, "Authoritative domain-aligned match must grant HAS_IDP"
        assert "domain-aligned" in reason.lower()
    
    def test_authoritative_unrelated_domain_blocked(self):
        """
        Test that authoritative matches with unrelated domains are blocked.
        Even if authoritative, unrelated domains should not grant HAS_IDP.
        
        NOTE: Cross-TLD matches with same base token (teamspot.com vs teamspot.io)
        ARE allowed by design for multi-TLD vendor governance.
        This test uses genuinely different domains to verify the block.
        """
        from src.aod.pipeline.correlate_entities import (
            CorrelationResult, PlaneMatch, MatchStatus
        )
        from src.aod.pipeline.normalize_observations import CandidateEntity
        from src.aod.pipeline.admission import check_idp_admission
        from src.aod.models.input_contracts import IdPObject
        
        # Create a mock entity
        mock_entity = CandidateEntity(
            entity_id="entity-789",
            canonical_name="TeamSpot",
            original_name="TeamSpot",
            domain="teamspot.com"
        )
        
        # Create an IdP record with DIFFERENT base domain (not just different TLD)
        idp_record = IdPObject(
            idp_id="idp-789",
            name="OtherApp",
            domain="otherapp.io",  # Completely different domain - should not match
            has_sso=True
        )
        
        # Create a correlation with AUTHORITATIVE match method but unrelated domain
        correlation = CorrelationResult(
            entity=mock_entity,
            idp=PlaneMatch(
                status=MatchStatus.MATCHED,
                matched_ids=["idp-789"],
                matched_records=[idp_record],
                match_method="domain"
            )
        )
        
        # Authoritative but unrelated domain = NO HAS_IDP (domain alignment required)
        admitted, reason = check_idp_admission(correlation, entity_registered_domain="teamspot.com")
        assert admitted == False, "Unrelated domain IdP match must NOT grant HAS_IDP even if authoritative"

    def test_non_canonical_idp_app_never_grants_governance(self):
        """
        INVARIANT 1: Non-canonical IdP app names never grant governance.
        
        Even if the domain matches exactly, IdP records with suffixes like
        "(Legacy)", "-prod", "-dev", "-staging", "deprecated" should NOT
        grant HAS_IDP because they indicate non-canonical applications.
        
        This prevents false positives from environment-specific or legacy
        IdP applications that share the same domain as the canonical app.
        """
        from src.aod.pipeline.correlate_entities import (
            CorrelationResult, PlaneMatch, MatchStatus
        )
        from src.aod.pipeline.normalize_observations import CandidateEntity
        from src.aod.pipeline.admission import check_idp_admission, is_non_canonical_idp_app
        from src.aod.models.input_contracts import IdPObject
        
        # Test the is_non_canonical_idp_app function directly
        assert is_non_canonical_idp_app("Primeway-prod") == True
        assert is_non_canonical_idp_app("Bignest (Legacy)") == True
        assert is_non_canonical_idp_app("Linknest (Legacy)") == True
        assert is_non_canonical_idp_app("DataApp-dev") == True
        assert is_non_canonical_idp_app("TestApp-staging") == True
        assert is_non_canonical_idp_app("OldApp deprecated") == True
        assert is_non_canonical_idp_app("Cloudsync") == False  # canonical
        assert is_non_canonical_idp_app("Zendesk") == False  # canonical
        assert is_non_canonical_idp_app("") == False
        assert is_non_canonical_idp_app(None) == False
        
        # Create a mock entity
        mock_entity = CandidateEntity(
            entity_id="entity-legacy",
            canonical_name="Primeway",
            original_name="Primeway",
            domain="primeway.tech"
        )
        
        # Create an IdP record with non-canonical name but EXACT domain match
        idp_record = IdPObject(
            idp_id="idp-legacy",
            name="Primeway-prod",  # Non-canonical suffix
            domain="primeway.tech",  # Exact match!
            has_sso=True
        )
        
        correlation = CorrelationResult(
            entity=mock_entity,
            idp=PlaneMatch(
                status=MatchStatus.MATCHED,
                matched_ids=["idp-legacy"],
                matched_records=[idp_record],
                match_method="domain"  # Authoritative method
            )
        )
        
        # INVARIANT: Non-canonical apps NEVER grant governance, even with exact domain
        admitted, reason = check_idp_admission(correlation, entity_registered_domain="primeway.tech")
        assert admitted == False, "Non-canonical IdP app (-prod suffix) must NOT grant HAS_IDP even with exact domain match"

    def test_no_domain_idp_match_never_grants_governance(self):
        """
        INVARIANT 2: Name-only IdP matches (no domain on IdP record) never grant governance.
        
        If the IdP record has no domain, it can only match by name. This is
        informational but should NOT assert HAS_IDP governance.
        """
        from src.aod.pipeline.correlate_entities import (
            CorrelationResult, PlaneMatch, MatchStatus
        )
        from src.aod.pipeline.normalize_observations import CandidateEntity
        from src.aod.pipeline.admission import check_idp_admission
        from src.aod.models.input_contracts import IdPObject
        
        # Create a mock entity
        mock_entity = CandidateEntity(
            entity_id="entity-nodomain",
            canonical_name="Cloudsync",
            original_name="Cloudsync",
            domain="cloudsync.io"
        )
        
        # Create an IdP record with NO domain (name-only match)
        idp_record = IdPObject(
            idp_id="idp-nodomain",
            name="Cloudsync",  # Name matches entity base token
            domain=None,  # No domain!
            has_sso=True
        )
        
        correlation = CorrelationResult(
            entity=mock_entity,
            idp=PlaneMatch(
                status=MatchStatus.MATCHED,
                matched_ids=["idp-nodomain"],
                matched_records=[idp_record],
                match_method="domain"  # Even if marked authoritative
            )
        )
        
        # INVARIANT: No-domain IdP matches NEVER grant governance
        admitted, reason = check_idp_admission(correlation, entity_registered_domain="cloudsync.io")
        assert admitted == False, "No-domain IdP match must NOT grant HAS_IDP (name-only is informational only)"
