"""
Canonical Key Module - Single Source of Truth for Domain Normalization

This module provides the ONLY implementation for converting domains to canonical asset keys.
All other modules MUST use compute_canonical_key() for domain normalization.

ARCHITECTURE:
- Single unified function: compute_canonical_key()
- Handles all normalization: eTLD+1 extraction + alias collapsing
- Returns all domain variants for alias expansion

INVARIANTS:
- Primary key determined from domains[0] only
- All domain variants preserved in alias_keys
- Vendor fallback ONLY when no domain evidence exists
- No duplicate implementations elsewhere in codebase

Phase 1 Consolidation (Jan 2026):
Replaces 5 competing normalization functions:
1. resolve_domain_from_observation() - now uses IdentityNormalizer + this
2. _extract_registered_domain() - now calls compute_canonical_key()
3. _resolve_domain_key() - now calls compute_canonical_key()
4. _compute_merge_key() - now calls compute_canonical_key()
5. _extract_raw_domain() - kept for tracing only (documented)
"""

from dataclasses import dataclass
from typing import Optional
import logging

from .vendor_inference import (
    extract_registered_domain,
    DOMAIN_TO_VENDOR,
    VENDOR_TO_DOMAIN
)

logger = logging.getLogger(__name__)


@dataclass
class CanonicalKeyResult:
    """
    Result of canonical key computation.

    Attributes:
        primary_key: The canonical domain key (e.g., "microsoft.com")
        registered_domain: The eTLD+1 domain (e.g., "microsoftonline.com")
        is_canonical: True if key is from domain evidence, False if from name/vendor
        all_variants: All domain forms [raw, registered, canonical] for alias expansion
    """
    primary_key: str
    registered_domain: Optional[str]
    is_canonical: bool
    all_variants: list[str]


# ALIAS_DOMAINS_TO_COLLAPSE: Single Source of Truth
# Domains that should collapse to their canonical vendor domain.
# Note: Only aliases are listed here. Legitimate primary domains (atlassian.net,
# notion.so, segment.io, datadoghq.com) are NOT in this set.
ALIAS_DOMAINS_TO_COLLAPSE: set[str] = {
    # Microsoft family - collapse to microsoft.com
    "microsoftonline.com",
    "microsoft365.com",  # Added: was missing in original
    "azure.com",
    "office.com",
    "office365.com",
    # NOTE: sharepoint.com is a PaaS root (multi-tenant), NOT collapsed - preserve subdomain identity
    "live.com",
    "outlook.com",
    "onedrive.com",
    "powerbi.com",
    # Google family - collapse to google.com
    "googleapis.com",
    "gstatic.com",
    # NOTE: googleusercontent.com is a PaaS root (multi-tenant), NOT collapsed - preserve subdomain identity
    # Zoom family - collapse to zoom.us
    "zoom.com",
    "zoom-video.com",
    "zoom-meetings.net",
    "zoomapp.io",
    # Atlassian aliases - collapse to atlassian.com
    # Note: atlassian.net is a legitimate primary domain (Jira Cloud), NOT collapsed
    "jira.com",
    "confluence.com",
    "opsgenie.com",
    # GitHub aliases
    "github.io",
    "githubusercontent.com",
    # Amazon/AWS aliases
    "amazonaws.com",
    "cloudfront.net",
    "awsstatic.com",
    # Dropbox aliases
    "dropboxapi.com",
    "dropboxusercontent.io",  # Added: was causing KEY_NORMALIZATION_MISMATCH
    # Other aliases
    "slackb2b.com",  # Slack
    "boxcdn.net",  # Box
    "oktapreview.com",  # Okta
    "sendgrid.net",  # Twilio
    "stripe.network",  # Stripe
    "zdassets.com",  # Zendesk
    "hubspotusercontent.com",  # HubSpot
    # Note: datadoghq.com is the canonical SaaS domain (app.datadoghq.com), NOT an alias
    "splunkcloud.com",  # Splunk
    "docusign.net",  # DocuSign
    "adobelogin.com",  # Adobe
    "cloudflareinsights.com",  # Cloudflare
    "snowflakecomputing.com",  # Snowflake (app.snowflakecomputing.com)
}


def normalize_to_canonical_vendor_domain(registered_domain: str) -> Optional[str]:
    """
    Normalize a registered domain to its canonical vendor domain (only for known aliases).

    This is the SINGLE implementation. The duplicate in aod_agent_reconcile.py and
    derived_classifications.py should call this function.

    Process:
    1. Check if domain is in ALIAS_DOMAINS_TO_COLLAPSE
    2. If yes, look up vendor in DOMAIN_TO_VENDOR
    3. Map vendor to canonical domain via VENDOR_TO_DOMAIN
    4. Return canonical domain

    Examples:
        microsoftonline.com -> microsoft.com (known alias)
        office365.com -> microsoft.com (known alias)
        googleapis.com -> google.com (known alias)
        atlassian.net -> None (legitimate primary domain, not an alias)
        notion.so -> None (canonical domain, not an alias)

    Args:
        registered_domain: The eTLD+1 domain to normalize

    Returns:
        Canonical vendor domain if this is a known alias, None otherwise
    """
    if not registered_domain:
        return None

    # Only normalize if this is a known alias domain
    if registered_domain not in ALIAS_DOMAINS_TO_COLLAPSE:
        return None

    # Look up vendor and map to canonical domain
    if registered_domain in DOMAIN_TO_VENDOR:
        vendor_name = DOMAIN_TO_VENDOR[registered_domain]
        vendor_key = vendor_name.lower().strip()
        if vendor_key in VENDOR_TO_DOMAIN:
            canonical = VENDOR_TO_DOMAIN[vendor_key]
            if canonical != registered_domain:
                logger.debug(f"normalize_alias: {registered_domain} -> {canonical}")
                return canonical

    return None


def compute_canonical_key(
    domains: list[str],
    vendor: Optional[str] = None,
    name: str = ""
) -> CanonicalKeyResult:
    """
    SINGLE SOURCE OF TRUTH for domain-to-key conversion.

    This function replaces all domain normalization logic across the codebase.
    All modules MUST call this function for canonical key computation.

    Normalization pipeline:
    1. Extract registered domain (eTLD+1) from domains[0]
    2. Check if registered domain is in ALIAS_DOMAINS_TO_COLLAPSE
    3. If yes, normalize to canonical vendor domain
    4. Collect all domain variants for alias expansion
    5. Return CanonicalKeyResult with primary key + all variants

    Vendor fallback (LAST RESORT ONLY):
    - Only executes if domains list is empty/None
    - NEVER overrides explicit domain evidence
    - Uses VENDOR_TO_DOMAIN mapping

    Examples:
        domains=["login.microsoftonline.com"]
        -> primary_key="microsoft.com", registered="microsoftonline.com"
        -> all_variants=["login.microsoftonline.com", "microsoftonline.com", "microsoft.com"]

        domains=["api.slack.com", "slack.com"]
        -> primary_key="slack.com", registered="slack.com"
        -> all_variants=["api.slack.com", "slack.com"]

        domains=[], vendor="Microsoft"
        -> primary_key="microsoft.com", registered=None
        -> all_variants=["microsoft.com"]

    Args:
        domains: List of domain strings (prioritizes domains[0])
        vendor: Optional vendor name for fallback lookup
        name: Optional asset name for fallback lookup

    Returns:
        CanonicalKeyResult with primary_key, registered_domain, is_canonical, all_variants
    """
    all_variants_set = set()
    primary_key = None
    registered_domain = None
    is_canonical = False

    # Process domains (prioritize domains[0] for primary key)
    if domains:
        for idx, domain in enumerate(domains):
            if not domain or "." not in domain:
                continue

            raw_domain = domain.lower().strip()
            all_variants_set.add(raw_domain)

            # Extract registered domain (eTLD+1)
            registered = extract_registered_domain(raw_domain)
            if registered:
                if registered != raw_domain:
                    all_variants_set.add(registered)

                # Normalize to canonical vendor domain if this is an alias
                canonical = normalize_to_canonical_vendor_domain(registered)
                if canonical:
                    all_variants_set.add(canonical)

                # PRIMARY KEY: Only set from first domain (index 0)
                if idx == 0 and primary_key is None:
                    if canonical:
                        primary_key = canonical
                    else:
                        primary_key = registered
                    registered_domain = registered
                    is_canonical = True

                    logger.debug(
                        f"canonical_key: domains[0]={raw_domain} -> "
                        f"registered={registered} -> primary={primary_key}"
                    )
            elif idx == 0 and primary_key is None:
                # Fallback: use raw domain if eTLD+1 extraction fails
                primary_key = raw_domain
                is_canonical = True
                logger.debug(f"canonical_key: domains[0]={raw_domain} -> primary={primary_key} (no eTLD+1)")

        if primary_key:
            return CanonicalKeyResult(
                primary_key=primary_key,
                registered_domain=registered_domain,
                is_canonical=is_canonical,
                all_variants=sorted(all_variants_set)
            )

    # Vendor fallback (ONLY if no domain evidence)
    if vendor and vendor.lower() not in ("unknown", "", "none"):
        vendor_key = vendor.lower().strip()
        if vendor_key in VENDOR_TO_DOMAIN:
            canonical = VENDOR_TO_DOMAIN[vendor_key]
            all_variants_set.add(canonical)
            logger.debug(f"canonical_key: vendor={vendor} -> primary={canonical} (fallback)")
            return CanonicalKeyResult(
                primary_key=canonical,
                registered_domain=None,
                is_canonical=True,
                all_variants=sorted(all_variants_set) if all_variants_set else [canonical]
            )

    # Name fallback (if name looks like a domain or matches VENDOR_TO_DOMAIN)
    if name:
        # Check if name looks like a domain
        name_lower = name.lower().strip()
        if "." in name_lower:
            parts = name_lower.split(".")
            if len(parts) >= 2 and len(parts[-1]) in (2, 3, 4) and parts[-1].isalpha():
                # Looks like a domain
                all_variants_set.add(name_lower)
                registered = extract_registered_domain(name_lower)
                if registered:
                    if registered != name_lower:
                        all_variants_set.add(registered)
                    canonical = normalize_to_canonical_vendor_domain(registered)
                    if canonical:
                        all_variants_set.add(canonical)
                        return CanonicalKeyResult(
                            primary_key=canonical,
                            registered_domain=registered,
                            is_canonical=True,
                            all_variants=sorted(all_variants_set)
                        )
                    return CanonicalKeyResult(
                        primary_key=registered,
                        registered_domain=registered,
                        is_canonical=True,
                        all_variants=sorted(all_variants_set)
                    )
                return CanonicalKeyResult(
                    primary_key=name_lower,
                    registered_domain=None,
                    is_canonical=True,
                    all_variants=sorted(all_variants_set)
                )

        # Check if name matches a vendor in VENDOR_TO_DOMAIN
        normalized_name = name_lower.replace(' ', '').replace('-', '').replace('_', '')
        if normalized_name in VENDOR_TO_DOMAIN:
            canonical = VENDOR_TO_DOMAIN[normalized_name]
            all_variants_set.add(canonical)
            return CanonicalKeyResult(
                primary_key=canonical,
                registered_domain=None,
                is_canonical=True,
                all_variants=sorted(all_variants_set) if all_variants_set else [canonical]
            )

    # Final fallback: sanitized name (NOT canonical)
    if name:
        import re
        sanitized = re.sub(r'[^a-z0-9]', '', name.lower())
        return CanonicalKeyResult(
            primary_key=sanitized,
            registered_domain=None,
            is_canonical=False,
            all_variants=sorted(all_variants_set) if all_variants_set else []
        )

    # No key could be determined
    raise ValueError("Cannot compute canonical key: no domains, vendor, or name provided")
