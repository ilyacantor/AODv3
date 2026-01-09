"""Tests for Long Tail domain normalization fallback logic"""

import pytest
import sys
sys.path.insert(0, 'src')

from aod.core.identity_normalizer import IdentityNormalizer, normalize_identity
from aod.pipeline.normalize_observations import normalize_domain
from aod.pipeline.vendor_inference import extract_registered_domain


class TestLongTailDomainNormalization:
    """Test that unknown domains correctly collapse to eTLD+1"""
    
    def test_api_netforce_io_normalizes_to_root(self):
        """api.netforce.io should normalize to netforce.io"""
        normalizer = IdentityNormalizer()
        assert normalizer.normalize("api.netforce.io") == "netforce.io"
    
    def test_www_cloudhub_org_normalizes_to_root(self):
        """www.cloudhub.org should normalize to cloudhub.org"""
        normalizer = IdentityNormalizer()
        assert normalizer.normalize("www.cloudhub.org") == "cloudhub.org"
    
    def test_cdn_random_startup_io_normalizes_to_root(self):
        """cdn.random-startup.io should normalize to random-startup.io"""
        normalizer = IdentityNormalizer()
        assert normalizer.normalize("cdn.random-startup.io") == "random-startup.io"
    
    def test_multiple_subdomains_collapse(self):
        """Multiple subdomain levels should collapse to eTLD+1"""
        normalizer = IdentityNormalizer()
        assert normalizer.normalize("api.v2.staging.unknown-saas.com") == "unknown-saas.com"
    
    def test_long_tail_via_normalize_identity(self):
        """normalize_identity function also collapses long tail domains"""
        assert normalize_identity("docs.random-tool.io") == "random-tool.io"
    
    def test_long_tail_via_normalize_domain(self):
        """normalize_domain in pipeline also collapses long tail domains"""
        assert normalize_domain("admin.obscure-platform.org") == "obscure-platform.org"


class TestNormalizationConsistency:
    """Test that all normalization paths produce consistent results for long tail domains"""
    
    @pytest.mark.parametrize("domain,expected", [
        ("api.netforce.io", "netforce.io"),
        ("www.cloudhub.org", "cloudhub.org"),
        ("cdn.random-startup.io", "random-startup.io"),
        ("docs.unknown-tool.com", "unknown-tool.com"),
        ("app.newplatform.io", "newplatform.io"),
    ])
    def test_normalize_domain_matches_identity_normalizer(self, domain, expected):
        """normalize_domain should produce same result as IdentityNormalizer"""
        normalizer = IdentityNormalizer()
        
        pipeline_result = normalize_domain(domain)
        core_result = normalizer.normalize(domain)
        
        assert pipeline_result == expected, f"normalize_domain({domain}) = {pipeline_result}, expected {expected}"
        assert core_result == expected, f"IdentityNormalizer.normalize({domain}) = {core_result}, expected {expected}"
        assert pipeline_result == core_result, "Normalization paths should be consistent"


class TestPaaSPreservation:
    """Test that PaaS tenant subdomains are preserved (not collapsed)"""
    
    @pytest.mark.parametrize("domain,expected", [
        ("flowsoft.okta.com", "flowsoft.okta.com"),
        ("acme.salesforce.com", "acme.salesforce.com"),
        ("mycompany.atlassian.net", "mycompany.atlassian.net"),
        ("corp.zendesk.com", "corp.zendesk.com"),
    ])
    def test_paas_subdomains_preserved(self, domain, expected):
        """PaaS tenant subdomains should be preserved, not collapsed"""
        normalizer = IdentityNormalizer()
        assert normalizer.normalize(domain) == expected


class TestAliasMapping:
    """Test that known aliases are mapped to canonical domains"""
    
    @pytest.mark.parametrize("alias,canonical", [
        ("zoom-video.com", "zoom.us"),
        ("microsoftonline.com", "microsoft.com"),
        ("login.microsoftonline.com", "microsoft.com"),
    ])
    def test_aliases_map_to_canonical(self, alias, canonical):
        """Known aliases should map to their canonical domain"""
        normalizer = IdentityNormalizer()
        assert normalizer.normalize(alias) == canonical


class TestDomainExtractionFromAlternativeFields:
    """Test domain extraction from external_ref, url, application_url fields - Jan 2026 fix"""
    
    def test_resolve_effective_domain_from_direct_domain(self):
        """Direct domain attribute should be extracted"""
        from aod.pipeline.admission import _resolve_effective_domain_from_record
        
        class MockRecord:
            domain = "flowbase.ai"
            raw_data = {}
        
        result = _resolve_effective_domain_from_record(MockRecord())
        assert result == "flowbase.ai"
    
    def test_resolve_effective_domain_from_external_ref(self):
        """Domain in raw_data['external_ref'] should be extracted via fallback"""
        from aod.pipeline.admission import _resolve_effective_domain_from_record
        
        class MockRecord:
            domain = None
            raw_data = {"external_ref": "https://flowbase.ai/app"}
        
        result = _resolve_effective_domain_from_record(MockRecord())
        assert result == "flowbase.ai"
    
    def test_resolve_effective_domain_from_url(self):
        """Domain in raw_data['url'] should be extracted via fallback"""
        from aod.pipeline.admission import _resolve_effective_domain_from_record
        
        class MockRecord:
            domain = None
            raw_data = {"url": "https://app.cloudservice.com:443/login"}
        
        result = _resolve_effective_domain_from_record(MockRecord())
        assert result == "app.cloudservice.com"
    
    def test_resolve_effective_domain_fallback_priority(self):
        """Fields should be checked in priority order: domain > external_ref > url"""
        from aod.pipeline.admission import _resolve_effective_domain_from_record
        
        class MockRecord:
            domain = "priority.com"
            raw_data = {"external_ref": "ignored.com", "url": "also-ignored.com"}
        
        result = _resolve_effective_domain_from_record(MockRecord())
        assert result == "priority.com"
    
    def test_resolve_effective_domain_skips_invalid(self):
        """Invalid domain values should be skipped, falling through to next field"""
        from aod.pipeline.admission import _resolve_effective_domain_from_record
        
        class MockRecord:
            domain = ""
            raw_data = {"domain": "", "external_ref": "", "url": "valid.io"}
        
        result = _resolve_effective_domain_from_record(MockRecord())
        assert result == "valid.io"
    
    def test_clean_url_to_domain_handles_protocols_and_ports(self):
        """URL cleaning should strip protocols, ports, and paths"""
        from aod.pipeline.admission import _clean_url_to_domain
        
        assert _clean_url_to_domain("https://example.com/path") == "example.com"
        assert _clean_url_to_domain("http://www.example.com:8080/") == "example.com"
        assert _clean_url_to_domain("example.com") == "example.com"
        assert _clean_url_to_domain(None) is None
        # Single tokens like "salesforce" are valid - mirrors _get_raw_domain behavior
        assert _clean_url_to_domain("salesforce") == "salesforce"
    
    def test_extract_all_domains_includes_both_raw_and_registered(self):
        """Domain extraction should include BOTH raw and registered forms for alias matching"""
        from aod.pipeline.admission import _extract_all_domains_from_correlation
        from aod.pipeline.correlate_entities import CorrelationResult, PlaneMatch, MatchStatus
        from aod.pipeline.normalize_observations import CandidateEntity
        
        class MockRecord:
            domain = "app.flowbase.ai"
            raw_data = {}
        
        # Create minimal entity for the correlation
        entity = CandidateEntity(
            entity_id="test",
            canonical_name="test app",
            original_name="Test App",
            domain=None
        )
        
        # Create correlation with a matched IdP record
        correlation = CorrelationResult(
            entity=entity,
            idp=PlaneMatch(status=MatchStatus.MATCHED, matched_records=[MockRecord()]),
            cmdb=PlaneMatch(status=MatchStatus.UNMATCHED, matched_records=[]),
            cloud=PlaneMatch(status=MatchStatus.UNMATCHED, matched_records=[]),
            finance=PlaneMatch(status=MatchStatus.UNMATCHED, matched_records=[])
        )
        
        domains = _extract_all_domains_from_correlation(correlation)
        
        # Should include BOTH the raw domain and the registered domain
        assert "app.flowbase.ai" in domains  # Raw
        assert "flowbase.ai" in domains  # Registered
    
    def test_extract_all_domains_includes_canonical_alias(self):
        """Domain extraction should include canonical alias for known mappings - mirrors indexing"""
        from aod.pipeline.admission import _extract_all_domains_from_correlation
        from aod.pipeline.correlate_entities import CorrelationResult, PlaneMatch, MatchStatus
        from aod.pipeline.normalize_observations import CandidateEntity
        
        class MockRecord:
            domain = "login.microsoftonline.com"
            raw_data = {}
        
        entity = CandidateEntity(
            entity_id="test",
            canonical_name="microsoft",
            original_name="Microsoft",
            domain=None
        )
        
        correlation = CorrelationResult(
            entity=entity,
            idp=PlaneMatch(status=MatchStatus.MATCHED, matched_records=[MockRecord()]),
            cmdb=PlaneMatch(status=MatchStatus.UNMATCHED, matched_records=[]),
            cloud=PlaneMatch(status=MatchStatus.UNMATCHED, matched_records=[]),
            finance=PlaneMatch(status=MatchStatus.UNMATCHED, matched_records=[])
        )
        
        domains = _extract_all_domains_from_correlation(correlation)
        
        # EXACT PARITY with indexing: canonical from normalize_domain + raw if different
        # normalize_domain("login.microsoftonline.com") -> "microsoft.com" (canonical alias)
        assert "microsoft.com" in domains  # Canonical alias from normalize_domain
        assert "login.microsoftonline.com" in domains  # Raw (different from canonical)
    
    def test_extract_all_domains_keeps_tenant_sso_subdomains(self):
        """Domain extraction mirrors indexing: preserves tenant SSO subdomains"""
        from aod.pipeline.admission import _extract_all_domains_from_correlation
        from aod.pipeline.correlate_entities import CorrelationResult, PlaneMatch, MatchStatus
        from aod.pipeline.normalize_observations import CandidateEntity
        
        class MockRecord:
            domain = "acme.okta.com"  # Tenant SSO subdomain
            raw_data = {}
        
        entity = CandidateEntity(
            entity_id="test",
            canonical_name="test app",
            original_name="Test App",
            domain=None
        )
        
        correlation = CorrelationResult(
            entity=entity,
            idp=PlaneMatch(status=MatchStatus.MATCHED, matched_records=[MockRecord()]),
            cmdb=PlaneMatch(status=MatchStatus.UNMATCHED, matched_records=[]),
            cloud=PlaneMatch(status=MatchStatus.UNMATCHED, matched_records=[]),
            finance=PlaneMatch(status=MatchStatus.UNMATCHED, matched_records=[])
        )
        
        domains = _extract_all_domains_from_correlation(correlation)
        
        # EXACT PARITY with indexing: tenant SSO subdomains are preserved
        # normalize_domain("acme.okta.com") -> "acme.okta.com" (preserved, not collapsed to okta.com)
        # This is correct: tenant-specific SSO subdomains are kept for exact matching
        assert "acme.okta.com" in domains  # Preserved tenant subdomain
