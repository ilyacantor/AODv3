"""Domain extraction utilities for admission processing."""

import logging
import re
from typing import Optional

from ..correlate_entities import CorrelationResult, MatchStatus
from ..vendor_inference import extract_registered_domain
from ..normalize_observations import normalize_domain
from ...models.input_contracts import IdPObject, CMDBConfigItem
from .constants import SSO_PROVIDER_DOMAINS

logger = logging.getLogger(__name__)


def _clean_url_to_domain(value: Optional[str]) -> Optional[str]:
    """
    Extract domain from URL, cleaning protocol/path/port.

    EXACTLY mirrors the logic in build_plane_indexes._get_raw_domain() to ensure
    consistent domain extraction between indexing and correlation.

    NOTE: Does NOT require a dot - single tokens like "salesforce" from external_ref
    are valid because indexing preserves them. The caller filters invalid entries.

    Examples:
        "https://flexflow.org/app" -> "flexflow.org"
        "company.okta.com:443/login" -> "company.okta.com"
        "flexflow.org" -> "flexflow.org"
        "salesforce" -> "salesforce"  # Valid - matches _get_raw_domain behavior
    """
    if not value:
        return None
    cleaned = value.lower().strip()
    cleaned = cleaned.removeprefix("http://")
    cleaned = cleaned.removeprefix("https://")
    cleaned = cleaned.split("/")[0]  # Remove path
    cleaned = cleaned.split(":")[0]  # Remove port
    cleaned = cleaned.removeprefix("www.")
    return cleaned if cleaned else None


def _resolve_effective_domain_from_record(record) -> Optional[str]:
    """
    Resolve effective domain from a plane record using same fallback chain as indexing.

    Mirrors the fallback logic in build_plane_indexes.build_idp_index() and
    build_cmdb_index() to ensure domain extraction is consistent with what was indexed.

    Priority: domain > raw_data['domain'] > raw_data['external_ref'] >
              raw_data['url'] > raw_data['application_url'] > raw_data['service_url']

    Returns the cleaned domain (after URL parsing) or None if no valid domain found.
    """
    if record is None:
        return None

    # First: check direct domain attribute
    raw_domain = getattr(record, 'domain', None)
    if raw_domain:
        cleaned = _clean_url_to_domain(raw_domain)
        if cleaned:
            return cleaned

    # Second: check raw_data fields with same priority as indexing
    raw_data = getattr(record, 'raw_data', None)
    if raw_data and isinstance(raw_data, dict):
        for field in ['domain', 'external_ref', 'url', 'application_url', 'service_url']:
            field_value = raw_data.get(field)
            if field_value:
                cleaned = _clean_url_to_domain(field_value)
                if cleaned:
                    return cleaned

    return None


def _is_sso_or_infrastructure_domain(domain: str) -> bool:
    """Check if domain is an SSO provider or infrastructure domain that should be filtered."""
    from ...core.policy import get_current_config
    if not domain:
        return False
    registered = extract_registered_domain(domain)
    if not registered:
        return False
    infra_domains = get_current_config().infrastructure_domains
    return registered in SSO_PROVIDER_DOMAINS or registered in infra_domains


def validate_cmdb_domain_for_identity(
    domain: str,
    is_cmdb_anchored: bool = False
) -> tuple[bool, str]:
    """
    Validate a CMDB domain for promotion to identifiers.domains.

    Jan 2026: CTO-mandated validation gates for CMDB domain promotion:
    1. Must parse as domain (no URL, path, scheme, @)
    2. Must not be an IP address
    3. Must have at least one dot
    4. Must not be in generic_collision_roots UNLESS anchored
    5. Must not be in shared_infra/vendor_root UNLESS anchored

    This is DIFFERENT from external_ref - we're validating record.domain (primary).
    Stage 1 fix protects against external_ref URL leakage.

    Args:
        domain: The domain to validate
        is_cmdb_anchored: True if CMDB match is authoritative (bypasses some checks)

    Returns:
        Tuple of (is_valid, reason)
    """
    from ...core.policy import get_current_config

    if not domain:
        return False, "empty_domain"

    cleaned = domain.lower().strip()

    # Gate 1: No URLs, paths, schemes
    if '://' in cleaned or cleaned.startswith('http'):
        return False, "contains_url_scheme"
    if '/' in cleaned:
        return False, "contains_path"
    if '@' in cleaned:
        return False, "contains_email_symbol"

    # Clean any port or www prefix
    cleaned = cleaned.split(':')[0]
    cleaned = cleaned.removeprefix('www.')

    # Gate 2: Must have a dot (valid domain structure)
    if '.' not in cleaned:
        return False, "no_dot_invalid_domain"

    # Gate 3: Must not be an IP address
    ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if re.match(ip_pattern, cleaned):
        return False, "is_ip_address"

    # Gate 4: Reasonable TLD (at least 2 chars)
    parts = cleaned.split('.')
    tld = parts[-1]
    if len(tld) < 2:
        return False, "invalid_tld"

    config = get_current_config()
    registered = extract_registered_domain(cleaned)

    # Gate 5: Generic collision roots - suppress unless anchored
    if not is_cmdb_anchored:
        if config.infrastructure_domain_handling.is_generic_collision_root(registered or cleaned):
            return False, "generic_collision_root_unanchored"

    # Gate 6: Shared infrastructure - suppress unless anchored
    if not is_cmdb_anchored:
        all_infra = config.infrastructure_domain_handling.get_all_infrastructure_domains()
        if registered in all_infra or cleaned in all_infra:
            return False, "infrastructure_domain_unanchored"

    return True, "valid"


def extract_cmdb_primary_domain(
    correlation: CorrelationResult,
    is_authoritative_match: bool = False
) -> tuple[str | None, bool]:
    """
    Extract the primary domain from CMDB record.domain field.

    Jan 2026: This is the AUTHORITATIVE CMDB domain, distinct from external_ref URLs.
    Only extracts from record.domain (the CMDBConfigItem.domain field), not from
    raw_data URLs or external_ref fields.

    GOVERNANCE SEMANTICS (Architect Review Jan 2026):
    - is_authoritative_match should be True ONLY when CMDB match is MATCHED (not AMBIGUOUS)
      AND passes all governance gates (valid CI type, valid lifecycle, etc.)
    - Validation bypasses generic_collision_root/infrastructure checks only for authoritative matches
    - AMBIGUOUS matches still validate against all filters

    Args:
        correlation: The correlation result
        is_authoritative_match: True only if CMDB match is authoritative (MATCHED + gates passed)

    Returns:
        Tuple of (domain, is_valid) where domain is the cleaned primary domain
    """
    cmdb_match = correlation.cmdb

    if cmdb_match.status not in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
        return None, False

    # Only MATCHED status (not AMBIGUOUS) with authoritative match method can bypass filters
    cmdb_is_authoritative = (
        cmdb_match.status == MatchStatus.MATCHED and
        is_authoritative_match and
        cmdb_match.match_method in ("domain", "uri", "canonical_name")
    )

    for record in cmdb_match.matched_records:
        if record is None:
            continue

        # ONLY use record.domain (primary domain field)
        # NOT external_ref or raw_data URLs (those go to reference_domains)
        domain = getattr(record, 'domain', None)
        if domain:
            is_valid, reason = validate_cmdb_domain_for_identity(
                domain,
                is_cmdb_anchored=cmdb_is_authoritative
            )
            if is_valid:
                cleaned = domain.lower().strip()
                cleaned = cleaned.split(':')[0]
                cleaned = cleaned.removeprefix('www.')
                return cleaned, True
            else:
                logger.debug(
                    f"CMDB_DOMAIN_REJECTED domain={domain} reason={reason} "
                    f"authoritative={cmdb_is_authoritative}"
                )

    return None, False


def extract_cmdb_external_ref_domains(correlation: CorrelationResult) -> list[str]:
    """
    Extract domains specifically from CMDB external_ref field.

    Stage 1 Metric: This function is used to track cmdb_external_ref_domains_extracted_total.
    The domains returned here should NOT be in identifiers.domains after Stage 1 fix.

    Returns:
        List of domains extracted from CMDB external_ref field only
    """
    domains = []
    cmdb_match = correlation.cmdb

    if cmdb_match.status not in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
        return domains

    for record in cmdb_match.matched_records:
        if record is None:
            continue

        raw_data = getattr(record, 'raw_data', None)
        if raw_data and isinstance(raw_data, dict):
            external_ref = raw_data.get('external_ref')
            if external_ref:
                cleaned = _clean_url_to_domain(external_ref)
                if cleaned:
                    domains.append(cleaned)

    return domains


def _extract_all_domains_from_correlation(correlation: CorrelationResult) -> list[str]:
    """
    Extract ALL domains from correlation matched records.

    KEY_NORMALIZATION_MISMATCH fix: When entities are admitted, include ALL domains
    found in correlated plane records (IdP, CMDB, etc.) in the asset's identifiers.domains.
    This allows reconciliation to match against ANY domain variant, not just the
    entity's original domain.

    Uses same fallback field chain as indexing (external_ref, url, application_url,
    service_url) and includes raw, registered, AND canonical alias forms for maximum
    alias matching coverage. EXACTLY mirrors build_plane_indexes.

    This is critical for zombie detection where:
    - Discovery observation has domain "flowbase-internal.com"
    - IdP record has domain "flowbase.ai" (in external_ref field)
    - Farm expects "flowbase.ai" as the zombie key
    - Without this fix, AOD only publishes "flowbase-internal.com"

    Returns:
        List of unique, valid domains from all matched plane records
    """
    domains = set()

    def _is_valid_domain_for_alias(value: str) -> bool:
        """Check if value is valid for alias matching.

        Accepts both full domains (flexflow.org) AND tokens (salesforce)
        to mirror what build_plane_indexes stores in by_domain index.
        Only rejects email addresses and empty strings.
        """
        if not value:
            return False
        if '@' in value:
            return False
        return True

    def _is_proper_domain(value: str) -> bool:
        """Check if value looks like a proper domain with TLD."""
        if not value or '.' not in value:
            return False
        parts = value.split('.')
        return len(parts) >= 2 and len(parts[-1]) in (2, 3, 4, 5, 6) and parts[-1].isalpha()

    for plane_match in [correlation.idp, correlation.cmdb, correlation.cloud, correlation.finance]:
        if plane_match.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
            for record in plane_match.matched_records:
                if record is None:
                    continue

                # Use shared helper that mirrors indexing fallback chain
                effective_domain = _resolve_effective_domain_from_record(record)

                if effective_domain and _is_valid_domain_for_alias(effective_domain):
                    # EXACT PARITY with build_plane_indexes:
                    # Index BOTH the canonical domain AND raw domain
                    # Mirrors build_idp_index logic:
                    #   registered = normalize_domain(effective_domain)  # canonical
                    #   raw = _get_raw_domain(effective_domain)
                    #   add_to_index(index.by_domain, registered, record_id)
                    #   if raw and raw != registered: add_to_index(index.by_domain, raw, record_id)

                    # 1. Add canonical domain from normalize_domain (handles alias mappings)
                    canonical = normalize_domain(effective_domain)
                    if canonical and _is_valid_domain_for_alias(canonical):
                        domains.add(canonical)

                    # 2. Add raw domain if different from canonical (preserves tenant subdomains)
                    if effective_domain != canonical:
                        domains.add(effective_domain)

    return sorted(domains)


def _extract_domain_from_correlation(correlation: CorrelationResult, debug_log: bool = False) -> Optional[str]:
    """
    Extract a canonical domain from correlation matched records or match keys.

    POST-CORRELATION REKEYING: When an entity doesn't have a domain from normalization,
    check if any plane correlation found a domain. This fixes KEY_NORMALIZATION_MISMATCH
    where entities keyed by name during normalization had valid plane correlations with
    domain-containing records, but the domain wasn't propagated.

    Priority order (most authoritative first):
    1. IdP matched_records[].domain (SSO domains are authoritative for active usage)
    2. CMDB matched_records[].domain (IT-registered infrastructure domains)
    3. Cloud matched_records (check for domain attribute)
    4. Finance matched_records (check for domain attribute)
    5. Fallback: match_key from any plane (for direct domain matches)

    Only returns a domain if it looks valid (contains '.') and can be extracted
    to a registered domain.

    SAFETY: Rejects values that look like emails or URIs to avoid mis-keying.
    """
    entity_key = correlation.entity.canonical_name if correlation.entity else "unknown"

    def _clean_domain_from_url(value: Optional[str]) -> Optional[str]:
        """Extract domain from URL if needed, strip protocol/path."""
        if not value:
            return None
        value = value.strip()
        if '://' in value or value.startswith('http'):
            try:
                from urllib.parse import urlparse
                parsed = urlparse(value if '://' in value else f'https://{value}')
                return parsed.netloc or None
            except Exception:
                return None
        return value

    def _is_valid_domain_candidate(value: Optional[str]) -> bool:
        if not value or '.' not in value:
            return False
        if '@' in value:
            return False
        if '://' in value or value.startswith('http'):
            return False
        if '/' in value:
            return False
        return True

    if correlation.idp.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
        for record in correlation.idp.matched_records:
            if isinstance(record, IdPObject) and record.domain:
                cleaned = _clean_domain_from_url(record.domain)
                if _is_valid_domain_candidate(cleaned):
                    domain = extract_registered_domain(cleaned)
                    if domain:
                        return domain

    if correlation.cmdb.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
        for record in correlation.cmdb.matched_records:
            if isinstance(record, CMDBConfigItem) and record.domain:
                cleaned = _clean_domain_from_url(record.domain)
                if _is_valid_domain_candidate(cleaned):
                    domain = extract_registered_domain(cleaned)
                    if domain:
                        return domain

    planes_checked = []
    for plane_name, plane_match in [("idp", correlation.idp), ("cmdb", correlation.cmdb), ("cloud", correlation.cloud), ("finance", correlation.finance)]:
        if plane_match.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
            planes_checked.append(plane_name)
            for record in plane_match.matched_records:
                if record is None:
                    continue

                candidate = None

                # 1. Try top-level domain (defensive check for dict vs object)
                if isinstance(record, dict):
                    candidate = _clean_domain_from_url(record.get('domain'))
                else:
                    candidate = _clean_domain_from_url(getattr(record, 'domain', None))

                # 2. Fallback: Dig into raw_data if top-level failed
                if not candidate:
                    raw_data = getattr(record, 'raw_data', None)
                    if raw_data and isinstance(raw_data, dict):
                        raw_candidate = (
                            raw_data.get('domain') or
                            raw_data.get('registered_domain') or
                            raw_data.get('external_ref') or
                            raw_data.get('url') or
                            raw_data.get('application_url') or
                            raw_data.get('service_url')
                        )
                        candidate = _clean_domain_from_url(raw_candidate)

                # 3. Validate and return
                if candidate and _is_valid_domain_candidate(candidate):
                    domain = extract_registered_domain(candidate)
                    if domain:
                        return domain

            # Fallback to match_key (existing behavior)
            match_key = plane_match.match_key
            if _is_valid_domain_candidate(match_key):
                domain = extract_registered_domain(match_key)
                if domain:
                    return domain

    if debug_log and planes_checked:
        logger.warning(f"DOMAIN_EXTRACTION_FAILED entity={entity_key} planes_checked={planes_checked}")
        for plane_name, plane_match in [("idp", correlation.idp), ("cmdb", correlation.cmdb)]:
            if plane_match.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
                for record in plane_match.matched_records:
                    if record is None:
                        continue
                    record_type = type(record).__name__
                    domain_val = getattr(record, 'domain', 'NO_ATTR')
                    raw_data = getattr(record, 'raw_data', None)
                    logger.warning(f"  {plane_name} record: type={record_type} domain={domain_val} raw_data_keys={list(raw_data.keys()) if raw_data else 'None'}")
                    if raw_data:
                        logger.warning(f"    raw_data={raw_data}")

    return None
