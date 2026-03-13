"""Maestra status endpoint for AOD.

Provides a read-only window into AOD's current discovery state for a given tenant.
Used by Maestra (the AI engagement lead for AOS Convergence) to understand
where each module stands before orchestrating cross-module workflows.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ...db.database import get_db_direct
from ...models.output_contracts import RunStatus, ProvisioningStatus, FabricPlaneType
from ...pipeline.derived_classifications import compute_derived_classifications
from ...core.policy import get_current_config
from ..routes.utils import get_run_snapshot_as_of as _get_run_snapshot_as_of

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/maestra")


def _map_run_status_to_phase(status: RunStatus) -> str:
    """Map AOD RunStatus to Maestra's discovery_phase vocabulary."""
    if status in (RunStatus.PENDING,):
        return "pending"
    if status in (RunStatus.RUNNING,):
        return "running"
    if status in (
        RunStatus.COMPLETED,
        RunStatus.COMPLETED_WITH_RESULTS,
        RunStatus.COMPLETED_NO_ASSETS,
    ):
        return "complete"
    # FAILED, INVALID_SNAPSHOT, INVALID_INPUT_CONTRACT, UPSTREAM_ERROR
    # are terminal non-success states — report as complete (the run finished,
    # but with errors). Maestra can check healthy=false for failure detail.
    return "complete"


def _build_fabric_availability(run) -> dict:
    """Build fabric_availability from the run's input_meta.

    The session spec asks for: identity, collaboration, operations, data.
    AOD's fabric plane types are: ipaas, api_gateway, event_bus, warehouse.

    Mapping:
      - identity   → no direct AOD fabric plane (IdP is a lens, not a fabric plane)
                     GAP: AOD detects IdP presence via lens correlation, not fabric planes.
                     We report True if the run has any IdP-matched assets.
      - collaboration → ipaas (integration platform = collaboration backbone)
      - operations    → api_gateway or event_bus (operational connectivity)
      - data          → warehouse (data plane)
    """
    fabric_planes = []
    if run.input_meta:
        farm_planes = run.input_meta.get("fabric_planes")
        if farm_planes and isinstance(farm_planes, list):
            fabric_planes = farm_planes

    plane_types_present = set()
    for fp in fabric_planes:
        pt = fp.get("plane_type", "").lower()
        if pt:
            plane_types_present.add(pt)

    return {
        # GAP: identity availability is not tracked as a fabric plane in AOD.
        # IdP is a correlation lens, not a fabric control plane.
        # Defaulting to False; a future enhancement could check IdP lens match rate.
        "identity": False,
        "collaboration": "ipaas" in plane_types_present,
        "operations": bool(
            {"api_gateway", "event_bus"} & plane_types_present
        ),
        "data": "warehouse" in plane_types_present or "data_warehouse" in plane_types_present,
    }


def _build_fabric_availability_from_assets(assets) -> dict:
    """Fallback: compute fabric availability from asset fabric_plane_tags."""
    plane_types_present = set()
    for asset in assets:
        if asset.fabric_plane_tag:
            pt = asset.fabric_plane_tag.plane_type
            pt_val = pt.value if hasattr(pt, "value") else str(pt)
            plane_types_present.add(pt_val.lower())

    return {
        # GAP: identity availability — see note in _build_fabric_availability
        "identity": False,
        "collaboration": "ipaas" in plane_types_present,
        "operations": bool(
            {"api_gateway", "event_bus"} & plane_types_present
        ),
        "data": "warehouse" in plane_types_present or "data_warehouse" in plane_types_present,
    }


@router.get("/status")
async def maestra_status(tenant_id: str = Query(..., description="Tenant ID to query status for")):
    """
    Maestra status endpoint — read-only window into AOD discovery state.

    Returns structured JSON describing the current discovery state for the
    given tenant. Queries existing AOD state only — no new business logic.
    """
    db = await get_db_direct()

    run = await db.get_latest_run_for_tenant(tenant_id)

    # No run exists for this tenant — return empty defaults
    if not run:
        return {
            "module": "aod",
            "tenant_id": tenant_id,
            "discovery_phase": "pending",
            "systems_discovered": {"count": 0, "list": []},
            "shadows_detected": {"count": 0, "list": []},
            "governance_items": {"count": 0, "items": []},
            "fabric_availability": {
                "identity": False,
                "collaboration": False,
                "operations": False,
                "data": False,
            },
            "last_run_at": None,
            "healthy": True,
        }

    # Fetch assets and findings for this run
    assets = await db.get_assets_by_run(run.run_id)
    findings = await db.get_findings_by_run(run.run_id)

    # Discovery phase
    discovery_phase = _map_run_status_to_phase(run.status)

    # Systems discovered — all admitted assets
    systems_list = sorted(set(a.name for a in assets))

    # Shadows detected — assets with QUARANTINE provisioning status
    shadow_list = sorted(set(
        a.name for a in assets
        if a.provisioning_status == ProvisioningStatus.QUARANTINE
    ))

    # Governance items — findings from this run
    governance_items = [
        {
            "finding_id": str(f.finding_id),
            "type": f.finding_type.value,
            "category": f.category.value,
            "severity": f.severity.value,
            "explanation": f.explanation,
        }
        for f in findings
    ]

    # Fabric availability — from Farm-provided metadata or computed from assets
    farm_planes = run.input_meta.get("fabric_planes") if run.input_meta else None
    if farm_planes and isinstance(farm_planes, list) and len(farm_planes) > 0:
        fabric_availability = _build_fabric_availability(run)
    else:
        fabric_availability = _build_fabric_availability_from_assets(assets)

    # last_run_at — use completed_at if available, else started_at
    last_run_at = None
    if run.completed_at:
        last_run_at = run.completed_at.isoformat()
    elif run.started_at:
        last_run_at = run.started_at.isoformat()

    # healthy — True if the latest run completed successfully
    run_succeeded = run.status in (
        RunStatus.COMPLETED,
        RunStatus.COMPLETED_WITH_RESULTS,
        RunStatus.COMPLETED_NO_ASSETS,
    )

    return {
        "module": "aod",
        "tenant_id": tenant_id,
        "discovery_phase": discovery_phase,
        "systems_discovered": {"count": len(systems_list), "list": systems_list},
        "shadows_detected": {"count": len(shadow_list), "list": shadow_list},
        "governance_items": {"count": len(governance_items), "items": governance_items},
        "fabric_availability": fabric_availability,
        "last_run_at": last_run_at,
        "healthy": run_succeeded,
    }
