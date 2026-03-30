"""IdP-related helper functions for domain extraction and matching."""

from datetime import datetime, timezone
from typing import Optional

from ...models.input_contracts import IdPObject
from ..vendor_inference import extract_registered_domain, DOMAIN_TO_VENDOR
from ..domain_cache import extract_domain


def build_idp_activity_map(idp_records: dict) -> dict[str, datetime]:
    """
    Build a mapping of IdP name -> max login timestamp across ALL IdP records.

    Jan 2026: Cross-IdP activity aggregation using IdP NAME as the grouping key.
    This aligns with Farm's vendor family logic where multiple IdP records for
    the same vendor (e.g., "Cloudsync" with domains .dev, .io, .tech) share activity.

    The IdP `name` field is a safe aggregation key because:
    1. It represents the vendor/product name, not a shared domain like okta.com
    2. Farm uses vendor name for family grouping
    3. Unlike domains, IdP names are specific to the application

    Generic names are blocked to prevent false matches.

    Args:
        idp_records: Dictionary of idp_id -> IdPObject from PlaneIndex.records

    Returns:
        Dictionary of normalized IdP name -> max last_login_at datetime
    """
    # Generic names that could match multiple unrelated apps - must block
    GENERIC_IDP_NAMES = {
        'app', 'portal', 'admin', 'login', 'sso', 'auth', 'api', 'web', 'test',
        'staging', 'dev', 'prod', 'demo', 'internal', 'external', 'legacy',
        'service', 'system', 'platform', 'dashboard', 'console', 'gateway',
        'proxy', 'agent', 'client', 'server', 'manager', 'hub', 'connector'
    }

    name_to_max_login: dict[str, datetime] = {}

    for idp_id, obj in idp_records.items():
        if not isinstance(obj, IdPObject):
            continue

        name = obj.name
        if not name:
            continue

        normalized_name = name.lower().strip()

        # Skip generic names that could match unrelated apps
        if normalized_name in GENERIC_IDP_NAMES:
            continue

        # Skip names that are too short (likely abbreviations/codes)
        if len(normalized_name) < 4:
            continue

        login_ts = obj.last_login_at

        # Fallback: Check raw_data for login timestamps if main field is empty
        if login_ts is None and obj.raw_data and isinstance(obj.raw_data, dict):
            for field in ['last_login_at', 'lastLoginAt', 'lastLogin', 'last_activity', 'lastActivity']:
                raw_val = obj.raw_data.get(field)
                if raw_val:
                    if isinstance(raw_val, datetime):
                        login_ts = raw_val
                        break
                    elif isinstance(raw_val, str):
                        try:
                            parsed = datetime.fromisoformat(raw_val.replace('Z', '+00:00'))
                            if parsed.tzinfo is None:
                                parsed = parsed.replace(tzinfo=timezone.utc)
                            login_ts = parsed
                            break
                        except (ValueError, AttributeError):
                            continue

        if login_ts:
            current_max = name_to_max_login.get(normalized_name)
            if current_max is None or login_ts > current_max:
                name_to_max_login[normalized_name] = login_ts

    return name_to_max_login


def _extract_idp_domain(record: IdPObject) -> Optional[str]:
    """
    Extract registered domain from IdP record.

    Jan 2026: Domain-scoped IdP activity gating + vendor-based domain inference.

    Extraction logic (in order):
    1. record.domain field
    2. record.raw_data['external_ref']
    3. Infer from record.name via VENDOR_TO_DOMAIN mapping

    Step 3 enables vendor-based governance for name-only IdP matches.
    Example: IdP record "Teamsuite" (no domain field) → infers "teamsuite.cloud"
             which matches entity "teamsuite.ai" via vendor="TeamSuite"

    Returns:
        Registered domain (eTLD+1) if found, None otherwise
    """
    from ..vendor_inference import VENDOR_TO_DOMAIN

    # Step 1: Check domain field
    idp_domain = record.domain

    # Step 2: Check external_ref in raw_data
    if not idp_domain and record.raw_data and isinstance(record.raw_data, dict):
        ext_ref = record.raw_data.get('external_ref')
        if ext_ref and isinstance(ext_ref, str):
            ext_result = extract_domain(ext_ref)
            if ext_result.registered_domain:
                idp_domain = ext_result.registered_domain

    # Step 3: Infer from name via VENDOR_TO_DOMAIN
    # This enables cross-domain vendor governance for name-only IdP matches
    if not idp_domain and record.name:
        # Normalize IdP name for vendor lookup
        normalized_name = record.name.lower().strip()

        # Direct lookup (e.g., "microsoft 365" → "microsoft.com")
        if normalized_name in VENDOR_TO_DOMAIN:
            idp_domain = VENDOR_TO_DOMAIN[normalized_name]
        else:
            # Try matching vendor names (e.g., "Teamsuite" → find "TeamSuite" vendor → "teamsuite.cloud")
            # Build reverse vendor map (vendor → domain)
            vendor_to_canonical_domain = {}
            for domain, vendor in DOMAIN_TO_VENDOR.items():
                vendor_lower = vendor.lower().strip()
                if vendor_lower not in vendor_to_canonical_domain:
                    # Prefer .com/.so/.io/.us domains as canonical
                    vendor_to_canonical_domain[vendor_lower] = domain
                elif domain.endswith(('.com', '.so', '.io', '.us')):
                    vendor_to_canonical_domain[vendor_lower] = domain

            # Check if IdP name matches a known vendor
            if normalized_name in vendor_to_canonical_domain:
                idp_domain = vendor_to_canonical_domain[normalized_name]

    if idp_domain:
        return extract_registered_domain(idp_domain)
    return None


def _idp_domain_matches_entity(
    idp_registered_domain: Optional[str],
    entity_registered_domain: Optional[str],
    idp_name: Optional[str] = None
) -> bool:
    """
    Check if IdP domain matches entity domain for activity and governance purposes.

    Domain-aligned IdP governance matching with strict name-based fallback.

    Domains match if:
    1. Exact domain match (e.g., salesforce.com == salesforce.com)
    2. Same vendor via DOMAIN_TO_VENDOR (e.g., teamsuite.cloud and teamsuite.org both map to "TeamSuite")
    3. Name-based fallback (Option B): If IdP has no domain, normalized IdP name
       must exactly equal entity base token, and base token must be >= 5 chars.

    Examples:
    - salesforce.com (entity) vs salesforce.com (IdP) → MATCH (exact domain)
    - teamsuite.cloud (entity) vs teamsuite.org (IdP) → MATCH IF both map to same vendor
    - smartsuite.cloud (entity) vs smartsuite.org (IdP) → NO MATCH (no vendor mapping)
    - fastbox.cloud (entity) vs fastbox.ai (IdP) → NO MATCH (different TLD, no vendor link)
    - coreio.ai (entity) vs IdP "Coreio" with no domain → MATCH (exact name, 6 chars >= 5)
    - test.com (entity) vs IdP "Test" with no domain → NO MATCH (4 chars < 5 minimum)

    Matching rules:
    1. IdP has no domain → name-based fallback (exact match, >= 5 chars)
    2. Entity has no domain → True (allow match)
    3. Exact registered domain match → True
    4. Same vendor (via DOMAIN_TO_VENDOR) → True
    5. Different domains, no vendor link → False
    """
    # Name-based fallback (Option B): If IdP has no domain, allow exact name
    # match against entity base token with strict rules:
    # 1. Entity base token must be >= 5 chars (avoid short-token collisions)
    # 2. Normalized IdP name must EXACTLY equal entity base token (no startswith)
    # 3. Normalization: lowercase, strip dashes/underscores/spaces
    if not idp_registered_domain:
        if not idp_name or not entity_registered_domain:
            return False

        # Extract entity base token (part before first dot)
        entity_base = entity_registered_domain.split('.')[0].lower().strip()
        if len(entity_base) < 5:
            return False

        # Normalize IdP name: lowercase, strip dashes, underscores, spaces
        import re
        normalized_idp = re.sub(r'[-_\s]', '', idp_name.lower().strip())

        if normalized_idp == entity_base:
            return True

        return False

    # If entity has no domain, allow the match
    if not entity_registered_domain:
        return True

    # Exact registered domain match
    if idp_registered_domain == entity_registered_domain:
        return True

    # Check if both domains belong to the same vendor
    # This enables multi-TLD vendor governance (teamsuite.cloud inherits from teamsuite.org)
    from ..vendor_inference import infer_vendor_from_domain

    idp_vendor_result = infer_vendor_from_domain(idp_registered_domain)
    entity_vendor_result = infer_vendor_from_domain(entity_registered_domain)

    if idp_vendor_result and entity_vendor_result:
        # Both domains have vendor mappings - check if they're the same vendor
        if idp_vendor_result.value.lower() == entity_vendor_result.value.lower():
            return True

    # Jan 2026 FIX: Cross-TLD base-token matching was too permissive.
    # Farm does NOT match cross-TLD without an explicit vendor mapping.
    # 
    # Previous (buggy) behavior:
    # - smartsuite.cloud (entity) vs smartsuite.org (IdP) → MATCH (base tokens equal)
    #
    # Correct (Farm-aligned) behavior:
    # - smartsuite.cloud (entity) vs smartsuite.org (IdP) → NO MATCH (no vendor link)
    # - Only match cross-TLD if DOMAIN_TO_VENDOR maps both to same vendor
    #
    # The vendor mapping (lines 220-230 above) already handles legitimate cross-TLD
    # matching for known vendors. Pure base-token matching was causing 23 false
    # positives where AOD said HAS_IDP but Farm expected NO_IDP.
    #
    # REMOVED: Cross-TLD base-token matching without vendor link.
    # This aligns with the docstring: "fastbox.cloud vs fastbox.ai → NO MATCH (no vendor link)"

    # Different domains with no vendor link - no match
    return False
