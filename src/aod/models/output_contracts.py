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
    # Stage 3: Farm-style vendor governance propagation
    # True if governance inherited from another asset sharing the same vendor domain set
    vendor_governed: bool = False


class MatchDebugInfo(BaseModel):
    """Debug info for plane matching - helps diagnose false positives/negatives"""
    match_method: Optional[str] = Field(default=None, description="How match was made: domain, name, vendor, etc.")
    match_key: Optional[str] = Field(default=None, description="The key value that matched")
    matched_record_id: Optional[str] = Field(default=None, description="The matched record ID from the plane")
    matched_record_name: Optional[str] = Field(default=None, description="The matched record name from the plane")
    ambiguity_code: Optional[str] = Field(default=None, description="Disambiguation code if multiple matches")
    disambiguation_detail: Optional[str] = Field(default=None, description="Detail about disambiguation resolution")
    is_authoritative: bool = Field(default=False, description="True if match is authoritative (can assert governance)")
    matched_record_domain: Optional[str] = Field(default=None, description="The matched record domain if any")


class LensMatchDebug(BaseModel):
    """Debug info for all plane matches"""
    idp: Optional[MatchDebugInfo] = None
    cmdb: Optional[MatchDebugInfo] = None
    cloud: Optional[MatchDebugInfo] = None
    finance: Optional[MatchDebugInfo] = None
    idp_candidate: bool = Field(default=False, description="True if heuristic IdP match (no governance)")
    cmdb_candidate: bool = Field(default=False, description="True if heuristic CMDB match (no governance)")


class DomainSource(str, Enum):
    """Source of a domain in identifiers.domains - separates 'where domain came from' from 'how we matched'"""
    DISCOVERY = "discovery"      # From discovery observations (network, endpoint, etc.)
    CMDB = "cmdb"               # From CMDB record.domain (primary domain field)
    IDP = "idp"                 # From IdP record.domain
    VENDOR_MAP = "vendor_map"   # From VENDOR_TO_DOMAIN mapping
    INFERRED = "inferred"       # From name/vendor inference


class AssetIdentifiers(BaseModel):
    """Asset identifiers"""
    domains: list[str] = Field(default_factory=list)
    hostnames: list[str] = Field(default_factory=list)
    uris: list[str] = Field(default_factory=list)
    # Reference domains from CMDB external_ref/URLs - enrichment only, not for identity/admission
    reference_domains: list[str] = Field(default_factory=list)
    # Jan 2026: Domain provenance tracking (parallel field, backward compatible)
    # Maps domain -> source enum to track where each domain came from
    # This is SEPARATE from match_method (how we correlated) - tracks domain origin
    domain_provenance: dict[str, str] = Field(
        default_factory=dict,
        description="Maps domain to its source: discovery, cmdb, idp, vendor_map, inferred"
    )


class ActivityEvidence(BaseModel):
    """Activity timestamps from various planes"""
    idp_last_login_at: Optional[datetime] = None
    discovery_observed_at: Optional[datetime] = None
    cloud_observed_at: Optional[datetime] = None
    endpoint_last_seen_at: Optional[datetime] = None
    network_last_seen_at: Optional[datetime] = None
    finance_last_transaction_at: Optional[datetime] = None
    latest_activity_at: Optional[datetime] = None
    # Jan 2026: Domain-aligned IdP governance flag
    # True if any matched IdP record has a domain that matches the entity's domain.
    # This is INDEPENDENT of whether that IdP has activity (last_login_at).
    # Used for zombie classification to distinguish domain-aligned IdP from cross-domain matches.
    idp_governance_aligned: bool = False


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


class VendorGovernanceTrace(BaseModel):
    """
    Stage 3: Trace info for vendor governance propagation.
    
    Records the vendor and seed domain that granted governance via propagation.
    Fully traceable - no magic governance assertions.
    """
    vendor: str = Field(description="Vendor name that granted governance")
    seed_domain: str = Field(description="Domain that had authoritative governance and seeded propagation")
    seed_asset_id: Optional[str] = Field(default=None, description="Asset ID that provided the governance seed")


class SORTagging(BaseModel):
    """
    System of Record (SOR) tagging for an asset.
    
    Identifies assets that are likely authoritative data sources for specific
    data domains (customer, employee, financial, etc.).
    
    ORTHOGONAL to Shadow/Zombie/Governed - an asset can be:
    - Governed + SOR (ideal state)
    - Shadow + SOR-candidate (ungoverned CRM - red flag!)
    - Zombie + former-SOR (abandoned authoritative system)
    """
    likelihood: str = Field(default="none", description="SOR likelihood: high, medium, low, none")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence score 0.0-1.0")
    evidence: list[str] = Field(default_factory=list, description="Evidence strings explaining the score")
    domain: Optional[str] = Field(default=None, description="Data domain: customer, employee, financial, product, identity, it_assets")
    signals_matched: list[str] = Field(default_factory=list, description="Signal names that contributed to score")


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
    lens_match_debug: Optional[LensMatchDebug] = Field(default=None, description="Debug info for plane matching - helps diagnose mismatches")
    activity_evidence: ActivityEvidence = Field(default_factory=ActivityEvidence)
    tags: list[str] = Field(default_factory=list)
    admission_reason: str = ""
    provisioning_status: ProvisioningStatus = ProvisioningStatus.QUARANTINE
    llm_metadata: Optional[LLMMetadata] = None
    has_critical_gap: bool = Field(default=False, description="True if ACTIVE asset has identity_gap finding (no IdP match)")
    owner: Optional[str] = Field(default=None, description="Business owner email - assigned via Triage or sourced from CMDB/IdP")
    discovery_sources: list[str] = Field(
        default_factory=list,
        description="Single source of truth for discovery evidence. lens_coverage.discovery and HAS_DISCOVERY derive from this."
    )
    # Stage 3: Farm-style vendor governance propagation trace
    vendor_governance_trace: Optional[VendorGovernanceTrace] = Field(
        default=None, 
        description="Trace info when governance was inherited via vendor domain set propagation"
    )
    # Jan 2026: System of Record (SOR) tagging
    sor_tagging: Optional[SORTagging] = Field(
        default=None,
        description="SOR scoring results - identifies likely Systems of Record"
    )
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


class PipelineStageTimings(BaseModel):
    """Timing measurements for each pipeline stage in seconds"""
    fetch_snapshot: float = 0.0
    validate_snapshot: float = 0.0
    normalize: float = 0.0
    build_indexes: float = 0.0
    correlate: float = 0.0
    artifacts: float = 0.0
    admission: float = 0.0
    findings: float = 0.0
    persist: float = 0.0
    total: float = 0.0


class RunLog(BaseModel):
    """Run log entry"""
    run_id: str
    tenant_id: str
    status: RunStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    input_meta: dict = Field(default_factory=dict)
    counts: RunCounts = Field(default_factory=RunCounts)
    stage_timings: Optional[PipelineStageTimings] = Field(default=None, description="Pipeline stage timing in seconds")
    failure_reasons: list[str] = Field(default_factory=list)
    sync_status: SyncStatus = SyncStatus.NOT_APPLICABLE
    sync_error: Optional[str] = None
    policy_snapshot: Optional[dict] = Field(default=None, description="Policy configuration snapshot used for this run")


