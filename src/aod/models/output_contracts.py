"""Pydantic v2 models for AOD output contracts"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class AssetType(str, Enum):
    """Asset type enumeration"""
    SAAS = "saas"
    SERVICE = "service"
    DATABASE = "database"
    INFRA = "infra"
    CLOUD_RESOURCE = "cloud_resource"
    UNKNOWN = "unknown"


class Environment(str, Enum):
    """Environment enumeration"""
    PROD = "prod"
    STAGING = "staging"
    DEV = "dev"
    UNKNOWN = "unknown"


class LensStatus(str, Enum):
    """Lens correlation status"""
    MATCHED = "matched"
    AMBIGUOUS = "ambiguous"
    UNMATCHED = "unmatched"


class LensStatuses(BaseModel):
    """Lens statuses for all planes"""
    idp: LensStatus = LensStatus.UNMATCHED
    cmdb: LensStatus = LensStatus.UNMATCHED
    cloud: LensStatus = LensStatus.UNMATCHED
    finance: LensStatus = LensStatus.UNMATCHED


class LensCoverage(BaseModel):
    """Lens coverage booleans (true only if matched AND evidence content supports)"""
    idp: bool = False
    cmdb: bool = False
    cloud: bool = False
    finance: bool = False


class AssetIdentifiers(BaseModel):
    """Asset identifiers"""
    domains: list[str] = Field(default_factory=list)
    hostnames: list[str] = Field(default_factory=list)
    uris: list[str] = Field(default_factory=list)


class Asset(BaseModel):
    """Asset in the catalog - systems only"""
    asset_id: UUID
    tenant_id: str
    run_id: str
    name: str
    asset_type: AssetType = AssetType.UNKNOWN
    identifiers: AssetIdentifiers = Field(default_factory=AssetIdentifiers)
    vendor: Optional[str] = None
    environment: Environment = Environment.UNKNOWN
    evidence_refs: list[str] = Field(default_factory=list)
    lens_status: LensStatuses = Field(default_factory=LensStatuses)
    lens_coverage: LensCoverage = Field(default_factory=LensCoverage)
    tags: list[str] = Field(default_factory=list)
    admission_reason: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ArtifactType(str, Enum):
    """Artifact type enumeration"""
    DASHBOARD = "dashboard"
    REPORT = "report"
    CALCULATOR = "calculator"
    WORKSHEET = "worksheet"
    VIEW = "view"
    SAVED_QUERY = "saved_query"
    FILE = "file"
    OTHER = "other"


class Artifact(BaseModel):
    """Artifact - non-system objects like dashboards, reports, etc."""
    artifact_id: UUID
    tenant_id: str
    run_id: str
    parent_asset_id: Optional[UUID] = None
    name: str
    artifact_type: ArtifactType
    source: str
    evidence_ref: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FindingType(str, Enum):
    """Finding type enumeration"""
    GOVERNANCE_GAP = "governance_gap"
    IDENTITY_GAP = "identity_gap"
    CMDB_GAP = "cmdb_gap"
    FINANCE_GAP = "finance_gap"
    DATA_CONFLICT = "data_conflict"
    DUPLICATION_RISK = "duplication_risk"


class Severity(str, Enum):
    """Severity enumeration"""
    LOW = "low"
    MED = "med"
    HIGH = "high"


class Finding(BaseModel):
    """Explainable finding"""
    finding_id: UUID
    asset_id: Optional[UUID] = None
    tenant_id: str
    run_id: str
    finding_type: FindingType
    severity: Severity
    explanation: str
    evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RunStatus(str, Enum):
    """Run status enumeration with IRL semantics"""
    PENDING = "pending"
    RUNNING = "running"
    UPSTREAM_ERROR = "upstream_error"
    INVALID_SNAPSHOT = "invalid_snapshot"
    COMPLETED_NO_ASSETS = "completed_no_assets"
    COMPLETED_WITH_RESULTS = "completed_with_results"
    COMPLETED = "completed"
    FAILED = "failed"
    INVALID_INPUT_CONTRACT = "invalid_input_contract"


class RunCounts(BaseModel):
    """Run counts"""
    observations_in: int = 0
    candidates_out: int = 0
    assets_admitted: int = 0
    artifacts_recorded: int = 0
    rejected: int = 0
    ambiguous_matches: int = 0
    findings_generated: int = 0


class RunLog(BaseModel):
    """Run log entry"""
    run_id: str
    tenant_id: str
    status: RunStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    input_meta: dict = Field(default_factory=dict)
    counts: RunCounts = Field(default_factory=RunCounts)
    failure_reasons: list[str] = Field(default_factory=list)
