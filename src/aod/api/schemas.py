"""Pydantic schema classes for AOD API routes"""

from typing import Any, Optional

from pydantic import BaseModel, Field

from ..models.output_contracts import RunCounts, PipelineStageTimings


class FarmRunRequest(BaseModel):
    """Request for creating a run from Farm"""
    tenant_id: str
    farm_base_url: str | None = None
    snapshot_id: str
    industry: str | None = Field(
        default=None,
        description="Industry vertical for fabric generation (e.g., 'finance', 'healthcare'). "
                    "When provided, fabric planes are weighted by industry-specific vendor preferences."
    )
    entity_id: str | None = Field(
        default=None,
        description="Business entity identifier for triple store writes. "
                    "Falls back to snapshot meta.entity_id or AOD_DEFAULT_ENTITY_ID env var."
    )


class RunResponse(BaseModel):
    """Response for run creation"""
    run_id: str
    tenant_id: str
    entity_id: Optional[str] = None
    status: str
    counts: RunCounts
    message: str
    sync_status: Optional[str] = None
    sync_error: Optional[str] = None


class RunDetailResponse(BaseModel):
    """Response for run detail"""
    run_id: str
    tenant_id: str
    status: str
    started_at: str
    completed_at: Optional[str]
    input_meta: dict
    counts: RunCounts
    stage_timings: Optional[PipelineStageTimings] = None
    failure_reasons: list[str]
    sync_status: str = "not_applicable"
    sync_error: Optional[str] = None


class CatalogResponse(BaseModel):
    """Response for catalog"""
    run_id: str
    assets: list[dict[str, Any]]
    count: int


class FindingsResponse(BaseModel):
    """Response for findings"""
    run_id: str
    findings: list[dict[str, Any]]
    count: int


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str


class SnapshotListResponse(BaseModel):
    """Response for snapshot listing"""
    snapshots: list[dict[str, Any]]
    count: int


class TenantListResponse(BaseModel):
    """Response for tenant listing"""
    tenants: list[str]
    count: int


class ResyncRequest(BaseModel):
    """Request for re-syncing a run to Farm"""
    run_id: str
    mode: str = "sprawl"


class ResyncResponse(BaseModel):
    """Response for re-sync operation"""
    run_id: str
    sync_status: str
    sync_error: Optional[str] = None
    shadow_asset_keys: list[str]
    zombie_asset_keys: list[str]
    asset_summaries_keys: list[str]


class ZombieExplainRequest(BaseModel):
    """Request for zombie explanation"""
    tenant_id: str
    run_id: str
    keys: list[str]
    window_days: int = 30


class KeyExplanation(BaseModel):
    """Explanation for a single key"""
    key: str
    matched_asset_ids: list[str]
    normalized_keys_considered: list[str]
    idp_present: bool
    idp_evidence: Optional[dict] = None
    cmdb_present: bool
    cmdb_evidence: Optional[dict] = None
    activity_signals: dict[str, Optional[str]]
    activity_within_window: Optional[bool]
    zombie_decision: str
    why: list[str]


class ZombieExplainResponse(BaseModel):
    """Response for zombie explanation"""
    run_id: str
    tenant_id: str
    window_days: int
    explanations: list[KeyExplanation]
    summary: dict


class ZombieReconcileRequest(BaseModel):
    """Request for zombie reconciliation report"""
    tenant_id: str
    run_id: str
    expected_zombie_keys: list[str]
    extra_zombie_keys: list[str]
    window_days: int = 30


class ZombieReconcileResponse(BaseModel):
    """Response for zombie reconciliation report"""
    run_id: str
    tenant_id: str
    window_days: int
    expected_count: int
    extra_count: int
    missed_zombies_summary: dict
    extra_zombies_summary: dict
    compact_report: str
    sample_explanation: Optional[dict] = None


class TimestampCoverageRequest(BaseModel):
    """Request for timestamp coverage report"""
    tenant_id: str
    snapshot_id: str
    run_id: Optional[str] = None


class PlaneCoverage(BaseModel):
    """Coverage stats for a single plane"""
    raw_count: int
    raw_with_timestamp: int
    raw_timestamp_field_names_found: list[str]
    normalized_with_timestamp: int
    normalized_timestamp_fields_used: list[str]
    examples_with_timestamp: list[dict]
    examples_missing_timestamp: list[dict]


class TimestampCoverageResponse(BaseModel):
    """Response for timestamp coverage report"""
    snapshot_id: str
    run_id: Optional[str]
    planes: dict[str, PlaneCoverage]
    summary: dict
    conclusion: str


class AODActualResultsRequest(BaseModel):
    """Request for AOD actual results (pure emitter - no expected data consumed)"""
    run_id: str
    activity_window_days: int = 90


class AODActualResultsResponse(BaseModel):
    """
    AOD Actual Results Response - Pure Emitter
    
    DESIGN PRINCIPLE:
    - Farm owns reconciliation UI (has expected + actual + diffs)
    - AOD owns its structured "actual" output only
    - Farm displays side-by-side and runs the RCA reducer
    
    DATA FLOW:
    - AOD publishes: shadow_actual, zombie_actual, admission_actual, actual_reason_codes
    - Farm already has: shadow_expected, zombie_expected, expected_reason_codes
    - Farm computes: extra, missed, rca_code per mismatch
    
    HARD RULE: AOD NEVER consumes Farm expected/rca data
    """
    run_id: str
    shadow_actual: list[str]
    zombie_actual: list[str]
    admission_actual: dict[str, str]
    actual_reason_codes: dict[str, list[str]]
    asset_details: dict[str, dict]
    summary: dict


class ExplainNonflagRequest(BaseModel):
    """
    Request for explain-nonflag endpoint.
    
    Farm sends ONLY keys + snapshot_id + ask-type.
    No expected data is sent or consumed by AOD.
    """
    snapshot_id: str
    asset_keys: list[str]
    ask: str = Field(description="'shadow' | 'zombie' | 'both'")


class NonflagExplanation(BaseModel):
    """
    Per-key explanation for why an asset was NOT flagged.
    
    Decisions:
    - unknown_key: AOD never saw it / couldn't form candidate
    - not_admitted: Saw it, but no admission gate satisfied
    - admitted_not_shadow: Admitted, but fails shadow conditions (has presence)
    - admitted_not_zombie: Admitted, but not stale (has recent activity)
    """
    asset_key: str
    present_in_aod: bool
    decision: str
    reason_codes: list[str] = Field(default_factory=list)
    primary_reason: str | None = None


class ExplainNonflagResponse(BaseModel):
    """Response for explain-nonflag endpoint"""
    snapshot_id: str
    ask: str
    explanations: list[NonflagExplanation]


class RunTestsRequest(BaseModel):
    """Request for running tests"""
    test_path: str = "tests/"


class RunTestsResponse(BaseModel):
    """Response for test run"""
    passed: bool
    total: int
    passed_count: int
    failed_count: int
    summary: str
    output: str


class AssetTraceRequest(BaseModel):
    """Request for single-asset trace debugging"""
    run_id: str
    asset_key: str


class DomainTraceStep(BaseModel):
    """One step in domain canonicalization trace"""
    step: str
    input_value: str
    output_value: Optional[str]
    function: str
    module: str


class AssetTraceResponse(BaseModel):
    """Response for single-asset trace debugging"""
    asset_key: str
    found_in_assets: bool
    found_in_observations: bool
    raw_evidence_domains: list[str]
    canonicalization_steps: list[DomainTraceStep]
    final_asset_key: Optional[str]
    key_source: Optional[str]
    asset_data: Optional[dict] = None
    observations: list[dict] = []


class TwoPathDiffRequest(BaseModel):
    """Request for two-path diff test"""
    domains: list[str]


class PathDiffResult(BaseModel):
    """Result of comparing two canonicalization paths"""
    raw_domain: str
    vendor_inference_result: Optional[str]
    reconcile_result: Optional[str]
    match: bool


class TwoPathDiffResponse(BaseModel):
    """Response for two-path diff test"""
    results: list[PathDiffResult]
    all_match: bool
    mismatches: list[str]


class DecisionTraceRequest(BaseModel):
    """Request for decision trace"""
    run_id: str
    activity_window_days: int = 90


class DecisionTraceResponse(BaseModel):
    """Response with decision traces for all assets"""
    run_id: str
    traces: dict[str, dict]
    count: int
    fields: list[str]


class TriageActionRequest(BaseModel):
    """Request to record a triage action"""
    run_id: str
    item_id: str
    item_type: str
    action: str
    owner: Optional[str] = None
    defer_days: Optional[int] = None
    ignore_reason: Optional[str] = None


class TriageActionResponse(BaseModel):
    """Response for triage action"""
    success: bool
    action_id: str
    item_id: str
    item_type: str
    action: str
    state: str
    owner: Optional[str] = None
    defer_until: Optional[str] = None
    ignore_reason: Optional[str] = None


class ProvisioningActionRequest(BaseModel):
    """
    Request for asset provisioning state transition.
    
    Actions:
    - SANCTION: Approve shadow IT → sets status to ACTIVE
    - BAN: Reject asset → sets status to BLOCKED
    - DEPROVISION: Retire zombie → sets status to RETIRED
    """
    action: str = Field(..., description="Action: SANCTION, BAN, or DEPROVISION")
    reason: Optional[str] = Field(None, description="Reason for the action")
    actor: Optional[str] = Field(None, description="User performing the action")
    item_type: Optional[str] = Field(None, description="Triage item type: shadow, zombie, blocked, hygiene, etc.")


class ProvisioningActionResponse(BaseModel):
    """Response for provisioning state transition"""
    success: bool
    asset_id: str
    asset_name: str
    previous_status: str
    new_status: str
    action: str
    reason: Optional[str] = None
    actor: Optional[str] = None
    message: str


# ============================================================================
# Fabric API Schemas - Industry-Weighted Vendor Selection (Farm Integration)
# ============================================================================

class IndustryVertical(BaseModel):
    """A single industry vertical with its characteristics"""
    id: str = Field(..., description="Industry identifier (e.g., 'finance', 'healthcare')")
    name: str = Field(..., description="Display name for the industry")
    compliance_focus: list[str] = Field(default_factory=list, description="Key compliance frameworks (e.g., ['SOX', 'PCI-DSS'])")
    typical_scale: str = Field(default="medium", description="Typical enterprise scale: small, medium, large")
    description: Optional[str] = Field(None, description="Brief description of the industry vertical")


class IndustryListResponse(BaseModel):
    """Response for listing all industry verticals"""
    industries: list[IndustryVertical]
    count: int


class VendorWeight(BaseModel):
    """Weight/probability for a single vendor within a plane"""
    vendor: str = Field(..., description="Vendor name (e.g., 'mulesoft', 'workato')")
    weight: float = Field(..., ge=0, le=1, description="Selection probability (0.0-1.0)")
    display_name: Optional[str] = Field(None, description="Human-readable vendor name")


class PlaneWeights(BaseModel):
    """Vendor weights for a single fabric plane type"""
    plane_type: str = Field(..., description="Plane type: ipaas, api_gateway, event_bus, warehouse")
    vendors: list[VendorWeight]


class IndustryWeightsResponse(BaseModel):
    """Response for vendor weights for a specific industry"""
    industry: str
    industry_name: str
    planes: list[PlaneWeights]
    compliance_focus: list[str] = Field(default_factory=list)


class WeightsMatrixEntry(BaseModel):
    """A single entry in the weights matrix"""
    industry: str
    plane_type: str
    vendor: str
    weight: float


class WeightsMatrixResponse(BaseModel):
    """Complete matrix of vendor weights across all industries"""
    matrix: list[WeightsMatrixEntry]
    industries: list[str]
    plane_types: list[str]
    vendors: list[str]


class FabricGenerateRequest(BaseModel):
    """Request to generate a fabric configuration"""
    industry: str = Field(..., description="Industry vertical ID")
    seed: Optional[int] = Field(None, description="Seed for deterministic generation")
    scale: str = Field(default="medium", description="Scale: small, medium, large")


class GeneratedVendorSelection(BaseModel):
    """A vendor selected for a fabric plane"""
    plane_type: str
    vendor: str
    display_name: str
    confidence: float = Field(..., description="Selection confidence based on industry weight")


class FabricGenerateResponse(BaseModel):
    """Response for fabric configuration generation"""
    industry: str
    seed: int
    scale: str
    fabric_config: list[GeneratedVendorSelection]
    deterministic: bool = Field(default=True, description="True = same seed+industry always produces same config")
