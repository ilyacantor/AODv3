"""Triage action endpoints for AOD"""

from datetime import datetime, timedelta
import uuid

from fastapi import APIRouter, HTTPException

from ..schemas import TriageActionRequest, TriageActionResponse
from ...db.database import get_db_direct

router = APIRouter(prefix="/triage")


@router.post("/action", response_model=TriageActionResponse)
async def record_triage_action(request: TriageActionRequest):
    """Record a triage action (acknowledge, assign, defer, ignore)"""
    from datetime import datetime, timedelta
    
    db = await get_db_direct()
    
    run = await db.get_run(request.run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {request.run_id} not found")
    
    state_map = {
        "acknowledge": "acknowledged",
        "assign": "acknowledged",
        "defer": "deferred",
        "ignore": "ignored"
    }
    state = state_map.get(request.action, "new")
    
    defer_until = None
    if request.action == "defer" and request.defer_days:
        defer_until = (datetime.utcnow() + timedelta(days=request.defer_days)).isoformat()
    
    result = await db.save_triage_action(
        tenant_id=run.tenant_id,
        run_id=request.run_id,
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


@router.get("/actions/{run_id}")
async def get_triage_actions(run_id: str):
    """Get all triage actions for a run"""
    db = await get_db_direct()
    
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    actions = await db.get_triage_actions_by_run(run_id)
    
    return {"run_id": run_id, "actions": actions}
