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
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/handoff")


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
    """
    run_id: str
    scan_session_id: Optional[str] = Field(default=None, description="DiscoveryScan session ID (alias for run_id)")
    candidates: List[ConnectionCandidate]
    count: int
    fabric_planes: List[FabricPlaneSummary] = Field(default_factory=list, description="Farm's authoritative fabric planes")
    systems_of_record: List[SORSummary] = Field(default_factory=list, description="Farm's authoritative Systems of Record")


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
        filtered_assets = [a for a in all_assets if a.provisioning_status == ProvisioningStatus.ACTIVE]
    
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
            vendor_display = plane.get("vendor", "").replace("_", " ").title()
            connected_via = f"Connect via {vendor_display}"
        elif asset.fabric_plane_tag:
            vendor_display = asset.fabric_plane_tag.controller_vendor.replace("_", " ").title()
            connected_via = f"Connect via {vendor_display}"
        
        execution_allowed, action_type = determine_execution_flags(asset_findings)
        
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
            action_type=action_type
        )
        candidates.append(candidate)
    
    candidates.sort(key=lambda c: c.priority_score or 0, reverse=True)
    
    fabric_plane_summaries = [
        FabricPlaneSummary(
            plane_type=p.get("plane_type", "unknown"),
            vendor=p.get("vendor", "unknown"),
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
    
    logger.info("handoff.aam_candidates.exported", extra={
        "run_id": run_id,
        "candidate_count": len(candidates),
        "fabric_plane_count": len(fabric_plane_summaries),
        "sor_count": len(sor_summaries),
        "status_filter": status_filter or "active"
    })
    
    return AAMCandidatesResponse(
        run_id=run_id,
        scan_session_id=run_id,
        candidates=candidates,
        count=len(candidates),
        fabric_planes=fabric_plane_summaries,
        systems_of_record=sor_summaries
    )


class AAMExportCandidate(BaseModel):
    """Candidate format for AAM receive endpoint"""
    asset_key: str
    vendor_name: Optional[str] = None
    display_name: str
    category: Optional[str] = None
    governance_status: str
    known_endpoints: Optional[List[str]] = None
    execution_allowed: bool = True
    action_type: str = "provision"
    aod_run_id: str
    aod_asset_id: str


class AAMExportRequest(BaseModel):
    """Request body for AAM /api/handoff/aod/receive"""
    run_id: str
    candidates: List[AAMExportCandidate]


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
            vendor_name=asset.vendor,
            display_name=asset.name,
            category=infer_category(asset),
            governance_status=map_governance_status(asset.provisioning_status),
            known_endpoints=known_endpoints if known_endpoints else None,
            execution_allowed=execution_allowed,
            action_type=action_type,
            aod_run_id=run_id,
            aod_asset_id=str(asset.asset_id)
        )
        aam_candidates.append(aam_candidate)
    
    export_payload = AAMExportRequest(
        run_id=run_id,
        candidates=aam_candidates
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
