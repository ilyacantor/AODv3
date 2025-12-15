"""
Zombie v0 Standalone Server

Minimal standalone FastAPI server for zombie classification.
Runs on port 5055, completely independent of main AOD.
"""

import os
import json
import asyncpg
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

app = FastAPI(title="Zombie v0 Standalone")


def get_db_url() -> str:
    url = os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("No database URL configured")
    return url


def parse_timestamp(ts_str) -> datetime | None:
    if not ts_str:
        return None
    try:
        if isinstance(ts_str, datetime):
            if ts_str.tzinfo is None:
                return ts_str.replace(tzinfo=timezone.utc)
            return ts_str
        ts_str = str(ts_str).strip()
        for fmt in [
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
        ]:
            try:
                dt = datetime.strptime(ts_str, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
        return None
    except Exception:
        return None


async def get_assets_for_run(run_id: str) -> list[dict]:
    url = get_db_url()
    conn = await asyncpg.connect(url)
    try:
        rows = await conn.fetch(
            "SELECT asset_id, name, lens_status, activity_evidence FROM assets WHERE run_id = $1",
            run_id
        )
        assets = []
        for row in rows:
            lens_status = row["lens_status"]
            if isinstance(lens_status, str):
                lens_status = json.loads(lens_status)
            
            activity_evidence = row["activity_evidence"]
            if isinstance(activity_evidence, str):
                activity_evidence = json.loads(activity_evidence)
            
            assets.append({
                "asset_id": str(row["asset_id"]),
                "name": row["name"],
                "lens_status": lens_status or {},
                "activity_evidence": activity_evidence or {}
            })
        return assets
    finally:
        await conn.close()


def classify_zombies(assets: list[dict], window_days: int) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    results = []
    
    for asset in assets:
        lens = asset.get("lens_status", {})
        activity = asset.get("activity_evidence", {})
        
        exists_in_sor = (
            lens.get("idp") == "matched" or
            lens.get("cmdb") == "matched" or
            lens.get("cloud") == "matched" or
            lens.get("finance") == "matched"
        )
        
        sor_sources = []
        if lens.get("idp") == "matched":
            sor_sources.append("IdP")
        if lens.get("cmdb") == "matched":
            sor_sources.append("CMDB")
        if lens.get("cloud") == "matched":
            sor_sources.append("Cloud")
        if lens.get("finance") == "matched":
            sor_sources.append("Finance")
        
        latest_ts = parse_timestamp(activity.get("latest_activity_at"))
        
        activity_in_window = False
        if latest_ts and latest_ts >= cutoff:
            activity_in_window = True
        
        is_zombie = exists_in_sor and not activity_in_window
        
        sor_list = ", ".join(sor_sources) if sor_sources else "unknown SOR"
        
        if is_zombie:
            if latest_ts:
                reason = f"Exists in {sor_list}; last activity was {latest_ts.strftime('%Y-%m-%d')}, outside {window_days}-day window."
            else:
                reason = f"Exists in {sor_list}; no activity observed in last {window_days} days."
        else:
            if not exists_in_sor:
                reason = "Does not exist in any system of record."
            else:
                reason = f"Exists in {sor_list}; has activity within {window_days}-day window."
        
        results.append({
            "asset_id": asset.get("name", asset["asset_id"]),
            "exists_in_sor": exists_in_sor,
            "activity_in_window": activity_in_window,
            "zombie": is_zombie,
            "last_activity_observed_at": latest_ts.isoformat() if latest_ts else None,
            "reason": reason
        })
    
    return results


@app.get("/zombies")
async def get_zombies(
    run_id: str = Query(..., description="Run ID to analyze"),
    window_days: int = Query(..., description="Activity window in days")
):
    assets = await get_assets_for_run(run_id)
    
    if not assets:
        return JSONResponse(
            status_code=404,
            content={"error": f"No assets found for run_id: {run_id}"}
        )
    
    results = classify_zombies(assets, window_days)
    
    return {
        "run_id": run_id,
        "window_days": window_days,
        "results": results
    }


@app.get("/health")
async def health():
    return {"status": "ok", "service": "zombie-v0-standalone"}
