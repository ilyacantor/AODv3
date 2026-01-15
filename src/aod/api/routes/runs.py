"""Run-related API routes for AOD"""

from typing import Any, Optional
import json
import os
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends

from ..schemas import (
    FarmRunRequest,
    RunResponse,
    RunDetailResponse,
    ResyncRequest,
    ResyncResponse,
)
from ...db.database import get_db, get_db_direct, Database
from ..deps import now_pst, get_farm_url
from ...farm_client import FarmClient, validate_schema_version
from ...farm_reconcile import reconcile_to_farm
from ...pipeline.pipeline_executor import execute_pipeline
from ...models.output_contracts import RunStatus, SyncStatus
from ...pipeline.derived_classifications import compute_derived_classifications, classify_zombie, compute_zombie_status
from ...pipeline.cache import invalidate_run_caches, get_domain_rollups_cache, get_derived_classifications_cache
from ...core.policy import get_current_config
from .utils import (
    parse_iso_datetime as _parse_iso_datetime,
    parse_snapshot_generated_at as _parse_snapshot_generated_at,
    get_run_snapshot_as_of as _get_run_snapshot_as_of,
    generate_ambiguous_explanation as _generate_ambiguous_explanation,
)


router = APIRouter(prefix="/runs")


@router.post("", response_model=RunResponse)
async def create_run(file: UploadFile = File(...)):
    """
    Create a new discovery run.
    
    Accepts a snapshot JSON file.
    Returns run_id + summary counts.
    """
    try:
        content = await file.read()
        data = json.loads(content.decode('utf-8'))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")
    
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    started_at = now_pst()

    db = await get_db_direct()
    result = await execute_pipeline(data, db, run_id=run_id, started_at=started_at)
    
    if not result.success:
        if result.run_log.status == RunStatus.INVALID_INPUT_CONTRACT:
            raise HTTPException(status_code=400, detail=result.error)
        raise HTTPException(status_code=500, detail=result.error)
    
    return RunResponse(
        run_id=result.run_log.run_id,
        tenant_id=result.run_log.tenant_id,
        status=result.run_log.status.value,
        counts=result.run_log.counts,
        message=f"Discovery completed. {result.run_log.counts.assets_admitted} assets admitted, {result.run_log.counts.findings_generated} findings generated."
    )


@router.post("/json", response_model=RunResponse)
async def create_run_json(snapshot: dict[str, Any]):
    """
    Create a new discovery run from JSON body.
    
    Accepts a snapshot JSON object directly.
    Returns run_id + summary counts.
    """
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    started_at = now_pst()

    db = await get_db_direct()
    result = await execute_pipeline(snapshot, db, run_id=run_id, started_at=started_at)
    
    if not result.success:
        if result.run_log.status == RunStatus.INVALID_INPUT_CONTRACT:
            raise HTTPException(status_code=400, detail=result.error)
        raise HTTPException(status_code=500, detail=result.error)
    
    return RunResponse(
        run_id=result.run_log.run_id,
        tenant_id=result.run_log.tenant_id,
        status=result.run_log.status.value,
        counts=result.run_log.counts,
        message=f"Discovery completed. {result.run_log.counts.assets_admitted} assets admitted, {result.run_log.counts.findings_generated} findings generated."
    )


@router.post("/from-farm", response_model=RunResponse)
async def create_run_from_farm(request: FarmRunRequest):
    """
    Create a new discovery run by fetching snapshot from Farm.
    
    Fetches snapshot from {farm_base_url}/api/snapshots/{snapshot_id}
    Uses FARM_URL from environment if farm_base_url not provided.
    Validates HTTP status, Content-Type, non-empty JSON body.
    Requires meta.schema_version == "farm.v1"
    
    Persists provenance: farm_url, snapshot_id, schema_version, fetch_duration_ms
    
    Returns run_id + summary counts.
    """
    farm_url = request.farm_base_url or get_farm_url()
    if not farm_url:
        raise HTTPException(status_code=400, detail="No Farm URL configured. Set FARM_URL environment variable or provide farm_base_url.")
    
    farm_client = FarmClient(farm_url)
    
    fetch_start = time.time()
    fetch_result = await farm_client.fetch_snapshot(request.snapshot_id)
    fetch_duration_ms = int((time.time() - fetch_start) * 1000)
    
    if not fetch_result.success:
        raise HTTPException(
            status_code=502,
            detail=f"{fetch_result.error_type}: {fetch_result.error}"
        )
    
    snapshot_data = fetch_result.data
    if snapshot_data is None:
        raise HTTPException(status_code=502, detail="Farm returned empty data")
    
    schema_valid, schema_error = validate_schema_version(snapshot_data)
    if not schema_valid:
        raise HTTPException(
            status_code=400,
            detail=f"INVALID_INPUT_CONTRACT: {schema_error}"
        )
    
    schema_version = snapshot_data.get("meta", {}).get("schema_version", "unknown")
    
    if "meta" in snapshot_data and "tenant_id" not in snapshot_data["meta"]:
        snapshot_data["meta"]["tenant_id"] = request.tenant_id
    
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    started_at = now_pst()
    
    snapshot_generated_at = _parse_snapshot_generated_at(snapshot_data)
    
    provenance = {
        "source": "farm",
        "farm_url": farm_url,
        "snapshot_id": request.snapshot_id,
        "schema_version": schema_version,
        "fetch_duration_ms": fetch_duration_ms,
        "snapshot_generated_at": snapshot_generated_at.isoformat() if snapshot_generated_at else None
    }
    
    db = await get_db_direct()
    result = await execute_pipeline(snapshot_data, db, run_id=run_id, started_at=started_at, provenance=provenance)
    
    if not result.success:
        if result.run_log.status == RunStatus.INVALID_INPUT_CONTRACT:
            raise HTTPException(status_code=400, detail=result.error)
        raise HTTPException(status_code=500, detail=result.error)
    
    sync_status = SyncStatus.PENDING
    sync_error = None
    
    if result.run_log.status in (RunStatus.COMPLETED_WITH_RESULTS, RunStatus.COMPLETED_NO_ASSETS, RunStatus.COMPLETED):
        result.run_log.sync_status = SyncStatus.PENDING
        await db.update_run(result.run_log)
        
        rejections, _ = await db.get_rejections_by_run(run_id, limit=get_current_config().query_limits.default_rejection_limit)
        
        snapshot_as_of = snapshot_generated_at
        
        success, error = await reconcile_to_farm(
            run_log=result.run_log,
            assets=result.assets,
            findings=result.findings,
            snapshot_id=request.snapshot_id,
            farm_url=farm_url,
            rejections=rejections,
            snapshot_as_of=snapshot_as_of
        )
        
        if success:
            result.run_log.sync_status = SyncStatus.SYNCED
            result.run_log.sync_error = None
        else:
            result.run_log.sync_status = SyncStatus.FAILED
            result.run_log.sync_error = error
        
        await db.update_run(result.run_log)
        sync_status = result.run_log.sync_status
        sync_error = result.run_log.sync_error
    
    return RunResponse(
        run_id=result.run_log.run_id,
        tenant_id=result.run_log.tenant_id,
        status=result.run_log.status.value,
        counts=result.run_log.counts,
        message=f"Discovery completed from Farm. {result.run_log.counts.assets_admitted} assets admitted, {result.run_log.counts.findings_generated} findings generated.",
        sync_status=sync_status.value,
        sync_error=sync_error
    )


@router.post("/resync", response_model=ResyncResponse)
async def resync_run_to_farm(request: ResyncRequest):
    """
    Re-sync an existing run to Farm.
    
    This endpoint allows manually re-triggering the Farm callback for an existing run.
    Useful for testing that the callback payload contains correct domain-keyed assets.
    
    Returns the sync status and a sample of the payload that was sent.
    """
    db = await get_db_direct()
    run = await db.get_run(request.run_id)
    
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {request.run_id} not found")
    
    farm_url = get_farm_url()
    if not farm_url:
        raise HTTPException(status_code=400, detail="No Farm URL configured")
    
    snapshot_id = run.input_meta.get("snapshot_id")
    if not snapshot_id:
        raise HTTPException(status_code=400, detail="Run has no snapshot_id in metadata")
    
    assets = await db.get_assets_by_run(request.run_id)
    findings = await db.get_findings_by_run(request.run_id)
    rejections, _ = await db.get_rejections_by_run(request.run_id, limit=get_current_config().query_limits.default_rejection_limit)
    
    mode = request.mode or "sprawl"
    
    snapshot_as_of = _get_run_snapshot_as_of(run)
    
    success, error = await reconcile_to_farm(
        run_log=run,
        assets=assets,
        findings=findings,
        snapshot_id=snapshot_id,
        farm_url=farm_url,
        rejections=rejections,
        mode=mode,
        snapshot_as_of=snapshot_as_of
    )
    
    if success:
        run.sync_status = SyncStatus.SYNCED
        run.sync_error = None
    else:
        run.sync_status = SyncStatus.FAILED
        run.sync_error = error
    
    await db.update_run(run)
    
    from ...pipeline.aod_agent_reconcile import emit_actual_results
    actual_results = emit_actual_results(
        run_id=request.run_id,
        assets=assets,
        activity_window_days=get_current_config().activity_windows.default_activity_window_days,
        rejections=rejections,
        mode=mode,
        snapshot_as_of=snapshot_as_of
    )
    
    return ResyncResponse(
        run_id=request.run_id,
        sync_status=run.sync_status.value,
        sync_error=run.sync_error,
        shadow_asset_keys=actual_results.shadow_actual,
        zombie_asset_keys=actual_results.zombie_actual,
        asset_summaries_keys=sorted(actual_results.actual_reasons.keys())
    )


@router.get("/latest", response_model=RunDetailResponse)
async def get_latest_run(tenant_id: str, snapshot_id: Optional[str] = None):
    """
    Get the latest run for a tenant and optionally a specific snapshot.
    
    Returns HTTP 404 if no matching run exists.
    """
    db = await get_db_direct()
    runs = await db.get_all_runs()
    
    matching = [r for r in runs if r.tenant_id == tenant_id]
    if snapshot_id:
        matching = [r for r in matching if r.input_meta.get("snapshot_id") == snapshot_id]
    
    if not matching:
        raise HTTPException(status_code=404, detail=f"No run found for tenant {tenant_id}" + (f" and snapshot {snapshot_id}" if snapshot_id else ""))
    
    run = matching[0]
    return RunDetailResponse(
        run_id=run.run_id,
        tenant_id=run.tenant_id,
        status=run.status.value,
        started_at=run.started_at.isoformat(),
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        input_meta=run.input_meta,
        counts=run.counts,
        stage_timings=run.stage_timings,
        failure_reasons=run.failure_reasons,
        sync_status=run.sync_status.value,
        sync_error=run.sync_error
    )


@router.get("", response_model=list[RunDetailResponse])
async def list_runs(tenant_id: Optional[str] = None):
    """List all discovery runs, optionally filtered by tenant_id"""
    db = await get_db_direct()
    runs = await db.get_all_runs()
    
    if tenant_id:
        runs = [r for r in runs if r.tenant_id == tenant_id]
    
    return [
        RunDetailResponse(
            run_id=run.run_id,
            tenant_id=run.tenant_id,
            status=run.status.value,
            started_at=run.started_at.isoformat(),
            completed_at=run.completed_at.isoformat() if run.completed_at else None,
            input_meta=run.input_meta,
            counts=run.counts,
            stage_timings=run.stage_timings,
            failure_reasons=run.failure_reasons,
            sync_status=run.sync_status.value,
            sync_error=run.sync_error
        )
        for run in runs
    ]


@router.delete("")
async def delete_all_runs():
    """Delete all discovery runs and associated data"""
    db = await get_db_direct()
    deleted = await db.delete_all_runs()

    # Invalidate all caches when deleting all runs
    get_domain_rollups_cache().clear()
    get_derived_classifications_cache().clear()

    return {"message": f"Deleted {deleted} runs and all associated data", "deleted": deleted}


@router.get("/{run_id}", response_model=RunDetailResponse)
async def get_run(run_id: str, db: Database = Depends(get_db)):
    """Get run detail + counts"""
    run = await db.get_run(run_id)
    
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    return RunDetailResponse(
        run_id=run.run_id,
        tenant_id=run.tenant_id,
        status=run.status.value,
        started_at=run.started_at.isoformat(),
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        input_meta=run.input_meta,
        counts=run.counts,
        stage_timings=run.stage_timings,
        failure_reasons=run.failure_reasons,
        sync_status=run.sync_status.value,
        sync_error=run.sync_error
    )


@router.get("/{run_id}/observations")
async def get_observations(run_id: str, limit: int = 100, offset: int = 0):
    """Get observation samples for a run"""
    db = await get_db_direct()
    
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    items, total = await db.get_observation_samples_by_run(run_id, limit=limit, offset=offset)
    
    return {
        "run_id": run_id,
        "items": items,
        "count": len(items),
        "total": total
    }


@router.get("/{run_id}/ambiguous")
async def get_ambiguous(run_id: str, limit: int = 100, offset: int = 0):
    """Get ambiguous matches for a run"""
    db = await get_db_direct()
    
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    items, total = await db.get_ambiguous_matches_by_run(run_id, limit=limit, offset=offset)
    
    enriched_items = []
    for item in items:
        item["explanation"] = _generate_ambiguous_explanation(item)
        enriched_items.append(item)
    
    return {
        "run_id": run_id,
        "items": enriched_items,
        "count": len(enriched_items),
        "total": total
    }


@router.get("/{run_id}/rejections")
async def get_rejections(run_id: str, limit: int = 100, offset: int = 0):
    """Get rejections for a run"""
    db = await get_db_direct()
    
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    items, total = await db.get_rejections_by_run(run_id, limit=limit, offset=offset)
    
    return {
        "run_id": run_id,
        "items": items,
        "count": len(items),
        "total": total
    }


@router.get("/{run_id}/assets")
async def get_run_assets(run_id: str, classification: Optional[str] = None):
    """Get assets for a run, optionally filtered by classification"""
    db = await get_db_direct()
    
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    assets = await db.get_assets_by_run(run_id)
    snapshot_as_of = _get_run_snapshot_as_of(run)

    if classification:
        summary = compute_derived_classifications(assets, activity_window_days=get_current_config().activity_windows.default_activity_window_days, run_id=run_id, snapshot_as_of=snapshot_as_of)
        if classification == "zombie":
            asset_ids = {a["asset_id"] for a in summary.zombie_assets}
            assets = [a for a in assets if str(a.asset_id) in asset_ids]
        elif classification == "shadow":
            asset_ids = {a["asset_id"] for a in summary.shadow_assets}
            assets = [a for a in assets if str(a.asset_id) in asset_ids]
    
    return {
        "run_id": run_id,
        "assets": [
            {
                "asset_id": str(a.asset_id),
                "name": a.name,
                "vendor": a.vendor,
                "asset_type": a.asset_type.value,
                "environment": a.environment.value,
                "lens_status": {
                    "idp": a.lens_status.idp.value,
                    "cmdb": a.lens_status.cmdb.value,
                    "cloud": a.lens_status.cloud.value,
                    "finance": a.lens_status.finance.value
                },
                "activity_evidence": {
                    "latest_activity_at": a.activity_evidence.latest_activity_at.isoformat() if a.activity_evidence.latest_activity_at else None
                }
            }
            for a in assets
        ],
        "count": len(assets)
    }


@router.get("/{run_id}/summary")
async def get_run_summary(run_id: str):
    """Get summary for a run including derived classifications"""
    db = await get_db_direct()
    
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    assets = await db.get_assets_by_run(run_id)
    findings = await db.get_findings_by_run(run_id)
    snapshot_as_of = _get_run_snapshot_as_of(run)
    derived = compute_derived_classifications(assets, activity_window_days=get_current_config().activity_windows.default_activity_window_days, run_id=run_id, snapshot_as_of=snapshot_as_of)

    return {
        "run_id": run_id,
        "tenant_id": run.tenant_id,
        "status": run.status.value,
        "started_at": run.started_at.isoformat(),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "counts": {
            "observations_in": run.counts.observations_in,
            "candidates_out": run.counts.candidates_out,
            "assets_admitted": run.counts.assets_admitted,
            "artifacts_recorded": run.counts.artifacts_recorded,
            "rejected": run.counts.rejected,
            "findings_generated": run.counts.findings_generated,
            "shadow_count": derived.shadow_count,
            "zombie_count": derived.zombie_count
        },
        "sync_status": run.sync_status.value,
        "sync_error": run.sync_error
    }


@router.get("/{run_id}/classifications")
async def get_classifications(run_id: str):
    """Get shadow/zombie classifications for a run"""
    db = await get_db_direct()
    
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    assets = await db.get_assets_by_run(run_id)
    snapshot_as_of = _get_run_snapshot_as_of(run)
    derived = compute_derived_classifications(assets, activity_window_days=get_current_config().activity_windows.default_activity_window_days, run_id=run_id, snapshot_as_of=snapshot_as_of)

    return {
        "run_id": run_id,
        "shadow_count": derived.shadow_count,
        "zombie_count": derived.zombie_count,
        "shadow_assets": [a["name"] for a in derived.shadow_assets],
        "zombie_assets": [a["name"] for a in derived.zombie_assets]
    }


@router.get("/{run_id}/reconcile-payload")
async def get_reconcile_payload(run_id: str):
    """Get the reconcile payload that would be sent to Farm.
    
    Uses build_reconcile_payload() from farm_reconcile module.
    This is the SINGLE SOURCE OF TRUTH for payload structure,
    shared with the actual reconcile_to_farm() callback.
    """
    from ...farm_reconcile import build_reconcile_payload
    
    db = await get_db_direct()
    
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    assets = await db.get_assets_by_run(run_id)
    findings = await db.get_findings_by_run(run_id)
    rejections, _ = await db.get_rejections_by_run(run_id, limit=get_current_config().query_limits.default_rejection_limit)
    
    snapshot_id = run.input_meta.get("snapshot_id") if run.input_meta else None
    
    return build_reconcile_payload(
        run_log=run,
        assets=assets,
        findings=findings,
        snapshot_id=snapshot_id,
        rejections=rejections
    )


@router.get("/{run_id}/lens")
async def get_lens_summary(run_id: str):
    """Get lens status summary for a run"""
    db = await get_db_direct()
    
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    assets = await db.get_assets_by_run(run_id)
    
    lens_counts = {
        "idp": {"matched": 0, "unmatched": 0, "indeterminate": 0},
        "cmdb": {"matched": 0, "unmatched": 0, "indeterminate": 0},
        "cloud": {"matched": 0, "unmatched": 0, "indeterminate": 0},
        "finance": {"matched": 0, "unmatched": 0, "indeterminate": 0}
    }
    
    for asset in assets:
        lens_counts["idp"][asset.lens_status.idp.value] += 1
        lens_counts["cmdb"][asset.lens_status.cmdb.value] += 1
        lens_counts["cloud"][asset.lens_status.cloud.value] += 1
        lens_counts["finance"][asset.lens_status.finance.value] += 1
    
    return {
        "run_id": run_id,
        "total_assets": len(assets),
        "lens_counts": lens_counts
    }


@router.get("/cache/stats")
async def get_cache_stats():
    """Get cache statistics for monitoring and debugging"""
    return {
        "domain_rollups_cache": get_domain_rollups_cache().stats(),
        "derived_classifications_cache": get_derived_classifications_cache().stats()
    }


@router.post("/cache/clear")
async def clear_caches():
    """Clear all caches (for debugging/testing)"""
    get_domain_rollups_cache().clear()
    get_derived_classifications_cache().clear()
    return {"message": "All caches cleared"}


@router.get("/{run_id}/derived")
async def get_derived_classifications(run_id: str, activity_window_days: int = 90):
    """
    Get derived classifications (Shadow/Zombie) for a run.
    
    These are computed on-read from asset evidence, not stored as flags.
    
    Shadow Asset = has finance/cloud/discovery evidence but NO IdP or CMDB match
                   AND has recent activity within the activity window
    Zombie Asset = in CMDB or IdP but NO discovery/activity evidence
                   OR has no recent activity within the activity window
    
    Args:
        run_id: The run to get classifications for
        activity_window_days: Number of days to consider for recent activity (default 90)
    """
    db = await get_db_direct()
    
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    assets = await db.get_assets_by_run(run_id)
    snapshot_as_of = _get_run_snapshot_as_of(run)

    summary = compute_derived_classifications(assets, activity_window_days, run_id=run_id, snapshot_as_of=snapshot_as_of)

    return {
        "run_id": run_id,
        "activity_window_days": activity_window_days,
        "snapshot_as_of": snapshot_as_of.isoformat() if snapshot_as_of else None,
        "shadow_count": summary.shadow_count,
        "zombie_count": summary.zombie_count,
        "indeterminate_count": summary.indeterminate_count,
        "distribution": {
            "total_assets": summary.distribution.total_assets,
            "with_idp_match": summary.distribution.with_idp_match,
            "with_cmdb_match": summary.distribution.with_cmdb_match,
            "with_activity_last_30_days": summary.distribution.with_activity_last_30_days,
            "with_any_activity_timestamp": summary.distribution.with_any_activity_timestamp,
            "indeterminate_count": summary.distribution.indeterminate_count
        },
        "shadow_assets": summary.shadow_assets,
        "zombie_assets": summary.zombie_assets
    }
