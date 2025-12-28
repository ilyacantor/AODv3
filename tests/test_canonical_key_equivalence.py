"""
Canonical Key Equivalence Tests

Table-driven tests to ensure domain extraction and canonicalization work correctly.
This catches KEY_NORMALIZATION_MISMATCH regressions before they hit production.
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
    """Test _extract_registered_domain for asset key derivation"""
    
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
    
    def test_domain_like_name_used_when_no_identifiers(self):
        """Asset name that looks like domain should be used as key"""
        asset = self._make_asset("slack-hq.com", domains=[], vendor="Slack")
        result = _extract_registered_domain(asset)
        assert result == "slack-hq.com"
    
    def test_typosquat_name_not_overwritten_by_vendor(self):
        """Typosquat domain names must not be overwritten by vendor lookup"""
        test_cases = [
            ("s1ack.com", "Slack", "s1ack.com"),
            ("g00gle.com", "Google", "g00gle.com"),
            ("dr0pbox.com", "Dropbox", "dr0pbox.com"),
            ("z00m.us", "Zoom", "z00m.us"),
            ("micros0ft.com", "Microsoft", "micros0ft.com"),
        ]
        for name, vendor, expected in test_cases:
            asset = self._make_asset(name, domains=[], vendor=vendor)
            result = _extract_registered_domain(asset)
            assert result == expected, f"Typosquat {name} was altered to {result} by vendor {vendor}"
    
    def test_alias_domains_normalized_to_canonical(self):
        """Known alias domains should be normalized to canonical vendor domain.
        
        Dec 2025 Fix: Only domains in ALIAS_DOMAINS_TO_COLLAPSE are normalized.
        This fixes KEY_NORMALIZATION_MISMATCH for Microsoft/Google/Zoom aliases
        while preserving legitimate SaaS keys like atlassian.net, notion.so.
        """
        test_cases = [
            # Domain-like name with known alias -> canonical domain
            ("zoom-video.com", "Zoom", "zoom.us"),  # zoom-video.com is alias -> zoom.us
            ("microsoftonline.com", "Microsoft", "microsoft.com"),  # alias -> canonical
            ("googleapis.com", "Google", "google.com"),  # alias -> canonical
        ]
        for name, vendor, expected_canonical in test_cases:
            asset = self._make_asset(name, domains=[], vendor=vendor)
            result = _extract_registered_domain(asset)
            assert result == expected_canonical, f"Alias domain {name} should normalize to {expected_canonical}, got {result}"
    
    def test_primary_domains_preserved(self):
        """Legitimate primary SaaS domains should NOT be normalized to vendor canonical.
        
        atlassian.net, notion.so, etc are legitimate primary domains, not aliases.
        They should be preserved as-is even though they're in DOMAIN_TO_VENDOR.
        """
        test_cases = [
            ("atlassian.net", "Atlassian", "atlassian.net"),  # Primary domain, NOT collapsed
            ("notion.so", "Notion", "notion.so"),  # Primary domain, preserved
            ("intercom.io", "Intercom", "intercom.io"),  # Primary domain, preserved
            ("sentry.io", "Sentry", "sentry.io"),  # Primary domain, preserved
        ]
        for name, vendor, expected in test_cases:
            asset = self._make_asset(name, domains=[], vendor=vendor)
            result = _extract_registered_domain(asset)
            assert result == expected, f"Primary domain {name} should be preserved as {expected}, got {result}"
    
    def test_unknown_variant_domains_preserved(self):
        """Variant domains NOT in DOMAIN_TO_VENDOR must be preserved as-is"""
        test_cases = [
            ("slack-hq.com", "Slack", "slack-hq.com"),  # Not in DOMAIN_TO_VENDOR
            ("slackapp.com", "Slack", "slackapp.com"),  # Not in DOMAIN_TO_VENDOR
            ("sfdc.io", "Salesforce", "sfdc.io"),  # Not in DOMAIN_TO_VENDOR
        ]
        for name, vendor, expected in test_cases:
            asset = self._make_asset(name, domains=[], vendor=vendor)
            result = _extract_registered_domain(asset)
            assert result == expected, f"Unknown variant {name} was altered to {result}"
    
    def test_vendor_fallback_when_no_domain(self):
        """Vendor lookup should only apply when there's no domain evidence"""
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
    
    Dec 2025 Update: The reconcile path now normalizes known vendor domains
    to their canonical vendor domain (e.g., zoom-video.com -> zoom.us).
    This is intentional to fix KEY_NORMALIZATION_MISMATCH errors.
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
    
    # Domains with vendor mapping - test alias normalization vs primary preservation
    ALIAS_DOMAINS = [
        ("app.slack.com", "slack.com"),  # subdomain -> registered -> canonical (same)
        ("zoom-video.com", "zoom.us"),   # alias domain -> normalized to zoom.us
        ("microsoftonline.com", "microsoft.com"),  # alias -> normalized
    ]
    
    # Primary domains that should be PRESERVED (not in ALIAS_DOMAINS_TO_COLLAPSE)
    PRIMARY_DOMAINS = [
        ("atlassian.net", "atlassian.net"),  # Primary domain, NOT collapsed
        ("notion.so", "notion.so"),  # Primary domain, preserved
        ("sentry.io", "sentry.io"),  # Primary domain, preserved
    ]
    
    def test_unknown_domains_match_extract_registered(self):
        """Unknown domains should match extract_registered_domain exactly"""
        from src.aod.pipeline.vendor_inference import extract_registered_domain as vendor_extract
        
        mismatches = []
        for domain in self.UNKNOWN_DOMAINS:
            vendor_result = vendor_extract(domain)
            
            asset = Asset(
                asset_id=uuid.uuid4(),
                tenant_id="test-tenant",
                run_id="test",
                name=domain,
                identifiers=AssetIdentifiers(domains=[]),
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
    
    def test_alias_domains_normalize_to_canonical(self):
        """Alias domains should normalize to canonical vendor domain"""
        for domain, expected_canonical in self.ALIAS_DOMAINS:
            asset = Asset(
                asset_id=uuid.uuid4(),
                tenant_id="test-tenant",
                run_id="test",
                name=domain,
                identifiers=AssetIdentifiers(domains=[]),
                vendor=None,
                lens_status=LensStatuses(),
                lens_coverage=LensCoverage(),
            )
            result = _extract_registered_domain(asset)
            assert result == expected_canonical, f"Alias domain {domain} should normalize to {expected_canonical}, got {result}"
    
    def test_primary_domains_are_preserved(self):
        """Primary domains should NOT be normalized (preserved as-is)"""
        for domain, expected in self.PRIMARY_DOMAINS:
            asset = Asset(
                asset_id=uuid.uuid4(),
                tenant_id="test-tenant",
                run_id="test",
                name=domain,
                identifiers=AssetIdentifiers(domains=[]),
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
