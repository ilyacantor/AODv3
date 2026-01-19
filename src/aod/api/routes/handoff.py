"""
Handoff API - Target Manifests and Connector Provisioning

AOD (Asset Observation & Discovery) identifies assets and their governance state.
This module provides handoff interfaces to:
- AAM (Adaptive API Mesh) - Target Manifests for connection establishment
- DCL (Data Connectivity Layer) - Direct provisioning for the Ingest Sidecar

Phase 4: The Autonomous Handshake
AOD finds the route -> POSTs config to DCL -> DCL starts ingesting.
"""

import os
import logging

import httpx
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel

from src.aod.db.database import get_db_direct
from src.aod.models.output_contracts import ProvisioningStatus
from src.aod.pipeline.middleware_scanner import MiddlewareScanner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/handoff")

DCL_URL = os.environ.get("DCL_URL", "http://localhost:5001")
DCL_PROVISION_ENDPOINT = "/api/ingest/provision"


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
    """Target Manifest for AAM - what to connect to"""
    run_id: str
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
        manifest_type="provisioning_orders",
        orders=orders,
        count=len(orders)
    )


class ScanResponse(BaseModel):
    """Response from middleware scan."""
    platform: str
    detected_url: str
    related_asset: str
    confidence: float
    stream_type: str


class ScanAllResponse(BaseModel):
    """Response from scan-all request."""
    routes: list[ScanResponse]
    count: int


class ProvisionRequest(BaseModel):
    """Request to provision a connector to DCL."""
    platform: str = "mulesoft"
    chaos_mode: bool = True
    dcl_url: Optional[str] = None


class ProvisionResponse(BaseModel):
    """Response from provision request."""
    status: str
    message: str
    connector_id: str
    dcl_response: Optional[dict] = None


@router.get("/scan-middleware", response_model=ScanResponse)
async def scan_middleware(platform: str = "mulesoft"):
    """
    Scan for middleware integration routes.
    
    Returns detected middleware route configuration for platforms like
    MuleSoft, Workato, Zapier, etc.
    """
    scanner = MiddlewareScanner()
    route = scanner.scan(platform)
    
    return ScanResponse(
        platform=route.platform,
        detected_url=route.detected_url,
        related_asset=route.related_asset,
        confidence=route.confidence,
        stream_type=route.stream_type
    )


@router.get("/scan-middleware/all", response_model=ScanAllResponse)
async def scan_middleware_all():
    """
    Scan for all known middleware integration routes.
    
    Returns list of all detected middleware routes across known platforms.
    """
    scanner = MiddlewareScanner()
    routes = scanner.scan_all()
    
    return ScanAllResponse(
        routes=[
            ScanResponse(
                platform=r.platform,
                detected_url=r.detected_url,
                related_asset=r.related_asset,
                confidence=r.confidence,
                stream_type=r.stream_type
            )
            for r in routes
        ],
        count=len(routes)
    )


@router.post("/provision-connector", response_model=ProvisionResponse)
async def provision_connector(request: ProvisionRequest):
    """
    Provision a connector from AOD to DCL (The Autonomous Handshake).
    
    Flow:
    1. AOD scans for middleware route
    2. AOD generates Targeting Package
    3. AOD POSTs to DCL's provision endpoint
    4. DCL reconfigures its Ingest Sidecar
    
    Returns provisioning status and the targeting package sent.
    """
    scanner = MiddlewareScanner()
    route = scanner.scan(request.platform)
    
    targeting_package = scanner.to_targeting_package(route, chaos_mode=request.chaos_mode)
    
    dcl_url = (request.dcl_url or DCL_URL).rstrip("/")
    provision_url = f"{dcl_url}{DCL_PROVISION_ENDPOINT}"
    
    logger.info("handoff.provision_connector", extra={
        "platform": request.platform,
        "connector_id": targeting_package["connector_id"],
        "target_url": targeting_package["target_url"],
        "dcl_url": provision_url
    })
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                provision_url,
                json=targeting_package
            )
            
            if response.status_code == 200:
                dcl_response = response.json()
                return ProvisionResponse(
                    status="success",
                    message="Provisioning Command Sent",
                    connector_id=targeting_package["connector_id"],
                    dcl_response=dcl_response
                )
            else:
                logger.warning("handoff.provision_connector.dcl_error", extra={
                    "status_code": response.status_code,
                    "response": response.text[:500]
                })
                return ProvisionResponse(
                    status="dcl_error",
                    message=f"DCL returned {response.status_code}: {response.text[:200]}",
                    connector_id=targeting_package["connector_id"],
                    dcl_response=None
                )
                
    except httpx.ConnectError:
        logger.warning("handoff.provision_connector.dcl_unreachable", extra={
            "dcl_url": provision_url
        })
        return ProvisionResponse(
            status="dcl_unreachable",
            message=f"DCL not reachable at {dcl_url}. Package ready for manual provisioning.",
            connector_id=targeting_package["connector_id"],
            dcl_response={"targeting_package": targeting_package}
        )
        
    except httpx.TimeoutException:
        return ProvisionResponse(
            status="timeout",
            message="DCL provision request timed out",
            connector_id=targeting_package["connector_id"],
            dcl_response=None
        )
        
    except Exception as e:
        logger.exception("handoff.provision_connector.error")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to provision connector: {str(e)}"
        )


@router.get("/targeting-package")
async def get_targeting_package(platform: str = "mulesoft", chaos_mode: bool = True):
    """
    Get the Targeting Package without sending to DCL.
    
    Useful for debugging or manual provisioning scenarios.
    Returns both the detected route and the formatted targeting package.
    """
    scanner = MiddlewareScanner()
    route = scanner.scan(platform)
    package = scanner.to_targeting_package(route, chaos_mode=chaos_mode)
    
    return {
        "detected_route": {
            "platform": route.platform,
            "detected_url": route.detected_url,
            "related_asset": route.related_asset,
            "confidence": route.confidence
        },
        "targeting_package": package
    }
