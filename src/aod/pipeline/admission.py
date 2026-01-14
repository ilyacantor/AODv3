"""Stage 5: Admission (AAC) - Apply admission criteria to determine assets"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from ..models.output_contracts import (
    Asset, AssetType, Environment, LensStatus, LensStatuses, LensCoverage, AssetIdentifiers,
    ActivityEvidence, ProvisioningStatus, MatchDebugInfo, LensMatchDebug
)
from ..models.input_contracts import IdPObject, CMDBConfigItem, CloudResource, Contract, Transaction, Observation
from .correlate_entities import CorrelationResult, MatchStatus
from .deterministic_ids import deterministic_uuid
from .normalize_observations import CandidateEntity, normalize_domain
from .vendor_inference import DOMAIN_TO_VENDOR, extract_registered_domain
from .domain_cache import extract_domain
from ..constants import INFRASTRUCTURE_DOMAINS


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


VALID_CI_TYPES = {"app", "application", "service", "database", "infra", "infrastructure", "server", "system"}
VALID_LIFECYCLES = {"prod", "production", "staging", "stage", "live", "active"}


def _get_record_name(record) -> str:
    """Extract name from a plane record."""
    if hasattr(record, 'name'):
        return record.name
    if hasattr(record, 'app_name'):
        return record.app_name
    if hasattr(record, 'vendor_name'):
        return record.vendor_name
    return str(record) if record else ""


def build_match_debug_info(plane_match) -> Optional[MatchDebugInfo]:
    """Build debug info from a PlaneMatch for debugging CMDB/IdP matching issues."""
    if plane_match.status == MatchStatus.UNMATCHED:
        return None
    
    matched_record_id = plane_match.matched_ids[0] if plane_match.matched_ids else None
    matched_record_name = None
    if plane_match.matched_records:
        first_record = plane_match.matched_records[0]
        if first_record:
            matched_record_name = _get_record_name(first_record)
    
    return MatchDebugInfo(
        match_method=plane_match.match_method,
        match_key=plane_match.match_key,
        matched_record_id=matched_record_id,
        matched_record_name=matched_record_name,
        ambiguity_code=plane_match.ambiguity_code.value if plane_match.ambiguity_code else None,
        disambiguation_detail=plane_match.disambiguation_detail
    )


def build_lens_match_debug(correlation: CorrelationResult) -> Optional[LensMatchDebug]:
    """Build lens match debug info from a correlation result."""
    idp_debug = build_match_debug_info(correlation.idp)
    cmdb_debug = build_match_debug_info(correlation.cmdb)
    cloud_debug = build_match_debug_info(correlation.cloud)
    finance_debug = build_match_debug_info(correlation.finance)
    
    if not any([idp_debug, cmdb_debug, cloud_debug, finance_debug]):
        return None
    
    return LensMatchDebug(
        idp=idp_debug,
        cmdb=cmdb_debug,
        cloud=cloud_debug,
        finance=finance_debug
    )

SSO_PROVIDER_DOMAINS: set[str] = {
    "okta.com", "oktapreview.com",
    "auth0.com",
    "onelogin.com",
    "pingidentity.com", "pingone.com",
    "duo.com", "duosecurity.com",
    "jumpcloud.com",
}


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
    
    Jan 2026 Fix: This mirrors the fallback logic in build_plane_indexes.build_idp_index()
    and build_cmdb_index() to ensure domain extraction is consistent with what was indexed.
    
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
    if not domain:
        return False
    registered = extract_registered_domain(domain)
    if not registered:
        return False
    return registered in SSO_PROVIDER_DOMAINS or registered in INFRASTRUCTURE_DOMAINS


def _extract_all_domains_from_correlation(correlation: CorrelationResult) -> list[str]:
    """
    Extract ALL domains from correlation matched records.
    
    Dec 2025 Fix for KEY_NORMALIZATION_MISMATCH: When entities are admitted,
    we should include ALL domains found in correlated plane records (IdP, CMDB, etc.)
    in the asset's identifiers.domains. This allows reconciliation to match
    against ANY domain variant, not just the entity's original domain.
    
    Jan 2026 Fix: Now uses same fallback field chain as indexing (external_ref, url,
    application_url, service_url) and includes raw, registered, AND canonical alias
    forms for maximum alias matching coverage. EXACTLY mirrors build_plane_indexes.
    
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
    import logging
    logger = logging.getLogger(__name__)
    
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


# Banned domains - immediately BLOCKED (not QUARANTINE)
# These are domains that are policy-forbidden regardless of governance status
# Note: tiktok.com removed Jan 2026 - it's a common marketing platform, not policy-forbidden
BANNED_DOMAINS = {
    "kaspersky.com",
}


def is_banned_domain(domain: Optional[str]) -> bool:
    """Check if domain is in the BANNED_DOMAINS policy list.
    
    Banned domains are immediately blocked regardless of any governance evidence.
    Returns True if the registered domain (eTLD+1) matches a banned domain.
    """
    if not domain:
        return False
    registered = extract_registered_domain(domain)
    if not registered:
        return False
    return registered.lower() in BANNED_DOMAINS


# Corporate/marketing root domains - NEVER admit these
# These are the TENANT'S OWN domains (not vendor SaaS platforms)
# NOTE: SaaS vendor domains (okta.com, workday.com, etc.) are OPERATIONAL
# assets that SHOULD be admitted and classified as shadow IT if ungoverned.
# Only block the tenant's own corporate domains.
CORPORATE_ROOT_DOMAINS = {
    # Placeholder - populated dynamically per tenant if available
    # Example: "acme-corp.com", "acme.io" for tenant ACME
    # For now, we don't block any domains globally since all vendor
    # SaaS platforms are legitimate discovery targets.
}


def is_corporate_root_domain(domain: Optional[str]) -> bool:
    """Check if domain is a corporate/marketing root domain that should never be admitted."""
    if not domain:
        return False
    domain_lower = domain.lower().strip()
    return domain_lower in CORPORATE_ROOT_DOMAINS


def is_infrastructure_domain(domain: Optional[str]) -> bool:
    """Check if domain is an infrastructure/tooling domain that should not be admitted as a SaaS asset."""
    if not domain:
        return False
    registered = extract_registered_domain(domain)
    if not registered:
        return False
    return registered in INFRASTRUCTURE_DOMAINS


VALID_CLOUD_RESOURCE_TYPES = {
    "compute", "ec2", "vm", "instance", "container", "ecs", "eks", "kubernetes",
    "database", "rds", "dynamodb", "aurora", "redis", "elasticache",
    "storage", "s3", "bucket", "ebs",
    "lambda", "function", "serverless",
    "api", "gateway", "load_balancer", "elb", "alb",
    "queue", "sqs", "sns", "eventbridge",
    "service", "ecs_service", "app_runner"
}


@dataclass
class AdmissionResult:
    """
    Result of admission evaluation with Traffic Light status.
    
    Traffic Light System (fail-closed):
    - IGNORED: Hard rejection (invalid TLD, infrastructure domain) - dropped
    - ACTIVE: Trusted (has IdP or CMDB) - flows to DCL
    - REVIEW: Needs cleanup (CMDB but stale activity) - flagged for review
    - QUARANTINE: Shadow IT (Cloud/Finance/Discovery but no IdP/CMDB) - blocked from DCL
    """
    admitted: bool
    provisioning_status: ProvisioningStatus = ProvisioningStatus.QUARANTINE
    asset: Optional[Asset] = None
    rejection_reason: Optional[str] = None
    admission_reason: Optional[str] = None


def check_idp_admission(correlation: CorrelationResult, entity_registered_domain: Optional[str] = None) -> tuple[bool, str]:
    """
    Check IdP plane admission criteria:
    - IdP match with DOMAIN-ALIGNED governance (exact domain match required)
    - SSO/SCIM provides stronger confidence but STILL requires domain alignment
    NOTE: Both MATCHED and AMBIGUOUS count as having IdP evidence.

    Jan 2026 Fix: Farm requires domain-aligned IdP for admission, NOT cross-domain matches.
    SSO/SCIM does NOT override domain alignment - it's a stronger signal FOR domain-aligned matches.

    Cross-domain IdP matches (e.g., fastbox.cloud matched to fastbox.ai IdP) do NOT
    provide governance for admission, even if the IdP has SSO/SCIM enabled.
    Farm's decision traces confirm: idp_present=False for cross-domain matches.

    Examples:
    - fastbox.cloud entity + fastbox.ai IdP with SSO → NOT admitted (cross-domain)
    - fastbox.cloud entity + fastbox.cloud IdP with SSO → admitted (domain-aligned + SSO)
    - easyworks.ai entity + easyworks.ai IdP → admitted (exact match)
    """
    if correlation.idp.status not in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
        return False, ""

    for record in correlation.idp.matched_records:
        if isinstance(record, IdPObject):
            # Check for domain alignment FIRST (required for all IdP admission)
            idp_domain = None
            if record.domain:
                idp_domain = extract_registered_domain(record.domain)

            if _idp_domain_matches_entity(idp_domain, entity_registered_domain, idp_name=record.name):
                # Domain-aligned match - check for SSO/SCIM as stronger signal
                if record.has_sso:
                    return True, "IdP match with SSO enabled (domain-aligned governance)"
                if record.has_scim:
                    return True, "IdP match with SCIM enabled (domain-aligned governance)"
                # Domain-aligned match without SSO/SCIM still counts
                return True, "IdP match with domain-aligned governance"

    # Cross-domain IdP matches (even with SSO/SCIM) do NOT provide admission governance
    return False, ""


def check_cmdb_admission(correlation: CorrelationResult) -> tuple[bool, str]:
    """
    Check CMDB plane admission criteria:
    - CMDB match (any CI is sufficient for admission)
    - Prefer: ci_type in app/service/database/infra AND lifecycle in prod/staging (stronger signal)
    NOTE: Both MATCHED and AMBIGUOUS count as having CMDB evidence.
    
    RELAXED: Any CMDB match counts. Valid ci_type/lifecycle provides stronger confidence but is not required.
    """
    if correlation.cmdb.status not in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
        return False, ""
    
    for record in correlation.cmdb.matched_records:
        if isinstance(record, CMDBConfigItem):
            ci_type_valid = record.ci_type.lower() in VALID_CI_TYPES
            lifecycle_valid = record.lifecycle.lower() in VALID_LIFECYCLES
            
            if ci_type_valid and lifecycle_valid:
                return True, f"CMDB match: {record.ci_type} in {record.lifecycle}"
    
    if correlation.cmdb.matched_records:
        return True, "CMDB match (configuration item)"
    
    return False, ""


def check_cloud_admission(correlation: CorrelationResult) -> tuple[bool, str]:
    """
    Check Cloud plane admission criteria:
    - Cloud match (any cloud resource is sufficient for admission)
    - Prefer: resource_type indicates real system/resource (stronger signal)
    NOTE: Both MATCHED and AMBIGUOUS count as having Cloud evidence.
    
    RELAXED: Any cloud match counts. Valid resource_type provides stronger confidence but is not required.
    """
    if correlation.cloud.status not in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
        return False, ""
    
    for record in correlation.cloud.matched_records:
        if isinstance(record, CloudResource):
            resource_type = record.resource_type.lower()
            for valid_type in VALID_CLOUD_RESOURCE_TYPES:
                if valid_type in resource_type:
                    return True, f"Cloud match: {record.resource_type}"
    
    if correlation.cloud.matched_records:
        return True, "Cloud match (cloud resource)"
    
    return False, ""


def has_recurring_finance_spend(correlation: CorrelationResult) -> bool:
    """
    Check if the correlation has recurring finance spend (ongoing finance).
    
    Returns True if there are:
    - Recurring contracts with amount > 0, OR
    - Recurring transactions with amount > 0
    
    NOTE: Multiple non-recurring transactions do NOT qualify as recurring spend.
    Only explicitly marked is_recurring=True records count as ongoing finance.
    
    This is used by the admission policy to allow finance-only admission
    when there's strong recurring spend evidence combined with recent activity.
    """
    if correlation.finance.status not in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
        return False
    
    for record in correlation.finance.matched_records:
        if isinstance(record, Contract):
            if record.is_recurring and record.amount > 0:
                return True
        elif isinstance(record, Transaction):
            if record.is_recurring and record.amount > 0:
                return True
    
    return False


def check_finance_admission(correlation: CorrelationResult) -> tuple[bool, str]:
    """
    Check Finance plane admission criteria:
    - Finance match with any spend evidence
    - Prefer: recurring contracts/transactions (stronger signal)
    
    RELAXED: Any finance match with amount > 0 counts for admission.
    Recurring spend provides stronger confidence but is not required.
    
    NOTE: Both MATCHED and AMBIGUOUS count as having finance evidence.
    Vendor-only matches are NOT sufficient for finance admission.
    """
    if correlation.finance.status not in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
        return False, ""
    
    # Check for actual finance records (Contract or Transaction)
    has_actual_finance_record = False
    for record in correlation.finance.matched_records:
        if isinstance(record, Contract):
            has_actual_finance_record = True
            if record.is_recurring and record.amount > 0:
                return True, f"Finance match: Recurring contract ${record.amount}"
            elif record.amount > 0:
                return True, f"Finance match: Contract ${record.amount}"
        elif isinstance(record, Transaction):
            has_actual_finance_record = True
            if record.is_recurring and record.amount > 0:
                return True, f"Finance match: Recurring transaction ${record.amount}"
            elif record.amount > 0:
                return True, f"Finance match: Transaction ${record.amount}"
    
    # If we found Contract/Transaction records (even with amount=0), admit
    if has_actual_finance_record:
        return True, "Finance match (spend evidence)"
    
    # Check match_method - only trust non-vendor finance matches
    # Vendor-only matches don't indicate actual finance evidence
    if correlation.finance.match_method and correlation.finance.match_method != "vendor":
        return True, "Finance match (correlation status)"
    
    # Vendor-only match or empty records - not sufficient for finance admission
    return False, ""


DISCOVERY_ACTIVITY_WINDOW_DAYS = 90

SOURCE_TO_PLANE = {
    "dns": "network",
    "proxy": "network",
    "web_filter": "network",
    "firewall": "network",
    "netflow": "network",
    "packet_capture": "network",
    "casb": "network",
    "swg": "network",
    "dlp": "network",
    "siem": "network",
    "zscaler": "network",
    "zscaler_proxy": "network",
    "zscaler_zia": "network",
    "zscaler_gre": "network",
    "paloalto": "network",
    "paloalto_panorama": "network",
    "netskope": "network",
    "netskope_casb": "network",
    "symantec_proxy": "network",
    "bluecoat": "network",
    "fortigate": "network",
    "cisco_umbrella": "network",
    "cato": "network",
    "cloudflare_gateway": "network",
    "menlo": "network",
    "iboss": "network",
    "browser": "network",
    "network_scan": "network",
    "edr": "endpoint",
    "mdm": "endpoint",
    "av": "endpoint",
    "agent": "endpoint",
    "endpoint": "endpoint",
    "endpoint_protection": "endpoint",
    "crowdstrike": "endpoint",
    "sentinelone": "endpoint",
    "carbonblack": "endpoint",
    "defender": "endpoint",
    "jamf": "endpoint",
    "intune": "endpoint",
    "workspace_one": "endpoint",
    "kandji": "endpoint",
    "sso": "idp",
    "oauth": "idp",
    "saml": "idp",
    "directory": "idp",
    "ldap": "idp",
    "okta": "idp",
    "azure_ad": "idp",
    "entra_id": "idp",
    "onelogin": "idp",
    "ping": "idp",
    "jumpcloud": "idp",
    "cloud_trail": "cloud",
    "cloudtrail": "cloud",
    "aws_config": "cloud",
    "azure_monitor": "cloud",
    "gcp_audit": "cloud",
    "aws": "cloud",
    "azure": "cloud",
    "gcp": "cloud",
    "cloud_api": "cloud",
    "saas_audit_log": "discovery",
    "contract": "finance",
    "invoice": "finance",
    "expense": "finance",
    "purchase_order": "finance",
    "procurement": "finance",
    "finance": "finance",
    "finance_coupa": "finance",
    "finance_netsuite": "finance",
    "finance_sap": "finance",
    "finance_ariba": "finance",
    "finance_concur": "finance",
    "coupa": "finance",
    "netsuite": "finance",
    "sap_ariba": "finance",
    "concur": "finance",
    "workday": "finance",
    "spend": "finance",
    "cmdb": "cmdb",
    "servicenow": "cmdb",
    "discovery": "discovery",
    "simulation": "discovery",
    "generator": "discovery",
    "farm_dns": "network",
    "farm_proxy": "network",
    "farm_network": "network",
    "farm_endpoint": "endpoint",
    "farm_idp": "idp",
    "farm_sso": "idp",
    "farm_cloud": "cloud",
    "farm_finance": "finance",
    "farm_cmdb": "cmdb",
    "simulated_dns": "network",
    "simulated_proxy": "network",
    "simulated_network": "network",
    "simulated_endpoint": "endpoint",
    "simulated_idp": "idp",
    "simulated_sso": "idp",
    "simulated_cloud": "cloud",
    "simulated_finance": "finance",
    "simulated_cmdb": "cmdb",
    "test_dns": "network",
    "test_proxy": "network",
    "test_network": "network",
    "test_endpoint": "endpoint",
    "test_idp": "idp",
    "test_cloud": "cloud",
    "synthetic_dns": "network",
    "synthetic_proxy": "network",
    "synthetic_network": "network",
    "synthetic_endpoint": "endpoint",
    "synthetic_idp": "idp",
    "synthetic_cloud": "cloud",
    "network": "network",
    "endpoint": "endpoint",
    "idp": "idp",
    "cloud": "cloud",
}


def source_to_plane(source: str) -> Optional[str]:
    """
    Map a source to its parent plane.
    
    Returns None for unknown sources to ensure they don't contribute to plane diversity.
    Unknown sources are quarantined from counting to prevent signal inflation.
    """
    return SOURCE_TO_PLANE.get(source.lower())


DISCOVERY_CORROBORATION_PLANES = {"network", "endpoint", "idp", "cloud", "discovery"}

# FARM_CREDITED_DISCOVERY_SOURCES: Sources Farm recognizes as "hard discovery"
# Excludes user-activity exhaust like proxy, browser, saas_audit_log which are too noisy
# Farm policy only credits sources that represent:
# - Direct system/network scans (dns, network_scan)
# - Endpoint agent telemetry (edr, mdm, endpoint)
# - Cloud API discovery (cloud_api, cloud_trail)
# Ref: Farm assessment discrepancy - 51 FPs from proxy/browser sources Farm ignores
FARM_CREDITED_DISCOVERY_SOURCES = {
    # Network hard discovery (not user activity)
    "dns", "network_scan", "firewall", "netflow", "packet_capture",
    "zscaler_gre", "paloalto_panorama",
    # Endpoint agents
    "edr", "mdm", "av", "agent", "endpoint", "endpoint_protection",
    "crowdstrike", "sentinelone", "carbonblack", "defender",
    "jamf", "intune", "workspace_one", "kandji",
    # Cloud API discovery
    "cloud_api", "cloud_trail", "cloudtrail", "aws_config", "azure_monitor", "gcp_audit",
    "aws", "azure", "gcp",
    # IdP (for SSO discovery)
    "sso", "oauth", "saml", "directory", "ldap", "okta", "azure_ad", "entra_id",
    "onelogin", "ping", "jumpcloud",
    # Explicit discovery sources
    "discovery",
    # Simulated/test variants
    "simulated_dns", "simulated_endpoint", "simulated_cloud", "simulated_idp",
    "farm_dns", "farm_endpoint", "farm_cloud", "farm_idp",
    "synthetic_dns", "synthetic_endpoint", "synthetic_cloud", "synthetic_idp",
    "test_dns", "test_endpoint", "test_cloud", "test_idp",
}

# USER_ACTIVITY_EXHAUST: Sources that are user-behavior/proxy data
# Farm ignores these as they don't represent "real" discovery evidence
USER_ACTIVITY_EXHAUST = {
    "proxy", "browser", "saas_audit_log", "casb", "swg", "dlp", "siem",
    "web_filter", "zscaler", "zscaler_proxy", "zscaler_zia", "netskope",
    "netskope_casb", "symantec_proxy", "bluecoat", "fortigate",
    "cisco_umbrella", "cato", "cloudflare_gateway", "menlo", "iboss",
    "simulated_proxy", "farm_proxy", "synthetic_proxy", "test_proxy",
    "simulated_network", "farm_network", "synthetic_network", "test_network",
    "network",  # Generic "network" is too ambiguous
}

MIN_DISCOVERY_SOURCES = 2

import logging
logger = logging.getLogger(__name__)


class DiscoveryInvariantError(Exception):
    """Raised when discovery evidence invariants fail - indicates split-brain state."""
    pass


def _validate_discovery_invariants(asset, expected_sources: list[str], asset_key: str) -> None:
    """
    Runtime invariants to ensure discovery_sources is the single source of truth.
    
    FAIL FAST: If any invariant fails, raise DiscoveryInvariantError and stop.
    Do not limp forward with inconsistent state.
    
    Invariant 1: lens_coverage.discovery == bool(discovery_sources)
    Invariant 2: asset.discovery_sources matches expected sources from footprint
    """
    has_sources = len(expected_sources) > 0
    
    # Invariant 1: lens_coverage.discovery must equal bool(discovery_sources)
    if asset.lens_coverage.discovery != has_sources:
        raise DiscoveryInvariantError(
            f"INVARIANT_VIOLATION: Asset {asset_key} | "
            f"lens_coverage.discovery={asset.lens_coverage.discovery} but "
            f"discovery_sources={expected_sources} (bool={has_sources}). "
            f"These must agree. Fix: lens_coverage.discovery should derive from discovery_sources."
        )
    
    # Invariant 2: asset.discovery_sources must match expected sources
    if sorted(asset.discovery_sources) != sorted(expected_sources):
        raise DiscoveryInvariantError(
            f"INVARIANT_VIOLATION: Asset {asset_key} | "
            f"asset.discovery_sources={asset.discovery_sources} but "
            f"expected from footprint={expected_sources}. "
            f"These must agree. Fix: discovery_sources should be set only from footprint."
        )


@dataclass
class DiscoveryFootprint:
    """Evidence footprint for discovery admission."""
    discovery_sources: set
    planes_present: set
    recent_activity: bool
    latest_activity_at: Optional[datetime]
    reason_codes: list


def build_discovery_footprint(
    observations: Optional[list[Observation]],
    canonical_key: Optional[str] = None,
    snapshot_timestamp: Optional[datetime] = None
) -> DiscoveryFootprint:
    """
    Build an evidence footprint for a CandidateEntity's discovery observations.
    
    Jan 2026 Fix: Count sources with RECENT activity relative to SNAPSHOT timestamp.
    Farm uses the snapshot generation timestamp as the reference point for the 90-day
    activity window, not the current time. This ensures consistent results across runs.
    
    Returns:
        DiscoveryFootprint with:
        - discovery_sources: set of distinct source names WITH RECENT ACTIVITY
        - planes_present: set of mapped planes with recent activity
        - recent_activity: True if any observation is within 90 days of snapshot
        - latest_activity_at: timestamp of most recent observation
        - reason_codes: list of reason codes for this footprint
    """
    from datetime import timedelta, timezone
    
    all_discovery_sources: set = set()
    all_planes_present: set = set()
    latest_activity: Optional[datetime] = None
    reason_codes: list = []
    
    if not observations:
        return DiscoveryFootprint(
            discovery_sources=set(),
            planes_present=set(),
            recent_activity=False,
            latest_activity_at=None,
            reason_codes=["NO_DISCOVERY"]
        )
    
    # Calculate cutoff for recent activity - use snapshot timestamp as reference if provided
    # Farm uses snapshot timestamp, not current time, for consistent 90-day windows
    reference_time = snapshot_timestamp if snapshot_timestamp else datetime.now(timezone.utc)
    if reference_time.tzinfo is None:
        reference_time = reference_time.replace(tzinfo=timezone.utc)
    cutoff = reference_time - timedelta(days=DISCOVERY_ACTIVITY_WINDOW_DAYS)
    
    # Count only sources with RECENT activity (using snapshot timestamp as reference)
    # Farm's policy: count sources where the observation is within 90 days of snapshot
    for obs in observations:
        # Track latest activity timestamp
        if obs.observed_at:
            obs_time = obs.observed_at
            if obs_time.tzinfo is None:
                obs_time = obs_time.replace(tzinfo=timezone.utc)
            if latest_activity is None or obs_time > latest_activity:
                latest_activity = obs_time
        
        # Only count sources with RECENT activity (within 90 days of snapshot)
        if obs.source and obs.observed_at:
            obs_time = obs.observed_at
            if obs_time.tzinfo is None:
                obs_time = obs_time.replace(tzinfo=timezone.utc)
            
            # Only count if observation is recent relative to snapshot timestamp
            if obs_time >= cutoff:
                source_lower = obs.source.lower()
                plane = source_to_plane(source_lower)
                # Only count sources that map to discovery-corroboration planes
                # Exclude CMDB and finance sources as they aren't "real" discovery evidence
                if plane is not None and plane in DISCOVERY_CORROBORATION_PLANES:
                    all_discovery_sources.add(source_lower)
                    all_planes_present.add(plane)
    
    recent_activity = latest_activity is not None and latest_activity >= cutoff
    
    # Use the sources with recent activity
    discovery_sources = all_discovery_sources
    planes_present = all_planes_present
    
    if len(discovery_sources) >= MIN_DISCOVERY_SOURCES:
        reason_codes.append("DISCOVERY_SOURCE_COUNT_GE_2")
    else:
        reason_codes.append("DISCOVERY_SOURCE_COUNT_LT_2")
    
    if len(planes_present) >= 2:
        reason_codes.append("PLANE_DIVERSITY_GE_2")
    else:
        reason_codes.append("PLANE_DIVERSITY_LT_2")
    
    if discovery_sources:
        reason_codes.append("HAS_DISCOVERY")
    else:
        reason_codes.append("NO_DISCOVERY")
    
    if recent_activity:
        reason_codes.append("RECENT_ACTIVITY")
    elif latest_activity:
        reason_codes.append("STALE_ACTIVITY")
    else:
        reason_codes.append("NO_ACTIVITY_TIMESTAMPS")
    
    return DiscoveryFootprint(
        discovery_sources=discovery_sources,
        planes_present=planes_present,
        recent_activity=recent_activity,
        latest_activity_at=latest_activity,
        reason_codes=reason_codes
    )


def check_discovery_admission(
    observations: Optional[list[Observation]],
    min_sources: int = MIN_DISCOVERY_SOURCES,
    canonical_key: Optional[str] = None,
    snapshot_timestamp: Optional[datetime] = None
) -> tuple[bool, str]:
    """
    Check discovery-only admission criteria.
    
    Admit discovery-only candidates when usage is corroborated and recent:
    - Evidence from ≥2 distinct DISCOVERY SOURCES (not planes!)
    - Recent activity ≤ 90 days
    
    CRITICAL FIX (Dec 2025):
    - Gate on distinct SOURCES (browser, proxy, dns = 3 sources) NOT distinct planes
    - Plane diversity is an annotation/confidence signal, NOT an admission blocker
    - This fixes shadow misses where assets like asana.com with 3 sources
      (browser, proxy, dns) were rejected because they all map to "network" plane
    
    Args:
        observations: List of discovery observations
        min_sources: Minimum distinct sources required (default: 2)
        canonical_key: Entity key for debug logging
        snapshot_timestamp: Snapshot timestamp for 90-day window reference
        
    Returns:
        Tuple of (admitted: bool, reason: str)
    """
    footprint = build_discovery_footprint(observations, canonical_key, snapshot_timestamp)
    
    source_count = len(footprint.discovery_sources)
    plane_count = len(footprint.planes_present)
    
    if source_count < min_sources:
        if canonical_key:
            logger.debug(
                f"DISCOVERY_ADMISSION_FAIL: {canonical_key} | "
                f"sources={sorted(footprint.discovery_sources)} (count={source_count}) | "
                f"planes={sorted(footprint.planes_present)} (count={plane_count}) | "
                f"recent_activity={footprint.recent_activity}"
            )
        return False, ""
    
    if not footprint.recent_activity:
        if canonical_key:
            logger.debug(
                f"DISCOVERY_ADMISSION_FAIL: {canonical_key} | "
                f"sources={sorted(footprint.discovery_sources)} (count={source_count}) | "
                f"planes={sorted(footprint.planes_present)} (count={plane_count}) | "
                f"recent_activity={footprint.recent_activity} | "
                f"latest_activity={footprint.latest_activity_at}"
            )
        return False, ""
    
    plane_note = f", {plane_count} planes" if plane_count >= 2 else ""
    activity_date = footprint.latest_activity_at.date() if footprint.latest_activity_at else "unknown"
    
    return True, f"Discovery: {source_count} sources ({', '.join(sorted(footprint.discovery_sources))}){plane_note}, last activity {activity_date}"


def determine_asset_type(correlation: CorrelationResult, entity: Optional[CandidateEntity] = None) -> AssetType:
    """
    Determine asset type from correlation evidence.
    
    AMBIGUOUS is treated the same as MATCHED for type inference - if we found
    evidence (even with multiple matches), we can still infer the type.
    
    Fallback: If no correlation evidence gives a type, check if the entity's
    domain is in our known SaaS vendor list (DOMAIN_TO_VENDOR).
    """
    has_cloud = correlation.cloud.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS)
    has_cmdb = correlation.cmdb.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS)
    has_idp = correlation.idp.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS)
    has_finance = correlation.finance.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS)
    
    if has_cloud:
        for record in correlation.cloud.matched_records:
            if isinstance(record, CloudResource):
                rt = record.resource_type.lower()
                if "database" in rt or "rds" in rt or "dynamodb" in rt:
                    return AssetType.DATABASE
                if "lambda" in rt or "function" in rt:
                    return AssetType.SERVICE
                return AssetType.CLOUD_RESOURCE
    
    if has_cmdb:
        for record in correlation.cmdb.matched_records:
            if isinstance(record, CMDBConfigItem):
                ct = record.ci_type.lower()
                if "database" in ct:
                    return AssetType.DATABASE
                if "infra" in ct or "server" in ct:
                    return AssetType.INFRA
                if "service" in ct:
                    return AssetType.SERVICE
                return AssetType.SAAS
    
    if has_idp:
        return AssetType.SAAS
    
    if has_finance:
        return AssetType.SAAS
    
    KNOWN_DATABASE_DOMAINS = {
        "postgresql.org", "postgres.org", "mysql.com", "mysql.org",
        "mariadb.org", "mariadb.com", "mongodb.com", "mongodb.org",
        "redis.io", "redis.com", "cassandra.apache.org", "couchbase.com",
        "neo4j.com", "influxdata.com", "timescale.com", "cockroachlabs.com",
        "planetscale.com", "supabase.com", "supabase.io", "neon.tech",
        "fauna.com", "arangodb.com", "dgraph.io", "singlestore.com"
    }
    
    KNOWN_DATABASE_NAMES = {
        "postgresql", "postgres", "mysql", "mariadb", "mongodb", "mongo",
        "redis", "cassandra", "couchbase", "neo4j", "influxdb", "timescaledb",
        "cockroachdb", "planetscale", "supabase", "neon", "fauna", "arangodb",
        "dgraph", "singlestore", "dynamodb", "aurora", "rds"
    }
    
    if entity:
        if entity.domain:
            domain_key = entity.domain.lower().strip()
            if domain_key in KNOWN_DATABASE_DOMAINS:
                return AssetType.DATABASE
            if domain_key in DOMAIN_TO_VENDOR:
                return AssetType.SAAS
        
        name_key = entity.original_name.lower().strip().replace("-", "").replace("_", "")
        for db_name in KNOWN_DATABASE_NAMES:
            if db_name in name_key:
                return AssetType.DATABASE
    
    return AssetType.UNKNOWN


def determine_environment(correlation: CorrelationResult) -> Environment:
    """Determine environment from correlation evidence"""
    if correlation.cmdb.status == MatchStatus.MATCHED:
        for record in correlation.cmdb.matched_records:
            if isinstance(record, CMDBConfigItem):
                env = record.environment.lower()
                if "prod" in env:
                    return Environment.PROD
                if "stag" in env:
                    return Environment.STAGING
                if "dev" in env:
                    return Environment.DEV
    
    if correlation.cloud.status == MatchStatus.MATCHED:
        for record in correlation.cloud.matched_records:
            if isinstance(record, CloudResource):
                env = record.environment.lower()
                if "prod" in env:
                    return Environment.PROD
                if "stag" in env:
                    return Environment.STAGING
                if "dev" in env:
                    return Environment.DEV
    
    return Environment.UNKNOWN


def _extract_base_name_from_domain(domain: Optional[str]) -> Optional[str]:
    """
    Extract the base name (first token) from a registered domain.
    
    Example: flowapp.co -> flowapp, worktech.cloud -> worktech
    
    Returns:
        Base name (lowercased) if extractable, None otherwise
    """
    if not domain or "." not in domain:
        return None
    base = domain.split(".")[0].lower()
    if len(base) >= 3:  # Require at least 3 chars to avoid false positives
        return base
    return None


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
    from .vendor_inference import VENDOR_TO_DOMAIN

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
            from .vendor_inference import DOMAIN_TO_VENDOR
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

    Jan 2026 Fix: Multi-domain vendor governance alignment and name-based fallback.

    Domains match if:
    1. Exact domain match (e.g., salesforce.com == salesforce.com)
    2. Same vendor (e.g., teamsuite.cloud and teamsuite.org both map to "TeamSuite")
    3. IdP has no domain but IdP name matches entity's base domain token

    This enables cross-domain IdP governance for multi-TLD vendors while preserving
    the strict matching for unrelated domains with the same base name.

    Examples:
    - teamsuite.cloud (entity) vs teamsuite.org (IdP) → MATCH (same vendor "TeamSuite")
    - coreio.ai (entity) vs IdP "Coreio" with no domain → MATCH (name matches base token)
    - dataflow.cloud (entity) vs dataflow.net (IdP) → NO MATCH (no vendor mapping)
    - salesforce.com (entity) vs salesforce.com (IdP) → MATCH (exact domain)
    - fastbox.cloud (entity) vs fastbox.ai (IdP) → NO MATCH (different TLD, no vendor link)

    Matching rules:
    1. IdP has no domain → check if IdP name matches entity's base token
    2. Entity has no domain → True (allow match)
    3. Exact registered domain match → True
    4. Same vendor (via DOMAIN_TO_VENDOR) → True
    5. Different domains, no vendor link → False
    """
    # If IdP has no domain, check if the IdP name matches entity's base domain token
    # This handles cases where the IdP record has no domain field but the name aligns
    if not idp_registered_domain:
        if idp_name and entity_registered_domain:
            # Extract base token from entity domain (e.g., "coreio.ai" → "coreio")
            entity_base = entity_registered_domain.split('.')[0].lower()
            
            # Jan 2026 Fix: Apply the same suffix check as cross-TLD matching
            # IdP names with suffixes like "(Legacy)" or "-prod" indicate non-canonical
            # applications, so they should NOT provide governance or activity inheritance
            normalized_idp_name = idp_name.lower()
            for suffix in [' (legacy)', ' (deprecated)', '-legacy', '-prod', '-dev', '-staging',
                           ' legacy', ' deprecated', ' production', '-production']:
                if normalized_idp_name.endswith(suffix):
                    return False
            if '(legacy)' in normalized_idp_name or '(deprecated)' in normalized_idp_name:
                return False
            
            # Now check if IdP name starts with or equals entity base token
            idp_name_normalized = normalized_idp_name.replace('-', '').replace('_', '').replace(' ', '')
            if idp_name_normalized == entity_base or idp_name_normalized.startswith(entity_base):
                return True
        return False

    # If entity has no domain, allow the match
    if not entity_registered_domain:
        return True

    # Exact registered domain match
    if idp_registered_domain == entity_registered_domain:
        return True

    # Jan 2026 Fix: Check if both domains belong to the same vendor
    # This enables multi-TLD vendor governance (teamsuite.cloud inherits from teamsuite.org)
    from .vendor_inference import infer_vendor_from_domain

    idp_vendor_result = infer_vendor_from_domain(idp_registered_domain)
    entity_vendor_result = infer_vendor_from_domain(entity_registered_domain)

    if idp_vendor_result and entity_vendor_result:
        # Both domains have vendor mappings - check if they're the same vendor
        if idp_vendor_result.value.lower() == entity_vendor_result.value.lower():
            return True

    # Jan 2026 Fix: Same base token with different TLD counts as a match, BUT
    # Farm requires the IdP name to be a CLEAN match (no suffixes like "(Legacy)" or "-prod")
    # 
    # Farm's idp_present_direct=True for cases like:
    # - cloudsync.io (entity) vs cloudsync.org (IdP) + name "cloudsync" → MATCH
    # - datacloud.co (entity) vs datacloud.cloud (IdP) + name "datacloud" → MATCH
    # 
    # Farm's idp_present_direct=False for cases like:
    # - fastbox.cloud (entity) vs fastbox.ai (IdP) + name "Fastbox (Legacy)" → NO MATCH
    # - flowbase.dev (entity) vs flowbase.app (IdP) + name "Flowbase-prod" → NO MATCH
    #
    # The difference: "(Legacy)" and "-prod" suffixes indicate the IdP is not the
    # canonical/current application for that brand, so cross-TLD governance doesn't apply.
    
    idp_base = idp_registered_domain.split('.')[0].lower()
    entity_base = entity_registered_domain.split('.')[0].lower()
    
    if idp_base == entity_base:
        # For cross-TLD match, also require IdP name to be a clean match
        # Strip suffixes/modifiers and check if it matches entity base
        if idp_name:
            # Normalize IdP name: remove common suffixes, convert to lowercase
            normalized_idp_name = idp_name.lower()
            # Remove common suffixes that indicate non-canonical IdP
            for suffix in [' (legacy)', ' (deprecated)', '-legacy', '-prod', '-dev', '-staging',
                           ' legacy', ' deprecated', ' production', '-production']:
                if normalized_idp_name.endswith(suffix):
                    # IdP has a suffix indicating it's not canonical - reject cross-TLD match
                    return False
            
            # Also check if IdP name contains the suffix as a substring (e.g., "(Legacy)")
            if '(legacy)' in normalized_idp_name or '(deprecated)' in normalized_idp_name:
                return False
        
        # IdP name is clean, allow cross-TLD match
        return True

    # Different domains with no vendor or base-token link
    return False


def extract_activity_timestamps(
    correlation: CorrelationResult,
    entity: CandidateEntity,
    observations: Optional[list[Observation]] = None,
    idp_activity_map: Optional[dict[str, datetime]] = None,
    propagated_idp: bool = False
) -> ActivityEvidence:
    """
    Extract activity timestamps from correlation evidence and observations.
    
    Jan 2026 Enhancement: Cross-IdP activity aggregation. If the entity's matched IdP
    record has no last_login_at, we look up the IdP name in idp_activity_map to get
    the aggregated max login timestamp from ALL IdP records with the same name.
    
    Jan 2026 Fix: Domain-scoped IdP activity. Only count IdP activity if the IdP
    record's domain matches the entity's primary registered domain. This prevents
    cross-domain IdP inheritance (e.g., easydesk.app IdP activity being counted
    for easydesk.dev entities) which causes false RECENT activity status.
    
    Args:
        correlation: Correlation result with matched records from various planes
        entity: The candidate entity being processed
        observations: Optional list of original observations for this entity
        idp_activity_map: Optional mapping of normalized IdP name -> max last_login_at
        
    Returns:
        ActivityEvidence with timestamps from each plane and computed latest_activity_at
    """
    timestamps: list[datetime] = []
    
    idp_last_login_at: Optional[datetime] = None
    discovery_observed_at: Optional[datetime] = None
    cloud_observed_at: Optional[datetime] = None
    endpoint_last_seen_at: Optional[datetime] = None
    network_last_seen_at: Optional[datetime] = None
    finance_last_transaction_at: Optional[datetime] = None
    idp_governance_aligned: bool = False  # Jan 2026: Track domain-aligned IdP separately from activity
    
    # Get entity's registered domains for IdP domain scoping
    # Jan 2026: For IdP governance, use entity domain + non-IdP plane domains
    # We DON'T include IdP domains here to avoid circular matching
    # Example: linkify.co entity shouldn't get governance from linkify.app IdP
    # But flowapp.app entity with ['flowapp.app', 'flowapp.co'] from discovery DOES get governance from flowapp.co IdP
    entity_registered_domain = extract_registered_domain(entity.domain) if entity.domain else None
    entity_discovery_domains: set[str] = set()
    if entity_registered_domain:
        entity_discovery_domains.add(entity_registered_domain)
    # Include domains from non-IdP plane records (CMDB, Cloud, Finance, Discovery)
    # These represent the entity's actual presence, not just IdP correlation
    for plane_match in [correlation.cmdb, correlation.cloud, correlation.finance]:
        if plane_match and plane_match.matched_records:
            for rec in plane_match.matched_records:
                if rec is None:
                    continue
                rec_domain = getattr(rec, 'domain', None) or getattr(rec, 'app_domain', None)
                if not rec_domain and hasattr(rec, 'raw_data') and isinstance(rec.raw_data, dict):
                    ext_ref = rec.raw_data.get('external_ref') or rec.raw_data.get('url')
                    if ext_ref and isinstance(ext_ref, str):
                        ext_result = extract_domain(ext_ref)
                        if ext_result.registered_domain:
                            rec_domain = ext_result.registered_domain
                if rec_domain:
                    reg = extract_registered_domain(rec_domain)
                    if reg:
                        entity_discovery_domains.add(reg)
    
    # Dec 2025: Also extract timestamps from AMBIGUOUS status (multiple matches still have valid timestamps)
    # Jan 2026 Fix: Also check raw_data for login timestamps with various field names
    # 
    # Jan 2026: REVISED IdP strategy based on Farm behavior analysis:
    # 
    # IdP governance and activity are BOTH inherited from ALL matched IdP records.
    # However, for certain TLD combinations (same base name, different TLD),
    # we need to check if the entity's ORIGINAL domain matches the IdP domain:
    #
    # Case 1: Entity .dev, IdP .app → IdP activity should NOT be inherited (different products)
    # Case 2: Entity .co, IdP .cloud → IdP activity SHOULD be inherited (same vendor family)
    #
    # Key insight from Farm data:
    # - easydesk.dev should be zombie (IdP easydesk.app has recent activity, but cross-TLD)
    # - datacloud.co should NOT be zombie (IdP datacloud.cloud has recent activity, inherited)
    #
    # The pattern: .dev vs .app/.com are treated as different products by Farm.
    # Other TLD combinations like .co/.cloud are treated as the same product.
    
    # Extract IdP activity and governance with TLD-aware domain matching
    # Jan 2026: Use TLD-family matching for BOTH governance and activity
    # - .dev vs non-.dev = different products (no match)
    # - Other TLD combinations = same product family (match)
    if correlation.idp.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
        for record in correlation.idp.matched_records:
            if isinstance(record, IdPObject):
                # Jan 2026 Fix: Check for non-canonical IdP name suffixes
                # IdP names with suffixes like "(Legacy)" or "-prod" indicate non-canonical
                # applications that should NOT provide activity inheritance for cross-domain entities
                is_canonical_idp = True
                if record.name:
                    normalized_idp_name = record.name.lower()
                    for suffix in [' (legacy)', ' (deprecated)', '-legacy', '-prod', '-dev', '-staging',
                                   ' legacy', ' deprecated', ' production', '-production']:
                        if normalized_idp_name.endswith(suffix):
                            is_canonical_idp = False
                            break
                    if '(legacy)' in normalized_idp_name or '(deprecated)' in normalized_idp_name:
                        is_canonical_idp = False
                
                idp_registered_domain = _extract_idp_domain(record)

                # Use TLD-family matching for governance and activity
                domain_aligned = _idp_domain_matches_entity(
                    idp_registered_domain, entity_registered_domain, record.name
                )

                if domain_aligned:
                    # Exact or vendor-family domain match - provide governance and activity
                    idp_governance_aligned = True
                elif record.has_sso or record.has_scim:
                    # SSO/SCIM provides governance for cross-domain matches, BUT:
                    # - Only canonical IdPs (no Legacy/prod suffixes) should provide activity
                    # - Non-canonical IdPs provide governance but NOT activity
                    idp_governance_aligned = True
                    if not is_canonical_idp:
                        # Non-canonical IdP - provides governance but skip activity inheritance
                        continue
                else:
                    # No domain match and no SSO/SCIM - skip entirely
                    continue
                
                login_ts = record.last_login_at
                # Fallback: Check raw_data for login timestamps if main field is empty
                if login_ts is None and record.raw_data and isinstance(record.raw_data, dict):
                    for field in ['last_login_at', 'lastLoginAt', 'lastLogin', 'last_activity', 'lastActivity']:
                        raw_val = record.raw_data.get(field)
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
                
                # Jan 2026: Cross-IdP activity aggregation (only applies within same domain family)
                # Farm considers ALL IdP records with the same vendor name as a single family.
                # If ANY record in the family has recent login activity, ALL assets in
                # that family are considered RECENT.
                # 
                # CRITICAL FIX: Always check the aggregated map for the MAX login timestamp,
                # even if the matched record has its own timestamp. Use whichever is newer.
                # Example: maxflow.ai matches to stale record (Feb 2025), but maxflow.org
                # sibling has recent login (Dec 2025) - we should use the Dec 2025 date.
                # NOTE: This aggregation only applies if domain gating passed above.
                if idp_activity_map and record.name:
                    normalized_name = record.name.lower().strip()
                    aggregated_ts = idp_activity_map.get(normalized_name)
                    if aggregated_ts:
                        # Use the aggregated max if it's newer than the record's own timestamp
                        if login_ts is None or aggregated_ts > login_ts:
                            login_ts = aggregated_ts
                
                if login_ts:
                    if idp_last_login_at is None or login_ts > idp_last_login_at:
                        idp_last_login_at = login_ts
        if idp_last_login_at:
            timestamps.append(idp_last_login_at)
    
    if observations:
        for obs in observations:
            if obs.observed_at and obs.source:
                source_lower = obs.source.lower()
                plane = source_to_plane(source_lower)
                # Only count observations from discovery-corroboration planes
                # Exclude CMDB and finance sources as they aren't "real" discovery
                if plane is not None and plane in DISCOVERY_CORROBORATION_PLANES:
                    if discovery_observed_at is None or obs.observed_at > discovery_observed_at:
                        discovery_observed_at = obs.observed_at
        if discovery_observed_at:
            timestamps.append(discovery_observed_at)
    
    # Dec 2025: Also extract timestamps from AMBIGUOUS status (multiple matches still have valid timestamps)
    if correlation.cloud.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
        for record in correlation.cloud.matched_records:
            if isinstance(record, CloudResource) and record.observed_at:
                if cloud_observed_at is None or record.observed_at > cloud_observed_at:
                    cloud_observed_at = record.observed_at
        if cloud_observed_at:
            timestamps.append(cloud_observed_at)
    
    # Dec 2025: Also extract timestamps from AMBIGUOUS status (multiple matches still have valid timestamps)
    # NOTE: Finance timestamps are stored for metadata but NOT included in latest_activity_at.
    # Per design: "Activity = Network Visibility OR Authentication Success"
    # Finance transactions are billing events, not actual usage/activity evidence.
    if correlation.finance.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
        for record in correlation.finance.matched_records:
            if isinstance(record, Transaction) and record.date:
                if finance_last_transaction_at is None or record.date > finance_last_transaction_at:
                    finance_last_transaction_at = record.date
        # Jan 2026: Do NOT add finance_last_transaction_at to timestamps!
        # Finance is metadata for ongoing_finance flag, NOT activity evidence.
    
    latest_activity_at = max(timestamps) if timestamps else None

    # Jan 2026 Fix: Vendor-propagated IdP governance counts as domain-aligned
    # Vendor family relationships (e.g., googleapis.com inheriting from google.com)
    # are strong governance signals and should be treated as aligned for shadow detection
    if propagated_idp and not idp_governance_aligned:
        idp_governance_aligned = True

    return ActivityEvidence(
        idp_last_login_at=idp_last_login_at,
        discovery_observed_at=discovery_observed_at,
        cloud_observed_at=cloud_observed_at,
        endpoint_last_seen_at=endpoint_last_seen_at,
        network_last_seen_at=network_last_seen_at,
        finance_last_transaction_at=finance_last_transaction_at,
        latest_activity_at=latest_activity_at,
        idp_governance_aligned=idp_governance_aligned
    )


def apply_admission_criteria(
    correlation: CorrelationResult,
    tenant_id: str,
    run_id: str,
    snapshot_id: str,
    observations: Optional[list[Observation]] = None,
    propagated_idp: bool = False,
    propagated_cmdb: bool = False,
    propagation_reason: Optional[str] = None,
    idp_activity_map: Optional[dict[str, datetime]] = None,
    snapshot_timestamp: Optional[datetime] = None
) -> AdmissionResult:
    """
    Apply admission criteria to determine if entity should be admitted as asset.
    
    Admit as asset only if it satisfies at least one hard criterion:
    - Identity plane: IdP match AND (has_sso OR has_scim OR idp_type==service_principal)
    - CMDB plane: CMDB match AND (ci_type in app/service/database/infra) AND (lifecycle in prod/staging)
    - Cloud plane: cloud match AND resource_type indicates real system/resource
    - Finance plane: finance match AND (contract exists OR transaction evidence indicates recurring vendor/product spend)
    - Discovery plane: ≥2 distinct SOURCES AND recent activity ≤90 days (allows shadow IT admission)
    
    NOTE (Dec 2025 fix): Discovery admission gates on distinct SOURCES (browser, proxy, dns = 3),
    NOT distinct planes. Plane diversity is an annotation/confidence signal only.

    VENDOR GOVERNANCE PROPAGATION (Jan 2026 fix):
    Propagated IdP/CMDB from vendor siblings CAN cause admission, matching Farm's policy.
    Example: googleapis.com inherits HAS_IDP from "Google+" IdP record via vendor propagation.

    INVARIANTS:
    - Corporate/marketing root domains are ALWAYS rejected
    - Vendor alone is not admission
    
    Args:
        correlation: Correlation result for the entity
        tenant_id: Tenant ID
        run_id: Run ID
        snapshot_id: Snapshot ID
        observations: Discovery observations for this entity
        propagated_idp: IdP governance propagated from vendor sibling (can cause admission)
        propagated_cmdb: CMDB governance propagated from vendor sibling (can cause admission)
        propagation_reason: Explanation of governance propagation (stored in asset metadata)
        idp_activity_map: Optional mapping of IdP name -> max login timestamp for cross-IdP activity
        
    Returns:
        AdmissionResult indicating whether entity is admitted
    """
    entity = correlation.entity

    # =========================================================================
    # PRE-STEP 0: POST-CORRELATION DOMAIN RECOVERY
    # If entity has no domain, try to recover from correlation match keys
    # This fixes KEY_NORMALIZATION_MISMATCH where name-keyed entities have plane matches
    # =========================================================================
    effective_domain = entity.domain
    recovered_from_correlation = False
    
    if not effective_domain:
        recovered_domain = _extract_domain_from_correlation(correlation, debug_log=True)
        if recovered_domain:
            effective_domain = recovered_domain
            recovered_from_correlation = True
            # Persist recovered domain onto entity for downstream consistency
            entity.domain = effective_domain
    
    # =========================================================================
    # STEP 0: HARD REJECTION (The Filter) - Results in IGNORED status
    # These assets are dropped and do not enter Triage
    # =========================================================================
    
    # GATE 0: Reject invalid TLDs / internal hostnames
    # Must have a valid public suffix (e.g., .com, .io, .org)
    if effective_domain:
        extracted = extract_domain(effective_domain)
        if not extracted.suffix:
            return AdmissionResult(
                admitted=False,
                provisioning_status=ProvisioningStatus.IGNORED,
                rejection_reason=f"Invalid TLD / Internal hostname: {effective_domain}"
            )
    else:
        # No domain at all - reject
        return AdmissionResult(
            admitted=False,
            provisioning_status=ProvisioningStatus.IGNORED,
            rejection_reason="No resolvable domain - requires domain-first identity"
        )
    
    # Compute registered domain (eTLD+1) ONCE for all subsequent gates
    # This ensures mail.google.com -> google.com for gate checks
    registered_domain = extract_registered_domain(effective_domain)
    if not registered_domain:
        return AdmissionResult(
            admitted=False,
            provisioning_status=ProvisioningStatus.IGNORED,
            rejection_reason=f"Cannot extract registered domain from: {effective_domain}"
        )
    
    # GATE 0.5: BANNED_DOMAINS policy - immediately BLOCKED (not QUARANTINE/IGNORED)
    # These domains are policy-forbidden regardless of any governance evidence
    # Results in BLOCKED status - enters triage but is permanently blocked
    if is_banned_domain(registered_domain):
        return AdmissionResult(
            admitted=False,
            provisioning_status=ProvisioningStatus.BLOCKED,
            rejection_reason=f"BANNED_DOMAINS policy: {registered_domain} is policy-forbidden"
        )
    
    # GATE 1: Reject corporate/marketing root domains unconditionally
    # Check against REGISTERED domain, not raw FQDN (fixes mail.google.com -> google.com)
    if is_corporate_root_domain(registered_domain):
        return AdmissionResult(
            admitted=False,
            provisioning_status=ProvisioningStatus.IGNORED,
            rejection_reason=f"Corporate root domain: {registered_domain} (from {effective_domain})"
        )
    
    # Check each admission criterion FIRST (before infrastructure filter)
    idp_admitted, idp_reason = check_idp_admission(correlation, entity_registered_domain=registered_domain)
    cmdb_admitted, cmdb_reason = check_cmdb_admission(correlation)

    # GATE 2: Reject infrastructure/tooling domains ONLY if they lack governance
    # Jan 2026 Fix: Farm admits infrastructure domains (postgresql.org, mongodb.com, etc.)
    # if they have IdP or CMDB governance. Only reject ungoverned infrastructure.
    # Check against REGISTERED domain, not raw FQDN
    if is_infrastructure_domain(registered_domain):
        if not (idp_admitted or cmdb_admitted):
            return AdmissionResult(
                admitted=False,
                provisioning_status=ProvisioningStatus.IGNORED,
                rejection_reason=f"Infrastructure domain without governance: {registered_domain} (from {effective_domain})"
            )
        # Infrastructure domain WITH governance - continue to admission
    cloud_admitted, cloud_reason = check_cloud_admission(correlation)
    finance_admitted, finance_reason = check_finance_admission(correlation)
    discovery_admitted, discovery_reason = check_discovery_admission(
        observations,
        canonical_key=effective_domain or entity.canonical_name if entity else None,
        snapshot_timestamp=snapshot_timestamp
    )

    # =========================================================================
    # FARM ADMISSION POLICY (Jan 2026 Fix) - Now policy-driven
    # =========================================================================
    from aod.core.policy.loader import get_policy_config
    policy_config = get_policy_config()
    
    # Policy toggles
    enable_vendor_propagation = policy_config.admission_gates.enable_vendor_propagation
    allow_finance_only = policy_config.admission_gates.allow_finance_only_admission
    finance_requires_discovery = policy_config.admission_gates.finance_requires_discovery
    require_corroboration = policy_config.admission_gates.require_corroboration
    noise_floor = policy_config.admission_gates.noise_floor
    
    footprint = build_discovery_footprint(
        observations,
        canonical_key=effective_domain or entity.canonical_name if entity else None,
        snapshot_timestamp=snapshot_timestamp
    )
    
    # Discovery admission: controlled by require_corroboration toggle
    # When require_corroboration=True (default): Require 2+ sources for discovery-only admission
    # When require_corroboration=False: Honor noise_floor (can be 1)
    if require_corroboration:
        has_sufficient_discovery = len(footprint.discovery_sources) >= 2
    else:
        has_sufficient_discovery = len(footprint.discovery_sources) >= noise_floor
    
    # Override discovery_admitted based on corroboration policy
    if not require_corroboration and len(footprint.discovery_sources) >= noise_floor:
        discovery_admitted = True

    # Finance admission policy (controlled by multiple toggles)
    #
    # allow_finance_only_admission=True: Finance alone is sufficient
    # finance_requires_discovery=False: Finance doesn't need discovery corroboration
    # (Both can independently relax the finance requirements)
    if allow_finance_only:
        finance_can_admit = finance_admitted
    elif not finance_requires_discovery:
        # Finance can admit with governance OR without discovery
        finance_can_admit = finance_admitted and (
            idp_admitted or cmdb_admitted or cloud_admitted or True  # No discovery required
        )
    else:
        # Default: Finance requires governance OR sufficient discovery
        finance_can_admit = finance_admitted and (
            idp_admitted or
            cmdb_admitted or
            cloud_admitted or
            discovery_admitted
        )

    # Vendor propagation: controlled by enable_vendor_propagation toggle
    # When enabled (default): vendor-propagated IdP/CMDB counts for admission
    # When disabled: only direct matches count
    if enable_vendor_propagation:
        idp_can_admit = idp_admitted or propagated_idp
        cmdb_can_admit = cmdb_admitted or propagated_cmdb
    else:
        idp_can_admit = idp_admitted
        cmdb_can_admit = cmdb_admitted

    # Admission: IdP OR CMDB OR Cloud OR Discovery (≥2) OR Finance (with corroboration)
    if not any([idp_can_admit, cmdb_can_admit, cloud_admitted, finance_can_admit, discovery_admitted]):
        return AdmissionResult(
            admitted=False,
            provisioning_status=ProvisioningStatus.IGNORED,
            rejection_reason="No admission criteria satisfied"
        )
    
    # =========================================================================
    # TRAFFIC LIGHT LOGIC - Determine provisioning_status
    # Strict precedence order: GREEN (ACTIVE) > AMBER (REVIEW) > RED (QUARANTINE)
    # =========================================================================
    
    # STEP 1: GREEN LANE (Trusted) - IdP OR CMDB (with discovery corroboration) = ACTIVE
    # These flow to DCL automatically
    has_governance = idp_can_admit or cmdb_can_admit
    
    # STEP 2: AMBER LANE (Review) - CMDB + Stale Activity = REVIEW
    # Check if activity is stale (zombie indicator) using policy-driven stale_window_days
    stale_window_days = policy_config.admission_gates.stale_window_days
    is_stale_activity = False
    if observations:
        from datetime import timedelta, timezone
        latest_activity = None
        for obs in observations:
            if obs.observed_at:
                if latest_activity is None or obs.observed_at > latest_activity:
                    latest_activity = obs.observed_at
        if latest_activity:
            cutoff = datetime.now(timezone.utc) - timedelta(days=stale_window_days)
            if latest_activity.tzinfo is None:
                latest_activity = latest_activity.replace(tzinfo=timezone.utc)
            is_stale_activity = latest_activity < cutoff
    
    # Determine provisioning status based on Traffic Light rules
    # Jan 2026 Fix: Farm catalogs discovery-only assets (>= 2 sources), not shadow
    # Only stale CMDB-only assets go to REVIEW (zombie candidates)
    if has_governance:
        if cmdb_can_admit and is_stale_activity and not idp_can_admit:
            # STEP 2: AMBER - CMDB but stale activity (zombie candidate)
            provisioning_status = ProvisioningStatus.REVIEW
        else:
            # STEP 1: GREEN - Has IdP or active CMDB
            provisioning_status = ProvisioningStatus.ACTIVE
    elif discovery_admitted:
        # STEP 1: GREEN - Discovery-only with >= 2 sources + recent activity
        # Farm catalogs these as active assets, not shadow IT
        provisioning_status = ProvisioningStatus.ACTIVE
    elif finance_can_admit:
        # STEP 2: AMBER - Finance with governance/discovery corroboration
        # Finance-admitted assets go to REVIEW for validation
        provisioning_status = ProvisioningStatus.REVIEW
    else:
        # STEP 3: RED - Cloud/Finance only (insufficient evidence)
        # These need governance or discovery corroboration
        provisioning_status = ProvisioningStatus.QUARANTINE
    
    admission_reasons = []
    if idp_admitted:
        admission_reasons.append(idp_reason)
    if cmdb_admitted:
        admission_reasons.append(cmdb_reason)
    if cloud_admitted:
        admission_reasons.append(cloud_reason)
    if finance_admitted:
        admission_reasons.append(finance_reason)
    if discovery_admitted:
        admission_reasons.append(discovery_reason)
    # Jan 2026 Fix: Add vendor propagation reason if that's what caused admission
    if propagation_reason and (propagated_idp or propagated_cmdb):
        admission_reasons.append(f"Vendor governance: {propagation_reason}")

    # Jan 2026 Fix: Include propagated governance in lens_status for classification
    # When vendor governance is propagated, set lens_status to MATCHED so classification
    # logic recognizes the asset as governed (not shadow IT).
    idp_status = correlation.idp.status.value
    if propagated_idp and correlation.idp.status == MatchStatus.UNMATCHED:
        idp_status = MatchStatus.MATCHED.value

    cmdb_status = correlation.cmdb.status.value
    if propagated_cmdb and correlation.cmdb.status == MatchStatus.UNMATCHED:
        cmdb_status = MatchStatus.MATCHED.value

    lens_status = LensStatuses(
        idp=LensStatus(idp_status),
        cmdb=LensStatus(cmdb_status),
        cloud=LensStatus(correlation.cloud.status.value),
        finance=LensStatus(correlation.finance.status.value)
    )
    
    # Single source of truth: discovery_sources from footprint
    # lens_coverage.discovery is DERIVED from discovery_sources (not independent)
    discovery_sources_list = sorted(footprint.discovery_sources)

    # Jan 2026 Fix: Include propagated governance in lens_coverage
    # lens_coverage indicates whether asset has governance "coverage" (direct or propagated)
    lens_coverage = LensCoverage(
        idp=idp_admitted or propagated_idp,
        cmdb=cmdb_admitted or propagated_cmdb,
        cloud=cloud_admitted,
        finance=finance_admitted,
        discovery=bool(discovery_sources_list)  # Derived from discovery_sources
    )
    
    # Jan 2026 Fix for KEY_NORMALIZATION_MISMATCH:
    # Include ALL domains from correlated plane records (IdP, CMDB, etc.)
    # This allows reconciliation to match against ANY domain variant.
    # 
    # CRITICAL: Discovery domain MUST be first (index 0) - it is the Primary Key.
    # Governance domains (from IdP/CMDB) are aliases that enable correlation,
    # but must NOT hijack the asset's identity.
    # 
    # Priority hierarchy:
    # 1. effective_domain (Discovery) - "Observed Reality", anchor for Activity
    # 2. plane_domains (Governance) - "Bureaucratic Records", anchors for Status
    domain_list = []
    seen_domains = set()
    
    # Discovery domain is PRIMARY - must be first
    if effective_domain:
        normalized = effective_domain.lower().strip()
        domain_list.append(normalized)
        seen_domains.add(normalized)
    
    # Add governance domains as secondary aliases (preserving correlation without breaking identity)
    plane_domains = _extract_all_domains_from_correlation(correlation)
    for pd in plane_domains:
        if pd not in seen_domains:
            domain_list.append(pd)
            seen_domains.add(pd)
    
    identifiers = AssetIdentifiers(
        domains=domain_list,
        hostnames=[entity.hostname] if entity.hostname else [],
        uris=[entity.uri] if entity.uri else []
    )
    
    tags = []
    if idp_admitted:
        tags.append("identity_managed")
    if cmdb_admitted:
        tags.append("cmdb_registered")
    if cloud_admitted:
        tags.append("cloud_hosted")
    if finance_admitted:
        tags.append("finance_tracked")
    if discovery_admitted:
        tags.append("discovery_only")
    
    activity_evidence = extract_activity_timestamps(correlation, entity, observations, idp_activity_map, propagated_idp)
    
    from ..models.output_contracts import VendorHypothesis
    vendor_hypothesis = None
    if entity.vendor_hypothesis:
        vendor_hypothesis = VendorHypothesis(
            value=entity.vendor_hypothesis.value,
            confidence=entity.vendor_hypothesis.confidence,
            basis=entity.vendor_hypothesis.basis
        )
    
    canonical_domain = registered_domain
    
    # PRIMARY KEY FREEZE: The key was chosen in normalize_observations - never change it
    asset_key = canonical_domain
    
    import os
    if os.environ.get("AOD_DEBUG_KEYS"):
        logger.info("admission.primary_key_freeze", extra={
            "entity_domain": entity.domain,
            "registered_domain": registered_domain,
            "asset_key": asset_key,
            "from_correlation_recovery": recovered_from_correlation
        })
    
    display_name = entity.original_name
    
    # Add traffic light status tag
    tags.append(f"traffic_light:{provisioning_status.value}")
    
    asset = Asset(
        asset_id=deterministic_uuid(snapshot_id, run_id, "asset", asset_key),
        tenant_id=tenant_id,
        run_id=run_id,
        name=display_name,
        asset_type=determine_asset_type(correlation, entity),
        identifiers=identifiers,
        vendor=entity.vendor,
        vendor_hypothesis=vendor_hypothesis,
        environment=determine_environment(correlation),
        evidence_refs=correlation.all_evidence_refs(),
        lens_status=lens_status,
        lens_coverage=lens_coverage,
        lens_match_debug=build_lens_match_debug(correlation),
        activity_evidence=activity_evidence,
        tags=tags,
        admission_reason="; ".join(admission_reasons),
        provisioning_status=provisioning_status,
        discovery_sources=discovery_sources_list  # Single source of truth
    )
    
    # =========================================================================
    # RUNTIME INVARIANTS: Fail fast if discovery evidence diverges
    # These ensure discovery_sources remains the single source of truth
    # =========================================================================
    _validate_discovery_invariants(asset, discovery_sources_list, asset_key)

    return AdmissionResult(
        admitted=True,
        provisioning_status=provisioning_status,
        asset=asset,
        admission_reason="; ".join(admission_reasons)
    )
