"""Zombie v0 API - completely isolated, read-only database access.

Route prefix: /experimental/zombie_v0
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import json

from .types import ZombieV0Response, ZombieV0Result
from .logic import classify_zombie_v0

router = APIRouter(prefix="/experimental/zombie_v0", tags=["Zombie v0 Experimental"])


@router.get("/zombies", response_model=ZombieV0Response)
async def get_zombies(
    run_id: str = Query(..., description="Run ID to analyze"),
    window_days: int = Query(..., description="Activity window in days")
):
    """
    Get zombie classifications for all assets in a run.
    
    Zombie rule (binary): zombie = exists_in_sor AND NOT activity_in_window
    
    This is a read-only endpoint that does NOT:
    - Write to the database
    - Emit data to Farm
    - Call existing zombie logic
    """
    if not run_id:
        raise HTTPException(status_code=400, detail="run_id is required")
    if window_days is None or window_days < 1:
        raise HTTPException(status_code=400, detail="window_days is required and must be positive")
    
    from aod.db.database import get_db
    
    db = await get_db()
    pool = await db.get_pool()
    
    async with pool.acquire() as conn:
        run_row = await conn.fetchrow("SELECT run_id, status FROM runs WHERE run_id = $1", run_id)
        if not run_row:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
        
        asset_rows = await conn.fetch(
            """
            SELECT asset_id, name, lens_status, activity_evidence
            FROM assets
            WHERE run_id = $1
            """,
            run_id
        )
    
    results: list[ZombieV0Result] = []
    
    for row in asset_rows:
        asset_id = row["name"] or str(row["asset_id"])
        
        lens_status_raw = row["lens_status"]
        if isinstance(lens_status_raw, str):
            lens_status = json.loads(lens_status_raw)
        elif lens_status_raw is None:
            lens_status = {}
        else:
            lens_status = dict(lens_status_raw)
        
        activity_raw = row["activity_evidence"]
        if isinstance(activity_raw, str):
            activity_evidence = json.loads(activity_raw)
        elif activity_raw is None:
            activity_evidence = {}
        else:
            activity_evidence = dict(activity_raw)
        
        result = classify_zombie_v0(
            asset_id=asset_id,
            lens_status=lens_status,
            activity_evidence=activity_evidence,
            window_days=window_days
        )
        results.append(result)
    
    return ZombieV0Response(
        run_id=run_id,
        window_days=window_days,
        results=results
    )
