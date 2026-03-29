"""Run-related API routes for AOD"""

from typing import Any, Optional
import json
import os
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Query
import logging

logger = logging.getLogger(__name__)

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
from ...cache import write_snapshot_cache
from ...pipeline.derived_classifications import compute_derived_classifications, classify_zombie, compute_zombie_status
from ...pipeline.cache import invalidate_run_caches, get_domain_rollups_cache, get_derived_classifications_cache
from ...core.policy import get_current_config
from .utils import (
    parse_iso_datetime as _parse_iso_datetime,
    parse_snapshot_generated_at as _parse_snapshot_generated_at,
    get_run_snapshot_as_of as _get_run_snapshot_as_of,
    generate_ambiguous_explanation as _generate_ambiguous_explanation,
)
from ...pipeline.sor_scoring import batch_score_sor
from ...converters.triple_converter import convert_discovery_to_triples
from ...converters.triple_writer import write_triples_to_pg
from ...converters.entity_resolver import resolve_entity_id


async def _emit_discovery_triples(
    result,
    db: Database,
    run_id: str,
    snapshot_data: dict | None = None,
    request_entity_id: str | None = None,
) -> None:
    """Convert discovery output to EAV triples and write to PG.

    Additive step — does not block or replace the AAM handoff.
    If triple conversion or write fails, logs the error and continues.
    The scan result is returned to the caller regardless.
    """
    if not result.success or not result.assets:
        return

    try:
        entity_id = resolve_entity_id(
            snapshot_data=snapshot_data,
            request_entity_id=request_entity_id,
        )
        fabric_plane_registry = result.run_log.input_meta.get(
            "_aod_fabric_plane_registry", []
        )
        triples = convert_discovery_to_triples(
            assets=result.assets,
            findings=result.findings,
            fabric_plane_registry=fabric_plane_registry,
            entity_id=entity_id,
            tenant_id=result.run_log.tenant_id,
            run_id=run_id,
        )
        if triples:
            pool = await db.get_pool()
            count = await write_triples_to_pg(triples, pool)
            logger.info(
                "triple_conversion.complete",
                extra={
                    "run_id": run_id,
                    "triples_written": count,
                    "entity_id": entity_id,
                },
            )
    except Exception as e:
        logger.error(
            "triple_conversion.failed",
            extra={"run_id": run_id, "error": str(e)},
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

    await _emit_discovery_triples(result, db, run_id, snapshot_data=data)

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
    
    Accepts a snapshot JSON object directly (Farm format or normalized).
    Automatically normalizes Farm-format snapshots.
    Returns run_id + summary counts.
    """
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    started_at = now_pst()

    db = await get_db_direct()
    result = await execute_pipeline(
        snapshot, 
        db, 
        run_id=run_id, 
        started_at=started_at,
        provenance={"source": "farm"}
    )
    
    if not result.success:
        if result.run_log.status == RunStatus.INVALID_INPUT_CONTRACT:
            raise HTTPException(status_code=400, detail=result.error)
        raise HTTPException(status_code=500, detail=result.error)

    await _emit_discovery_triples(result, db, run_id, snapshot_data=snapshot)

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
    # Resolve entity_id: request > snapshot meta.  Fail loudly if missing.
    entity_id = request.entity_id or snapshot_data.get("meta", {}).get("entity_id")
    if not entity_id:
        raise HTTPException(
            status_code=400,
            detail="No entity_id available — provide entity_id in request or ensure "
                   "Farm snapshot meta contains entity_id. "
                   f"snapshot_id={request.snapshot_id}"
        )
    if "meta" in snapshot_data:
        snapshot_data["meta"]["entity_id"] = entity_id
    
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    started_at = now_pst()
    
    snapshot_generated_at = _parse_snapshot_generated_at(snapshot_data)
    
    # Extract snapshot fingerprint for drift detection (Jan 2026)
    snapshot_fingerprint = snapshot_data.get("meta", {}).get("snapshot_fingerprint") or snapshot_data.get("snapshot_fingerprint")
    
    provenance = {
        "source": "farm",
        "farm_url": farm_url,
        "snapshot_id": request.snapshot_id,
        "schema_version": schema_version,
        "fetch_duration_ms": fetch_duration_ms,
        "snapshot_generated_at": snapshot_generated_at.isoformat() if snapshot_generated_at else None,
        "snapshot_fingerprint": snapshot_fingerprint,  # For detecting snapshot regeneration
        "industry": request.industry  # Industry vertical for fabric plane weighting
    }
    
    db = await get_db_direct()
    result = await execute_pipeline(snapshot_data, db, run_id=run_id, started_at=started_at, provenance=provenance)
    
    if not result.success:
        if result.run_log.status == RunStatus.INVALID_INPUT_CONTRACT:
            raise HTTPException(status_code=400, detail=result.error)
        raise HTTPException(status_code=500, detail=result.error)

    await _emit_discovery_triples(
        result, db, run_id,
        snapshot_data=snapshot_data,
        request_entity_id=request.entity_id,
    )

    # Cache snapshot for offline resilience (write-through)
    # Only cache Farm-sourced snapshots, not re-cached data
    try:
        snapshot_name = snapshot_data.get("meta", {}).get("name", request.snapshot_id)
        write_snapshot_cache(
            snapshot_data=snapshot_data,
            snapshot_id=request.snapshot_id,
            snapshot_name=snapshot_name,
            tenant_id=result.run_log.tenant_id,
            asset_count=result.run_log.counts.assets_admitted,
            finding_count=result.run_log.counts.findings_generated,
            run_id=run_id,
        )
    except Exception as e:
        # Cache write failure is non-fatal - log and continue
        logger.warning("cache.write_failed_nonfatal", extra={"error": str(e)})

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
        entity_id=result.run_log.entity_id,
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

    Uses a SQL WHERE clause — does NOT load all runs.
    Returns HTTP 404 if no matching run exists.
    """
    db = await get_db_direct()
    run = await db.get_latest_run_for_tenant(tenant_id, snapshot_id)

    if not run:
        raise HTTPException(status_code=404, detail=f"No run found for tenant {tenant_id}" + (f" and snapshot {snapshot_id}" if snapshot_id else ""))

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

    # Stage 1 Metrics: Check for CMDB external_ref domain leakage
    # After Stage 1, reference_domains should contain CMDB external_ref domains
    # and identifiers.domains should NOT contain them
    stage1_metrics = _compute_stage1_asset_metrics(assets)

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
        "zombie_assets": summary.zombie_assets,
        "stage1_metrics": stage1_metrics
    }


@router.get("/{run_id}/artifacts")
async def get_run_artifacts(run_id: str):
    """
    Get discovered artifacts for a run: Fabric Planes and Systems of Record.

    PRIORITY: Use Farm's authoritative fabric_planes and sors from snapshot metadata.
    Farm is the source of truth for these values - AOD should NOT recompute them.

    Returns:
        - fabric_planes: List of fabric control planes (iPaaS, API Gateway, Event Bus, Warehouse)
        - systems_of_record: List of SORs for specific domains (CRM, HR, Finance, etc.)
        - summary counts for UI KPI display

    Data source priority:
        1. Farm-provided values in input_meta (authoritative)
        2. Fallback: AOD-computed values if Farm didn't provide them
    """
    db = await get_db_direct()

    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    # Get industry from input_meta
    industry = None
    if run.input_meta:
        industry = run.input_meta.get("industry")

    # ==========================================================================
    # FABRIC PLANES: Use Farm's authoritative data if available
    # ==========================================================================
    farm_fabric_planes = None
    if run.input_meta:
        farm_fabric_planes = run.input_meta.get("fabric_planes")

    def _format_plane_display_name(plane_type: str, vendor: str) -> str:
        """Format fabric plane display name as 'Vendor, Plane Type'"""
        vendor_display = vendor.replace("_", " ").replace(".", " ").title()
        plane_type_display = {
            'ipaas': 'iPaaS',
            'api_gateway': 'API Gateway',
            'event_bus': 'Event Bus',
            'data_warehouse': 'Data Warehouse',
        }.get(plane_type.lower(), plane_type.replace('_', ' ').title())
        return f"{vendor_display}, {plane_type_display}"

    if farm_fabric_planes and isinstance(farm_fabric_planes, list) and len(farm_fabric_planes) > 0:
        # Use Farm's authoritative fabric planes
        fabric_planes = []
        by_type: dict[str, list] = {"ipaas": [], "api_gateway": [], "event_bus": [], "data_warehouse": []}

        for fp in farm_fabric_planes:
            plane_type = fp.get("plane_type", "unknown")
            vendor = fp.get("vendor", "unknown")
            is_healthy = fp.get("is_healthy", True)

            plane_data = {
                "plane_id": f"{plane_type}:{vendor}",
                "plane_type": plane_type,
                "vendor": vendor,
                "display_name": _format_plane_display_name(plane_type, vendor),
                "is_healthy": is_healthy,
                "source": "farm"
            }
            fabric_planes.append(plane_data)

            # Group by type
            type_key = plane_type.lower()
            if type_key in by_type:
                by_type[type_key].append(plane_data)

        fabric_response = {
            "count": len(fabric_planes),
            "planes": fabric_planes,
            "total_assets_with_fabric_tag": len(fabric_planes),
            "by_plane_type": by_type,
            "source": "farm"
        }
    else:
        # Fallback: Compute from assets (legacy behavior)
        assets = await db.get_assets_by_run(run_id)
        fabric_planes = []
        fabric_plane_assets = []
        plane_vendor_counts: dict[str, dict] = {}

        for asset in assets:
            if asset.fabric_plane_tag:
                tag = asset.fabric_plane_tag
                vendor = tag.controller_vendor
                plane_type = tag.plane_type.value if hasattr(tag.plane_type, 'value') else str(tag.plane_type)

                if vendor not in plane_vendor_counts:
                    plane_vendor_counts[vendor] = {
                        "vendor": vendor,
                        "plane_type": plane_type,
                        "display_name": _format_plane_display_name(plane_type, vendor),
                        "count": 0,
                        "assets": []
                    }

                plane_vendor_counts[vendor]["count"] += 1
                plane_vendor_counts[vendor]["assets"].append({
                    "asset_id": str(asset.asset_id),
                    "name": asset.name,
                    "domain": tag.controller_domain
                })

                fabric_plane_assets.append({
                    "asset_id": str(asset.asset_id),
                    "name": asset.name,
                    "vendor": asset.vendor,
                    "plane_type": plane_type,
                    "controller_vendor": vendor,
                    "controller_domain": tag.controller_domain,
                    "confidence": tag.confidence
                })

        for vendor, data in plane_vendor_counts.items():
            fabric_planes.append({
                "plane_id": f"{data['plane_type']}:{vendor}",
                "plane_type": data["plane_type"],
                "vendor": vendor,
                "display_name": data["display_name"],
                "managed_asset_count": data["count"],
                "sample_assets": data["assets"][:5],
                "source": "computed"
            })

        fabric_response = {
            "count": len(fabric_planes),
            "planes": fabric_planes,
            "total_assets_with_fabric_tag": len(fabric_plane_assets),
            "by_plane_type": _group_planes_by_type(fabric_planes),
            "source": "computed"
        }

    # ==========================================================================
    # SYSTEMS OF RECORD: Use Farm's authoritative data if available
    # ==========================================================================
    farm_sors = None
    if run.input_meta:
        farm_sors = run.input_meta.get("sors")

    if farm_sors and isinstance(farm_sors, list) and len(farm_sors) > 0:
        # Use Farm's authoritative SORs
        sor_assets = []
        sor_by_domain: dict[str, list] = {}

        for sor in farm_sors:
            domain = sor.get("domain", "unknown")
            sor_name = sor.get("sor_name", "Unknown")
            sor_type = sor.get("sor_type", "unknown")
            confidence = sor.get("confidence", "high")

            sor_asset = {
                "name": sor_name,
                "sor_domain": domain,
                "sor_type": sor_type,
                "sor_likelihood": confidence,
                "sor_confidence": 1.0 if confidence == "high" else 0.7 if confidence == "medium" else 0.4,
                "sor_evidence": [f"Farm-designated {domain} SOR"],
                "source": "farm"
            }
            sor_assets.append(sor_asset)

            if domain not in sor_by_domain:
                sor_by_domain[domain] = []
            sor_by_domain[domain].append(sor_asset)

        sor_response = {
            "count": len(sor_assets),
            "high_confidence_count": len([a for a in sor_assets if a["sor_likelihood"] == "high"]),
            "medium_confidence_count": len([a for a in sor_assets if a["sor_likelihood"] == "medium"]),
            "assets": sor_assets,
            "by_domain": sor_by_domain,
            "source": "farm"
        }
    else:
        # Fallback: Compute from assets (legacy behavior)
        # Need to fetch assets if not already loaded (when fabric planes came from Farm)
        try:
            assets_for_sor = assets  # type: ignore
        except NameError:
            assets_for_sor = await db.get_assets_by_run(run_id)

        sor_results = batch_score_sor(assets_for_sor)
        sor_assets = []
        sor_by_domain: dict[str, list] = {}

        for asset in assets_for_sor:
            asset_id = str(asset.asset_id)
            if asset_id in sor_results:
                result = sor_results[asset_id]
                if result.likelihood in ("high", "medium"):
                    sor_asset = {
                        "asset_id": asset_id,
                        "name": asset.name,
                        "vendor": asset.vendor,
                        "sor_likelihood": result.likelihood,
                        "sor_confidence": result.confidence,
                        "sor_domain": result.domain,
                        "sor_evidence": result.evidence[:3],
                        "source": "computed"
                    }
                    sor_assets.append(sor_asset)

                    domain = result.domain or "unknown"
                    if domain not in sor_by_domain:
                        sor_by_domain[domain] = []
                    sor_by_domain[domain].append(sor_asset)

        sor_response = {
            "count": len(sor_assets),
            "high_confidence_count": len([a for a in sor_assets if a["sor_likelihood"] == "high"]),
            "medium_confidence_count": len([a for a in sor_assets if a["sor_likelihood"] == "medium"]),
            "assets": sor_assets,
            "by_domain": sor_by_domain,
            "source": "computed"
        }

    return {
        "run_id": run_id,
        "industry": industry,
        "fabric_planes": fabric_response,
        "systems_of_record": sor_response
    }


def _group_planes_by_type(fabric_planes: list[dict]) -> dict:
    """Group fabric planes by plane type for UI display"""
    by_type: dict[str, list] = {
        "ipaas": [],
        "api_gateway": [],
        "event_bus": [],
        "warehouse": []
    }

    for plane in fabric_planes:
        plane_type = plane.get("plane_type", "unknown")
        if plane_type in by_type:
            by_type[plane_type].append(plane)

    return by_type


@router.get("/{run_id}/policy")
async def get_run_policy(run_id: str):
    """
    Get the policy snapshot used for a specific run.
    
    Returns the exact policy configuration that was in effect when
    the pipeline executed for this run. This enables reproducible
    grading - Farm can fetch this endpoint to grade with identical policy.
    
    Contract:
        200 OK: { run_id, policy_hash, captured_at, policy }
        404: Run not found
        410: Policy snapshot expired/garbage collected (future)
    
    Args:
        run_id: The run to get the policy snapshot for
    
    Returns:
        The policy configuration used for this run
    """
    import hashlib
    
    db = await get_db_direct()
    
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    if not run.policy_snapshot:
        raise HTTPException(
            status_code=410, 
            detail="Policy snapshot not available for this run. Runs before Jan 2026 may not have snapshots."
        )
    
    policy_json = json.dumps(run.policy_snapshot, sort_keys=True)
    policy_hash = f"sha256:{hashlib.sha256(policy_json.encode()).hexdigest()}"
    
    captured_at = run.started_at.isoformat() if run.started_at else None
    
    return {
        "run_id": run_id,
        "policy_hash": policy_hash,
        "captured_at": captured_at,
        "policy": run.policy_snapshot
    }


def _compute_stage1_asset_metrics(assets: list) -> dict:
    """
    Compute Stage 1 metrics from persisted assets.
    
    Stage 1 Fix: CMDB external_ref domains should be in reference_domains (enrichment),
    NOT in identifiers.domains (identity/admission).
    
    This checks for domain overlap as a proxy for Stage 1 effectiveness:
    - reference_domains_total: Total domains stored as reference (enrichment)
    - domains_in_both_identity_and_reference: Should be 0 (overlap indicates leakage)
    - stage1_effective: True if no overlap detected
    
    Note: This is a heuristic check since we don't have correlation data at query time.
    The definitive Stage 1 metrics are logged during pipeline execution.
    """
    reference_domains_total = 0
    domains_in_both = 0
    assets_with_reference_domains = 0
    
    for asset in assets:
        identifiers = asset.identifiers if hasattr(asset, 'identifiers') else asset.get("identifiers", {})
        if not identifiers:
            continue
        
        # Get domains from identifiers
        identity_domains = set()
        if hasattr(identifiers, 'domains'):
            identity_domains = set(d.lower() for d in (identifiers.domains or []))
        elif isinstance(identifiers, dict):
            identity_domains = set(d.lower() for d in (identifiers.get("domains") or []))
        
        # Get reference domains (CMDB external_ref domains after Stage 1)
        reference_domains = set()
        if hasattr(identifiers, 'reference_domains'):
            reference_domains = set(d.lower() for d in (identifiers.reference_domains or []))
        elif isinstance(identifiers, dict):
            reference_domains = set(d.lower() for d in (identifiers.get("reference_domains") or []))
        
        reference_domains_total += len(reference_domains)
        if reference_domains:
            assets_with_reference_domains += 1
        
        # Check overlap - domains that are in BOTH identity and reference
        overlap = identity_domains & reference_domains
        domains_in_both += len(overlap)
    
    return {
        "reference_domains_total": reference_domains_total,
        "assets_with_reference_domains": assets_with_reference_domains,
        "domains_in_both_identity_and_reference": domains_in_both,
        "stage1_effective": domains_in_both == 0,
        "note": "Definitive metrics logged during pipeline execution with key 'stage1.cmdb_external_ref_metrics'"
    }
