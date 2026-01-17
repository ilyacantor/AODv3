"""Asset classification utilities - determine asset type and environment."""

from typing import Optional

from ..correlate_entities import CorrelationResult, MatchStatus
from ..normalize_observations import CandidateEntity
from ..vendor_inference import DOMAIN_TO_VENDOR
from ...models.input_contracts import CloudResource, CMDBConfigItem
from ...models.output_contracts import AssetType, Environment
from .constants import KNOWN_DATABASE_DOMAINS, KNOWN_DATABASE_NAMES


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
    """Determine environment from correlation evidence."""
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
