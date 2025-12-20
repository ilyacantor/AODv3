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
from .vendor_inference import DOMAIN_TO_VENDOR


VALID_CI_TYPES = {"app", "application", "service", "database", "infra", "infrastructure", "server", "system"}
VALID_LIFECYCLES = {"prod", "production", "staging", "stage", "live", "active"}
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
    - IdP match AND (has_sso OR has_scim OR idp_type==service_principal)
    NOTE: Both MATCHED and AMBIGUOUS count as having IdP evidence.
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
    
    return False, ""


def check_cmdb_admission(correlation: CorrelationResult) -> tuple[bool, str]:
    """
    Check CMDB plane admission criteria:
    - CMDB match AND (ci_type in app/service/database/infra) AND (lifecycle in prod/staging)
    NOTE: Both MATCHED and AMBIGUOUS count as having CMDB evidence.
    """
    if correlation.cmdb.status not in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
        return False, ""
    
    for record in correlation.cmdb.matched_records:
        if isinstance(record, CMDBConfigItem):
            ci_type_valid = record.ci_type.lower() in VALID_CI_TYPES
            lifecycle_valid = record.lifecycle.lower() in VALID_LIFECYCLES
            
            if ci_type_valid and lifecycle_valid:
                return True, f"CMDB match: {record.ci_type} in {record.lifecycle}"
    
    return False, ""


def check_cloud_admission(correlation: CorrelationResult) -> tuple[bool, str]:
    """
    Check Cloud plane admission criteria:
    - Cloud match AND resource_type indicates real system/resource
    NOTE: Both MATCHED and AMBIGUOUS count as having Cloud evidence.
    """
    if correlation.cloud.status not in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
        return False, ""
    
    for record in correlation.cloud.matched_records:
        if isinstance(record, CloudResource):
            resource_type = record.resource_type.lower()
            for valid_type in VALID_CLOUD_RESOURCE_TYPES:
                if valid_type in resource_type:
                    return True, f"Cloud match: {record.resource_type}"
    
    return False, ""


def check_finance_admission(correlation: CorrelationResult) -> tuple[bool, str]:
    """
    Check Finance plane admission criteria:
    - Finance match AND recurring spend (contract or transaction)
    
    POLICY: One-time purchases and expense reimbursements are not actionable.
    Only recurring spend qualifies for finance-based admission.
    
    IMPORTANT: Vendor alone is not admission.
    NOTE: Both MATCHED and AMBIGUOUS count as having finance evidence.
    """
    if correlation.finance.status not in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
        return False, ""
    
    for record in correlation.finance.matched_records:
        if isinstance(record, Contract):
            if record.is_recurring and record.amount > 0:
                return True, f"Finance match: Recurring contract ${record.amount}"
        elif isinstance(record, Transaction):
            if record.is_recurring and record.amount > 0:
                return True, f"Finance match: Recurring transaction ${record.amount}"
    
    return False, ""


DISCOVERY_ACTIVITY_WINDOW_DAYS = 90


def check_discovery_admission(
    observations: Optional[list[Observation]],
    min_sources: int = 2
) -> tuple[bool, str]:
    """
    Check discovery-only admission criteria.
    
    Admit discovery-only candidates when usage is corroborated and recent:
    - Evidence from ≥2 distinct discovery sources
    - Recent activity ≤ 90 days
    
    This allows shadow IT to be admitted before finance/cloud evidence appears,
    since usage signals typically precede contracts or infrastructure.
    """
    if not observations:
        return False, ""
    
    from datetime import datetime, timedelta, timezone
    
    sources = set()
    latest_activity: Optional[datetime] = None
    
    for obs in observations:
        if obs.source:
            sources.add(obs.source.lower())
        if obs.observed_at:
            if latest_activity is None or obs.observed_at > latest_activity:
                latest_activity = obs.observed_at
    
    if len(sources) < min_sources:
        return False, ""
    
    if latest_activity is None:
        return False, ""
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=DISCOVERY_ACTIVITY_WINDOW_DAYS)
    if latest_activity.tzinfo is None:
        latest_activity = latest_activity.replace(tzinfo=timezone.utc)
    
    if latest_activity < cutoff:
        return False, ""
    
    return True, f"Discovery: {len(sources)} sources ({', '.join(sorted(sources))}), last activity {latest_activity.date()}"


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
    - Propagated governance: IdP/CMDB presence propagated from vendor sibling
    
    IMPORTANT: Vendor alone is not admission.
    
    Args:
        correlation: Correlation result for the entity
        tenant_id: Tenant ID
        run_id: Run ID
        snapshot_id: Snapshot ID
        observations: Discovery observations for this entity
        propagated_idp: IdP governance propagated from vendor sibling
        propagated_cmdb: CMDB governance propagated from vendor sibling
        propagation_reason: Explanation of governance propagation
        
    Returns:
        AdmissionResult indicating whether entity is admitted
    """
    entity = correlation.entity
    
    idp_admitted, idp_reason = check_idp_admission(correlation)
    cmdb_admitted, cmdb_reason = check_cmdb_admission(correlation)
    cloud_admitted, cloud_reason = check_cloud_admission(correlation)
    finance_admitted, finance_reason = check_finance_admission(correlation)
    discovery_admitted, discovery_reason = check_discovery_admission(observations)
    
    governance_admitted = False
    governance_reason = ""
    if propagated_idp or propagated_cmdb:
        governance_admitted = True
        governance_reason = f"Propagated governance: {propagation_reason}"
    
    if not any([idp_admitted, cmdb_admitted, cloud_admitted, finance_admitted, discovery_admitted, governance_admitted]):
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
    if governance_admitted:
        admission_reasons.append(governance_reason)
    
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
    if governance_admitted:
        tags.append("vendor_governed")
    
    activity_evidence = extract_activity_timestamps(correlation, entity, observations)
    
    from ..models.output_contracts import VendorHypothesis
    vendor_hypothesis = None
    if entity.vendor_hypothesis:
        vendor_hypothesis = VendorHypothesis(
            value=entity.vendor_hypothesis.value,
            confidence=entity.vendor_hypothesis.confidence,
            basis=entity.vendor_hypothesis.basis
        )
    
    asset = Asset(
        asset_id=deterministic_uuid(snapshot_id, run_id, "asset", entity.original_name),
        tenant_id=tenant_id,
        run_id=run_id,
        name=entity.original_name,
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
