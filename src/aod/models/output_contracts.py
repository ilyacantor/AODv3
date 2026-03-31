"""Pydantic v2 models for AOD output contracts"""

from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional, List, Dict
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


# CONTRACT: must match AAM AODActionType enum in aam/app/models.py
class AODActionType(str, Enum):
    """Execution intent for AAM handoff.

    PROVISION: Asset is clear for auto-connection. No blocking findings.
    INVENTORY_ONLY: Asset requires human review. Blocking findings exist.
    """
    PROVISION = "provision"
    INVENTORY_ONLY = "inventory_only"


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


class FabricPlaneType(str, Enum):
    """
    Types of Fabric Control Planes.

    AAM connects ONLY to Fabric Planes that aggregate data.
    Direct app connections only in "Preset 6 (Scrappy)" mode.
    """
    IPAAS = "ipaas"               # Workato, MuleSoft - integration flows
    API_GATEWAY = "api_gateway"   # Kong, Apigee - managed API access
    EVENT_BUS = "event_bus"       # Kafka, EventBridge - streaming backbone
    DATA_WAREHOUSE = "warehouse"  # Snowflake, BigQuery - source of truth storage
    DIRECT = "direct"             # Direct app connection (Preset 6 only)
    UNMANAGED = "unmanaged"       # Direct point-to-point connection bypassing all planes
    UNKNOWN = "unknown"


# ==============================================================================
# EVIDENCE-BASED FABRIC CLASSIFICATION (Feb 2026 Blueprint)
# ==============================================================================

class EvidenceTier(str, Enum):
    """
    Evidence tier for fabric plane classification.

    Determines confidence level based on how the routing evidence was obtained.
    Higher tiers = more reliable evidence = higher confidence.
    """
    TIER_1_DIRECT = "tier_1_direct"      # Direct plane crawl - authoritative (0.95)
    TIER_2_OBSERVED = "tier_2_observed"  # Observation plane signals (0.70-0.90)
    TIER_3_INFERRED = "tier_3_inferred"  # Category-based heuristic (0.30-0.50)


class EvidenceSourcePlane(str, Enum):
    """
    Source plane that provided the fabric routing evidence.
    """
    CLOUD = "cloud"           # Cloud resource inventory (AWS, Azure, GCP)
    NETWORK = "network"       # Network flow/traffic patterns
    CMDB = "cmdb"            # CMDB dependency records
    FINANCE = "finance"       # Financial/contract records
    IDP = "idp"              # Identity provider OAuth grants
    ENDPOINT = "endpoint"     # Endpoint installed software
    DIRECT_CRAWL = "direct_crawl"  # Direct fabric plane API crawl


class ClassificationMethod(str, Enum):
    """
    How the fabric plane assignment was determined.
    """
    DIRECT_CRAWL = "direct_crawl"      # Found via plane catalog crawl
    EVIDENCE_BASED = "evidence_based"  # Multiple evidence sources combined
    OBSERVED = "observed"              # Observed via observation plane signals
    INFERRED = "inferred"              # Inferred from asset category (legacy, demoted)


class EvidenceLeadType(str, Enum):
    """
    What kind of connection hint this evidence lead represents.

    AOD generates these from observation plane data.
    AAM validates them against actual plane crawl results.
    """
    NETWORK_FLOW = "network_flow"           # Traffic observed to a plane endpoint
    OAUTH_GRANT = "oauth_grant"             # IdP shows OAuth client authorized on a plane
    CMDB_DEPENDENCY = "cmdb_dependency"     # CMDB says "App X integrates via MuleSoft"
    FINANCE_SUBSCRIPTION = "finance_subscription"  # Finance shows iPaaS/gateway subscription
    CLOUD_RESOURCE = "cloud_resource"       # Cloud inventory shows plane infrastructure


class EvidenceLead(BaseModel):
    """
    A hint that an asset MAY connect through a specific fabric plane.

    AOD generates these from observation plane data during discovery.
    AAM validates them against actual plane crawl results.

    This is the key handoff artifact for RACI compliance:
    - AOD owns: generating evidence leads from observation planes
    - AAM owns: validating leads via direct plane crawl
    """
    lead_id: str = Field(description="Unique evidence lead identifier")
    asset_id: str = Field(description="Which discovered asset this hint is about")
    asset_domain: Optional[str] = Field(default=None, description="Asset domain e.g. salesforce.com")
    asset_name: str = Field(description="Asset display name")

    # Suggested fabric plane routing
    suggested_plane_type: FabricPlaneType = Field(description="Suggested fabric plane: IPAAS, API_GATEWAY, etc.")
    suggested_plane_product: Optional[str] = Field(default=None, description="Suggested vendor: Workato, Kong, etc.")

    # Evidence source
    evidence_source: EvidenceSourcePlane = Field(description="Which observation plane produced this")
    evidence_type: EvidenceLeadType = Field(description="What kind of signal")
    evidence_detail: str = Field(description="Human-readable description of the signal")

    # Confidence and timing
    confidence: float = Field(ge=0.0, le=1.0, description="How strong the hint is (0.0-1.0)")
    observed_at: datetime = Field(default_factory=now_pst, description="When the signal was observed")

    # Raw data for debugging
    raw_data: Optional[dict] = Field(default=None, description="Raw signal data for audit")


class FabricPlaneRegistryEntry(BaseModel):
    """
    A detected fabric plane instance for the handoff registry.

    AOD detects these planes exist via domain matching, cloud inventory, etc.
    AAM connects to them to crawl their catalogs.
    """
    plane_type: FabricPlaneType = Field(description="IPAAS, API_GATEWAY, EVENT_BUS, DATA_WAREHOUSE")
    product: str = Field(description="Workato, Kong, Snowflake, Kafka, etc.")
    endpoint: Optional[str] = Field(default=None, description="Management API endpoint if known")
    domain: Optional[str] = Field(default=None, description="Plane domain e.g. workato.com")
    detection_evidence: List[str] = Field(default_factory=list, description="Why AOD thinks this plane exists")
    is_shadow: bool = Field(default=False, description="True if not in CMDB/finance (rogue Zapier, etc.)")
    confidence: float = Field(ge=0.0, le=1.0, default=0.0, description="Detection confidence")


class PipeGovernanceStatus(str, Enum):
    """
    Governance status for a pipe connection.
    """
    SANCTIONED = "sanctioned"           # Approved, managed connection
    GOVERNED = "governed"               # Confirmed via fabric plane crawl
    KNOWN = "known"                     # High confidence evidence
    UNDER_REVIEW = "under_review"       # Pending governance review
    INVESTIGATION_NEEDED = "investigation_needed"  # Needs manual investigation
    SHADOW = "shadow"                   # Unapproved/unknown connection
    UNKNOWN = "unknown"                 # Status not determined


class DriftStatus(str, Enum):
    """
    Schema/connectivity drift status for a pipe.
    """
    OK = "ok"                # No drift detected
    DETECTED = "detected"    # Drift detected, not yet addressed
    OPEN = "open"           # Known drift, under investigation


class ConnectivityModality(str, Enum):
    """
    How data flows through the pipe.

    Determines the integration pattern for AAM connection strategy.
    """
    API = "api"                              # Direct API calls (REST, GraphQL, SOAP)
    DB = "db"                                # Database connection (SQL, query)
    FILE = "file"                            # File-based transfer (S3, SFTP)
    STREAM = "stream"                        # Event streaming (Kafka, Kinesis)
    CONTROL_PLANE = "control_plane"          # iPaaS recipes, orchestrated flows
    DECLARED_INTERFACE = "declared_interface" # API Gateway routes, managed APIs
    PASSIVE_SUBSCRIPTION = "passive_subscription"  # Event bus topics, streams
    MINIMAL_TEE = "minimal_tee"              # One additional sink on existing flow
    DIRECT_P2P = "direct_p2p"                # Direct point-to-point (unmanaged)


class FabricRoutingEvidence(BaseModel):
    """
    Individual evidence record for fabric plane routing.

    Each piece of evidence that contributes to determining which fabric plane
    a pipe routes through. Evidence from multiple sources is aggregated
    to compute composite confidence.

    PRINCIPLE: A pipe's fabric plane is determined by the evidence of how AOD
    discovered or observed the connection — never by inferring from asset type.
    """
    evidence_id: str = Field(description="Unique evidence identifier")
    source_plane: EvidenceSourcePlane = Field(description="Which observation plane provided this")
    signal_type: str = Field(description="Type of signal: network_flow_to_kong, cmdb_dependency, etc.")
    signal_detail: str = Field(description="Raw evidence: IP, hostname, record ID, etc.")
    confidence: float = Field(ge=0.0, le=1.0, description="Individual signal confidence")
    timestamp: datetime = Field(description="When this evidence was collected")
    fabric_plane_type: Optional[FabricPlaneType] = Field(
        default=None,
        description="Fabric plane indicated by this evidence"
    )
    fabric_plane_vendor: Optional[str] = Field(
        default=None,
        description="Specific vendor if identifiable (kong, workato, snowflake)"
    )
    raw_data: Optional[dict] = Field(
        default=None,
        description="Raw signal data for debugging/audit"
    )


class Pipe(BaseModel):
    """
    A data pipe connecting systems through a fabric plane.

    CORE PRINCIPLE: A pipe's fabric plane is determined by evidence of how AOD
    discovered the connection — not by asset category inference.

    One SOR can have multiple pipes through different fabric planes simultaneously.
    Example: Salesforce might have:
    - iPaaS pipe (Workato recipe syncing Opportunities)
    - API Gateway pipe (Kong proxying REST API)
    - Data Warehouse pipe (Snowflake landing table with nightly extracts)

    Each of these is a DISTINCT pipe record with different fabric plane assignments.
    """
    pipe_id: str = Field(description="Unique pipe identifier")
    name: str = Field(description="Human-readable name encoding routing path")
    source_system: str = Field(description="SOR at the data-producing end")
    target_system: Optional[str] = Field(
        default=None,
        description="SOR at the data-consuming end (if known)"
    )

    # Fabric plane assignment
    fabric_plane: FabricPlaneType = Field(description="Assigned fabric plane type")
    fabric_plane_instance: Optional[str] = Field(
        default=None,
        description="Specific instance: 'Kong Production', 'Workato Org 1'"
    )

    # Connectivity modality
    modality: ConnectivityModality = Field(
        default=ConnectivityModality.CONTROL_PLANE,
        description="How data flows through this pipe"
    )

    # Evidence-based classification
    classification_method: ClassificationMethod = Field(
        description="How this classification was determined"
    )
    classification_evidence: List[FabricRoutingEvidence] = Field(
        default_factory=list,
        description="All evidence records supporting this classification"
    )
    classification_confidence: float = Field(
        ge=0.0, le=1.0,
        description="Composite confidence computed from evidence"
    )
    evidence_tier: EvidenceTier = Field(
        description="Highest evidence tier supporting this classification"
    )

    # Governance
    governance_status: PipeGovernanceStatus = Field(
        default=PipeGovernanceStatus.UNKNOWN
    )

    # Schema and drift
    entity_scope: List[str] = Field(
        default_factory=list,
        description="Business entities flowing through this pipe"
    )
    trust_labels: int = Field(default=0, description="Count of applied trust labels")
    drift_status: DriftStatus = Field(default=DriftStatus.OK)

    # Ownership
    owner: Optional[str] = Field(default=None, description="Team/vendor ownership")

    # Metadata
    discovered_at: datetime = Field(default_factory=now_pst)
    last_validated_at: Optional[datetime] = None

    # Contradiction tracking
    has_contradictions: bool = Field(
        default=False,
        description="True if evidence sources disagree"
    )
    contradiction_detail: Optional[str] = Field(
        default=None,
        description="Description of contradicting evidence"
    )


class FabricPlaneRegistry(BaseModel):
    """
    Registry of confirmed fabric planes in the environment.

    Phase 1 output: After processing observation planes, AOD builds this
    registry of known fabric planes with their evidence sources.
    """
    planes: List["FabricPlane"] = Field(default_factory=list)
    shadow_plane_candidates: List["FabricPlane"] = Field(
        default_factory=list,
        description="Planes detected but not in Finance/official inventory"
    )
    evidence_summary: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of evidence by source plane"
    )
    generated_at: datetime = Field(default_factory=now_pst)


class RoutingEvidenceTable(BaseModel):
    """
    Per-asset collection of all fabric routing signals.

    Phase 1 output: Aggregates all evidence indicating how each asset
    connects to fabric planes.
    """
    asset_key: str = Field(description="Asset identifier (domain/vendor)")
    evidence: List[FabricRoutingEvidence] = Field(default_factory=list)
    inferred_planes: List[FabricPlaneType] = Field(
        default_factory=list,
        description="Fabric planes suggested by evidence"
    )
    highest_confidence: float = Field(
        default=0.0,
        description="Max confidence from any single evidence"
    )
    evidence_count_by_plane: Dict[str, int] = Field(
        default_factory=dict,
        description="Evidence count per observation plane"
    )


class EnterprisePreset(str, Enum):
    """
    Enterprise Preset Patterns - determines AAM connection strategy.
    
    AAM switches logic based on organizational integration maturity.
    """
    PRESET_6_SCRAPPY = "preset_6_scrappy"         # Direct app connections
    PRESET_8_IPAAS = "preset_8_ipaas"             # iPaaS-centric (MuleSoft/Workato)
    PRESET_9_EVENT_DRIVEN = "preset_9_event"      # Event-driven (Kafka primary)
    PRESET_10_API_GATEWAY = "preset_10_gateway"   # API Gateway-centric (Kong/Apigee)
    PRESET_11_WAREHOUSE = "preset_11_warehouse"   # Warehouse-centric (Snowflake canonical)
    PRESET_HYBRID = "preset_hybrid"               # Mixed pattern
    PRESET_UNKNOWN = "preset_unknown"             # Unable to determine


class FabricPlaneTag(BaseModel):
    """
    Tag indicating asset is managed by a Fabric Control Plane.
    
    Assets tagged with this are connected VIA the plane, not directly.
    """
    plane_type: FabricPlaneType
    controller_vendor: str           # e.g., "mulesoft", "snowflake", "kafka"
    controller_domain: Optional[str] = None  # e.g., "anypoint.mulesoft.com"
    evidence: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class FabricPlane(BaseModel):
    """
    A detected Fabric Control Plane (Mothership).
    
    Finding 500 APIs is useless if they're all managed by one MuleSoft instance.
    AOD must prioritize discovering these Control Planes first.
    """
    plane_id: str
    plane_type: FabricPlaneType
    vendor: str
    display_name: str
    domain: Optional[str] = None
    managed_asset_count: int = 0
    evidence_refs: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class PresetContext(BaseModel):
    """
    Enterprise Preset inference result.
    
    Determines the organizational integration pattern based on
    Fabric Plane density and canonical data ownership.
    """
    preset: EnterprisePreset
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    rationale: str = ""
    density_scores: Dict[str, float] = Field(default_factory=dict)  # plane_type -> % of assets
    primary_plane: Optional[str] = None    # Primary control plane vendor
    evidence: List[str] = Field(default_factory=list)


class CandidateFinding(BaseModel):
    """Thin finding representation for ConnectionCandidate"""
    code: str
    severity: str
    message: str


class CandidateSORTagging(BaseModel):
    """Thin SOR tagging for ConnectionCandidate"""
    domain: Optional[str] = None
    confidence: str = "none"
    evidence: list[str] = Field(default_factory=list)


class CandidatePipeEvidence(BaseModel):
    """
    Evidence for a fabric plane pipe connection.

    Included in ConnectionCandidate to provide AAM with:
    1. Which fabric plane the asset connects through
    2. Confidence level and evidence tier
    3. Supporting evidence for audit trail
    """
    pipe_id: str = Field(description="Unique pipe identifier")
    fabric_plane_type: str = Field(description="Plane type: ipaas, api_gateway, event_bus, data_warehouse, unmanaged")
    fabric_plane_vendor: Optional[str] = Field(default=None, description="Vendor: workato, kong, snowflake, etc.")
    modality: str = Field(default="api", description="Connection modality: api, db, file, event")

    # Classification details
    evidence_tier: str = Field(description="Tier: tier_1_direct, tier_2_observed, tier_3_inferred")
    classification_confidence: float = Field(description="Confidence score 0.0-1.0")
    classification_method: str = Field(description="Method: direct_crawl, evidence_based, inferred")

    # Evidence chain (thin summary for handoff)
    evidence_sources: list[str] = Field(default_factory=list, description="Sources: network, cloud, finance, cmdb, idp, direct_crawl")
    evidence_count: int = Field(default=0, description="Total evidence pieces supporting this classification")
    top_evidence: list[str] = Field(default_factory=list, description="Top 3 evidence signals for this pipe")

    # Governance
    governance_status: str = Field(default="known", description="Pipe governance: governed, known, shadow, investigation_needed")
    has_contradictions: bool = Field(default=False, description="Whether conflicting evidence exists")
    contradiction_note: Optional[str] = Field(default=None, description="Brief note if contradictions exist")


class CandidateFabricPlaneSummary(BaseModel):
    """
    Summary of fabric plane classification for AAM handoff.

    Provides AAM with complete fabric plane context for the asset.
    """
    primary_plane: Optional[str] = Field(default=None, description="Primary fabric plane type")
    primary_vendor: Optional[str] = Field(default=None, description="Primary fabric plane vendor")
    primary_confidence: float = Field(default=0.0, description="Confidence in primary classification")

    # Multi-plane support
    all_planes: list[str] = Field(default_factory=list, description="All planes this asset connects through")
    is_multi_plane: bool = Field(default=False, description="True if asset routes through multiple planes")

    # Evidence summary
    total_evidence_count: int = Field(default=0, description="Total evidence across all planes")
    evidence_tier: str = Field(default="tier_3_inferred", description="Highest tier evidence available")

    # Flags
    has_shadow_plane: bool = Field(default=False, description="True if unauthorized plane detected")
    needs_investigation: bool = Field(default=False, description="True if classification needs review")


class ConnectionCandidate(BaseModel):
    """
    Connection candidate for AAM (Adaptive API Mesh).
    
    AOD emits ConnectionCandidates to express connection INTENT + EVIDENCE.
    AOD does NOT decide how to connect - AAM handles that.
    AOD does NOT talk directly to DCL for provisioning.
    
    This is a one-way handoff: AOD -> AAM.
    
    EXECUTION SIGNALING:
    - execution_allowed: Whether AAM should auto-provision this candidate
    - action_type: "provision" (clear to act) or "inventory_only" (blocked, do not act)
    
    Blocking findings (critical severity) set execution_allowed=False.
    AAM receives complete inventory but knows which candidates require triage resolution.
    """
    asset_key: str = Field(description="Canonical asset key (domain/vendor)")
    vendor_name: Optional[str] = None
    display_name: str
    category: Optional[str] = Field(default=None, description="Category: crm, erp, finance, data, idp, etc.")
    governance_status: str = Field(description="governed | shadow | zombie | edge")
    findings: list[CandidateFinding] = Field(default_factory=list, description="Existing AOD findings")
    sor_tagging: Optional[CandidateSORTagging] = None
    evidence_refs: list[str] = Field(default_factory=list, description="Pointers to AOD evidence/observations")
    signals_summary: dict = Field(default_factory=dict, description="Thin summary: counts, matches, booleans")
    known_endpoints: Optional[dict] = Field(default=None, description="Known API endpoints if available")
    preferred_modality: Optional[str] = Field(default=None, description="Preferred connection modality")
    priority_score: Optional[float] = Field(default=None, description="Priority score for connection ordering")
    connected_via_plane: Optional[str] = Field(default=None, description="Fabric plane connection: 'Connect via MuleSoft', etc.")
    execution_allowed: bool = Field(default=True, description="Whether AAM should auto-provision. False if blocking findings exist.")
    action_type: AODActionType = Field(default=AODActionType.PROVISION, description="Execution intent: 'provision' (clear) or 'inventory_only' (blocked)")

    # Enhanced fabric plane classification (Sprint 5)
    pipes: list[CandidatePipeEvidence] = Field(
        default_factory=list,
        description="Fabric plane pipes for this asset with evidence chain"
    )
    fabric_plane_summary: Optional[CandidateFabricPlaneSummary] = Field(
        default=None,
        description="Summary of fabric plane classification"
    )

    # Evidence leads for AAM validation (RACI Sprint)
    evidence_leads: list["EvidenceLead"] = Field(
        default_factory=list,
        description="Connection hints for AAM to validate via plane crawl"
    )


class ConnectionCandidatePayload(BaseModel):
    """
    The full AOD → AAM handoff payload.

    This is the complete data package that AOD sends to AAM for connection
    provisioning. AAM receives the full inventory but AOD does NOT decide
    how to connect - that's AAM's job.

    RACI Compliance:
    - AOD is A/R for: asset discovery, fabric plane identification, evidence lead generation
    - AAM is A/R for: plane crawl, pipe creation, connection provisioning
    """
    aod_discovery_id: str = Field(description="Discovery run identifier")
    tenant_id: str = Field(description="Tenant identifier")
    timestamp: datetime = Field(default_factory=now_pst, description="Handoff timestamp")

    # Asset catalog — the discovered inventory
    candidates: list[ConnectionCandidate] = Field(
        default_factory=list,
        description="Connection candidates with governance status and SOR scores"
    )

    # Fabric Plane Registry — detected planes (AOD identifies, AAM connects)
    fabric_planes: list[FabricPlaneRegistryEntry] = Field(
        default_factory=list,
        description="Detected fabric plane instances"
    )

    # Enterprise Preset — inferred architecture type
    enterprise_preset: str = Field(
        default="preset_unknown",
        description="Inferred org pattern: preset_8_ipaas, preset_11_warehouse, etc."
    )
    preset_confidence: float = Field(
        default=0.0,
        ge=0.0, le=1.0,
        description="Confidence in preset inference"
    )
    preset_rationale: str = Field(
        default="",
        description="Why this preset was inferred"
    )

    # Evidence Leads — connection hints for AAM to validate
    evidence_leads: list[EvidenceLead] = Field(
        default_factory=list,
        description="All evidence leads from observation planes"
    )

    # Findings — issues discovered during scan
    findings: list[CandidateFinding] = Field(
        default_factory=list,
        description="Discovery findings (identity gaps, finance gaps, etc.)"
    )

    # Policy Manifest — governance rules for AAM to enforce
    policy_manifest: dict = Field(
        default_factory=dict,
        description="Governance policies for AAM connection decisions"
    )

    # Statistics
    total_assets: int = Field(default=0, description="Total assets discovered")
    governed_count: int = Field(default=0, description="Assets with governed status")
    shadow_count: int = Field(default=0, description="Shadow IT assets")
    sor_count: int = Field(default=0, description="Identified Systems of Record")


class Asset(BaseModel):
    """Asset in the catalog - systems only"""
    asset_id: UUID
    tenant_id: str
    aod_discovery_id: str
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
    # Jan 2026: Fabric Plane tagging - identifies assets behind control planes
    fabric_plane_tag: Optional[FabricPlaneTag] = Field(
        default=None,
        description="Fabric Plane tag - indicates asset is managed by a control plane"
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
    aod_discovery_id: str
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
    aod_discovery_id: str
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
    # Normalization funnel breakdown (observations_in → candidates_out)
    iron_dome_rejected: int = 0        # Invalid domains/names rejected at normalization
    domain_merged: int = 0             # Observations merged into existing entity (many-to-one)
    entities_normalized: int = 0       # Unique entities after normalization (pre-artifact filter)


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
    """
    Run log entry for a DiscoveryScan session.

    The aod_discovery_id field also serves as the scan_session_id for downstream handoffs to AAM.
    The scan_session_id property is provided as an alias for clarity in the new terminology.
    """
    aod_discovery_id: str
    tenant_id: str
    entity_id: Optional[str] = Field(default=None, description="Business entity key (e.g. 'meridian'). Set from Console request.")
    status: RunStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    input_meta: dict = Field(default_factory=dict)
    counts: RunCounts = Field(default_factory=RunCounts)
    stage_timings: Optional[PipelineStageTimings] = Field(default=None, description="DiscoveryScan stage timing in seconds")
    failure_reasons: list[str] = Field(default_factory=list)
    sync_status: SyncStatus = SyncStatus.NOT_APPLICABLE
    sync_error: Optional[str] = None
    policy_snapshot: Optional[dict] = Field(default=None, description="Policy configuration snapshot used for this scan")
    
    @property
    def scan_session_id(self) -> str:
        """Alias for aod_discovery_id - the unique identifier for this DiscoveryScan session."""
        return self.aod_discovery_id


# Backward-compatible type alias
DiscoveryScanSession = RunLog
"""Type alias for RunLog - represents a DiscoveryScan session."""


