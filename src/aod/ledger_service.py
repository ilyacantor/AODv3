"""
Ledger Service - Run-scoped breach queries for Farm grading.

Provides endpoints to export observed breaches by run_id for
deterministic, contract-grade grading by Farm.
"""
import json
from typing import Dict, Any, List, Optional
from src.aod.db import fetch, fetchrow


async def get_run_metadata(run_id: str) -> Optional[Dict[str, Any]]:
    """Get metadata for a specific run."""
    row = await fetchrow("""
        SELECT id, tenant_id, archetype, scale, status, started_at, finished_at,
               total_assets, shadow_it_count, parked_count, cataloged_count,
               company_name, message
        FROM ingest_runs
        WHERE id = $1
    """, run_id)
    
    if not row:
        return None
    
    return {
        "run_id": str(row["id"]),
        "tenant_id": row["tenant_id"],
        "archetype": row["archetype"],
        "scale": row["scale"],
        "status": row["status"],
        "started_at": row["started_at"].isoformat() if row["started_at"] else None,
        "finished_at": row["finished_at"].isoformat() if row["finished_at"] else None,
        "total_assets": row["total_assets"] or 0,
        "shadow_it_count": row["shadow_it_count"] or 0,
        "parked_count": row["parked_count"] or 0,
        "cataloged_count": row["cataloged_count"] or 0,
        "company_name": row["company_name"] or "",
        "message": row["message"] or ""
    }


async def get_observed_breaches_by_run(run_id: str) -> Dict[str, Any]:
    """
    Get all observed breaches for a run, grouped by asset.
    
    Returns machine-readable format for Farm grading:
    {
        "run_id": "...",
        "run_metadata": {...},
        "assets": [
            {
                "asset_id": "...",
                "farm_asset_id": "...",
                "observed_breaches": [...]
            }
        ],
        "summary": {...}
    }
    """
    run_metadata = await get_run_metadata(run_id)
    
    if not run_metadata:
        return {
            "error": f"Run {run_id} not found",
            "run_id": run_id,
            "assets": [],
            "summary": {}
        }
    
    rows = await fetch("""
        SELECT 
            ob.asset_id,
            a.farm_asset_id,
            a.name as asset_name,
            a.lifecycle_state,
            a.farm_bucket,
            ob.breach_id,
            ob.name as breach_name,
            ob.is_breached,
            ob.severity_base,
            ob.evidence,
            ob.source
        FROM observed_breaches ob
        JOIN assets a ON ob.asset_id = a.id
        WHERE ob.run_id = $1
        ORDER BY a.farm_asset_id, ob.breach_id
    """, run_id)
    
    assets_map = {}
    summary = {
        "total_assets": 0,
        "assets_with_breaches": 0,
        "total_breaches": 0,
        "blocker_count": 0,
        "non_blocking_count": 0,
        "tag_count": 0,
        "breaches_by_id": {}
    }
    
    for row in rows:
        asset_id = str(row["asset_id"])
        
        if asset_id not in assets_map:
            assets_map[asset_id] = {
                "asset_id": asset_id,
                "farm_asset_id": row["farm_asset_id"],
                "asset_name": row["asset_name"],
                "lifecycle_state": row["lifecycle_state"],
                "farm_bucket": row["farm_bucket"],
                "observed_breaches": []
            }
        
        evidence = row["evidence"]
        if isinstance(evidence, str):
            try:
                evidence = json.loads(evidence)
            except:
                evidence = {}
        
        breach = {
            "breach_id": row["breach_id"],
            "name": row["breach_name"],
            "is_breached": row["is_breached"],
            "severity_base": row["severity_base"],
            "evidence": evidence,
            "source": row["source"]
        }
        
        assets_map[asset_id]["observed_breaches"].append(breach)
        
        summary["total_breaches"] += 1
        
        breach_id = row["breach_id"]
        summary["breaches_by_id"][breach_id] = summary["breaches_by_id"].get(breach_id, 0) + 1
        
        severity = row["severity_base"]
        if severity == "BLOCKER":
            summary["blocker_count"] += 1
        elif severity == "NON_BLOCKING":
            summary["non_blocking_count"] += 1
        elif severity == "TAG":
            summary["tag_count"] += 1
    
    assets_list = list(assets_map.values())
    summary["total_assets"] = run_metadata.get("total_assets", 0)
    summary["assets_with_breaches"] = len(assets_list)
    
    return {
        "run_id": run_id,
        "run_metadata": run_metadata,
        "assets": assets_list,
        "summary": summary
    }


async def get_breach_summary_by_run(run_id: str) -> Dict[str, Any]:
    """Get just the summary counts for a run."""
    rows = await fetch("""
        SELECT 
            breach_id,
            severity_base,
            COUNT(*) as count
        FROM observed_breaches
        WHERE run_id = $1
        GROUP BY breach_id, severity_base
    """, run_id)
    
    summary = {
        "run_id": run_id,
        "total_breaches": 0,
        "blocker_count": 0,
        "non_blocking_count": 0,
        "tag_count": 0,
        "breaches_by_id": {}
    }
    
    for row in rows:
        count = row["count"]
        summary["total_breaches"] += count
        summary["breaches_by_id"][row["breach_id"]] = count
        
        severity = row["severity_base"]
        if severity == "BLOCKER":
            summary["blocker_count"] += count
        elif severity == "NON_BLOCKING":
            summary["non_blocking_count"] += count
        elif severity == "TAG":
            summary["tag_count"] += count
    
    return summary


async def get_all_runs_with_breaches() -> List[Dict[str, Any]]:
    """Get all runs that have observed breaches."""
    rows = await fetch("""
        SELECT 
            ir.id as run_id,
            ir.company_name,
            ir.archetype,
            ir.scale,
            ir.status,
            ir.started_at,
            ir.finished_at,
            ir.total_assets,
            COUNT(DISTINCT ob.id) as breach_count,
            COUNT(DISTINCT ob.asset_id) as assets_with_breaches
        FROM ingest_runs ir
        LEFT JOIN observed_breaches ob ON ir.id = ob.run_id
        GROUP BY ir.id
        ORDER BY ir.started_at DESC
    """)
    
    return [
        {
            "run_id": str(row["run_id"]),
            "company_name": row["company_name"] or "",
            "archetype": row["archetype"],
            "scale": row["scale"],
            "status": row["status"],
            "started_at": row["started_at"].isoformat() if row["started_at"] else None,
            "finished_at": row["finished_at"].isoformat() if row["finished_at"] else None,
            "total_assets": row["total_assets"] or 0,
            "breach_count": row["breach_count"] or 0,
            "assets_with_breaches": row["assets_with_breaches"] or 0
        }
        for row in rows
    ]
