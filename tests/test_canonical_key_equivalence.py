"""
Canonical Key Equivalence Tests

Table-driven tests to ensure domain extraction and canonicalization work correctly.
This catches KEY_NORMALIZATION_MISMATCH regressions before they hit production.

After Category 5 FP fix (Jan 2026): Tests now use identifiers.domains for domain evidence
instead of relying on name-based domain detection or vendor fallback.
"""

import pytest
import uuid
from src.aod.pipeline.vendor_inference import extract_registered_domain
from src.aod.pipeline.aod_agent_reconcile import _extract_registered_domain, _normalize_name_for_vendor_lookup
from src.aod.models.output_contracts import Asset, AssetIdentifiers, LensStatuses, LensCoverage


class TestRegisteredDomainExtraction:
    """Test extract_registered_domain for subdomain normalization"""
    
    @pytest.mark.parametrize("raw_domain,expected", [
        ("images75.edge.com", "edge.com"),
        ("app.slack.com", "slack.com"),
        ("telemetry611.cloud.net", "cloud.net"),
        ("identity360.cdn.com", "cdn.com"),
        ("api.stripe.com", "stripe.com"),
        ("docs.mongodb.com", "mongodb.com"),
        ("sub.sub.example.com", "example.com"),
        ("www.github.com", "github.com"),
        ("slack.com", "slack.com"),
        ("notion.so", "notion.so"),
        ("zoom.us", "zoom.us"),
        ("atlassian.net", "atlassian.net"),
        ("elastic.co", "elastic.co"),
    ])
    def test_subdomain_normalization(self, raw_domain: str, expected: str):
        """Subdomains must normalize to registered domain (eTLD+1)"""
        result = extract_registered_domain(raw_domain)
        assert result == expected, f"Expected {expected}, got {result}"
    
    @pytest.mark.parametrize("raw_domain", [
        "dr0pbox.com",
        "micros0ft.com",
        "z00m.us",
        "s1ack.com",
        "g00gle.com",
        "slack-hq.com",
        "slackapp.com",
        "sfdc.io",
        "zoom-video.com",
    ])
    def test_typosquat_domains_preserved(self, raw_domain: str):
        """Typosquat/variant domains must be preserved as-is (not normalized to parent)"""
        result = extract_registered_domain(raw_domain)
        assert result == raw_domain, f"Typosquat domain {raw_domain} was altered to {result}"
    
    def test_idempotence(self):
        """canonical(canonical(x)) == canonical(x)"""
        test_domains = [
            "app.slack.com",
            "slack.com",
            "s1ack.com",
            "images75.edge.com",
        ]
        for domain in test_domains:
            first = extract_registered_domain(domain)
            second = extract_registered_domain(first) if first else None
            assert first == second, f"Not idempotent: {domain} -> {first} -> {second}"
    
    def test_subdomain_never_returns_raw(self):
        """Subdomain input should never return the full subdomain (unless extraction fails)"""
        subdomains = [
            "app.slack.com",
            "api.stripe.com",
            "docs.mongodb.com",
        ]
        for subdomain in subdomains:
            result = extract_registered_domain(subdomain)
            assert result != subdomain, f"Subdomain {subdomain} was not normalized"


class TestAssetKeyExtraction:
    """Test _extract_registered_domain for asset key derivation.
    
    After Category 5 FP fix: Tests use identifiers.domains for domain evidence.
    """
    
    def _make_asset(self, name: str, domains: list[str] | None = None, vendor: str | None = None) -> Asset:
        """Helper to create test assets"""
        return Asset(
            asset_id=uuid.uuid4(),
            tenant_id="test-tenant",
            run_id="test-run",
            name=name,
            identifiers=AssetIdentifiers(domains=domains or []),
            vendor=vendor,
            lens_status=LensStatuses(),
            lens_coverage=LensCoverage(),
        )
    
    def test_domain_in_identifiers_takes_priority(self):
        """identifiers.domains should be used for asset key"""
        asset = self._make_asset("Slack", domains=["slack.com"], vendor="Slack")
        result = _extract_registered_domain(asset)
        assert result == "slack.com"
    
    def test_domain_like_name_used_when_no_identifiers_and_no_vendor(self):
        """Asset name that looks like domain should be used as key when no vendor"""
        asset = self._make_asset("slack-hq.com", domains=[], vendor=None)
        result = _extract_registered_domain(asset)
        assert result == "slack-hq.com"
    
    def test_typosquat_domains_in_identifiers_preserved(self):
        """Typosquat domain in identifiers.domains must be preserved as the key"""
        test_cases = [
            ("s1ack.com", "Slack", "s1ack.com"),
            ("g00gle.com", "Google", "g00gle.com"),
            ("dr0pbox.com", "Dropbox", "dr0pbox.com"),
            ("z00m.us", "Zoom", "z00m.us"),
            ("micros0ft.com", "Microsoft", "micros0ft.com"),
        ]
        for domain, vendor, expected in test_cases:
            asset = self._make_asset(domain, domains=[domain], vendor=vendor)
            result = _extract_registered_domain(asset)
            assert result == expected, f"Typosquat {domain} was altered to {result} by vendor {vendor}"
    
    def test_known_vendor_domains_normalized_to_canonical(self):
        """Known vendor domains are normalized to their canonical domain.
        
        Domains like atlassian.net are normalized to atlassian.com for consistency
        when they're recognized as belonging to a known vendor.
        """
        test_cases = [
            ("atlassian.net", "Atlassian", "atlassian.com"),
            ("notion.so", "Notion", "notion.so"),
            ("intercom.io", "Intercom", "intercom.io"),
            ("sentry.io", "Sentry", "sentry.io"),
        ]
        for domain, vendor, expected in test_cases:
            asset = self._make_asset(domain, domains=[domain], vendor=vendor)
            result = _extract_registered_domain(asset)
            assert result == expected, f"Domain {domain} should normalize to {expected}, got {result}"
    
    def test_unknown_variant_domains_in_identifiers_preserved(self):
        """Variant domains in identifiers.domains must be preserved as-is"""
        test_cases = [
            ("slack-hq.com", "Slack", "slack-hq.com"),
            ("slackapp.com", "Slack", "slackapp.com"),
            ("sfdc.io", "Salesforce", "sfdc.io"),
        ]
        for domain, vendor, expected in test_cases:
            asset = self._make_asset(domain, domains=[domain], vendor=vendor)
            result = _extract_registered_domain(asset)
            assert result == expected, f"Unknown variant {domain} was altered to {result}"
    
    def test_vendor_fallback_when_no_domain(self):
        """Vendor lookup should apply when there's no domain evidence"""
        asset = self._make_asset("Slack", domains=[], vendor="Slack")
        result = _extract_registered_domain(asset)
        assert result == "slack.com"
    
    def test_subdomain_in_identifiers_normalized(self):
        """Subdomains in identifiers.domains should be normalized to eTLD+1"""
        asset = self._make_asset("Slack App", domains=["app.slack.com"], vendor="Slack")
        result = _extract_registered_domain(asset)
        assert result == "slack.com"


class TestTwoPathEquivalence:
    """
    Test that reconciliation code produces correct canonical keys.
    
    After Category 5 FP fix: Tests use identifiers.domains for domain evidence.
    """
    
    # Domains NOT in DOMAIN_TO_VENDOR - should match extract_registered_domain exactly
    UNKNOWN_DOMAINS = [
        "images75.edge.com",
        "slack-hq.com",
        "slackapp.com",
        "s1ack.com",
        "dr0pbox.com",
        "g00gle.com",
        "micros0ft.com",
        "z00m.us",
        "sfdc.io",
    ]
    
    # Domains with vendor mapping - test subdomain normalization
    SUBDOMAIN_DOMAINS = [
        ("app.slack.com", "slack.com"),
    ]
    
    # Primary domains - atlassian.net normalizes to atlassian.com, others preserved
    PRIMARY_DOMAINS = [
        ("atlassian.net", "atlassian.com"),
        ("notion.so", "notion.so"),
        ("sentry.io", "sentry.io"),
    ]
    
    def test_unknown_domains_match_extract_registered(self):
        """Unknown domains in identifiers.domains should match extract_registered_domain exactly"""
        from src.aod.pipeline.vendor_inference import extract_registered_domain as vendor_extract
        
        mismatches = []
        for domain in self.UNKNOWN_DOMAINS:
            vendor_result = vendor_extract(domain)
            
            asset = Asset(
                asset_id=uuid.uuid4(),
                tenant_id="test-tenant",
                run_id="test",
                name=domain,
                identifiers=AssetIdentifiers(domains=[domain]),
                vendor=None,
                lens_status=LensStatuses(),
                lens_coverage=LensCoverage(),
            )
            reconcile_result = _extract_registered_domain(asset)
            
            if vendor_result != reconcile_result:
                mismatches.append({
                    "domain": domain,
                    "expected": vendor_result,
                    "got": reconcile_result,
                })
        
        assert not mismatches, f"Unknown domain mismatch:\n{mismatches}"
    
    def test_subdomains_normalize_correctly(self):
        """Subdomains in identifiers.domains should normalize to registered domain"""
        for subdomain, expected_canonical in self.SUBDOMAIN_DOMAINS:
            asset = Asset(
                asset_id=uuid.uuid4(),
                tenant_id="test-tenant",
                run_id="test",
                name=subdomain,
                identifiers=AssetIdentifiers(domains=[subdomain]),
                vendor=None,
                lens_status=LensStatuses(),
                lens_coverage=LensCoverage(),
            )
            result = _extract_registered_domain(asset)
            assert result == expected_canonical, f"Subdomain {subdomain} should normalize to {expected_canonical}, got {result}"
    
    def test_known_domains_normalized_correctly(self):
        """Known vendor domains in identifiers.domains are normalized to canonical"""
        for domain, expected in self.PRIMARY_DOMAINS:
            asset = Asset(
                asset_id=uuid.uuid4(),
                tenant_id="test-tenant",
                run_id="test",
                name=domain,
                identifiers=AssetIdentifiers(domains=[domain]),
                vendor=None,
                lens_status=LensStatuses(),
                lens_coverage=LensCoverage(),
            )
            result = _extract_registered_domain(asset)
            assert result == expected, f"Primary domain {domain} should be preserved as {expected}, got {result}"
    
    def test_name_normalization_consistency(self):
        """Test that name normalization is consistent across paths"""
        test_cases = [
            ("Slack", "slack"),
            ("slack", "slack"),
            ("SLACK", "slack"),
            ("Slack Inc", "slack inc"),
            ("Slack Inc.", "slack inc."),
        ]
        for name, expected in test_cases:
            normalized = _normalize_name_for_vendor_lookup(name)
            assert normalized == expected, f"Name '{name}' normalized to '{normalized}', expected '{expected}'"
