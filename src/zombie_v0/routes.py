"""
Zombie v0 Routes - Walled-off API endpoints

These endpoints are completely isolated from the main pipeline.
They do NOT reuse existing reconciliation payload logic.

Route prefix: /v0
"""

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from .compute import compute_zombies_v0

router = APIRouter(prefix="/v0", tags=["zombie-v0"])


class ZombieV0Item(BaseModel):
    """Single zombie v0 result item"""
    asset_id: str
    exists_in_sor: bool
    activity_in_window: bool
    zombie: bool
    last_activity_observed_at: Optional[datetime]
    reason: str


class ZombieV0Response(BaseModel):
    """Response from /v0/zombies endpoint"""
    run_id: str
    window_days: int
    zombies: list[ZombieV0Item]
    total_assets: int
    zombie_count: int


@router.get("/zombies", response_model=ZombieV0Response)
async def get_zombies_v0(
    run_id: str = Query(..., description="Run ID to analyze"),
    window_days: int = Query(..., description="Activity window in days (required, no default)")
):
    """
    Get zombie v0 classifications for a run.
    
    This endpoint is completely walled-off from the main pipeline.
    It does NOT reuse existing reconciliation payload logic.
    
    Zombie Definition:
    - exists_in_sor = present in any System of Record (IdP, CMDB, Cloud, Finance)
    - activity_in_window = any observed_at timestamp within window_days
    - zombie = exists_in_sor AND NOT activity_in_window
    
    No ML, no thresholds, no anomaly scores.
    """
    if window_days <= 0:
        raise HTTPException(status_code=400, detail="window_days must be positive")
    
    try:
        results = await compute_zombies_v0(run_id, window_days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error computing zombies: {str(e)}")
    
    zombies = [
        ZombieV0Item(
            asset_id=r.asset_id,
            exists_in_sor=r.exists_in_sor,
            activity_in_window=r.activity_in_window,
            zombie=r.zombie,
            last_activity_observed_at=r.last_activity_observed_at,
            reason=r.reason
        )
        for r in results
        if r.zombie
    ]
    
    return ZombieV0Response(
        run_id=run_id,
        window_days=window_days,
        zombies=zombies,
        total_assets=len(results),
        zombie_count=len(zombies)
    )


@router.get("/zombies/all", response_model=ZombieV0Response)
async def get_all_assets_v0(
    run_id: str = Query(..., description="Run ID to analyze"),
    window_days: int = Query(..., description="Activity window in days (required, no default)")
):
    """
    Get ALL asset zombie v0 classifications for a run (not just zombies).
    
    Useful for debugging and viewing the full table.
    """
    if window_days <= 0:
        raise HTTPException(status_code=400, detail="window_days must be positive")
    
    try:
        results = await compute_zombies_v0(run_id, window_days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error computing zombies: {str(e)}")
    
    all_items = [
        ZombieV0Item(
            asset_id=r.asset_id,
            exists_in_sor=r.exists_in_sor,
            activity_in_window=r.activity_in_window,
            zombie=r.zombie,
            last_activity_observed_at=r.last_activity_observed_at,
            reason=r.reason
        )
        for r in results
    ]
    
    zombie_count = sum(1 for r in results if r.zombie)
    
    return ZombieV0Response(
        run_id=run_id,
        window_days=window_days,
        zombies=all_items,
        total_assets=len(results),
        zombie_count=zombie_count
    )
