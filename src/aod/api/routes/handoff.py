"""
Handoff API - ConnectionCandidate Export for AAM

AOD (Asset Observation & Discovery) identifies assets and their governance state.
This module provides handoff interfaces to AAM (Adaptive API Mesh).

ARCHITECTURE:
- AOD emits ConnectionCandidates to express connection INTENT + EVIDENCE
- AOD does NOT decide how to connect - AAM handles that
- AOD does NOT talk directly to DCL for provisioning

GUARDRAILS:
- AOD does NOT provision connectors
- AOD does NOT call DCL ingestion/provision endpoints
- AOD emits intent + evidence only
- If something is unknown, emit it as-is; do NOT infer connectivity details
"""

import logging
import os
from datetime import datetime, timezone
import httpx

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel, Field

from src.aod.db.database import get_db_direct
from src.aod.models.output_contracts import (
    ProvisioningStatus,
    ConnectionCandidate,
    CandidateFinding,
    CandidateSORTagging,
    CandidatePipeEvidence,
    CandidateFabricPlaneSummary,
    EvidenceLead,
    FabricPlaneRegistryEntry,
    ConnectionCandidatePayload,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/handoff")

_last_aam_export: Optional[dict] = None

# Maps AOD's internal FabricPlaneType values to AAM's FabricPlane enum keys.
# AOD's DATA_WAREHOUSE enum value is "warehouse"; AAM expects "DATA_WAREHOUSE".
# This must stay in sync with AAM's PLANE_TYPE_ALIASES and FabricPlane enum.
_AOD_PLANE_TO_AAM: dict[str, str] = {
    "ipaas": "IPAAS",
    "api_gateway": "API_GATEWAY",
    "event_bus": "EVENT_BUS",
    "warehouse": "DATA_WAREHOUSE",
    "data_warehouse": "DATA_WAREHOUSE",
}


class GovernanceInfo(BaseModel):
    """Governance metadata for AAM connection establishment"""
    owner: Optional[str] = None
    auth_method: Optional[str] = None


class ProvisioningOrder(BaseModel):
    """A single provisioning order for AAM to execute"""
    target_asset: str
    asset_id: str
    provisioning_status: str
    governance: GovernanceInfo
    action_required: str
    identifiers: dict
    vendor: Optional[str] = None
    environment: str


class AAMManifestResponse(BaseModel):
    """
    Target Manifest for AAM - what to connect to.
    
    Produced by AOD DiscoveryScan. The scan_session_id field is an alias for run_id,
    provided for clarity in the new DiscoveryScan terminology.
    """
    run_id: str
    scan_session_id: Optional[str] = Field(default=None, description="DiscoveryScan session ID (alias for run_id)")
    manifest_type: str = "provisioning_orders"
    orders: List[ProvisioningOrder]
    count: int


def determine_action_required(asset) -> str:
    """Determine what action AAM should take for this asset
    
    Action semantics:
    - MAINTAIN_CONNECTION: Asset is governed (IdP/CMDB), keep connection alive
    - ESTABLISH_CONNECTION: Asset is active but needs initial connection setup
    - SUSPEND_PENDING_REVIEW: Zombie candidate, pause until cleanup decision
    - DECOMMISSION: Asset was deprovisioned, terminate all connections
    - ENFORCE_BAN: Asset is blocked (banned shadow IT), actively block access
    - QUARANTINE_PENDING: Asset is quarantined, awaiting approval decision
    """
    if asset.provisioning_status == ProvisioningStatus.ACTIVE:
        if asset.lens_status.idp or asset.lens_status.cmdb:
            return "MAINTAIN_CONNECTION"
        return "ESTABLISH_CONNECTION"
    elif asset.provisioning_status == ProvisioningStatus.REVIEW:
        return "SUSPEND_PENDING_REVIEW"
    elif asset.provisioning_status == ProvisioningStatus.RETIRED:
        return "DECOMMISSION"
    elif asset.provisioning_status == ProvisioningStatus.BLOCKED:
        return "ENFORCE_BAN"
    elif asset.provisioning_status == ProvisioningStatus.QUARANTINE:
        return "QUARANTINE_PENDING"
    elif asset.provisioning_status == ProvisioningStatus.IGNORED:
        return "NO_ACTION"
    return "NO_ACTION"


def infer_auth_method(asset) -> Optional[str]:
    """Infer authentication method from asset evidence"""
    if asset.lens_status.idp:
        return "SSO"
    if asset.identifiers.domain and "okta" in (asset.vendor or "").lower():
        return "OAUTH2"
    return None


@router.get("/aam-manifest", response_model=AAMManifestResponse)
async def get_aam_manifest(
    run_id: str,
    status_filter: Optional[str] = Query(None, description="Filter by status: active, review, all")
):
    """
    AAM Handoff API - Target Manifest for Adaptive API Mesh
    
    This endpoint provides the "Target List" for AAM. It tells AAM WHAT to connect to,
    not what the data is. AAM then executes the connections and pipes to DCL.
    
    Architecture: AOD -> /handoff/aam-manifest -> AAM -> DCL
    
    By default, returns ACTIVE assets (trusted, ready for connection).
    Use status_filter='all' to see all provisioning statuses.
    """
    db = await get_db_direct()
    
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    all_assets = await db.get_assets_by_run(run_id)
    
    if status_filter == "all":
        filtered_assets = all_assets
    elif status_filter == "review":
        filtered_assets = [a for a in all_assets if a.provisioning_status == ProvisioningStatus.REVIEW]
    else:
        filtered_assets = [a for a in all_assets if a.provisioning_status == ProvisioningStatus.ACTIVE]
    
    orders = []
    for asset in filtered_assets:
        primary_domain = asset.identifiers.domains[0] if asset.identifiers.domains else None
        orders.append(ProvisioningOrder(
            target_asset=primary_domain or asset.name,
            asset_id=str(asset.asset_id),
            provisioning_status=asset.provisioning_status.value,
            governance=GovernanceInfo(
                owner=asset.owner,
                auth_method=infer_auth_method(asset)
            ),
            action_required=determine_action_required(asset),
            identifiers=asset.identifiers.model_dump(),
            vendor=asset.vendor,
            environment=asset.environment.value
        ))
    
    return AAMManifestResponse(
        run_id=run_id,
        scan_session_id=run_id,
        manifest_type="provisioning_orders",
        orders=orders,
        count=len(orders)
    )


class FabricPlaneSummary(BaseModel):
    """Summary of a fabric plane from Farm's authoritative data"""
    plane_type: str
    vendor: str
    display_name: str = Field(default="", description="Formatted name: 'Vendor, Plane Type'")
    is_healthy: bool = True
    source: str = "farm"


class SORSummary(BaseModel):
    """Summary of a System of Record from Farm's authoritative data"""
    domain: str
    sor_name: str
    sor_type: str
    confidence: str = "high"
    source: str = "farm"


class AAMCandidatesResponse(BaseModel):
    """
    Response for AAM candidates export.

    Produced by AOD DiscoveryScan. The scan_session_id field is an alias for run_id,
    provided for clarity in the new DiscoveryScan terminology.

    Includes Farm's authoritative fabric_planes and systems_of_record data.

    RACI Compliance (Feb 2026):
    - evidence_leads: Connection hints for AAM to validate via plane crawl
    - fabric_plane_registry: Detected planes (AOD identifies, AAM connects)
    """
    run_id: str
    scan_session_id: Optional[str] = Field(default=None, description="DiscoveryScan session ID (alias for run_id)")
    candidates: List[ConnectionCandidate]
    count: int
    fabric_planes: List[FabricPlaneSummary] = Field(default_factory=list, description="Farm's authoritative fabric planes")
    systems_of_record: List[SORSummary] = Field(default_factory=list, description="Farm's authoritative Systems of Record")

    # RACI Sprint additions - Evidence Lead Export
    evidence_leads: List[EvidenceLead] = Field(default_factory=list, description="Connection hints for AAM to validate")
    fabric_plane_registry: List[FabricPlaneRegistryEntry] = Field(default_factory=list, description="Detected fabric planes")
    enterprise_preset: str = Field(default="preset_unknown", description="Inferred org architecture pattern")
    preset_confidence: float = Field(default=0.0, description="Preset inference confidence")


def infer_category(asset) -> Optional[str]:
    """Infer asset category from vendor/domain patterns"""
    vendor_lower = (asset.vendor or "").lower()
    domains = asset.identifiers.domains if asset.identifiers else []
    domain_str = " ".join(domains).lower()
    
    if any(x in vendor_lower or x in domain_str for x in ["salesforce", "hubspot", "zoho", "pipedrive"]):
        return "crm"
    if any(x in vendor_lower or x in domain_str for x in ["netsuite", "sap", "oracle", "dynamics"]):
        return "erp"
    if any(x in vendor_lower or x in domain_str for x in ["quickbooks", "xero", "sage", "freshbooks"]):
        return "finance"
    if any(x in vendor_lower or x in domain_str for x in ["workday", "adp", "bamboohr", "gusto"]):
        return "hcm"
    if any(x in vendor_lower or x in domain_str for x in ["okta", "onelogin", "auth0", "ping"]):
        return "idp"
    if any(x in vendor_lower or x in domain_str for x in ["snowflake", "databricks", "bigquery", "redshift"]):
        return "data"
    if any(x in vendor_lower or x in domain_str for x in ["servicenow", "jira", "zendesk", "freshdesk"]):
        return "itsm"
    return None


def map_governance_status(provisioning_status: ProvisioningStatus) -> str:
    """Map provisioning status to governance status string"""
    mapping = {
        ProvisioningStatus.ACTIVE: "governed",
        ProvisioningStatus.REVIEW: "zombie",
        ProvisioningStatus.QUARANTINE: "shadow",
        ProvisioningStatus.BLOCKED: "shadow",
        ProvisioningStatus.RETIRED: "zombie",
        ProvisioningStatus.IGNORED: "edge",
    }
    return mapping.get(provisioning_status, "edge")


def build_signals_summary(asset) -> dict:
    """Build thin signals summary from asset"""
    return {
        "has_idp": asset.lens_coverage.idp if asset.lens_coverage else False,
        "has_cmdb": asset.lens_coverage.cmdb if asset.lens_coverage else False,
        "has_finance": asset.lens_coverage.finance if asset.lens_coverage else False,
        "has_discovery": asset.lens_coverage.discovery if asset.lens_coverage else False,
        "discovery_source_count": len(asset.discovery_sources) if asset.discovery_sources else 0,
        "domain_count": len(asset.identifiers.domains) if asset.identifiers else 0,
        "vendor_governed": asset.lens_coverage.vendor_governed if asset.lens_coverage else False,
    }


def calculate_priority_score(asset, findings: List) -> float:
    """Calculate priority score for connection ordering"""
    score = 0.0
    
    if asset.sor_tagging:
        if asset.sor_tagging.likelihood == "high":
            score += 50.0
        elif asset.sor_tagging.likelihood == "medium":
            score += 30.0
        elif asset.sor_tagging.likelihood == "low":
            score += 10.0
    
    if asset.provisioning_status == ProvisioningStatus.ACTIVE:
        score += 20.0
    elif asset.provisioning_status == ProvisioningStatus.REVIEW:
        score += 10.0
    
    critical_findings = sum(1 for f in findings if f.severity.value == "critical")
    score += critical_findings * 5.0
    
    return round(score, 2)


def determine_execution_flags(findings: list) -> tuple[bool, str]:
    """
    Determine execution flags based on findings.

    Returns:
        tuple: (execution_allowed, action_type)
        - execution_allowed: False if any critical/blocking findings exist
        - action_type: "inventory_only" if blocked, "provision" if clear

    Logic:
        - CRITICAL severity findings = blocking → execution_allowed=False
        - No critical findings = clear → execution_allowed=True
    """
    has_blocking = any(f.severity.value == "critical" for f in findings)

    if has_blocking:
        return (False, "inventory_only")
    return (True, "provision")


def build_pipe_evidence_for_asset(asset) -> tuple[list[CandidatePipeEvidence], Optional[CandidateFabricPlaneSummary]]:
    """
    Build pipe evidence from asset's fabric plane data.

    Extracts evidence-based fabric plane classification from asset.pipes
    and asset.fabric_plane_tag to provide AAM with full context.

    Returns:
        tuple: (pipes list, fabric_plane_summary)
    """
    pipes: list[CandidatePipeEvidence] = []

    # Check if asset has pipes from reconciliation
    if hasattr(asset, 'pipes') and asset.pipes:
        for pipe in asset.pipes:
            # Extract evidence sources
            evidence_sources = []
            if hasattr(pipe, 'classification_evidence') and pipe.classification_evidence:
                evidence_sources = list(set(
                    e.source_plane.value if hasattr(e, 'source_plane') else str(e.get('source_plane', 'unknown'))
                    for e in pipe.classification_evidence[:10]
                ))

            # Build top evidence descriptions
            top_evidence = []
            if hasattr(pipe, 'classification_evidence') and pipe.classification_evidence:
                for e in pipe.classification_evidence[:3]:
                    detail = e.signal_detail if hasattr(e, 'signal_detail') else e.get('signal_detail', '')
                    if detail:
                        top_evidence.append(detail[:100])

            pipe_evidence = CandidatePipeEvidence(
                pipe_id=pipe.pipe_id if hasattr(pipe, 'pipe_id') else str(pipe.get('pipe_id', 'unknown')),
                fabric_plane_type=pipe.fabric_plane.value if hasattr(pipe.fabric_plane, 'value') else str(pipe.fabric_plane),
                fabric_plane_vendor=pipe.fabric_plane_instance if hasattr(pipe, 'fabric_plane_instance') else None,
                modality=pipe.modality.value if hasattr(pipe.modality, 'value') else str(pipe.modality),
                evidence_tier=pipe.evidence_tier.value if hasattr(pipe.evidence_tier, 'value') else str(pipe.evidence_tier),
                classification_confidence=pipe.classification_confidence if hasattr(pipe, 'classification_confidence') else 0.5,
                classification_method=pipe.classification_method.value if hasattr(pipe.classification_method, 'value') else 'inferred',
                evidence_sources=evidence_sources,
                evidence_count=len(pipe.classification_evidence) if hasattr(pipe, 'classification_evidence') else 0,
                top_evidence=top_evidence,
                governance_status=pipe.governance_status.value if hasattr(pipe.governance_status, 'value') else 'known',
                has_contradictions=pipe.has_contradictions if hasattr(pipe, 'has_contradictions') else False,
                contradiction_note=pipe.contradiction_detail if hasattr(pipe, 'contradiction_detail') else None
            )
            pipes.append(pipe_evidence)

    # If no pipes but has fabric_plane_tag, create legacy pipe
    elif hasattr(asset, 'fabric_plane_tag') and asset.fabric_plane_tag:
        tag = asset.fabric_plane_tag
        pipe_evidence = CandidatePipeEvidence(
            pipe_id=f"legacy_{asset.asset_id}",
            fabric_plane_type=tag.plane_type.value if hasattr(tag, 'plane_type') and tag.plane_type else None,
            fabric_plane_vendor=tag.controller_vendor if hasattr(tag, 'controller_vendor') else None,
            modality='api',
            evidence_tier='tier_3_inferred',  # Legacy = Tier 3
            classification_confidence=0.40,  # Demoted confidence
            classification_method='inferred',
            evidence_sources=['legacy_inference'],
            evidence_count=1,
            top_evidence=[f"Legacy inference from fabric_plane_tag: {tag.controller_vendor}"],
            governance_status='known',
            has_contradictions=False
        )
        pipes.append(pipe_evidence)

    # Build summary
    summary = None
    if pipes:
        # Sort by confidence to get primary
        sorted_pipes = sorted(pipes, key=lambda p: p.classification_confidence, reverse=True)
        primary = sorted_pipes[0]

        # Get all unique plane types
        all_planes = list(set(p.fabric_plane_type for p in pipes))

        # Determine highest tier
        tier_order = {'tier_1_direct': 1, 'tier_2_observed': 2, 'tier_3_inferred': 3}
        highest_tier = min(pipes, key=lambda p: tier_order.get(p.evidence_tier, 3)).evidence_tier

        summary = CandidateFabricPlaneSummary(
            primary_plane=primary.fabric_plane_type,
            primary_vendor=primary.fabric_plane_vendor,
            primary_confidence=primary.classification_confidence,
            all_planes=all_planes,
            is_multi_plane=len(all_planes) > 1,
            total_evidence_count=sum(p.evidence_count for p in pipes),
            evidence_tier=highest_tier,
            has_shadow_plane=any(p.governance_status == 'shadow' for p in pipes),
            needs_investigation=any(p.has_contradictions or p.governance_status == 'investigation_needed' for p in pipes)
        )

    return pipes, summary


@router.post("/aam/candidates", response_model=AAMCandidatesResponse)
async def export_aam_candidates(
    run_id: str,
    status_filter: Optional[str] = Query(None, description="Filter by status: active, review, all")
):
    """
    Export ConnectionCandidates for AAM (Adaptive API Mesh).
    
    AOD emits ConnectionCandidates to express connection INTENT + EVIDENCE.
    AOD does NOT decide how to connect - AAM handles connectivity.
    
    Uses Farm's authoritative fabric_planes and sors data when available.
    This endpoint is idempotent and non-blocking.
    """
    db = await get_db_direct()
    
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    input_meta = run.input_meta or {}
    farm_sors = input_meta.get("sors", [])
    farm_fabric_planes = input_meta.get("fabric_planes", [])
    
    farm_sor_by_name: dict[str, dict] = {}
    for sor in farm_sors:
        sor_name = sor.get("sor_name", "").lower()
        if sor_name:
            farm_sor_by_name[sor_name] = sor
    
    farm_fabric_by_vendor: dict[str, dict] = {}
    for plane in farm_fabric_planes:
        vendor = plane.get("vendor", "").lower()
        if vendor:
            farm_fabric_by_vendor[vendor] = plane
    
    all_assets = await db.get_assets_by_run(run_id)
    all_findings = await db.get_findings_by_run(run_id)
    
    findings_by_asset = {}
    for f in all_findings:
        asset_id = str(f.asset_id) if f.asset_id else None
        if asset_id:
            if asset_id not in findings_by_asset:
                findings_by_asset[asset_id] = []
            findings_by_asset[asset_id].append(f)

    if status_filter == "all":
        filtered_assets = all_assets
    elif status_filter == "review":
        filtered_assets = [a for a in all_assets if a.provisioning_status == ProvisioningStatus.REVIEW]
    else:
        # Default: ACTIVE assets + any high/medium confidence SORs regardless of status
        # RACI: Recognized SORs must be handed off to AAM even if not yet governed
        active_assets = [a for a in all_assets if a.provisioning_status == ProvisioningStatus.ACTIVE]
        active_asset_ids = {str(a.asset_id) for a in active_assets}

        def is_sor_candidate(asset) -> bool:
            """Check if asset is a high/medium confidence SOR (AOD scoring OR Farm designation)"""
            # Check AOD's internal SOR scoring
            if asset.sor_tagging and asset.sor_tagging.likelihood in ("high", "medium"):
                return True

            # Check Farm's authoritative SOR list (high/medium confidence)
            asset_name_lower = (asset.name or "").lower()
            if asset_name_lower in farm_sor_by_name:
                farm_confidence = farm_sor_by_name[asset_name_lower].get("confidence", "").lower()
                if farm_confidence in ("high", "medium"):
                    return True

            return False

        # Add SORs that aren't already included
        sor_assets = [
            a for a in all_assets
            if is_sor_candidate(a)
            and str(a.asset_id) not in active_asset_ids
        ]

        if sor_assets:
            logger.info("handoff.aam_candidates.sor_inclusion", extra={
                "run_id": run_id,
                "sor_assets_added": len(sor_assets),
                "sor_names": [a.name for a in sor_assets[:10]],
                "reason": "High/medium confidence SORs included regardless of provisioning status"
            })

        filtered_assets = active_assets + sor_assets

    candidates = []
    for asset in filtered_assets:
        primary_domain = asset.identifiers.domains[0] if asset.identifiers and asset.identifiers.domains else None
        asset_key = primary_domain or asset.name
        
        asset_findings = findings_by_asset.get(str(asset.asset_id), [])
        thin_findings = [
            CandidateFinding(
                code=f.finding_type.value,
                severity=f.severity.value,
                message=f.explanation
            )
            for f in asset_findings
        ]
        
        thin_sor = None
        asset_name_lower = asset.name.lower() if asset.name else ""
        asset_vendor_lower = asset.vendor.lower() if asset.vendor else ""
        
        if asset_name_lower in farm_sor_by_name:
            farm_sor = farm_sor_by_name[asset_name_lower]
            thin_sor = CandidateSORTagging(
                domain=farm_sor.get("domain"),
                confidence=farm_sor.get("confidence", "high"),
                evidence=[f"Farm-designated {farm_sor.get('domain')} SOR"]
            )
        elif asset.sor_tagging and asset.sor_tagging.likelihood != "none":
            thin_sor = CandidateSORTagging(
                domain=asset.sor_tagging.domain,
                confidence=asset.sor_tagging.likelihood,
                evidence=asset.sor_tagging.evidence[:5]
            )
        
        connected_via = None
        if asset_vendor_lower in farm_fabric_by_vendor:
            plane = farm_fabric_by_vendor[asset_vendor_lower]
            connected_via = _AOD_PLANE_TO_AAM.get(plane.get("plane_type", "").lower())
        elif asset.fabric_plane_tag:
            # .name is the Python enum member name — maps directly to AAM's FabricPlane enum key
            # e.g. FabricPlaneType.DATA_WAREHOUSE.name == "DATA_WAREHOUSE"
            connected_via = asset.fabric_plane_tag.plane_type.name

        execution_allowed, action_type = determine_execution_flags(asset_findings)

        # Build evidence-based pipe data (Sprint 5 enhancement)
        asset_pipes, fabric_summary = build_pipe_evidence_for_asset(asset)

        # Update connected_via from pipe evidence if available (overrides tag/farm assignment)
        if fabric_summary and fabric_summary.primary_plane:
            connected_via = _AOD_PLANE_TO_AAM.get(fabric_summary.primary_plane) or connected_via

        candidate = ConnectionCandidate(
            asset_key=asset_key,
            vendor_name=asset.vendor,
            display_name=asset.name,
            category=infer_category(asset),
            governance_status=map_governance_status(asset.provisioning_status),
            findings=thin_findings,
            sor_tagging=thin_sor,
            evidence_refs=asset.evidence_refs[:20] if asset.evidence_refs else [],
            signals_summary=build_signals_summary(asset),
            known_endpoints=None,
            preferred_modality=None,
            priority_score=calculate_priority_score(asset, asset_findings),
            connected_via_plane=connected_via,
            execution_allowed=execution_allowed,
            action_type=action_type,
            # Evidence-based fabric plane data (Sprint 5)
            pipes=asset_pipes,
            fabric_plane_summary=fabric_summary
        )
        candidates.append(candidate)

    # Include Farm-designated SORs that weren't discovered by AOD
    # These are critical business systems that must be handed off to AAM
    discovered_names = {(a.name or "").lower() for a in filtered_assets}
    undiscovered_sors = []

    for sor in farm_sors:
        sor_name = sor.get("sor_name", "")
        sor_name_lower = sor_name.lower()
        confidence = sor.get("confidence", "").lower()

        # Only add high/medium confidence SORs that weren't already discovered
        if confidence in ("high", "medium") and sor_name_lower not in discovered_names:
            # Create a synthetic candidate for this Farm SOR
            sor_candidate = ConnectionCandidate(
                asset_key=f"{sor_name_lower}.com",  # Best guess at domain
                vendor_name=sor_name,
                display_name=sor_name,
                category=sor.get("domain"),  # e.g., "financial", "identity"
                governance_status="farm_designated",  # Special status for undiscovered SORs
                findings=[],
                sor_tagging=CandidateSORTagging(
                    domain=sor.get("domain"),
                    confidence=confidence,
                    evidence=[f"Farm-designated {sor.get('domain')} SOR (not discovered by AOD)"]
                ),
                evidence_refs=[],
                signals_summary={
                    "has_idp": False,
                    "has_cmdb": False,
                    "has_finance": False,
                    "has_discovery": False,
                    "discovery_source_count": 0,
                    "domain_count": 0,
                    "vendor_governed": False,
                    "farm_designated_sor": True
                },
                known_endpoints=None,
                preferred_modality=None,
                priority_score=100.0 if confidence == "high" else 75.0,  # High priority for SORs
                connected_via_plane=None,
                execution_allowed=True,
                action_type="discover_and_provision",  # AAM needs to discover this
                pipes=[],
                fabric_plane_summary=None
            )
            undiscovered_sors.append(sor_candidate)
            candidates.append(sor_candidate)

    if undiscovered_sors:
        logger.info("handoff.aam_candidates.undiscovered_sors_added", extra={
            "run_id": run_id,
            "count": len(undiscovered_sors),
            "sor_names": [c.display_name for c in undiscovered_sors],
            "reason": "Farm-designated SORs not discovered by AOD but must be handed off"
        })

    candidates.sort(key=lambda c: c.priority_score or 0, reverse=True)
    
    def _format_plane_display_name(plane_type: str, vendor: str) -> str:
        """Format fabric plane display name as 'Vendor, Plane Type'"""
        # Capitalize vendor nicely
        vendor_display = vendor.replace("_", " ").title()
        # Format plane type nicely
        plane_type_display = {
            'ipaas': 'iPaaS',
            'api_gateway': 'API Gateway',
            'event_bus': 'Event Bus',
            'data_warehouse': 'Data Warehouse',
        }.get(plane_type.lower(), plane_type.replace('_', ' ').title())
        return f"{vendor_display}, {plane_type_display}"

    fabric_plane_summaries = [
        FabricPlaneSummary(
            plane_type=p.get("plane_type", "unknown"),
            vendor=p.get("vendor", "unknown"),
            display_name=_format_plane_display_name(p.get("plane_type", ""), p.get("vendor", "")),
            is_healthy=p.get("is_healthy", True),
            source="farm"
        )
        for p in farm_fabric_planes
    ]
    
    sor_summaries = [
        SORSummary(
            domain=s.get("domain", "unknown"),
            sor_name=s.get("sor_name", "unknown"),
            sor_type=s.get("sor_type", "unknown"),
            confidence=s.get("confidence", "high"),
            source="farm"
        )
        for s in farm_sors
    ]
    
    # RACI Sprint: Retrieve evidence data from pipeline execution
    # This data was stored in run_log.input_meta during pipeline execution
    evidence_leads_raw = input_meta.get("_aod_evidence_leads", [])
    fabric_plane_registry_raw = input_meta.get("_aod_fabric_plane_registry", [])
    preset_context_raw = input_meta.get("_aod_preset_context", {})

    # Reconstruct EvidenceLead objects from stored JSON
    evidence_leads_out: List[EvidenceLead] = []
    for lead_data in evidence_leads_raw:
        try:
            evidence_leads_out.append(EvidenceLead.model_validate(lead_data))
        except Exception as e:
            logger.warning("handoff.aam_candidates.evidence_lead_parse_error", extra={
                "run_id": run_id,
                "error": str(e),
                "lead_data": str(lead_data)[:200]
            })

    # Reconstruct FabricPlaneRegistryEntry objects from stored JSON
    fabric_plane_registry_out: List[FabricPlaneRegistryEntry] = []
    for entry_data in fabric_plane_registry_raw:
        try:
            fabric_plane_registry_out.append(FabricPlaneRegistryEntry.model_validate(entry_data))
        except Exception as e:
            logger.warning("handoff.aam_candidates.registry_entry_parse_error", extra={
                "run_id": run_id,
                "error": str(e),
                "entry_data": str(entry_data)[:200]
            })

    # Extract preset information
    enterprise_preset = preset_context_raw.get("preset", "preset_unknown")
    preset_confidence = preset_context_raw.get("confidence", 0.0)

    logger.info("handoff.aam_candidates.exported", extra={
        "run_id": run_id,
        "candidate_count": len(candidates),
        "fabric_plane_count": len(fabric_plane_summaries),
        "sor_count": len(sor_summaries),
        "evidence_lead_count": len(evidence_leads_out),
        "fabric_registry_count": len(fabric_plane_registry_out),
        "enterprise_preset": enterprise_preset,
        "status_filter": status_filter or "active"
    })

    return AAMCandidatesResponse(
        run_id=run_id,
        scan_session_id=run_id,
        candidates=candidates,
        count=len(candidates),
        fabric_planes=fabric_plane_summaries,
        systems_of_record=sor_summaries,
        # RACI Sprint additions - Full ConnectionCandidatePayload
        evidence_leads=evidence_leads_out,
        fabric_plane_registry=fabric_plane_registry_out,
        enterprise_preset=enterprise_preset,
        preset_confidence=preset_confidence
    )


class AAMExportCandidate(BaseModel):
    """Candidate format for AAM receive endpoint"""
    asset_key: str
    vendor_name: str = "unknown"
    display_name: str
    category: str = "other"
    governance_status: str
    known_endpoints: List[str] = []
    execution_allowed: bool = True
    action_type: str = "provision"
    aod_run_id: str
    aod_asset_id: str


class AAMExportFabricPlane(BaseModel):
    """Fabric plane declaration for AAM"""
    plane_type: str
    vendor: str
    display_name: Optional[str] = None
    is_healthy: bool = True

class AAMExportSOR(BaseModel):
    """System of Record declaration for AAM"""
    app_name: str
    domain: str
    sor_type: Optional[str] = None
    declared_by: str = "farm"
    confidence: Optional[str] = None

class AAMExportRequest(BaseModel):
    """Request body for AAM /api/handoff/aod/receive"""
    run_id: str
    snapshot_name: Optional[str] = None
    candidates: List[AAMExportCandidate]
    fabric_planes: List[AAMExportFabricPlane] = []
    sors: List[AAMExportSOR] = []


class AAMExportResponse(BaseModel):
    """Response from AOD export to AAM"""
    success: bool
    message: str
    run_id: str
    candidates_sent: int
    aam_response: Optional[dict] = None


@router.post("/aam/export", response_model=AAMExportResponse)
async def export_to_aam(
    run_id: str,
    status_filter: Optional[str] = Query("all", description="Filter by status: active, review, all")
):
    """
    Export ConnectionCandidates to AAM (Adaptive API Mesh).
    
    This endpoint:
    1. Fetches candidates for the given run
    2. Formats them for AAM's expected schema
    3. POSTs to AAM's /api/handoff/aod/receive endpoint
    
    Requires AAM_URL environment variable to be set.
    """
    aam_url = os.environ.get("AAM_URL")
    if not aam_url:
        raise HTTPException(
            status_code=503,
            detail="AAM_URL environment variable not configured. Please set AAM_URL to the AAM service URL."
        )
    
    db = await get_db_direct()
    
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    all_assets = await db.get_assets_by_run(run_id)
    all_findings = await db.get_findings_by_run(run_id)
    
    findings_by_asset = {}
    for f in all_findings:
        asset_id = str(f.asset_id) if f.asset_id else None
        if asset_id:
            if asset_id not in findings_by_asset:
                findings_by_asset[asset_id] = []
            findings_by_asset[asset_id].append(f)
    
    if status_filter == "all":
        filtered_assets = all_assets
    elif status_filter == "review":
        filtered_assets = [a for a in all_assets if a.provisioning_status == ProvisioningStatus.REVIEW]
    else:
        filtered_assets = [a for a in all_assets if a.provisioning_status == ProvisioningStatus.ACTIVE]
    
    aam_candidates = []
    for asset in filtered_assets:
        primary_domain = asset.identifiers.domains[0] if asset.identifiers and asset.identifiers.domains else None
        asset_key = primary_domain or asset.name
        
        asset_findings = findings_by_asset.get(str(asset.asset_id), [])
        execution_allowed, action_type = determine_execution_flags(asset_findings)
        
        known_endpoints = []
        if asset.identifiers and asset.identifiers.domains:
            known_endpoints = [f"https://{d}" for d in asset.identifiers.domains[:5]]
        
        aam_candidate = AAMExportCandidate(
            asset_key=asset_key,
            vendor_name=asset.vendor or "unknown",
            display_name=asset.name,
            category=infer_category(asset) or "other",
            governance_status=map_governance_status(asset.provisioning_status),
            known_endpoints=known_endpoints,
            execution_allowed=execution_allowed,
            action_type=action_type,
            aod_run_id=run_id,
            aod_asset_id=str(asset.asset_id)
        )
        aam_candidates.append(aam_candidate)
    
    input_meta = run.input_meta or {}
    
    farm_fabric_planes = []
    for p in input_meta.get("fabric_planes", []):
        vendor = p.get("vendor", "")
        plane_type = p.get("plane_type", "")
        display_name = f"{vendor.replace('_', ' ').title()}, {plane_type.replace('_', ' ').title()}"
        farm_fabric_planes.append(AAMExportFabricPlane(
            plane_type=plane_type,
            vendor=vendor,
            display_name=display_name,
            is_healthy=p.get("is_healthy", True),
        ))
    
    farm_sors = []
    for s in input_meta.get("sors", []):
        farm_sors.append(AAMExportSOR(
            app_name=s.get("sor_name", ""),
            domain=s.get("domain", ""),
            sor_type=s.get("sor_type"),
            declared_by="farm",
            confidence=s.get("confidence"),
        ))
    
    export_payload = AAMExportRequest(
        run_id=run_id,
        snapshot_name=run.tenant_id,
        candidates=aam_candidates,
        fabric_planes=farm_fabric_planes,
        sors=farm_sors,
    )
    
    aam_endpoint = f"{aam_url.rstrip('/')}/api/handoff/aod/receive"
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                aam_endpoint,
                json=export_payload.model_dump(),
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code >= 400:
                logger.error("handoff.aam_export.failed", extra={
                    "run_id": run_id,
                    "status_code": response.status_code,
                    "response": response.text[:500]
                })
                raise HTTPException(
                    status_code=502,
                    detail=f"AAM rejected export: {response.status_code} - {response.text[:200]}"
                )
            
            aam_response = response.json() if response.text else {}
            
            global _last_aam_export
            _last_aam_export = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "run_id": run_id,
                "snapshot_name": run.tenant_id,
                "candidates_sent": len(aam_candidates),
                "aam_status_code": response.status_code,
                "aam_response": aam_response,
                "payload": export_payload.model_dump(),
            }
            
            logger.info("handoff.aam_export.success", extra={
                "run_id": run_id,
                "candidates_sent": len(aam_candidates),
                "aam_status": response.status_code
            })
            
            return AAMExportResponse(
                success=True,
                message=f"Successfully exported {len(aam_candidates)} candidates to AAM",
                run_id=run_id,
                candidates_sent=len(aam_candidates),
                aam_response=aam_response
            )
    except httpx.RequestError as e:
        logger.error("handoff.aam_export.connection_error", extra={
            "run_id": run_id,
            "error": str(e)
        })
        raise HTTPException(
            status_code=503,
            detail=f"Failed to connect to AAM: {str(e)}"
        )


@router.get("/aod/debug/last-receive")
async def debug_last_receive():
    """
    Debug endpoint for AAM to inspect the last payload AOD sent.
    Returns the full export payload from the most recent /aam/export call.
    """
    if _last_aam_export is None:
        return {
            "status": "no_export_yet",
            "message": "No export has been sent to AAM yet this session. Use POST /api/handoff/aam/export to send one.",
        }
    return _last_aam_export


@router.post("/provision-connector")
async def provision_connector_deprecated():
    """
    DEPRECATED: Direct DCL provisioning has been disabled.
    
    AOD no longer provisions connectors directly to DCL.
    Use POST /handoff/aam/candidates to export ConnectionCandidates,
    then let AAM handle connectivity decisions.
    
    GUARDRAILS:
    - AOD does NOT decide how to connect
    - AOD does NOT talk directly to DCL for provisioning
    - AOD emits intent + evidence only via ConnectionCandidates
    """
    raise HTTPException(
        status_code=410,
        detail="Endpoint deprecated. Use POST /handoff/aam/candidates to export connection candidates to AAM. AOD no longer provisions connectors directly."
    )


@router.get("/targeting-package")
async def get_targeting_package_deprecated():
    """
    DEPRECATED: Targeting package generation has been disabled.

    AOD no longer generates targeting packages for DCL.
    Use POST /handoff/aam/candidates instead.
    """
    raise HTTPException(
        status_code=410,
        detail="Endpoint deprecated. Use POST /handoff/aam/candidates instead."
    )


# ============================================================================
# Fabric Allocation Audit Trail
# ============================================================================

class AllocationDecision(BaseModel):
    """Single allocation decision record for audit trail"""
    decision: str = Field(description="Routed, Not Routed, Shadow Detected, Contradicted")
    asset_name: str = Field(description="Asset name")
    asset_id: str = Field(description="Asset ID")
    plane_assigned: Optional[str] = Field(default=None, description="Fabric plane assignment e.g. 'iPaaS (Workato)'")
    evidence_tier: Optional[str] = Field(default=None, description="Tier 1, Tier 2, Tier 3, or None")
    confidence: Optional[float] = Field(default=None, description="Classification confidence 0.0-1.0")
    rationale: str = Field(description="Plain-english explanation of decision")


class AllocationSummary(BaseModel):
    """Summary statistics for allocation audit"""
    total_assets_scanned: int = Field(description="Total assets processed")
    routed_tier_1: int = Field(description="Routed via Tier 1 (direct crawl)")
    routed_tier_2: int = Field(description="Routed via Tier 2 (observed)")
    routed_tier_3: int = Field(description="Routed via Tier 3 (inferred)")
    not_routed: int = Field(description="Not routed (no evidence)")
    shadow_detected: int = Field(description="Shadow assets detected")
    contradictions_flagged: int = Field(description="Contradictions flagged")
    multi_plane_sors: int = Field(description="SORs with multiple fabric planes")


class FabricAllocationAuditResponse(BaseModel):
    """Complete fabric allocation audit trail"""
    run_id: str
    scan_session_id: Optional[str] = None
    generated_at: str
    summary: AllocationSummary
    decisions: List[AllocationDecision]


def _build_rationale(pipe, asset) -> str:
    """Build plain-english rationale for allocation decision"""
    if not pipe:
        return "No fabric routing evidence found across any observation plane or direct crawl"

    evidence = pipe.classification_evidence if hasattr(pipe, 'classification_evidence') else []
    if not evidence:
        return "Classification assigned but no evidence details recorded"

    # Get the top evidence item
    top = evidence[0] if evidence else None
    if not top:
        return "Evidence recorded but details unavailable"

    source = top.source_plane.value if hasattr(top, 'source_plane') and hasattr(top.source_plane, 'value') else str(getattr(top, 'source_plane', 'unknown'))
    detail = top.signal_detail if hasattr(top, 'signal_detail') else str(getattr(top, 'signal_detail', ''))
    signal_type = top.signal_type if hasattr(top, 'signal_type') else ''

    # Build human-readable rationale based on evidence type
    plane_type = pipe.fabric_plane.value if hasattr(pipe.fabric_plane, 'value') else str(pipe.fabric_plane)
    vendor = pipe.fabric_plane_instance if hasattr(pipe, 'fabric_plane_instance') else None

    if source == 'direct_crawl':
        if 'workato' in (vendor or '').lower():
            return f"Found in Workato recipe catalog: \"{detail[:80]}\""
        elif 'kong' in (vendor or '').lower():
            return f"Found in Kong service registry: \"{detail[:80]}\""
        elif 'snowflake' in (vendor or '').lower():
            return f"Found in Snowflake information schema: \"{detail[:80]}\""
        elif 'mulesoft' in (vendor or '').lower():
            return f"Found in MuleSoft API registry: \"{detail[:80]}\""
        else:
            return f"Direct crawl from {vendor or plane_type}: \"{detail[:80]}\""
    elif source == 'network':
        return f"Network traffic to {detail[:60]} detected"
    elif source == 'cloud':
        return f"Cloud resource association: {detail[:80]}"
    elif source == 'cmdb':
        return f"CMDB dependency record: {detail[:80]}"
    elif source == 'finance':
        return f"Finance record indicates: {detail[:80]}"
    elif source == 'idp':
        return f"IdP authentication pattern: {detail[:80]}"
    else:
        return f"Evidence from {source}: {detail[:80]}"


def _determine_decision_type(asset, pipes) -> str:
    """Determine the decision type for an asset"""
    if not pipes:
        return "Not Routed"

    has_contradiction = any(
        (p.has_contradictions if hasattr(p, 'has_contradictions') else False)
        for p in pipes
    )
    if has_contradiction:
        return "Contradicted"

    has_shadow = any(
        (p.governance_status.value if hasattr(p.governance_status, 'value') else str(p.governance_status)) == 'shadow'
        for p in pipes
    )
    if has_shadow:
        return "Shadow Detected"

    return "Routed"


def _format_plane_assignment(pipe) -> Optional[str]:
    """Format plane assignment as 'Type (Vendor)'"""
    if not pipe:
        return None

    plane_type = pipe.fabric_plane.value if hasattr(pipe.fabric_plane, 'value') else str(pipe.fabric_plane)
    vendor = pipe.fabric_plane_instance if hasattr(pipe, 'fabric_plane_instance') else None

    # Capitalize plane type nicely
    type_display = {
        'ipaas': 'iPaaS',
        'api_gateway': 'API Gateway',
        'event_bus': 'Event Bus',
        'data_warehouse': 'Data Warehouse',
        'unmanaged': 'Unmanaged'
    }.get(plane_type, plane_type.replace('_', ' ').title())

    if vendor:
        vendor_display = vendor.replace('_', ' ').title()
        return f"{type_display} ({vendor_display})"
    return type_display


def _format_evidence_tier(pipe) -> Optional[str]:
    """Format evidence tier for display"""
    if not pipe:
        return None

    tier = pipe.evidence_tier.value if hasattr(pipe.evidence_tier, 'value') else str(getattr(pipe, 'evidence_tier', ''))

    tier_display = {
        'tier_1_direct': 'Tier 1',
        'tier_2_observed': 'Tier 2',
        'tier_3_inferred': 'Tier 3'
    }.get(tier, tier.replace('_', ' ').title() if tier else None)

    return tier_display


@router.get("/fabric-allocation-audit/{run_id}", response_model=FabricAllocationAuditResponse)
async def get_fabric_allocation_audit(run_id: str):
    """
    Get fabric allocation audit trail for a discovery scan.

    Provides a plain-english table of all allocation decisions showing:
    - Decision type (Routed, Not Routed, Shadow Detected, Contradicted)
    - Asset name and assigned fabric plane
    - Evidence tier and confidence
    - Human-readable rationale explaining the decision

    Plus summary statistics for quick assessment.
    """
    from datetime import datetime, timezone

    db = await get_db_direct()

    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    all_assets = await db.get_assets_by_run(run_id)

    # Build allocation decisions
    decisions: List[AllocationDecision] = []

    # Counters for summary
    routed_tier_1 = 0
    routed_tier_2 = 0
    routed_tier_3 = 0
    not_routed = 0
    shadow_detected = 0
    contradictions_flagged = 0
    multi_plane_sors = set()

    for asset in all_assets:
        asset_name = asset.name if hasattr(asset, 'name') else asset.get('name', 'Unknown')
        asset_id = str(asset.asset_id) if hasattr(asset, 'asset_id') else str(asset.get('asset_id', 'unknown'))

        # Check for fabric_plane_tag (persisted data)
        tag = None
        if hasattr(asset, 'fabric_plane_tag') and asset.fabric_plane_tag:
            tag = asset.fabric_plane_tag

        # Determine governance status for shadow detection
        is_shadow = False
        if hasattr(asset, 'lens_coverage') and asset.lens_coverage:
            lc = asset.lens_coverage
            has_idp = lc.idp if hasattr(lc, 'idp') else False
            has_cmdb = lc.cmdb if hasattr(lc, 'cmdb') else False
            # Shadow = has fabric plane tag but no governance
            if tag and not has_idp and not has_cmdb:
                is_shadow = True

        if not tag:
            # No fabric plane assignment
            not_routed += 1
            decisions.append(AllocationDecision(
                decision="Not Routed",
                asset_name=asset_name,
                asset_id=asset_id,
                plane_assigned=None,
                evidence_tier=None,
                confidence=None,
                rationale="No fabric plane tag assigned - asset not routed through detected fabric planes"
            ))
        else:
            # Has fabric plane tag
            plane_type = tag.plane_type.value if hasattr(tag.plane_type, 'value') else str(tag.plane_type) if tag.plane_type else 'unknown'
            vendor = tag.controller_vendor if hasattr(tag, 'controller_vendor') else None
            confidence = tag.confidence if hasattr(tag, 'confidence') else 0.5
            evidence = tag.evidence if hasattr(tag, 'evidence') else []

            # Determine tier based on confidence
            if confidence >= 0.90:
                tier = "Tier 1"
                routed_tier_1 += 1
            elif confidence >= 0.60:
                tier = "Tier 2"
                routed_tier_2 += 1
            else:
                tier = "Tier 3"
                routed_tier_3 += 1

            # Determine decision type
            if is_shadow:
                decision_type = "Shadow Detected"
                shadow_detected += 1
            else:
                decision_type = "Routed"

            # Format plane assignment
            type_display = {
                'ipaas': 'iPaaS',
                'api_gateway': 'API Gateway',
                'event_bus': 'Event Bus',
                'data_warehouse': 'Data Warehouse',
                'unmanaged': 'Unmanaged'
            }.get(plane_type, plane_type.replace('_', ' ').title() if plane_type else 'Unknown')

            if vendor:
                vendor_display = vendor.replace('_', ' ').title()
                plane_assigned = f"{type_display} ({vendor_display})"
            else:
                plane_assigned = type_display

            # Build rationale from evidence
            if evidence:
                rationale = "; ".join(evidence[:3])
            else:
                rationale = f"Assigned to {plane_assigned} based on fabric plane detection"

            if is_shadow:
                rationale = f"Found via fabric plane but not in IdP/CMDB: {rationale}"

            decisions.append(AllocationDecision(
                decision=decision_type,
                asset_name=asset_name,
                asset_id=asset_id,
                plane_assigned=plane_assigned,
                evidence_tier=tier,
                confidence=confidence,
                rationale=rationale
            ))

    # Build summary
    summary = AllocationSummary(
        total_assets_scanned=len(all_assets),
        routed_tier_1=routed_tier_1,
        routed_tier_2=routed_tier_2,
        routed_tier_3=routed_tier_3,
        not_routed=not_routed,
        shadow_detected=shadow_detected,
        contradictions_flagged=contradictions_flagged,
        multi_plane_sors=len(multi_plane_sors)
    )

    return FabricAllocationAuditResponse(
        run_id=run_id,
        scan_session_id=run_id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        summary=summary,
        decisions=decisions
    )
