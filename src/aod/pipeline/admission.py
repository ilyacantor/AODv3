"""Stage 5: Admission (AAC) - Apply admission criteria to determine assets"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ..models.output_contracts import (
    Asset, AssetType, Environment, LensStatus, LensStatuses, LensCoverage, AssetIdentifiers,
    ActivityEvidence
)
from ..models.input_contracts import IdPObject, CMDBConfigItem, CloudResource, Contract, Transaction, Observation
from .correlate_entities import CorrelationResult, MatchStatus
from .deterministic_ids import deterministic_uuid
from .normalize_observations import CandidateEntity
from .vendor_inference import DOMAIN_TO_VENDOR, extract_registered_domain
import tldextract


VALID_CI_TYPES = {"app", "application", "service", "database", "infra", "infrastructure", "server", "system"}
VALID_LIFECYCLES = {"prod", "production", "staging", "stage", "live", "active"}

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


from ..constants import INFRASTRUCTURE_DOMAINS


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
    """Result of admission evaluation"""
    admitted: bool
    asset: Optional[Asset] = None
    rejection_reason: Optional[str] = None
    admission_reason: Optional[str] = None


def check_idp_admission(correlation: CorrelationResult) -> tuple[bool, str]:
    """
    Check IdP plane admission criteria:
    - IdP match (any IdP object is sufficient for admission)
    - Prefer: has_sso OR has_scim OR idp_type==service_principal (stronger signal)
    NOTE: Both MATCHED and AMBIGUOUS count as having IdP evidence.
    
    RELAXED: Any IdP match counts. SSO/SCIM provides stronger confidence but is not required.
    """
    if correlation.idp.status not in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
        return False, ""
    
    for record in correlation.idp.matched_records:
        if isinstance(record, IdPObject):
            if record.has_sso:
                return True, "IdP match with SSO enabled"
            if record.has_scim:
                return True, "IdP match with SCIM enabled"
            if record.idp_type == "service_principal":
                return True, "IdP match as service principal"
    
    if correlation.idp.matched_records:
        return True, "IdP match (directory object)"
    
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


def check_finance_admission(correlation: CorrelationResult) -> tuple[bool, str]:
    """
    Check Finance plane admission criteria:
    - Finance match with any spend evidence
    - Prefer: recurring contracts/transactions (stronger signal)
    
    RELAXED: Any finance match with amount > 0 counts for admission.
    Recurring spend provides stronger confidence but is not required.
    
    NOTE: Both MATCHED and AMBIGUOUS count as having finance evidence.
    """
    if correlation.finance.status not in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
        return False, ""
    
    for record in correlation.finance.matched_records:
        if isinstance(record, Contract):
            if record.is_recurring and record.amount > 0:
                return True, f"Finance match: Recurring contract ${record.amount}"
            elif record.amount > 0:
                return True, f"Finance match: Contract ${record.amount}"
        elif isinstance(record, Transaction):
            if record.is_recurring and record.amount > 0:
                return True, f"Finance match: Recurring transaction ${record.amount}"
            elif record.amount > 0:
                return True, f"Finance match: Transaction ${record.amount}"
    
    if correlation.finance.matched_records:
        return True, "Finance match (spend evidence)"
    
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
    "edr": "endpoint",
    "mdm": "endpoint",
    "av": "endpoint",
    "agent": "endpoint",
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

def check_discovery_admission(
    observations: Optional[list[Observation]],
    min_planes: int = 2
) -> tuple[bool, str]:
    """
    Check discovery-only admission criteria.
    
    Admit discovery-only candidates when usage is corroborated and recent:
    - Evidence from ≥2 distinct DISCOVERY CORROBORATION PLANES (not all planes!)
    - Recent activity ≤ 90 days
    
    CRITICAL: 
    - Count distinct planes, not distinct sources (dns + proxy = 1 network plane)
    - Only count discovery-corroborating planes: network, endpoint, idp, cloud, discovery
    - Finance and CMDB do NOT count as discovery corroboration (they are governance evidence)
    """
    if not observations:
        return False, ""
    
    from datetime import datetime, timedelta, timezone
    
    planes = set()
    latest_activity: Optional[datetime] = None
    
    for obs in observations:
        if obs.source:
            plane = source_to_plane(obs.source)
            if plane is not None and plane in DISCOVERY_CORROBORATION_PLANES:
                planes.add(plane)
        if obs.observed_at:
            if latest_activity is None or obs.observed_at > latest_activity:
                latest_activity = obs.observed_at
    
    if len(planes) < min_planes:
        return False, ""
    
    if latest_activity is None:
        return False, ""
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=DISCOVERY_ACTIVITY_WINDOW_DAYS)
    if latest_activity.tzinfo is None:
        latest_activity = latest_activity.replace(tzinfo=timezone.utc)
    
    if latest_activity < cutoff:
        return False, ""
    
    return True, f"Discovery: {len(planes)} corroborating planes ({', '.join(sorted(planes))}), last activity {latest_activity.date()}"


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


def extract_activity_timestamps(
    correlation: CorrelationResult,
    entity: CandidateEntity,
    observations: Optional[list[Observation]] = None
) -> ActivityEvidence:
    """
    Extract activity timestamps from correlation evidence and observations.
    
    Args:
        correlation: Correlation result with matched records from various planes
        entity: The candidate entity being processed
        observations: Optional list of original observations for this entity
        
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
    
    if correlation.idp.status == MatchStatus.MATCHED:
        for record in correlation.idp.matched_records:
            if isinstance(record, IdPObject) and record.last_login_at:
                if idp_last_login_at is None or record.last_login_at > idp_last_login_at:
                    idp_last_login_at = record.last_login_at
        if idp_last_login_at:
            timestamps.append(idp_last_login_at)
    
    if observations:
        for obs in observations:
            if obs.observed_at:
                if discovery_observed_at is None or obs.observed_at > discovery_observed_at:
                    discovery_observed_at = obs.observed_at
        if discovery_observed_at:
            timestamps.append(discovery_observed_at)
    
    if correlation.cloud.status == MatchStatus.MATCHED:
        for record in correlation.cloud.matched_records:
            if isinstance(record, CloudResource) and record.observed_at:
                if cloud_observed_at is None or record.observed_at > cloud_observed_at:
                    cloud_observed_at = record.observed_at
        if cloud_observed_at:
            timestamps.append(cloud_observed_at)
    
    if correlation.finance.status == MatchStatus.MATCHED:
        for record in correlation.finance.matched_records:
            if isinstance(record, Transaction) and record.date:
                if finance_last_transaction_at is None or record.date > finance_last_transaction_at:
                    finance_last_transaction_at = record.date
        if finance_last_transaction_at:
            timestamps.append(finance_last_transaction_at)
    
    latest_activity_at = max(timestamps) if timestamps else None
    
    return ActivityEvidence(
        idp_last_login_at=idp_last_login_at,
        discovery_observed_at=discovery_observed_at,
        cloud_observed_at=cloud_observed_at,
        endpoint_last_seen_at=endpoint_last_seen_at,
        network_last_seen_at=network_last_seen_at,
        finance_last_transaction_at=finance_last_transaction_at,
        latest_activity_at=latest_activity_at
    )


def apply_admission_criteria(
    correlation: CorrelationResult,
    tenant_id: str,
    run_id: str,
    snapshot_id: str,
    observations: Optional[list[Observation]] = None,
    propagated_idp: bool = False,
    propagated_cmdb: bool = False,
    propagation_reason: Optional[str] = None
) -> AdmissionResult:
    """
    Apply admission criteria to determine if entity should be admitted as asset.
    
    Admit as asset only if it satisfies at least one hard criterion:
    - Identity plane: IdP match AND (has_sso OR has_scim OR idp_type==service_principal)
    - CMDB plane: CMDB match AND (ci_type in app/service/database/infra) AND (lifecycle in prod/staging)
    - Cloud plane: cloud match AND resource_type indicates real system/resource
    - Finance plane: finance match AND (contract exists OR transaction evidence indicates recurring vendor/product spend)
    - Discovery plane: ≥2 distinct sources AND recent activity ≤90 days (allows shadow IT admission)
    
    INVARIANTS:
    - Vendor governance NEVER causes admission (only explains/classifies)
    - Corporate/marketing root domains are ALWAYS rejected
    - Vendor alone is not admission
    
    Args:
        correlation: Correlation result for the entity
        tenant_id: Tenant ID
        run_id: Run ID
        snapshot_id: Snapshot ID
        observations: Discovery observations for this entity
        propagated_idp: IdP governance propagated from vendor sibling (for classification only)
        propagated_cmdb: CMDB governance propagated from vendor sibling (for classification only)
        propagation_reason: Explanation of governance propagation (for metadata only)
        
    Returns:
        AdmissionResult indicating whether entity is admitted
    """
    entity = correlation.entity
    
    # GATE 0: Reject invalid TLDs / internal hostnames
    # Must have a valid public suffix (e.g., .com, .io, .org)
    if entity.domain:
        extracted = tldextract.extract(entity.domain)
        if not extracted.suffix:
            return AdmissionResult(
                admitted=False,
                rejection_reason=f"Invalid TLD / Internal hostname: {entity.domain}"
            )
    else:
        # No domain at all - reject
        return AdmissionResult(
            admitted=False,
            rejection_reason="No resolvable domain - requires domain-first identity"
        )
    
    # Compute registered domain (eTLD+1) ONCE for all subsequent gates
    # This ensures mail.google.com -> google.com for gate checks
    registered_domain = extract_registered_domain(entity.domain)
    if not registered_domain:
        return AdmissionResult(
            admitted=False,
            rejection_reason=f"Cannot extract registered domain from: {entity.domain}"
        )
    
    # GATE 1: Reject corporate/marketing root domains unconditionally
    # Check against REGISTERED domain, not raw FQDN (fixes mail.google.com -> google.com)
    if is_corporate_root_domain(registered_domain):
        return AdmissionResult(
            admitted=False,
            rejection_reason=f"Corporate root domain: {registered_domain} (from {entity.domain})"
        )
    
    # GATE 2: Reject infrastructure/tooling domains unconditionally
    # Check against REGISTERED domain, not raw FQDN
    if is_infrastructure_domain(registered_domain):
        return AdmissionResult(
            admitted=False,
            rejection_reason=f"Infrastructure domain: {registered_domain} (from {entity.domain})"
        )
    
    # Check each admission criterion
    idp_admitted, idp_reason = check_idp_admission(correlation)
    cmdb_admitted, cmdb_reason = check_cmdb_admission(correlation)
    cloud_admitted, cloud_reason = check_cloud_admission(correlation)
    finance_admitted, finance_reason = check_finance_admission(correlation)
    discovery_admitted, discovery_reason = check_discovery_admission(observations)
    
    # NOTE: Vendor governance propagation does NOT cause admission
    # It is recorded as metadata for classification/explanation only
    
    # Admission: ANY plane can admit (IdP, CMDB, Cloud, Finance, or Discovery)
    # Discovery-only admission is CRITICAL for Shadow IT detection
    if not any([idp_admitted, cmdb_admitted, cloud_admitted, finance_admitted, discovery_admitted]):
        return AdmissionResult(
            admitted=False,
            rejection_reason="No admission criteria satisfied"
        )
    
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
    
    lens_status = LensStatuses(
        idp=LensStatus(correlation.idp.status.value),
        cmdb=LensStatus(correlation.cmdb.status.value),
        cloud=LensStatus(correlation.cloud.status.value),
        finance=LensStatus(correlation.finance.status.value)
    )
    
    lens_coverage = LensCoverage(
        idp=idp_admitted,
        cmdb=cmdb_admitted,
        cloud=cloud_admitted,
        finance=finance_admitted,
        discovery=discovery_admitted
    )
    
    identifiers = AssetIdentifiers(
        domains=[entity.domain] if entity.domain else [],
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
    
    activity_evidence = extract_activity_timestamps(correlation, entity, observations)
    
    from ..models.output_contracts import VendorHypothesis
    vendor_hypothesis = None
    if entity.vendor_hypothesis:
        vendor_hypothesis = VendorHypothesis(
            value=entity.vendor_hypothesis.value,
            confidence=entity.vendor_hypothesis.confidence,
            basis=entity.vendor_hypothesis.basis
        )
    
    canonical_domain = extract_registered_domain(entity.domain) if entity.domain else None
    
    if not canonical_domain:
        return AdmissionResult(
            admitted=False,
            rejection_reason="No resolvable domain - requires domain-first identity"
        )
    
    asset_key = canonical_domain
    display_name = entity.original_name
    
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
        activity_evidence=activity_evidence,
        tags=tags,
        admission_reason="; ".join(admission_reasons)
    )
    
    return AdmissionResult(
        admitted=True,
        asset=asset,
        admission_reason="; ".join(admission_reasons)
    )
