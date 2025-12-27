"""Pydantic v2 models for AOD output contracts"""

from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field

PST = timezone(timedelta(hours=-8))

def now_pst() -> datetime:
    """Get current time in PST"""
    return datetime.now(PST)


class ProvisioningStatus(str, Enum):
    """
    Provisioning status for Traffic Light system.
    
    Separates Inventory (what we see) from Catalog (what we trust).
    Default is QUARANTINE (fail-closed) to ensure no untrusted assets
    leak to downstream consumers (DCL).
    
    ACTIVE: Trusted, flows to DCL automatically (Green)
    REVIEW: Admitted but flagged for cleanup - zombie candidate (Amber)
    QUARANTINE: Saved for triage but BLOCKED from DCL - shadow IT (Red)
    BLOCKED: User rejected via BAN action - permanently blocked (Black)
    RETIRED: User deprovisioned - removed from active use (Gray)
    IGNORED: Hard rejection at admission, dropped from pipeline
    """
    ACTIVE = "active"
    REVIEW = "review"
    QUARANTINE = "quarantine"
    BLOCKED = "blocked"
    RETIRED = "retired"
    IGNORED = "ignored"


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
    discovery: bool = False


class AssetIdentifiers(BaseModel):
    """Asset identifiers"""
    domains: list[str] = Field(default_factory=list)
    hostnames: list[str] = Field(default_factory=list)
    uris: list[str] = Field(default_factory=list)


class ActivityEvidence(BaseModel):
    """Activity timestamps from various planes"""
    idp_last_login_at: Optional[datetime] = None
    discovery_observed_at: Optional[datetime] = None
    cloud_observed_at: Optional[datetime] = None
    endpoint_last_seen_at: Optional[datetime] = None
    network_last_seen_at: Optional[datetime] = None
    finance_last_transaction_at: Optional[datetime] = None
    latest_activity_at: Optional[datetime] = None


class VendorHypothesis(BaseModel):
    """
    Inferred vendor identity - decorative only.
    
    Inference decorates reality; it does not redefine it.
    This is never authoritative and does not affect admission or shadow logic.
    
    INVARIANT: vendor_hypothesis is NON-DECISIONABLE metadata.
    It MUST NOT be referenced by:
    - admission.py (admission logic)
    - derived_classifications.py (classify_shadow, classify_zombie functions)
    - findings_engine.py (finding generation)
    - any policy, scoring, or automation logic
    
    Violation of this invariant breaks the evidence-only design principle.
    """
    value: str
    confidence: float = Field(ge=0.0, le=0.9, description="Max 0.9 - never authoritative")
    basis: str = Field(description="How this was inferred: domain, pattern, etc.")


class LLMMetadata(BaseModel):
    """
    LLM explainability metadata for an asset.
    
    First-class facts from LLM fringe resolution.
    When llm_used is True, the LLM was called to resolve ambiguous/missing data.
    """
    llm_used: bool = False
    llm_confidence: float = 0.0
    llm_reason: str = ""
    llm_asset_type: Optional[str] = None
    llm_canonical_vendor: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model_id: Optional[str] = None
    fact_id: Optional[str] = None
    exclusion_reason: Optional[str] = None
    cmdb_match_method: Optional[str] = None
    idp_match_method: Optional[str] = None


class Asset(BaseModel):
    """Asset in the catalog - systems only"""
    asset_id: UUID
    tenant_id: str
    run_id: str
    name: str
    asset_type: AssetType = AssetType.UNKNOWN
    identifiers: AssetIdentifiers = Field(default_factory=AssetIdentifiers)
    vendor: Optional[str] = None
    vendor_hypothesis: Optional[VendorHypothesis] = None
    environment: Environment = Environment.UNKNOWN
    evidence_refs: list[str] = Field(default_factory=list)
    lens_status: LensStatuses = Field(default_factory=LensStatuses)
    lens_coverage: LensCoverage = Field(default_factory=LensCoverage)
    activity_evidence: ActivityEvidence = Field(default_factory=ActivityEvidence)
    tags: list[str] = Field(default_factory=list)
    admission_reason: str = ""
    provisioning_status: ProvisioningStatus = ProvisioningStatus.QUARANTINE
    llm_metadata: Optional[LLMMetadata] = None
    has_critical_gap: bool = Field(default=False, description="True if ACTIVE asset has identity_gap finding (no IdP match)")
    owner: Optional[str] = Field(default=None, description="Business owner email - assigned via Triage or sourced from CMDB/IdP")
    created_at: datetime = Field(default_factory=now_pst)


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
    created_at: datetime = Field(default_factory=now_pst)


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
    CRITICAL = "critical"


class FindingCategory(str, Enum):
    """Finding category - enterprise risk taxonomy (Dec 2025)
    
    Security Risks (headline KPI):
    - IDENTITY_ACCESS: Ungoverned access paths
    - SHADOW_IT: Financially-backed shadow systems  
    - DATA_INTEGRITY: Conflicting authoritative data
    
    Non-Security (secondary KPIs):
    - VISIBILITY_GAP: Coverage gaps in control planes
    - GOVERNANCE_HYGIENE: Exposure amplifiers (ownership, duplication)
    """
    IDENTITY_ACCESS = "identity_access"
    SHADOW_IT = "shadow_it"
    DATA_INTEGRITY = "data_integrity"
    VISIBILITY_GAP = "visibility_gap"
    GOVERNANCE_HYGIENE = "governance_hygiene"
    SECURITY_RISK = "security_risk"
    GOVERNANCE_FINDING = "governance_finding"


class Confidence(str, Enum):
    """Confidence level for findings"""
    LOW = "low"
    MED = "med"
    HIGH = "high"


class Materiality(str, Enum):
    """Materiality level - business impact significance"""
    LOW = "low"
    MED = "med"
    HIGH = "high"


class TriagePriority(str, Enum):
    """Triage priority for actionable findings"""
    P0 = "p0"  # Immediate - high confidence + high materiality
    P1 = "p1"  # High priority - actionable
    P2 = "p2"  # Backlog / monitor


class Finding(BaseModel):
    """Explainable finding"""
    finding_id: UUID
    asset_id: Optional[UUID] = None
    tenant_id: str
    run_id: str
    finding_type: FindingType
    category: FindingCategory
    severity: Severity
    explanation: str
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: Confidence = Confidence.MED
    materiality: Materiality = Materiality.MED
    triage_priority: TriagePriority = TriagePriority.P2
    conflict_field: Optional[str] = None  # For DATA_CONFLICT deduplication
    created_at: datetime = Field(default_factory=now_pst)


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


class SyncStatus(str, Enum):
    """Farm sync status"""
    PENDING = "pending"
    SYNCED = "synced"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"


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
    sync_status: SyncStatus = SyncStatus.NOT_APPLICABLE
    sync_error: Optional[str] = None


