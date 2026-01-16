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
#
# Stage 4 Fix (Jan 2026): Infrastructure/service domains produce STABLE STANDALONE keys.
# These domains are NOT collapsed to vendor domain:
# - outlook.com: Microsoft email service (distinct SaaS endpoint)
# - office.com: Microsoft Office suite (distinct SaaS endpoint)
# - gstatic.com: Google static assets (distinct CDN/service)
# - cloudfront.net: AWS CDN service (distinct infrastructure)
# - awsstatic.com: AWS static assets (distinct infrastructure)
ALIAS_DOMAINS_TO_COLLAPSE: set[str] = {
    # Microsoft family - collapse to microsoft.com
    "microsoftonline.com",
    "microsoft365.com",  # Added: was missing in original
    "azure.com",
    # NOTE: office.com is a distinct service domain - NOT an alias (preserve identity)
    "office365.com",
    # NOTE: sharepoint.com is a PaaS root (multi-tenant), NOT collapsed - preserve subdomain identity
    "live.com",
    # Stage 4: outlook.com is a distinct email service - NOT collapsed (produces stable key)
    # "outlook.com",  # REMOVED - produces stable standalone key
    "onedrive.com",
    "powerbi.com",
    # Google family - collapse to google.com
    # NOTE: googleapis.com is a distinct service domain - NOT an alias (preserve identity)
    # Stage 4: gstatic.com is a distinct CDN service - NOT collapsed (produces stable key)
    # "gstatic.com",  # REMOVED - produces stable standalone key
    # NOTE: googleusercontent.com is a PaaS root (multi-tenant), NOT collapsed - preserve subdomain identity
    # Zoom family - collapse to zoom.com (Farm contract: zoom.com is canonical)
    "zoom.us",  # Jan 2026: Fixed direction - zoom.us collapses TO zoom.com
    "zoom-video.com",
    "zoom-meetings.net",
    "zoomapp.io",
    # Atlassian aliases - collapse to atlassian.com
    # Jan 2026: Added missing aliases per Farm contract
    "atlassian.net",  # Jira Cloud - Farm collapses to atlassian.com
    "trello.com",     # Farm collapses to atlassian.com
    "bitbucket.org",  # Farm collapses to atlassian.com
    "jira.com",
    "confluence.com",
    "opsgenie.com",
    "hipchat.com",    # Jan 2026: HipChat was Atlassian product (deprecated)
    # GitHub aliases
    "github.io",
    "githubusercontent.com",
    # Amazon/AWS aliases
    "amazonaws.com",
    # NOTE: cloudfront.net is a CDN domain - distinct service, NOT an alias
    # NOTE: awsstatic.com is a static asset domain - distinct service, NOT an alias
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
    # NOTE: cloudflareinsights.com is a distinct analytics/monitoring service, NOT collapsed
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
    Compute canonical key from domain list for reconciliation/matching.

    This function is used for alias expansion and reconciliation matching.
    For actual asset key selection during admission, see admission.py which
    uses lexicographic sort on discovery domains.

    Normalization pipeline:
    1. Extract registered domain (eTLD+1) from domains[0]
    2. Apply alias collapse for domains in ALIAS_DOMAINS_TO_COLLAPSE
    3. Collect all domain variants for alias expansion
    4. Return CanonicalKeyResult with primary key + all variants

    Vendor fallback (LAST RESORT ONLY):
    - Only executes if domains list is empty/None
    - NEVER overrides explicit domain evidence
    - Uses VENDOR_TO_DOMAIN mapping

    Examples:
        domains=["login.microsoftonline.com"]
        -> primary_key="microsoft.com", registered="microsoftonline.com"
        -> all_variants=["login.microsoftonline.com", "microsoft.com", "microsoftonline.com"]

        domains=["api.slack.com", "slack.com"]
        -> primary_key="slack.com", registered="slack.com"
        -> all_variants=["api.slack.com", "slack.com"]

        domains=[], vendor="Microsoft"
        -> primary_key="microsoft.com", registered=None
        -> all_variants=["microsoft.com"]

    Args:
        domains: List of domain strings (uses domains[0] for primary key)
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


def compute_canonical_key_v2(
    domains: list[str],
    domain_provenance: dict[str, str],
    vendor: Optional[str] = None,
    name: str = "",
    idp_app_id: Optional[str] = None
) -> CanonicalKeyResult:
    """
    V2 Key Generation Strategy (Jan 2026 Contract v2.0).
    
    Contract-aligned key selection:
    1. Filter to discovery domains only (domain_provenance[domain] == "discovery")
    2. Apply alias collapse
    3. Select via lexicographic sort (deterministic, order-independent)
    
    CMDB/IdP domains are reference/enrichment only - NOT used for keying unless
    there are no discovery domains AND policy explicitly enables promotion.
    
    See docs/contracts/KEY_SELECTION_CONTRACT.md for full specification.
    
    Args:
        domains: List of domain strings from identifiers.domains
        domain_provenance: Map of domain -> source (discovery, cmdb, idp, vendor_map, inferred)
        vendor: Optional vendor name for fallback
        name: Asset name for fallback
        idp_app_id: Optional IdP app object ID or service principal ID (fallback only)
        
    Returns:
        CanonicalKeyResult with contract-aligned primary_key
    """
    all_variants_set = set()
    collapsed_candidates = set()
    registered_to_raw = {}
    
    # Step 1: Filter to DISCOVERY domains only (contract requirement)
    discovery_domains = [
        d for d in domains 
        if d and "." in d and domain_provenance.get(d, "inferred") == "discovery"
    ]
    
    # Step 2 & 3: Extract eTLD+1 and apply alias collapse
    for domain in discovery_domains:
        raw_domain = domain.lower().strip()
        all_variants_set.add(raw_domain)
        
        registered = extract_registered_domain(raw_domain)
        if registered:
            if registered != raw_domain:
                all_variants_set.add(registered)
            
            if registered not in registered_to_raw:
                registered_to_raw[registered] = raw_domain
            
            canonical = normalize_to_canonical_vendor_domain(registered)
            if canonical:
                all_variants_set.add(canonical)
                collapsed_candidates.add(canonical)
            else:
                collapsed_candidates.add(registered)
        else:
            collapsed_candidates.add(raw_domain)
    
    # Step 4: Select via lexicographic sort (deterministic)
    if collapsed_candidates:
        sorted_candidates = sorted(collapsed_candidates)
        primary_key = sorted_candidates[0]
        
        # Find the registered domain that produced this key
        registered_domain = None
        for reg, raw in registered_to_raw.items():
            collapsed = normalize_to_canonical_vendor_domain(reg)
            if (collapsed and collapsed == primary_key) or (not collapsed and reg == primary_key):
                registered_domain = reg
                break
        
        if not registered_domain and primary_key in registered_to_raw:
            registered_domain = primary_key
        
        logger.debug(
            f"canonical_key_v2: discovery_domains={discovery_domains} -> "
            f"candidates={sorted_candidates} -> primary={primary_key} (lexicographic)"
        )
        
        return CanonicalKeyResult(
            primary_key=primary_key,
            registered_domain=registered_domain,
            is_canonical=True,
            all_variants=sorted(all_variants_set)
        )
    
    # Fallback: No discovery domains - use IdP app_id if stable
    if idp_app_id and idp_app_id.lower() not in ("unknown", "", "none"):
        import re
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        if re.match(uuid_pattern, idp_app_id.lower()) or len(idp_app_id) >= 20:
            logger.debug(f"canonical_key_v2: using idp_app_id={idp_app_id} as key (no discovery domains)")
            return CanonicalKeyResult(
                primary_key=f"idp:{idp_app_id}",
                registered_domain=None,
                is_canonical=False,
                all_variants=[]
            )
    
    # Final fallback: Use v1 behavior (includes all domains, vendor, name)
    return compute_canonical_key(domains=domains, vendor=vendor, name=name)


def compute_both_keys(
    domains: list[str],
    domain_provenance: dict[str, str],
    vendor: Optional[str] = None,
    name: str = "",
    idp_app_id: Optional[str] = None
) -> tuple[CanonicalKeyResult, CanonicalKeyResult]:
    """
    Compute both v1 and v2 keys for comparison during reconciliation.
    
    This allows us to:
    1. Track key drift between strategies
    2. Provide preview of v2 keys before switching
    3. Support Farm alignment without breaking existing consumers
    
    Returns:
        Tuple of (v1_result, v2_result)
    """
    v1_result = compute_canonical_key(domains=domains, vendor=vendor, name=name)
    v2_result = compute_canonical_key_v2(
        domains=domains, 
        domain_provenance=domain_provenance,
        vendor=vendor, 
        name=name,
        idp_app_id=idp_app_id
    )
    
    if v1_result.primary_key != v2_result.primary_key:
        logger.info(
            f"KEY_STRATEGY_DRIFT v1={v1_result.primary_key} v2={v2_result.primary_key} "
            f"domains={domains} provenance={domain_provenance}"
        )
    
    return v1_result, v2_result
