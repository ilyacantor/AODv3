"""
Zombie v0 Standalone App

A completely isolated FastAPI application for zombie classification.
Does NOT import or depend on any existing AOD modules.

Per Zombie Recognition Contract v1.0:
- Binary classification only (ZOMBIE or NOT_ZOMBIE)
- No anomaly scores, percentile cutoffs, or confidence values
- Evidence exhaustiveness - all sources checked must be enumerated
- window_days must be explicit (no defaults)
"""

import os
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import asyncpg
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field


app = FastAPI(
    title="Zombie v0 Standalone",
    description="Isolated zombie classification API - read-only DB access",
    version="0.1.0"
)


class ZombieResult(BaseModel):
    """Contract-compliant zombie classification result"""
    run_id: str
    asset_id: str
    classification: str = Field(description="ZOMBIE or NOT_ZOMBIE")
    window_days: int
    evidence_checked: list[str]
    last_activity_observed_at: Optional[str] = None
    reason: str


class ZombieResponse(BaseModel):
    """Response containing all zombie classifications for a run"""
    run_id: str
    window_days: int
    results: list[ZombieResult]


def get_db_url() -> str:
    """Get database URL - fail fast if not configured"""
    url = os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("No database configured. Set SUPABASE_DB_URL or DATABASE_URL.")
    return url


async def get_connection() -> asyncpg.Connection:
    """Get a database connection"""
    return await asyncpg.connect(get_db_url())


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok", "app": "zombie_v0_standalone"}


@app.get("/zombies", response_model=ZombieResponse)
async def get_zombies(
    run_id: str = Query(..., description="The run ID to analyze"),
    window_days: int = Query(..., description="Activity window in days - REQUIRED")
):
    """
    Get zombie classifications for all assets in a run.
    
    Zombie Definition (binary):
    1. Exists - Asset appears in ≥1 system of record (CMDB, Billing, IdP, Cloud)
    2. No activity within window - No observed_at ≥ (now - window_days)
    
    FORBIDDEN:
    - Anomaly scores, percentile cutoffs, "low usage" heuristics
    - Inferred last_seen, generated_at as activity
    - Confidence/probability outputs
    """
    evidence_checked = ["IdP", "CMDB", "Cloud", "Billing", "AccessLogs"]
    
    try:
        conn = await get_connection()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")
    
    try:
        run_check = await conn.fetchrow(
            "SELECT run_id FROM runs WHERE run_id = $1",
            run_id
        )
        if not run_check:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
        
        assets = await conn.fetch(
            """
            SELECT 
                asset_id::text,
                name,
                lens_status,
                activity_evidence
            FROM assets 
            WHERE run_id = $1
            """,
            run_id
        )
        
        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
        results: list[ZombieResult] = []
        
        for asset in assets:
            asset_id = asset["asset_id"]
            lens_status = asset["lens_status"] or {}
            activity_evidence = asset["activity_evidence"] or {}
            
            exists_in_sor = False
            existence_sources: list[str] = []
            
            if lens_status.get("idp") == "matched":
                exists_in_sor = True
                existence_sources.append("IdP")
            if lens_status.get("cmdb") == "matched":
                exists_in_sor = True
                existence_sources.append("CMDB")
            if lens_status.get("cloud") == "matched":
                exists_in_sor = True
                existence_sources.append("Cloud")
            if lens_status.get("finance") == "matched":
                exists_in_sor = True
                existence_sources.append("Billing")
            
            if not exists_in_sor:
                results.append(ZombieResult(
                    run_id=run_id,
                    asset_id=asset_id,
                    classification="NOT_ZOMBIE",
                    window_days=window_days,
                    evidence_checked=evidence_checked,
                    last_activity_observed_at=None,
                    reason="Asset does not exist in any system of record (IdP, CMDB, Cloud, Billing)."
                ))
                continue
            
            activity_timestamps: list[datetime] = []
            
            for key in ["idp_last_login_at", "discovery_observed_at", "cloud_observed_at", 
                        "endpoint_last_seen_at", "network_last_seen_at", "finance_last_transaction_at",
                        "latest_activity_at"]:
                ts_val = activity_evidence.get(key)
                if ts_val:
                    try:
                        if isinstance(ts_val, str):
                            ts = datetime.fromisoformat(ts_val.replace("Z", "+00:00"))
                        elif isinstance(ts_val, datetime):
                            ts = ts_val
                        else:
                            continue
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                        activity_timestamps.append(ts)
                    except (ValueError, TypeError):
                        pass
            
            if not activity_timestamps:
                results.append(ZombieResult(
                    run_id=run_id,
                    asset_id=asset_id,
                    classification="ZOMBIE",
                    window_days=window_days,
                    evidence_checked=evidence_checked,
                    last_activity_observed_at=None,
                    reason=f"Asset exists in {', '.join(existence_sources)} but has no observed activity timestamps."
                ))
                continue
            
            latest_activity = max(activity_timestamps)
            latest_str = latest_activity.isoformat()
            
            if latest_activity < cutoff:
                results.append(ZombieResult(
                    run_id=run_id,
                    asset_id=asset_id,
                    classification="ZOMBIE",
                    window_days=window_days,
                    evidence_checked=evidence_checked,
                    last_activity_observed_at=latest_str,
                    reason=f"Asset exists in {', '.join(existence_sources)} but last activity was {latest_activity.strftime('%Y-%m-%d')}, outside {window_days}-day window."
                ))
            else:
                results.append(ZombieResult(
                    run_id=run_id,
                    asset_id=asset_id,
                    classification="NOT_ZOMBIE",
                    window_days=window_days,
                    evidence_checked=evidence_checked,
                    last_activity_observed_at=latest_str,
                    reason=f"Asset has activity within {window_days}-day window (last: {latest_activity.strftime('%Y-%m-%d')})."
                ))
        
        return ZombieResponse(
            run_id=run_id,
            window_days=window_days,
            results=results
        )
    
    finally:
        await conn.close()
