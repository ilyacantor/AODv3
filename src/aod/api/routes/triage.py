"""Triage action endpoints for AOD"""

from datetime import datetime, timedelta
import uuid

from fastapi import APIRouter, HTTPException

from ..schemas import TriageActionRequest, TriageActionResponse
from ...db.database import get_db_direct

router = APIRouter(prefix="/triage")


@router.post("/action", response_model=TriageActionResponse)
async def record_triage_action(request: TriageActionRequest):
    """Record a triage action (acknowledge, assign, defer, ignore)
    
    For 'assign' action: Also updates asset.owner to fix governance_gap finding.
    This ensures the "Missing Owner" finding disappears on future runs.
    """
    from datetime import datetime, timedelta
    
    db = await get_db_direct()
    
    run = await db.get_run(request.aod_discovery_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {request.aod_discovery_id} not found")
    
    state_map = {
        "acknowledge": "acknowledged",
        "assign": "assigned",
        "defer": "deferred",
        "ignore": "ignored"
    }
    state = state_map.get(request.action, "new")
    
    defer_until = None
    if request.action == "defer" and request.defer_days:
        defer_until = (datetime.utcnow() + timedelta(days=request.defer_days)).isoformat()
    
    if request.action == "assign" and request.owner and request.item_type in ("asset", "shadow", "zombie", "hygiene", "toxic", "blocked"):
        await db.update_asset_owner(request.item_id, request.owner)
    
    result = await db.save_triage_action(
        tenant_id=run.tenant_id,
        run_id=request.aod_discovery_id,
        item_id=request.item_id,
        item_type=request.item_type,
        action=request.action,
        state=state,
        owner=request.owner,
        defer_until=defer_until,
        ignore_reason=request.ignore_reason
    )
    
    return TriageActionResponse(
        success=True,
        action_id=result["action_id"],
        item_id=result["item_id"],
        item_type=result["item_type"],
        action=result["action"],
        state=result["state"],
        owner=result.get("owner"),
        defer_until=result.get("defer_until"),
        ignore_reason=result.get("ignore_reason")
    )


@router.get("/actions/{aod_discovery_id}")
async def get_triage_actions(aod_discovery_id: str):
    """Get all triage actions for a run"""
    db = await get_db_direct()

    run = await db.get_run(aod_discovery_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {aod_discovery_id} not found")

    actions = await db.get_triage_actions_by_run(aod_discovery_id)

    return {"aod_discovery_id": aod_discovery_id, "actions": actions}


@router.delete("/action/{aod_discovery_id}/{item_id}")
async def revert_triage_action(aod_discovery_id: str, item_id: str):
    """Revert/undo a triage action by deleting it"""
    db = await get_db_direct()

    run = await db.get_run(aod_discovery_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {aod_discovery_id} not found")

    deleted = await db.delete_triage_action(aod_discovery_id, item_id)
    
    return {"success": True, "deleted": deleted, "item_id": item_id}
