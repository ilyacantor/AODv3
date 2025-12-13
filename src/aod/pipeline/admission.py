"""Stage 5: Admission (AAC) - Apply admission criteria to determine assets"""

from dataclasses import dataclass
from typing import Optional
from uuid import uuid4

from ..models.output_contracts import (
    Asset, AssetType, Environment, LensStatus, LensStatuses, LensCoverage, AssetIdentifiers
)
from ..models.input_contracts import IdPObject, CMDBConfigItem, CloudResource, Contract, Transaction
from .correlate_entities import CorrelationResult, MatchStatus


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
    """
    if correlation.idp.status != MatchStatus.MATCHED:
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
    """
    if correlation.cmdb.status != MatchStatus.MATCHED:
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
    """
    if correlation.cloud.status != MatchStatus.MATCHED:
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
    - Finance match AND (contract exists OR transaction evidence indicates recurring vendor/product spend)
    
    IMPORTANT: Vendor alone is not admission.
    """
    if correlation.finance.status != MatchStatus.MATCHED:
        return False, ""
    
    has_contract = False
    has_recurring_transaction = False
    
    for record in correlation.finance.matched_records:
        if isinstance(record, Contract):
            if record.amount > 0:
                has_contract = True
                return True, f"Finance match: Contract for ${record.amount}"
        elif isinstance(record, Transaction):
            if record.is_recurring and record.amount > 0:
                has_recurring_transaction = True
                return True, f"Finance match: Recurring transaction ${record.amount}"
    
    return False, ""


def determine_asset_type(correlation: CorrelationResult) -> AssetType:
    """Determine asset type from correlation evidence"""
    if correlation.cloud.status == MatchStatus.MATCHED:
        for record in correlation.cloud.matched_records:
            if isinstance(record, CloudResource):
                rt = record.resource_type.lower()
                if "database" in rt or "rds" in rt or "dynamodb" in rt:
                    return AssetType.DATABASE
                if "lambda" in rt or "function" in rt:
                    return AssetType.SERVICE
                return AssetType.CLOUD_RESOURCE
    
    if correlation.cmdb.status == MatchStatus.MATCHED:
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
    
    if correlation.idp.status == MatchStatus.MATCHED:
        return AssetType.SAAS
    
    if correlation.finance.status == MatchStatus.MATCHED:
        return AssetType.SAAS
    
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


def apply_admission_criteria(
    correlation: CorrelationResult,
    tenant_id: str,
    run_id: str
) -> AdmissionResult:
    """
    Apply admission criteria to determine if entity should be admitted as asset.
    
    Admit as asset only if it satisfies at least one hard criterion:
    - Identity plane: IdP match AND (has_sso OR has_scim OR idp_type==service_principal)
    - CMDB plane: CMDB match AND (ci_type in app/service/database/infra) AND (lifecycle in prod/staging)
    - Cloud plane: cloud match AND resource_type indicates real system/resource
    - Finance plane: finance match AND (contract exists OR transaction evidence indicates recurring vendor/product spend)
    
    IMPORTANT: Vendor alone is not admission.
    
    Args:
        correlation: Correlation result for the entity
        tenant_id: Tenant ID
        run_id: Run ID
        
    Returns:
        AdmissionResult indicating whether entity is admitted
    """
    entity = correlation.entity
    
    idp_admitted, idp_reason = check_idp_admission(correlation)
    cmdb_admitted, cmdb_reason = check_cmdb_admission(correlation)
    cloud_admitted, cloud_reason = check_cloud_admission(correlation)
    finance_admitted, finance_reason = check_finance_admission(correlation)
    
    if not any([idp_admitted, cmdb_admitted, cloud_admitted, finance_admitted]):
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
        finance=finance_admitted
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
    
    asset = Asset(
        asset_id=uuid4(),
        tenant_id=tenant_id,
        run_id=run_id,
        name=entity.original_name,
        asset_type=determine_asset_type(correlation),
        identifiers=identifiers,
        vendor=entity.vendor,
        environment=determine_environment(correlation),
        evidence_refs=correlation.all_evidence_refs(),
        lens_status=lens_status,
        lens_coverage=lens_coverage,
        tags=tags,
        admission_reason="; ".join(admission_reasons)
    )
    
    return AdmissionResult(
        admitted=True,
        asset=asset,
        admission_reason="; ".join(admission_reasons)
    )
