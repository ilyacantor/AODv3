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
