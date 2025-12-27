"""
AAM Handoff API - Target Manifest for Adaptive API Mesh

AOD (Asset Observation & Discovery) identifies assets and their governance state.
AAM (Adaptive API Mesh) is the downstream consumer that executes connections.

This module provides the handoff interface between AOD and AAM.
AOD NEVER talks directly to DCL - it provides a Target Manifest to AAM.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel

from src.aod.db.database import get_db_direct
from src.aod.models.output_contracts import ProvisioningStatus

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
