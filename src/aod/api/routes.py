"""FastAPI routes for AOD"""

from typing import Any, Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse

from pydantic import BaseModel, Field

PST = timezone(timedelta(hours=-8))

def now_pst() -> datetime:
    return datetime.now(PST)
import json
import os
import time
import uuid

from ..db.database import get_db
from ..pipeline.pipeline_executor import execute_pipeline
from ..pipeline.derived_classifications import compute_derived_classifications, classify_zombie, compute_zombie_status
import re
from ..models.output_contracts import RunLog, RunCounts, Asset, Finding, RunStatus, SyncStatus
from ..farm_client import FarmClient, FarmListResult, validate_schema_version
from ..farm_reconcile import reconcile_to_farm


router = APIRouter(prefix="/api")

class FarmRunRequest(BaseModel):
    """Request for creating a run from Farm"""
    tenant_id: str
    farm_base_url: str | None = None
    snapshot_id: str


class RunResponse(BaseModel):
    """Response for run creation"""
    run_id: str
    tenant_id: str
    status: str
    counts: RunCounts
    message: str
    sync_status: Optional[str] = None
    sync_error: Optional[str] = None


class RunDetailResponse(BaseModel):
    """Response for run detail"""
    run_id: str
    tenant_id: str
    status: str
    started_at: str
    completed_at: Optional[str]
    input_meta: dict
    counts: RunCounts
    failure_reasons: list[str]
    sync_status: str = "not_applicable"
    sync_error: Optional[str] = None


class CatalogResponse(BaseModel):
    """Response for catalog"""
    run_id: str
    assets: list[dict[str, Any]]
    count: int


class FindingsResponse(BaseModel):
    """Response for findings"""
    run_id: str
    findings: list[dict[str, Any]]
    count: int


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str


class SnapshotListResponse(BaseModel):
    """Response for snapshot listing"""
    snapshots: list[dict[str, Any]]
    count: int


class TenantListResponse(BaseModel):
    """Response for tenant listing"""
    tenants: list[str]
    count: int


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        version="1.0.0"
    )


@router.get("/farm/url")
async def get_farm_url():
    """Get the configured Farm URL"""
    farm_url = os.environ.get("FARM_URL")
    return {"farm_url": farm_url}


@router.get("/farm/tenants", response_model=TenantListResponse)
async def list_farm_tenants():
    """
    List available tenants from Farm.
    
    Fetches all snapshots and extracts unique tenant_ids.
    """
    farm_url = os.environ.get("FARM_URL")
    if not farm_url:
        raise HTTPException(status_code=400, detail="No Farm URL configured. Set FARM_URL environment variable.")
    
    farm_client = FarmClient(farm_url)
    result = await farm_client.list_snapshots("", limit=100)
    
    if not result.success:
        raise HTTPException(
            status_code=502,
            detail=f"{result.error_type}: {result.error}"
        )
    
    snapshots = result.snapshots or []
    tenants = sorted(set(s.get("tenant_id", "") for s in snapshots if s.get("tenant_id")))
    return TenantListResponse(tenants=tenants, count=len(tenants))


@router.get("/farm/snapshots", response_model=SnapshotListResponse)
async def list_farm_snapshots(tenant_id: str, size: Optional[str] = None):
    """
    List available snapshots from Farm for a tenant.
    
    Proxies to {FARM_URL}/api/snapshots?tenant_id=<tenant>&limit=20&size=<size>
    Returns metadata list with snapshot_id, tenant_id, created_at, schema_version.
    
    Args:
        tenant_id: The tenant to filter snapshots by
        size: Optional size filter (small, medium, large)
    """
    farm_url = os.environ.get("FARM_URL")
    if not farm_url:
        raise HTTPException(status_code=400, detail="No Farm URL configured. Set FARM_URL environment variable.")
    
    farm_client = FarmClient(farm_url)
    result = await farm_client.list_snapshots(tenant_id, size=size)
    
    if not result.success:
        raise HTTPException(
            status_code=502,
            detail=f"{result.error_type}: {result.error}"
        )
    
    snapshots = result.snapshots or []
    return SnapshotListResponse(
        snapshots=snapshots,
        count=len(snapshots)
    )


@router.post("/runs", response_model=RunResponse)
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
    
    db = await get_db()
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


@router.post("/runs/json", response_model=RunResponse)
async def create_run_json(snapshot: dict[str, Any]):
    """
    Create a new discovery run from JSON body.
    
    Accepts a snapshot JSON object directly.
    Returns run_id + summary counts.
    """
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    started_at = now_pst()
    
    db = await get_db()
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


@router.post("/runs/from-farm", response_model=RunResponse)
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
    farm_url = request.farm_base_url or os.environ.get("FARM_URL")
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
    
    provenance = {
        "source": "farm",
        "farm_url": farm_url,
        "snapshot_id": request.snapshot_id,
        "schema_version": schema_version,
        "fetch_duration_ms": fetch_duration_ms
    }
    
    db = await get_db()
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

        # Performance: Batch database queries in single transaction (3x faster)
        run_data = await db.get_run_data_batch(run_id)
        assets = run_data["assets"]
        findings = run_data["findings"]
        rejections = run_data["rejections"]

        success, error = await reconcile_to_farm(
            run_log=result.run_log,
            assets=assets,
            findings=findings,
            snapshot_id=request.snapshot_id,
            farm_url=farm_url,
            rejections=rejections
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


class ResyncRequest(BaseModel):
    """Request for re-syncing a run to Farm"""
    run_id: str
    mode: str = "sprawl"


class ResyncResponse(BaseModel):
    """Response for re-sync operation"""
    run_id: str
    sync_status: str
    sync_error: Optional[str] = None
    shadow_asset_keys: list[str]
    zombie_asset_keys: list[str]
    asset_summaries_keys: list[str]


@router.post("/runs/resync", response_model=ResyncResponse)
async def resync_run_to_farm(request: ResyncRequest):
    """
    Re-sync an existing run to Farm.
    
    This endpoint allows manually re-triggering the Farm callback for an existing run.
    Useful for testing that the callback payload contains correct domain-keyed assets.
    
    Returns the sync status and a sample of the payload that was sent.
    """
    db = await get_db()
    run = await db.get_run(request.run_id)
    
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {request.run_id} not found")
    
    farm_url = os.environ.get("FARM_URL")
    if not farm_url:
        raise HTTPException(status_code=400, detail="No Farm URL configured")
    
    snapshot_id = run.input_meta.get("snapshot_id")
    if not snapshot_id:
        raise HTTPException(status_code=400, detail="Run has no snapshot_id in metadata")

    # Performance: Batch database queries in single transaction (3x faster)
    run_data = await db.get_run_data_batch(request.run_id)
    assets = run_data["assets"]
    findings = run_data["findings"]
    rejections = run_data["rejections"]

    mode = request.mode or "sprawl"
    
    success, error = await reconcile_to_farm(
        run_log=run,
        assets=assets,
        findings=findings,
        snapshot_id=snapshot_id,
        farm_url=farm_url,
        rejections=rejections,
        mode=mode
    )
    
    if success:
        run.sync_status = SyncStatus.SYNCED
        run.sync_error = None
    else:
        run.sync_status = SyncStatus.FAILED
        run.sync_error = error
    
    await db.update_run(run)
    
    from ..pipeline.aod_agent_reconcile import emit_actual_results
    actual_results = emit_actual_results(
        run_id=request.run_id,
        assets=assets,
        activity_window_days=90,
        rejections=rejections,
        mode=mode
    )
    
    return ResyncResponse(
        run_id=request.run_id,
        sync_status=run.sync_status.value,
        sync_error=run.sync_error,
        shadow_asset_keys=actual_results.shadow_actual,
        zombie_asset_keys=actual_results.zombie_actual,
        asset_summaries_keys=sorted(actual_results.actual_reasons.keys())
    )


@router.get("/runs/latest", response_model=RunDetailResponse)
async def get_latest_run(tenant_id: str, snapshot_id: Optional[str] = None):
    """
    Get the latest run for a tenant and optionally a specific snapshot.

    Returns HTTP 404 if no matching run exists.
    """
    db = await get_db()
    # Performance: Use database filtering instead of loading all runs
    runs = await db.get_runs_by_tenant(tenant_id, snapshot_id)

    if not runs:
        raise HTTPException(status_code=404, detail=f"No run found for tenant {tenant_id}" + (f" and snapshot {snapshot_id}" if snapshot_id else ""))

    run = runs[0]
    return RunDetailResponse(
        run_id=run.run_id,
        tenant_id=run.tenant_id,
        status=run.status.value,
        started_at=run.started_at.isoformat(),
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        input_meta=run.input_meta,
        counts=run.counts,
        failure_reasons=run.failure_reasons,
        sync_status=run.sync_status.value,
        sync_error=run.sync_error
    )


@router.get("/runs", response_model=list[RunDetailResponse])
async def list_runs(tenant_id: Optional[str] = None):
    """List all discovery runs, optionally filtered by tenant_id"""
    db = await get_db()
    # Performance: Use database filtering when tenant_id specified
    if tenant_id:
        runs = await db.get_runs_by_tenant(tenant_id)
    else:
        runs = await db.get_all_runs()

    return [
        RunDetailResponse(
            run_id=run.run_id,
            tenant_id=run.tenant_id,
            status=run.status.value,
            started_at=run.started_at.isoformat(),
            completed_at=run.completed_at.isoformat() if run.completed_at else None,
            input_meta=run.input_meta,
            counts=run.counts,
            failure_reasons=run.failure_reasons,
            sync_status=run.sync_status.value,
            sync_error=run.sync_error
        )
        for run in runs
    ]


@router.delete("/runs")
async def delete_all_runs():
    """Delete all discovery runs and associated data"""
    db = await get_db()
    deleted = await db.delete_all_runs()
    return {"message": f"Deleted {deleted} runs and all associated data", "deleted": deleted}


@router.get("/runs/{run_id}", response_model=RunDetailResponse)
async def get_run(run_id: str):
    """Get run detail + counts"""
    db = await get_db()
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
        failure_reasons=run.failure_reasons,
        sync_status=run.sync_status.value,
        sync_error=run.sync_error
    )


@router.get("/catalog", response_model=CatalogResponse)
async def get_catalog(run_id: str):
    """Get assets for a run"""
    db = await get_db()
    
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    assets = await db.get_assets_by_run(run_id)
    
    return CatalogResponse(
        run_id=run_id,
        assets=[
            {
                "asset_id": str(a.asset_id),
                "name": a.name,
                "asset_type": a.asset_type.value,
                "vendor": a.vendor,
                "environment": a.environment.value,
                "identifiers": a.identifiers.model_dump(),
                "lens_status": a.lens_status.model_dump(),
                "lens_coverage": a.lens_coverage.model_dump(),
                "tags": a.tags,
                "admission_reason": a.admission_reason,
                "evidence_refs": a.evidence_refs,
                "created_at": a.created_at.isoformat()
            }
            for a in assets
        ],
        count=len(assets)
    )


@router.get("/catalog/view", response_class=HTMLResponse)
async def view_catalog(run_id: str):
    """Display catalog as HTML page"""
    db = await get_db()
    
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    assets = await db.get_assets_by_run(run_id)
    
    triage_actions = await db.get_triage_actions_by_run(run_id)
    findings = await db.get_findings_by_run(run_id)
    
    finding_to_asset = {str(f.finding_id): str(f.asset_id) for f in findings if f.asset_id}
    
    triage_by_asset = {}
    for action in triage_actions:
        item_id = action.get('item_id')
        item_type = action.get('item_type')
        
        if item_type == 'asset':
            triage_by_asset[item_id] = action
        elif item_type == 'finding':
            asset_id = finding_to_asset.get(item_id)
            if asset_id and asset_id not in triage_by_asset:
                triage_by_asset[asset_id] = action
    
    def get_tag(asset, key):
        """Get tag value from asset, handling both dict and list formats"""
        if not asset.tags:
            return None
        if isinstance(asset.tags, dict):
            return asset.tags.get(key)
        return None
    
    def get_triage_badge(asset_id):
        """Get triage disposition badge for an asset"""
        action = triage_by_asset.get(str(asset_id))
        if not action:
            return ''
        
        action_type = action.get('action_type', '')
        state = action.get('state', '')
        
        if action_type == 'assign':
            owner = action.get('metadata', {}).get('assigned_to', '')
            return f'<span style="background: #3b82f6; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 500;">Assigned: {owner}</span>'
        elif action_type == 'defer':
            days = action.get('metadata', {}).get('defer_days', '')
            return f'<span style="background: #8b5cf6; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 500;">Deferred {days}d</span>'
        elif action_type == 'ignore':
            return '<span style="background: #64748b; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 500;">Ignored</span>'
        elif state == 'acknowledged':
            return '<span style="background: #0ea5e9; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 500;">Acknowledged</span>'
        return ''
    
    shadow_count = sum(1 for a in assets if get_tag(a, 'shadow_actual') == True)
    zombie_count = sum(1 for a in assets if get_tag(a, 'zombie_actual') == True)
    governed_count = sum(1 for a in assets if a.lens_status and (a.lens_status.cmdb or a.lens_status.idp))
    
    # Triage summary stats
    triage_stats = {'acknowledged': 0, 'assigned': 0, 'deferred': 0, 'ignored': 0, 'pending': 0}
    triaged_asset_ids = set()
    for action in triage_actions:
        action_type = action.get('action_type', '')
        item_id = action.get('item_id', '')
        if action_type == 'acknowledge' or action.get('state') == 'acknowledged':
            triage_stats['acknowledged'] += 1
        elif action_type == 'assign':
            triage_stats['assigned'] += 1
        elif action_type == 'defer':
            triage_stats['deferred'] += 1
        elif action_type == 'ignore':
            triage_stats['ignored'] += 1
        triaged_asset_ids.add(item_id)
    triage_stats['pending'] = len(assets) - len(triaged_asset_ids.intersection({str(a.asset_id) for a in assets}))
    
    triaged_finding_ids = {action['item_id'] for action in triage_actions if action.get('item_type') == 'finding'}
    orphan_findings = [f for f in findings if not f.asset_id and str(f.finding_id) in triaged_finding_ids]
    
    def get_finding_triage_badge(finding_id):
        """Get triage disposition badge for a finding"""
        for action in triage_actions:
            if action.get('item_id') == str(finding_id):
                action_type = action.get('action', '')
                state = action.get('state', '')
                
                if action_type == 'assign':
                    owner = action.get('owner', '')
                    return f'<span style="background: #3b82f6; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 500;">Assigned: {owner}</span>'
                elif action_type == 'defer':
                    defer_until = action.get('defer_until', '')
                    return f'<span style="background: #8b5cf6; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 500;">Deferred</span>'
                elif action_type == 'ignore':
                    return '<span style="background: #64748b; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 500;">Ignored</span>'
                elif action_type == 'acknowledge' or state == 'acknowledged':
                    return '<span style="background: #0ea5e9; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 500;">Acknowledged</span>'
        return ''
    
    orphan_rows_html = ""
    for f in orphan_findings:
        vendor_match = None
        if f.explanation:
            import re
            match = re.search(r"Vendor '([^']+)'", f.explanation)
            if match:
                vendor_match = match.group(1)
        
        finding_type_display = f.finding_type.value.replace('_', ' ').title() if f.finding_type else '-'
        triage_badge = get_finding_triage_badge(f.finding_id)
        
        orphan_rows_html += f'''
        <tr style="border-bottom: 1px solid #334155;" data-type="finding" data-name="{vendor_match or 'Unknown'}">
            <td style="padding: 0.75rem; color: #f59e0b; font-weight: 500;">{vendor_match or 'Unknown Vendor'}</td>
            <td style="padding: 0.75rem; color: #94a3b8;">{finding_type_display}</td>
            <td style="padding: 0.75rem; color: #64748b; font-size: 0.8rem; max-width: 400px; overflow: hidden; text-overflow: ellipsis;">{f.explanation[:100] + '...' if f.explanation and len(f.explanation) > 100 else f.explanation or '-'}</td>
            <td style="padding: 0.75rem;">{triage_badge}</td>
        </tr>'''
    
    rows_html = ""
    for a in assets:
        is_shadow = get_tag(a, 'shadow_actual') == True
        is_zombie = get_tag(a, 'zombie_actual') == True
        
        status_badges = []
        if is_shadow:
            status_badges.append('<span style="background: #f59e0b; color: #000; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 600;">SHADOW</span>')
        if is_zombie:
            status_badges.append('<span style="background: #ef4444; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 600;">ZOMBIE</span>')
        if not is_shadow and not is_zombie:
            status_badges.append('<span style="background: #22c55e; color: #000; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 600;">GOVERNED</span>')
        
        lens_parts = []
        if a.lens_coverage:
            if a.lens_coverage.discovery: lens_parts.append('Discovery')
            if a.lens_coverage.idp: lens_parts.append('IdP')
            if a.lens_coverage.cmdb: lens_parts.append('CMDB')
            if a.lens_coverage.cloud: lens_parts.append('Cloud')
            if a.lens_coverage.finance: lens_parts.append('Finance')
        
        triage_badge = get_triage_badge(a.asset_id)
        
        rows_html += f'''
        <tr style="border-bottom: 1px solid #334155;">
            <td style="padding: 0.75rem; color: #06b6d4; font-weight: 500;">{a.name or 'Unknown'}</td>
            <td style="padding: 0.75rem; color: #94a3b8;">{a.vendor or '-'}</td>
            <td style="padding: 0.75rem; color: #94a3b8;">{a.asset_type.value if a.asset_type else '-'}</td>
            <td style="padding: 0.75rem; color: #94a3b8;">{a.environment.value if a.environment else '-'}</td>
            <td style="padding: 0.75rem;">{' '.join(status_badges)}</td>
            <td style="padding: 0.75rem; color: #64748b; font-size: 0.8rem;">{', '.join(lens_parts) or '-'}</td>
            <td style="padding: 0.75rem; color: #64748b; font-size: 0.75rem;">{a.admission_reason or '-'}</td>
            <td style="padding: 0.75rem;">{triage_badge or '<span style="color: #475569; font-size: 0.75rem;">-</span>'}</td>
        </tr>'''
    
    orphan_section = ""
    if orphan_rows_html:
        sort_icon = "&#8597;"
        orphan_section = f'''
            <div class="section-header">
                <div class="section-title">Triaged Findings (No Asset)</div>
                <div class="section-subtitle">{len(orphan_findings)} finding(s) triaged for vendors without a corresponding cataloged asset</div>
            </div>
            <table id="findingsTable">
                <thead>
                    <tr>
                        <th onclick="sortTable('findingsTable', 0)">Vendor <span class="sort-icon">{sort_icon}</span></th>
                        <th onclick="sortTable('findingsTable', 1)">Finding Type <span class="sort-icon">{sort_icon}</span></th>
                        <th>Description</th>
                        <th onclick="sortTable('findingsTable', 3)">Triage <span class="sort-icon">{sort_icon}</span></th>
                    </tr>
                </thead>
                <tbody>
                    {orphan_rows_html}
                </tbody>
            </table>
        '''
    
    # Triage summary section
    triage_summary_section = f'''
        <div id="triageSummary" class="section-header" style="border-left-color: #06b6d4;">
            <div class="section-title" style="color: #06b6d4;">Triage Summary</div>
            <div class="section-subtitle">Overview of triage actions taken on assets in this run</div>
        </div>
        <div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 1rem; margin-bottom: 2rem;">
            <div class="stat">
                <div class="stat-value" style="color: #f59e0b;">{triage_stats['pending']}</div>
                <div class="stat-label">Pending Review</div>
            </div>
            <div class="stat">
                <div class="stat-value" style="color: #0ea5e9;">{triage_stats['acknowledged']}</div>
                <div class="stat-label">Acknowledged</div>
            </div>
            <div class="stat">
                <div class="stat-value" style="color: #3b82f6;">{triage_stats['assigned']}</div>
                <div class="stat-label">Assigned</div>
            </div>
            <div class="stat">
                <div class="stat-value" style="color: #8b5cf6;">{triage_stats['deferred']}</div>
                <div class="stat-label">Deferred</div>
            </div>
            <div class="stat">
                <div class="stat-value" style="color: #64748b;">{triage_stats['ignored']}</div>
                <div class="stat-label">Ignored</div>
            </div>
        </div>
    '''
    
    sort_icon = "&#8597;"
    html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Asset Catalog - Run {run_id[:8]}</title>
        <link href="https://fonts.googleapis.com/css2?family=Quicksand:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ 
                font-family: 'Quicksand', sans-serif; 
                background: #0f172a; 
                color: #e2e8f0; 
                padding: 2rem;
                min-height: 100vh;
            }}
            .container {{ max-width: 1400px; margin: 0 auto; }}
            .header {{ 
                display: flex; 
                justify-content: space-between; 
                align-items: center; 
                margin-bottom: 2rem;
                padding-bottom: 1rem;
                border-bottom: 1px solid #334155;
            }}
            .title {{ font-size: 1.5rem; font-weight: 700; color: #06b6d4; }}
            .subtitle {{ font-size: 0.9rem; color: #64748b; margin-top: 0.25rem; }}
            .stats {{ display: flex; gap: 1.5rem; }}
            .stat {{ 
                background: #1e293b; 
                padding: 0.75rem 1.25rem; 
                border-radius: 8px;
                text-align: center;
            }}
            .stat-value {{ font-size: 1.25rem; font-weight: 700; color: #06b6d4; }}
            .stat-label {{ font-size: 0.75rem; color: #64748b; }}
            .export-btn {{
                background: #334155;
                color: #e2e8f0;
                padding: 0.5rem 1rem;
                border-radius: 6px;
                text-decoration: none;
                font-size: 0.85rem;
                display: inline-flex;
                align-items: center;
                gap: 0.5rem;
            }}
            .export-btn:hover {{ background: #475569; }}
            table {{ 
                width: 100%; 
                border-collapse: collapse; 
                background: #1e293b; 
                border-radius: 8px;
                overflow: hidden;
            }}
            th {{ 
                background: #334155; 
                padding: 0.75rem; 
                text-align: left; 
                font-weight: 600;
                color: #94a3b8;
                font-size: 0.8rem;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                cursor: pointer;
                user-select: none;
            }}
            th:hover {{ background: #3f5165; }}
            th .sort-icon {{ opacity: 0.5; margin-left: 0.25rem; }}
            th.sorted .sort-icon {{ opacity: 1; }}
            tr:hover {{ background: #263445; }}
            .section-header {{ 
                margin-top: 2rem; 
                margin-bottom: 1rem; 
                padding: 0.75rem 1rem;
                background: #1e293b;
                border-radius: 8px;
                border-left: 4px solid #f59e0b;
            }}
            .section-title {{ font-size: 1rem; font-weight: 600; color: #f59e0b; }}
            .section-subtitle {{ font-size: 0.8rem; color: #64748b; margin-top: 0.25rem; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div>
                    <div class="title">Asset Catalog</div>
                    <div class="subtitle">
                        Run: {run_id[:8]}... | 
                        Tenant: {run.tenant_id} | 
                        {run.completed_at.strftime('%Y-%m-%d %H:%M') if run.completed_at else 'In Progress'}
                    </div>
                </div>
                <div style="display: flex; align-items: center; gap: 1rem;">
                    <div class="stats">
                        <div class="stat">
                            <div class="stat-value">{len(assets)}</div>
                            <div class="stat-label">Total Assets</div>
                        </div>
                        <div class="stat">
                            <div class="stat-value" style="color: #f59e0b;">{shadow_count}</div>
                            <div class="stat-label">Shadow</div>
                        </div>
                        <div class="stat">
                            <div class="stat-value" style="color: #ef4444;">{zombie_count}</div>
                            <div class="stat-label">Zombie</div>
                        </div>
                        <div class="stat">
                            <div class="stat-value" style="color: #22c55e;">{governed_count}</div>
                            <div class="stat-label">Governed</div>
                        </div>
                    </div>
                    <a href="/api/catalog?run_id={run_id}" class="export-btn" target="_blank">
                        Export JSON ↗
                    </a>
                </div>
            </div>
            <table id="assetsTable">
                <thead>
                    <tr>
                        <th onclick="sortTable('assetsTable', 0)">Asset Name <span class="sort-icon">{sort_icon}</span></th>
                        <th onclick="sortTable('assetsTable', 1)">Vendor <span class="sort-icon">{sort_icon}</span></th>
                        <th onclick="sortTable('assetsTable', 2)">Type <span class="sort-icon">{sort_icon}</span></th>
                        <th onclick="sortTable('assetsTable', 3)">Environment <span class="sort-icon">{sort_icon}</span></th>
                        <th onclick="sortTable('assetsTable', 4)">Status <span class="sort-icon">{sort_icon}</span></th>
                        <th onclick="sortTable('assetsTable', 5)">Data Sources <span class="sort-icon">{sort_icon}</span></th>
                        <th onclick="sortTable('assetsTable', 6)">Admission Reason <span class="sort-icon">{sort_icon}</span></th>
                        <th onclick="scrollToTriageSummary()" style="color: #06b6d4; cursor: pointer;" title="Click to view triage summary">Triage ↓</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html if rows_html else '<tr><td colspan="8" style="padding: 2rem; text-align: center; color: #64748b;">No assets in catalog</td></tr>'}
                </tbody>
            </table>
            
            {orphan_section}
            
            {triage_summary_section}
        </div>
        <script>
            function scrollToTriageSummary() {{
                const el = document.getElementById('triageSummary');
                if (el) {{
                    el.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
                }}
            }}
            let sortDirections = {{}};
            function sortTable(tableId, colIndex) {{
                const table = document.getElementById(tableId);
                const tbody = table.querySelector('tbody');
                const rows = Array.from(tbody.querySelectorAll('tr'));
                
                const dir = sortDirections[tableId + '_' + colIndex] === 'asc' ? 'desc' : 'asc';
                sortDirections[tableId + '_' + colIndex] = dir;
                
                rows.sort((a, b) => {{
                    const aText = a.cells[colIndex]?.textContent?.trim() || '';
                    const bText = b.cells[colIndex]?.textContent?.trim() || '';
                    const cmp = aText.localeCompare(bText);
                    return dir === 'asc' ? cmp : -cmp;
                }});
                
                rows.forEach(row => tbody.appendChild(row));
                
                table.querySelectorAll('th').forEach((th, i) => {{
                    th.classList.toggle('sorted', i === colIndex);
                }});
            }}
        </script>
    </body>
    </html>
    '''
    return HTMLResponse(content=html)


@router.get("/findings", response_model=FindingsResponse)
async def get_findings(run_id: str):
    """Get findings for a run"""
    db = await get_db()
    
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    findings = await db.get_findings_by_run(run_id)
    assets = await db.get_assets_by_run(run_id)
    
    asset_map = {str(a.asset_id): a.name for a in assets}
    
    return FindingsResponse(
        run_id=run_id,
        findings=[
            {
                "finding_id": str(f.finding_id),
                "asset_id": str(f.asset_id) if f.asset_id else None,
                "asset_name": asset_map.get(str(f.asset_id), "") if f.asset_id else "",
                "finding_type": f.finding_type.value,
                "category": f.category.value,
                "severity": f.severity.value,
                "explanation": f.explanation,
                "evidence_refs": f.evidence_refs,
                "created_at": f.created_at.isoformat()
            }
            for f in findings
        ],
        count=len(findings)
    )


@router.get("/artifacts")
async def get_artifacts(run_id: str):
    """Get artifacts for a run"""
    db = await get_db()
    
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    artifacts = await db.get_artifacts_by_run(run_id)
    
    return {
        "run_id": run_id,
        "artifacts": [
            {
                "artifact_id": str(a.artifact_id),
                "name": a.name,
                "artifact_type": a.artifact_type.value,
                "source": a.source,
                "evidence_ref": a.evidence_ref,
                "parent_asset_id": str(a.parent_asset_id) if a.parent_asset_id else None,
                "created_at": a.created_at.isoformat()
            }
            for a in artifacts
        ],
        "count": len(artifacts)
    }


@router.get("/runs/{run_id}/observations")
async def get_observations(run_id: str, limit: int = 100, offset: int = 0):
    """Get observation samples for a run"""
    db = await get_db()
    
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


def _generate_ambiguous_explanation(item: dict) -> str:
    """Generate plain English explanation for why a match is ambiguous."""
    entity_name = item.get("entity_name", "Unknown")
    plane = item.get("plane", "unknown")
    candidate_ids = item.get("candidate_ids", [])
    candidate_names = item.get("candidate_names", [])
    
    num_candidates = len(candidate_ids)
    
    plane_labels = {
        "idp": "identity provider",
        "cmdb": "CMDB",
        "cloud": "cloud inventory",
        "finance": "finance system",
        "discovery": "discovery"
    }
    plane_label = plane_labels.get(plane, plane)
    
    if plane == "finance":
        vendors = [n for n in candidate_names if not n.startswith("transaction_id=")]
        transactions = [n for n in candidate_names if n.startswith("transaction_id=")]
        
        parts = []
        if vendors:
            parts.append(f"{len(vendors)} vendor record{'s' if len(vendors) > 1 else ''}")
        if transactions:
            parts.append(f"{len(transactions)} transaction{'s' if len(transactions) > 1 else ''}")
        
        records_desc = " and ".join(parts) if parts else f"{num_candidates} records"
        
        return (
            f'"{entity_name}" matched {records_desc} in the {plane_label}. '
            f"This is ambiguous because multiple separate payment records could represent "
            f"the same vendor relationship, making it unclear which is authoritative."
        )
    
    elif plane == "idp":
        return (
            f'"{entity_name}" matched {num_candidates} identity records. '
            f"This is ambiguous because the application name appears in multiple SSO/SCIM entries, "
            f"possibly due to naming variations or duplicate app registrations."
        )
    
    elif plane == "cmdb":
        return (
            f'"{entity_name}" matched {num_candidates} CMDB configuration items. '
            f"This is ambiguous because multiple CI records exist with similar names, "
            f"possibly due to environment variants (dev/prod) or legacy entries."
        )
    
    elif plane == "cloud":
        return (
            f'"{entity_name}" matched {num_candidates} cloud resources. '
            f"This is ambiguous because multiple cloud assets share this name, "
            f"possibly across regions, accounts, or resource types."
        )
    
    else:
        return (
            f'"{entity_name}" matched {num_candidates} records in the {plane_label}. '
            f"This is ambiguous because multiple records could represent this asset."
        )


@router.get("/runs/{run_id}/ambiguous")
async def get_ambiguous(run_id: str, limit: int = 100, offset: int = 0):
    """Get ambiguous matches for a run"""
    db = await get_db()
    
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


@router.get("/runs/{run_id}/rejections")
async def get_rejections(run_id: str, limit: int = 100, offset: int = 0):
    """Get rejections for a run"""
    db = await get_db()
    
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


@router.get("/runs/{run_id}/assets")
async def get_run_assets(run_id: str, classification: Optional[str] = None):
    """Get assets for a run, optionally filtered by classification"""
    db = await get_db()
    
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    assets = await db.get_assets_by_run(run_id)
    
    if classification:
        summary = compute_derived_classifications(assets, activity_window_days=90)
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


@router.get("/runs/{run_id}/summary")
async def get_run_summary(run_id: str):
    """Get summary for a run including derived classifications"""
    db = await get_db()
    
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    assets = await db.get_assets_by_run(run_id)
    findings = await db.get_findings_by_run(run_id)
    derived = compute_derived_classifications(assets, activity_window_days=90)
    
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


@router.get("/runs/{run_id}/classifications")
async def get_classifications(run_id: str):
    """Get shadow/zombie classifications for a run"""
    db = await get_db()
    
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    assets = await db.get_assets_by_run(run_id)
    derived = compute_derived_classifications(assets, activity_window_days=90)
    
    return {
        "run_id": run_id,
        "shadow_count": derived.shadow_count,
        "zombie_count": derived.zombie_count,
        "shadow_assets": [a["name"] for a in derived.shadow_assets],
        "zombie_assets": [a["name"] for a in derived.zombie_assets]
    }


@router.get("/runs/{run_id}/reconcile-payload")
async def get_reconcile_payload(run_id: str):
    """Get the reconcile payload that would be sent to Farm.
    
    Uses build_reconcile_payload() from farm_reconcile module.
    This is the SINGLE SOURCE OF TRUTH for payload structure,
    shared with the actual reconcile_to_farm() callback.
    """
    from ..farm_reconcile import build_reconcile_payload
    
    db = await get_db()
    
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    # Performance: Batch database queries in single transaction (3x faster)
    run_data = await db.get_run_data_batch(run_id)
    assets = run_data["assets"]
    findings = run_data["findings"]
    rejections = run_data["rejections"]

    snapshot_id = run.input_meta.get("snapshot_id") if run.input_meta else None
    
    return build_reconcile_payload(
        run_log=run,
        assets=assets,
        findings=findings,
        snapshot_id=snapshot_id,
        rejections=rejections
    )


@router.get("/runs/{run_id}/lens")
async def get_lens_summary(run_id: str):
    """Get lens status summary for a run"""
    db = await get_db()
    
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


@router.get("/runs/{run_id}/derived")
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
    db = await get_db()
    
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    assets = await db.get_assets_by_run(run_id)
    
    summary = compute_derived_classifications(assets, activity_window_days)
    
    return {
        "run_id": run_id,
        "activity_window_days": activity_window_days,
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


def normalize_key(name: str) -> str:
    """
    Normalize an asset name to a key for matching.
    Removes special chars, lowercases, strips whitespace.
    e.g. "Slack.com" -> "slackcom", "PostgreSQL Main" -> "postgresqlmain"
    """
    key = name.lower()
    key = re.sub(r'[^a-z0-9]', '', key)
    return key


class ZombieExplainRequest(BaseModel):
    """Request for zombie explanation"""
    tenant_id: str
    run_id: str
    keys: list[str]
    window_days: int = 30


class KeyExplanation(BaseModel):
    """Explanation for a single key"""
    key: str
    matched_asset_ids: list[str]
    normalized_keys_considered: list[str]
    idp_present: bool
    idp_evidence: Optional[dict] = None
    cmdb_present: bool
    cmdb_evidence: Optional[dict] = None
    activity_signals: dict[str, Optional[str]]
    activity_within_window: Optional[bool]
    zombie_decision: str
    why: list[str]


class ZombieExplainResponse(BaseModel):
    """Response for zombie explanation"""
    run_id: str
    tenant_id: str
    window_days: int
    explanations: list[KeyExplanation]
    summary: dict


@router.post("/debug/zombie-explain", response_model=ZombieExplainResponse)
async def debug_zombie_explain(request: ZombieExplainRequest):
    """
    Debug endpoint to explain zombie classification decisions.
    
    For each key provided, finds matching assets and explains
    why each was or wasn't classified as a zombie.
    
    Keys are normalized (lowercase, alphanumeric only) for matching.
    """
    db = await get_db()
    
    run = await db.get_run(request.run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {request.run_id} not found")
    
    if run.tenant_id != request.tenant_id:
        raise HTTPException(status_code=400, detail=f"Run {request.run_id} belongs to tenant {run.tenant_id}, not {request.tenant_id}")
    
    assets = await db.get_assets_by_run(request.run_id)
    
    asset_key_map: dict[str, list[Asset]] = {}
    for asset in assets:
        key = normalize_key(asset.name)
        if key not in asset_key_map:
            asset_key_map[key] = []
        asset_key_map[key].append(asset)
        
        for domain in asset.identifiers.domains:
            domain_key = normalize_key(domain)
            if domain_key not in asset_key_map:
                asset_key_map[domain_key] = []
            if asset not in asset_key_map[domain_key]:
                asset_key_map[domain_key].append(asset)
        
        if asset.vendor:
            vendor_key = normalize_key(asset.vendor)
            if vendor_key not in asset_key_map:
                asset_key_map[vendor_key] = []
            if asset not in asset_key_map[vendor_key]:
                asset_key_map[vendor_key].append(asset)
    
    explanations = []
    reason_counts: dict[str, int] = {
        "key_not_mapped": 0,
        "not_in_idp_cmdb": 0,
        "activity_within_window": 0,
        "no_activity_timestamps": 0,
        "activity_stale": 0,
        "zombie_yes": 0,
        "zombie_no": 0,
        "indeterminate": 0
    }
    
    cutoff_date = now_pst() - timedelta(days=request.window_days)
    
    for input_key in request.keys:
        normalized_input = normalize_key(input_key)
        
        matching_assets = asset_key_map.get(normalized_input, [])
        
        if not matching_assets:
            partial_matches = [k for k in asset_key_map.keys() if normalized_input in k or k in normalized_input]
            
            explanations.append(KeyExplanation(
                key=input_key,
                matched_asset_ids=[],
                normalized_keys_considered=[normalized_input] + partial_matches[:5],
                idp_present=False,
                cmdb_present=False,
                activity_signals={},
                activity_within_window=None,
                zombie_decision="INDETERMINATE",
                why=[
                    f"Key '{input_key}' (normalized: '{normalized_input}') did not map to any asset",
                    f"Partial matches found: {partial_matches[:5]}" if partial_matches else "No partial matches found",
                    "Cannot classify as zombie without a matching asset"
                ]
            ))
            reason_counts["key_not_mapped"] += 1
            reason_counts["indeterminate"] += 1
            continue
        
        for asset in matching_assets:
            asset_key = normalize_key(asset.name)
            domain_keys = [normalize_key(d) for d in asset.identifiers.domains]
            vendor_key = normalize_key(asset.vendor) if asset.vendor else None
            
            keys_considered = [asset_key] + domain_keys
            if vendor_key:
                keys_considered.append(vendor_key)
            
            from ..models.output_contracts import LensStatus
            idp_present = asset.lens_status.idp == LensStatus.MATCHED
            cmdb_present = asset.lens_status.cmdb == LensStatus.MATCHED
            
            idp_evidence = None
            if idp_present:
                idp_evidence = {
                    "lens_status": asset.lens_status.idp.value,
                    "last_login_at": asset.activity_evidence.idp_last_login_at.isoformat() if asset.activity_evidence.idp_last_login_at else None
                }
            
            cmdb_evidence = None
            if cmdb_present:
                cmdb_evidence = {
                    "lens_status": asset.lens_status.cmdb.value,
                    "lens_coverage": asset.lens_coverage.cmdb
                }
            
            activity_signals = {
                "discovery_observed_at": asset.activity_evidence.discovery_observed_at.isoformat() if asset.activity_evidence.discovery_observed_at else None,
                "idp_last_login_at": asset.activity_evidence.idp_last_login_at.isoformat() if asset.activity_evidence.idp_last_login_at else None,
                "endpoint_last_seen_at": asset.activity_evidence.endpoint_last_seen_at.isoformat() if asset.activity_evidence.endpoint_last_seen_at else None,
                "network_last_seen_at": asset.activity_evidence.network_last_seen_at.isoformat() if asset.activity_evidence.network_last_seen_at else None,
                "cloud_observed_at": asset.activity_evidence.cloud_observed_at.isoformat() if asset.activity_evidence.cloud_observed_at else None,
                "finance_last_transaction_at": asset.activity_evidence.finance_last_transaction_at.isoformat() if asset.activity_evidence.finance_last_transaction_at else None,
                "latest_activity_at": asset.activity_evidence.latest_activity_at.isoformat() if asset.activity_evidence.latest_activity_at else None
            }
            
            latest = asset.activity_evidence.latest_activity_at
            
            if latest is None:
                activity_within_window = None
            elif latest.tzinfo is None:
                activity_within_window = latest > cutoff_date.replace(tzinfo=None)
            else:
                activity_within_window = latest > cutoff_date
            
            is_zombie, is_indeterminate, zombie_reason = compute_zombie_status(asset, request.window_days)
            
            if is_zombie:
                zombie_decision = "YES"
                reason_counts["zombie_yes"] += 1
            elif is_indeterminate:
                zombie_decision = "INDETERMINATE"
                reason_counts["indeterminate"] += 1
            else:
                zombie_decision = "NO"
                reason_counts["zombie_no"] += 1
            
            why_bullets = []
            
            if not (idp_present or cmdb_present):
                why_bullets.append("Not in IdP or CMDB - cannot be zombie (zombie requires official presence)")
                reason_counts["not_in_idp_cmdb"] += 1
            else:
                official = []
                if idp_present:
                    official.append("IdP")
                if cmdb_present:
                    official.append("CMDB")
                why_bullets.append(f"Present in official systems: {', '.join(official)}")
                
                if latest is None:
                    if is_indeterminate:
                        why_bullets.append("No activity timestamps - indeterminate (cannot prove usage)")
                        reason_counts["no_activity_timestamps"] += 1
                    else:
                        why_bullets.append("No activity timestamps found - classified as zombie (no proof of usage)")
                        reason_counts["no_activity_timestamps"] += 1
                elif activity_within_window == False:
                    why_bullets.append(f"Last activity {latest.isoformat()} is outside {request.window_days}-day window - classified as zombie")
                    reason_counts["activity_stale"] += 1
                elif activity_within_window == True:
                    why_bullets.append(f"Recent activity found at {latest.isoformat()} - within {request.window_days}-day window - NOT zombie")
                    reason_counts["activity_within_window"] += 1
            
            why_bullets.append(zombie_reason)
            
            explanations.append(KeyExplanation(
                key=input_key,
                matched_asset_ids=[str(asset.asset_id)],
                normalized_keys_considered=keys_considered,
                idp_present=idp_present,
                idp_evidence=idp_evidence,
                cmdb_present=cmdb_present,
                cmdb_evidence=cmdb_evidence,
                activity_signals=activity_signals,
                activity_within_window=activity_within_window,
                zombie_decision=zombie_decision,
                why=why_bullets
            ))
    
    return ZombieExplainResponse(
        run_id=request.run_id,
        tenant_id=request.tenant_id,
        window_days=request.window_days,
        explanations=explanations,
        summary=reason_counts
    )


class ZombieReconcileRequest(BaseModel):
    """Request for zombie reconciliation report"""
    tenant_id: str
    run_id: str
    expected_zombie_keys: list[str]
    extra_zombie_keys: list[str]
    window_days: int = 30


class ZombieReconcileResponse(BaseModel):
    """Response for zombie reconciliation report"""
    run_id: str
    tenant_id: str
    window_days: int
    expected_count: int
    extra_count: int
    missed_zombies_summary: dict
    extra_zombies_summary: dict
    compact_report: str
    sample_explanation: Optional[dict] = None


@router.post("/debug/zombie-reconcile", response_model=ZombieReconcileResponse)
async def debug_zombie_reconcile(request: ZombieReconcileRequest):
    """
    Reconcile zombie classifications against Farm expectations.
    
    Takes two lists:
    - expected_zombie_keys: Keys Farm expects to be zombies (missed by AOD)
    - extra_zombie_keys: Keys AOD classified as zombies that Farm didn't expect
    
    Returns a compact report with counts by reason.
    """
    db = await get_db()
    
    run = await db.get_run(request.run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {request.run_id} not found")
    
    assets = await db.get_assets_by_run(request.run_id)
    
    asset_key_map: dict[str, list[Asset]] = {}
    for asset in assets:
        key = normalize_key(asset.name)
        if key not in asset_key_map:
            asset_key_map[key] = []
        asset_key_map[key].append(asset)
        
        for domain in asset.identifiers.domains:
            domain_key = normalize_key(domain)
            if domain_key not in asset_key_map:
                asset_key_map[domain_key] = []
            if asset not in asset_key_map[domain_key]:
                asset_key_map[domain_key].append(asset)
        
        if asset.vendor:
            vendor_key = normalize_key(asset.vendor)
            if vendor_key not in asset_key_map:
                asset_key_map[vendor_key] = []
            if asset not in asset_key_map[vendor_key]:
                asset_key_map[vendor_key].append(asset)
    
    def analyze_keys(keys: list[str], label: str) -> tuple[dict, list[dict]]:
        reasons: dict[str, int] = {
            "key_not_mapped": 0,
            "not_in_idp_cmdb": 0,
            "activity_within_window": 0,
            "no_activity_timestamps": 0,
            "activity_stale": 0
        }
        details = []
        cutoff_date = now_pst() - timedelta(days=request.window_days)
        
        for input_key in keys:
            normalized_input = normalize_key(input_key)
            matching_assets = asset_key_map.get(normalized_input, [])
            
            if not matching_assets:
                reasons["key_not_mapped"] += 1
                details.append({
                    "key": input_key,
                    "reason": "key_not_mapped",
                    "detail": f"No asset found matching '{normalized_input}'"
                })
                continue
            
            for asset in matching_assets:
                from ..models.output_contracts import LensStatus
                idp_present = asset.lens_status.idp == LensStatus.MATCHED
                cmdb_present = asset.lens_status.cmdb == LensStatus.MATCHED
                
                if not (idp_present or cmdb_present):
                    reasons["not_in_idp_cmdb"] += 1
                    details.append({
                        "key": input_key,
                        "asset_name": asset.name,
                        "reason": "not_in_idp_cmdb",
                        "detail": "Asset not in IdP or CMDB - cannot be zombie"
                    })
                    continue
                
                latest = asset.activity_evidence.latest_activity_at
                
                if latest is None:
                    reasons["no_activity_timestamps"] += 1
                    details.append({
                        "key": input_key,
                        "asset_name": asset.name,
                        "reason": "no_activity_timestamps",
                        "detail": "No activity timestamps - classified as zombie"
                    })
                else:
                    if latest.tzinfo is None:
                        is_stale = latest < cutoff_date.replace(tzinfo=None)
                    else:
                        is_stale = latest < cutoff_date
                    
                    if is_stale:
                        reasons["activity_stale"] += 1
                        details.append({
                            "key": input_key,
                            "asset_name": asset.name,
                            "reason": "activity_stale",
                            "detail": f"Activity at {latest.isoformat()} is stale (> {request.window_days} days)"
                        })
                    else:
                        reasons["activity_within_window"] += 1
                        details.append({
                            "key": input_key,
                            "asset_name": asset.name,
                            "reason": "activity_within_window",
                            "detail": f"Recent activity at {latest.isoformat()} - NOT zombie"
                        })
        
        return reasons, details
    
    missed_summary, missed_details = analyze_keys(request.expected_zombie_keys, "missed")
    extra_summary, extra_details = analyze_keys(request.extra_zombie_keys, "extra")
    
    report_lines = [
        f"=== Zombie Reconciliation Report ===",
        f"Run: {request.run_id}",
        f"Tenant: {request.tenant_id}",
        f"Window: {request.window_days} days",
        f"",
        f"--- Missed Zombies (Farm expected {len(request.expected_zombie_keys)}, AOD missed) ---",
    ]
    for reason, count in missed_summary.items():
        if count > 0:
            report_lines.append(f"  {reason}: {count}")
    
    report_lines.extend([
        f"",
        f"--- Extra Zombies (AOD found {len(request.extra_zombie_keys)}, Farm didn't expect) ---",
    ])
    for reason, count in extra_summary.items():
        if count > 0:
            report_lines.append(f"  {reason}: {count}")
    
    sample = None
    if missed_details:
        sample = missed_details[0]
    elif extra_details:
        sample = extra_details[0]
    
    return ZombieReconcileResponse(
        run_id=request.run_id,
        tenant_id=request.tenant_id,
        window_days=request.window_days,
        expected_count=len(request.expected_zombie_keys),
        extra_count=len(request.extra_zombie_keys),
        missed_zombies_summary=missed_summary,
        extra_zombies_summary=extra_summary,
        compact_report="\n".join(report_lines),
        sample_explanation=sample
    )


class TimestampCoverageRequest(BaseModel):
    """Request for timestamp coverage report"""
    tenant_id: str
    snapshot_id: str
    run_id: Optional[str] = None


class PlaneCoverage(BaseModel):
    """Coverage stats for a single plane"""
    raw_count: int
    raw_with_timestamp: int
    raw_timestamp_field_names_found: list[str]
    normalized_with_timestamp: int
    normalized_timestamp_fields_used: list[str]
    examples_with_timestamp: list[dict]
    examples_missing_timestamp: list[dict]


class TimestampCoverageResponse(BaseModel):
    """Response for timestamp coverage report"""
    snapshot_id: str
    run_id: Optional[str]
    planes: dict[str, PlaneCoverage]
    summary: dict
    conclusion: str


TIMESTAMP_FIELD_VARIANTS = {
    "discovery": ["observed_at", "observedAt", "timestamp", "ts", "created_at", "createdAt"],
    "idp": ["last_login_at", "lastLoginAt", "lastLogin", "last_activity", "lastActivity"],
    "cloud": ["observed_at", "observedAt", "timestamp", "ts", "created_at"],
    "finance_transactions": ["date", "datetime", "timestamp", "ts", "transaction_date", "transactionDate"],
    "endpoint_apps": ["last_seen_at", "lastSeenAt", "lastSeen", "observed_at"],
    "network_dns": ["timestamp", "observed_at", "observedAt", "ts"],
    "network_proxy": ["timestamp", "observed_at", "observedAt", "ts"],
}


@router.post("/debug/timestamp-coverage", response_model=TimestampCoverageResponse)
async def debug_timestamp_coverage(request: TimestampCoverageRequest):
    """
    Debug endpoint to analyze timestamp field coverage in raw vs normalized data.
    
    Compares what timestamp fields exist in the raw Farm snapshot payload
    vs what fields are present after normalization.
    """
    import httpx
    import os
    
    farm_url = os.environ.get("FARM_URL", "http://localhost:8000")
    
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            url = f"{farm_url.rstrip('/')}/api/snapshots/{request.snapshot_id}"
            response = await client.get(url)
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=f"Farm error: {response.text}")
            raw_snapshot = response.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Farm connection error: {str(e)}")
    
    from ..pipeline.farm_adapter import normalize_farm_snapshot
    from ..models.input_contracts import Snapshot
    
    normalized_dict = normalize_farm_snapshot(
        raw_snapshot,
        fallback_tenant_id=request.tenant_id,
        snapshot_id=request.snapshot_id
    )
    normalized = Snapshot.model_validate(normalized_dict)
    
    planes = raw_snapshot.get("planes", {})
    
    def analyze_plane(raw_records: list, normalized_records: list, 
                      timestamp_variants: list[str], normalized_field: str) -> PlaneCoverage:
        raw_count = len(raw_records)
        raw_with_ts = 0
        raw_field_names_found: set[str] = set()
        examples_with: list[dict] = []
        examples_missing: list[dict] = []
        
        for rec in raw_records:
            if not isinstance(rec, dict):
                continue
            found_ts = False
            for variant in timestamp_variants:
                if rec.get(variant) is not None:
                    found_ts = True
                    raw_field_names_found.add(variant)
            
            if found_ts:
                raw_with_ts += 1
                if len(examples_with) < 3:
                    example = {"id": rec.get("observation_id") or rec.get("idp_id") or rec.get("txn_id") or rec.get("resource_id") or "?"}
                    for variant in timestamp_variants:
                        if rec.get(variant) is not None:
                            example[variant] = str(rec[variant])
                    examples_with.append(example)
            else:
                if len(examples_missing) < 3:
                    example = {"id": rec.get("observation_id") or rec.get("idp_id") or rec.get("txn_id") or rec.get("resource_id") or "?"}
                    example["fields_checked"] = timestamp_variants
                    examples_missing.append(example)
        
        normalized_with_ts = 0
        normalized_fields_used: set[str] = set()
        
        for rec in normalized_records:
            val = getattr(rec, normalized_field, None) if hasattr(rec, normalized_field) else None
            if val is not None:
                normalized_with_ts += 1
                normalized_fields_used.add(normalized_field)
        
        return PlaneCoverage(
            raw_count=raw_count,
            raw_with_timestamp=raw_with_ts,
            raw_timestamp_field_names_found=sorted(raw_field_names_found),
            normalized_with_timestamp=normalized_with_ts,
            normalized_timestamp_fields_used=sorted(normalized_fields_used),
            examples_with_timestamp=examples_with,
            examples_missing_timestamp=examples_missing
        )
    
    results: dict[str, PlaneCoverage] = {}
    
    discovery_raw = planes.get("discovery", {}).get("observations", [])
    results["discovery"] = analyze_plane(
        discovery_raw, 
        normalized.planes.discovery.observations,
        TIMESTAMP_FIELD_VARIANTS["discovery"],
        "observed_at"
    )
    
    idp_raw = planes.get("idp", {}).get("objects", [])
    results["idp"] = analyze_plane(
        idp_raw,
        normalized.planes.idp.objects,
        TIMESTAMP_FIELD_VARIANTS["idp"],
        "last_login_at"
    )
    
    cloud_raw = planes.get("cloud", {}).get("resources", [])
    results["cloud"] = analyze_plane(
        cloud_raw,
        normalized.planes.cloud.resources,
        TIMESTAMP_FIELD_VARIANTS["cloud"],
        "observed_at"
    )
    
    finance_txns_raw = planes.get("finance", {}).get("transactions", [])
    results["finance_transactions"] = analyze_plane(
        finance_txns_raw,
        normalized.planes.finance.transactions,
        TIMESTAMP_FIELD_VARIANTS["finance_transactions"],
        "date"
    )
    
    endpoint_apps_raw = planes.get("endpoint", {}).get("installed_apps", [])
    results["endpoint_apps"] = analyze_plane(
        endpoint_apps_raw,
        normalized.planes.endpoint.installed_apps,
        TIMESTAMP_FIELD_VARIANTS["endpoint_apps"],
        "last_seen_at"
    )
    
    total_raw_with_ts = sum(p.raw_with_timestamp for p in results.values())
    total_raw_count = sum(p.raw_count for p in results.values())
    total_normalized_with_ts = sum(p.normalized_with_timestamp for p in results.values())
    
    if total_raw_with_ts == 0:
        conclusion = "TIMESTAMPS ABSENT UPSTREAM: Farm raw snapshot has 0 timestamp fields across all planes."
    elif total_normalized_with_ts == 0 and total_raw_with_ts > 0:
        conclusion = f"TIMESTAMPS DROPPED/MISMAPPED IN AOD: Raw has {total_raw_with_ts} timestamps, normalized has 0. Check field mapping."
    elif total_normalized_with_ts < total_raw_with_ts:
        conclusion = f"PARTIAL TIMESTAMP LOSS IN AOD: Raw has {total_raw_with_ts}, normalized has {total_normalized_with_ts}. Some fields not mapped."
    else:
        conclusion = f"TIMESTAMPS PRESERVED: Raw has {total_raw_with_ts}, normalized has {total_normalized_with_ts}."
    
    return TimestampCoverageResponse(
        snapshot_id=request.snapshot_id,
        run_id=request.run_id,
        planes=results,
        summary={
            "total_raw_records": total_raw_count,
            "total_raw_with_timestamp": total_raw_with_ts,
            "total_normalized_with_timestamp": total_normalized_with_ts,
            "timestamp_loss_count": total_raw_with_ts - total_normalized_with_ts
        },
        conclusion=conclusion
    )


class AODActualResultsRequest(BaseModel):
    """Request for AOD actual results (pure emitter - no expected data consumed)"""
    run_id: str
    activity_window_days: int = 90


class AODActualResultsResponse(BaseModel):
    """
    AOD Actual Results Response - Pure Emitter
    
    DESIGN PRINCIPLE:
    - Farm owns reconciliation UI (has expected + actual + diffs)
    - AOD owns its structured "actual" output only
    - Farm displays side-by-side and runs the RCA reducer
    
    DATA FLOW:
    - AOD publishes: shadow_actual, zombie_actual, admission_actual, actual_reason_codes
    - Farm already has: shadow_expected, zombie_expected, expected_reason_codes
    - Farm computes: extra, missed, rca_code per mismatch
    
    HARD RULE: AOD NEVER consumes Farm expected/rca data
    """
    run_id: str
    shadow_actual: list[str]
    zombie_actual: list[str]
    admission_actual: dict[str, str]
    actual_reason_codes: dict[str, list[str]]
    asset_details: dict[str, dict]
    summary: dict


@router.post("/debug/aod-agent-reconcile", response_model=AODActualResultsResponse)
async def debug_aod_agent_reconcile(request: AODActualResultsRequest):
    """
    AOD Actual Results Emitter - Pure Output Only.
    
    DESIGN PRINCIPLE:
    - Farm owns reconciliation UI (has expected + actual + diffs)
    - AOD owns its structured "actual" output only
    - Farm displays side-by-side and runs the RCA reducer
    
    DATA FLOW:
    - AOD publishes: shadow_actual, zombie_actual, admission_actual, actual_reason_codes
    - Farm already has: shadow_expected, zombie_expected, expected_reason_codes
    - Farm computes: extra, missed, rca_code per mismatch
    
    HARD RULE (prevents coupling):
    - AOD NEVER consumes Farm expected/rca data
    - AOD ONLY emits its own "actual + reasons"
    
    IMPORTANT: Includes BOTH admitted assets AND rejected candidates.
    This ensures Farm reconciliation always has aod_reason_codes for every
    asset it asks about (no more empty aod_reason_codes for missed assets).
    """
    from ..pipeline.aod_agent_reconcile import emit_actual_results
    
    db = await get_db()
    
    run = await db.get_run(request.run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run not found: {request.run_id}")
    
    assets = await db.get_assets_by_run(request.run_id)
    
    rejections_result = await db.get_rejections_by_run(request.run_id, limit=1000)
    rejections = rejections_result[0] if isinstance(rejections_result, tuple) else rejections_result
    
    if not assets and not rejections:
        raise HTTPException(status_code=404, detail=f"No assets or rejections found for run_id: {request.run_id}")
    
    result = emit_actual_results(
        run_id=request.run_id,
        assets=assets or [],
        activity_window_days=request.activity_window_days,
        rejections=rejections
    )
    
    return AODActualResultsResponse(
        run_id=result.run_id,
        shadow_actual=result.shadow_actual,
        zombie_actual=result.zombie_actual,
        admission_actual=result.admission_actual,
        actual_reason_codes=result.actual_reasons,
        asset_details=result.asset_details,
        summary=result.summary
    )


class ExplainNonflagRequest(BaseModel):
    """
    Request for explain-nonflag endpoint.
    
    Farm sends ONLY keys + snapshot_id + ask-type.
    No expected data is sent or consumed by AOD.
    """
    snapshot_id: str
    asset_keys: list[str]
    ask: str = Field(description="'shadow' | 'zombie' | 'both'")


class NonflagExplanation(BaseModel):
    """
    Per-key explanation for why an asset was NOT flagged.
    
    Decisions:
    - unknown_key: AOD never saw it / couldn't form candidate
    - not_admitted: Saw it, but no admission gate satisfied
    - admitted_not_shadow: Admitted, but fails shadow conditions (has presence)
    - admitted_not_zombie: Admitted, but not stale (has recent activity)
    """
    asset_key: str
    present_in_aod: bool
    decision: str
    reason_codes: list[str] = Field(default_factory=list)
    primary_reason: str | None = None


class ExplainNonflagResponse(BaseModel):
    """Response for explain-nonflag endpoint"""
    snapshot_id: str
    ask: str
    explanations: list[NonflagExplanation]


@router.post("/reconcile/explain-nonflag", response_model=ExplainNonflagResponse)
async def explain_nonflag(request: ExplainNonflagRequest):
    """
    Explain why specific assets are NOT in shadow/zombie lists.
    
    DESIGN PRINCIPLE:
    - Farm asks AOD a neutral question: "Why isn't this asset flagged?"
    - AOD returns its decision trace for NON-MEMBERSHIP
    - AOD does NOT consume any expected data from Farm
    
    GUARDRAIL: Farm only sends keys + snapshot_id + ask-type.
    """
    from ..pipeline.derived_classifications import classify_shadow, compute_zombie_status
    from datetime import datetime, timezone, timedelta
    
    db = await get_db()
    
    runs = await db.get_all_runs()
    matching_run = None
    for run in runs:
        input_meta = run.input_meta if hasattr(run, 'input_meta') else run.get("input_meta", {})
        if input_meta.get("snapshot_id") == request.snapshot_id:
            matching_run = run
            break
    
    if not matching_run:
        explanations = []
        for key in request.asset_keys:
            explanations.append(NonflagExplanation(
                asset_key=key,
                present_in_aod=False,
                decision="unknown_key",
                reason_codes=["NO_RUN_FOR_SNAPSHOT"],
                primary_reason="PRIMARY:NO_RUN_FOR_SNAPSHOT"
            ))
        return ExplainNonflagResponse(
            snapshot_id=request.snapshot_id,
            ask=request.ask,
            explanations=explanations
        )
    
    run_id = matching_run.run_id if hasattr(matching_run, 'run_id') else matching_run.get("run_id")
    assets = await db.get_assets_by_run(run_id)
    rejections_result = await db.get_rejections_by_run(run_id)
    rejections = rejections_result[0] if isinstance(rejections_result, tuple) else rejections_result
    
    assets_by_key: dict[str, Any] = {}
    for asset in assets:
        name = (asset.name if hasattr(asset, 'name') else asset.get("name", "")).lower().strip()
        assets_by_key[name] = asset
        identifiers = asset.identifiers if hasattr(asset, 'identifiers') else asset.get("identifiers", {})
        domains = identifiers.domains if hasattr(identifiers, 'domains') else identifiers.get("domains", [])
        for domain in domains:
            assets_by_key[domain.lower().strip()] = asset
    
    rejections_by_key: dict[str, dict] = {}
    for rej in rejections:
        name = rej.get("entity_name", "").lower().strip()
        rejections_by_key[name] = rej
        key = rej.get("entity_key", "").lower().strip()
        rejections_by_key[key] = rej
    
    now = datetime.now(timezone.utc)
    activity_cutoff = now - timedelta(days=90)
    
    explanations = []
    for key in request.asset_keys:
        normalized_key = key.lower().strip()
        
        asset = assets_by_key.get(normalized_key)
        rejection = rejections_by_key.get(normalized_key)
        
        if asset:
            lens_coverage = asset.lens_coverage if hasattr(asset, 'lens_coverage') else asset.get("lens_coverage", {})
            activity_evidence = asset.activity_evidence if hasattr(asset, 'activity_evidence') else asset.get("activity_evidence", {})
            
            def get_coverage(lc, key):
                if hasattr(lc, key):
                    return getattr(lc, key)
                elif isinstance(lc, dict):
                    return lc.get(key)
                return False
            
            def get_activity(ae, key):
                if hasattr(ae, key):
                    return getattr(ae, key)
                elif isinstance(ae, dict):
                    return ae.get(key)
                return None
            
            reason_codes = []
            
            if get_coverage(lens_coverage, "idp"):
                reason_codes.append("HAS_IDP")
            else:
                reason_codes.append("NO_IDP")
            
            if get_coverage(lens_coverage, "cmdb"):
                reason_codes.append("HAS_CMDB")
            else:
                reason_codes.append("NO_CMDB")
            
            if get_coverage(lens_coverage, "finance"):
                reason_codes.append("HAS_FINANCE")
            else:
                reason_codes.append("NO_FINANCE")
            
            if get_coverage(lens_coverage, "cloud"):
                reason_codes.append("HAS_CLOUD")
            else:
                reason_codes.append("NO_CLOUD")
            
            if get_coverage(lens_coverage, "discovery"):
                reason_codes.append("HAS_DISCOVERY")
            else:
                reason_codes.append("NO_DISCOVERY")
            
            latest_activity_str = get_activity(activity_evidence, "latest_activity_at")
            if latest_activity_str:
                try:
                    if isinstance(latest_activity_str, str):
                        latest_activity = datetime.fromisoformat(latest_activity_str.replace("Z", "+00:00"))
                    else:
                        latest_activity = latest_activity_str
                    
                    if latest_activity.tzinfo is None:
                        latest_activity = latest_activity.replace(tzinfo=timezone.utc)
                    
                    if latest_activity >= activity_cutoff:
                        reason_codes.append("RECENT_ACTIVITY")
                    else:
                        reason_codes.append("STALE_ACTIVITY")
                except:
                    reason_codes.append("NO_ACTIVITY_TIMESTAMPS")
            else:
                reason_codes.append("NO_ACTIVITY_TIMESTAMPS")
            
            if request.ask in ("shadow", "both"):
                has_presence = get_coverage(lens_coverage, "idp") or get_coverage(lens_coverage, "cmdb")
                if has_presence:
                    decision = "admitted_not_shadow"
                    primary = "HAS_IDP" if get_coverage(lens_coverage, "idp") else "HAS_CMDB"
                else:
                    decision = "admitted_not_shadow"
                    primary = "NO_IDP"
                    
            elif request.ask == "zombie":
                has_presence = get_coverage(lens_coverage, "idp") or get_coverage(lens_coverage, "cmdb")
                has_recent_activity = "RECENT_ACTIVITY" in reason_codes
                
                if not has_presence:
                    decision = "admitted_not_zombie"
                    primary = "NO_IDP"
                elif has_recent_activity:
                    decision = "admitted_not_zombie"
                    primary = "RECENT_ACTIVITY"
                else:
                    decision = "admitted_not_zombie"
                    primary = "STALE_ACTIVITY"
            else:
                decision = "admitted_not_shadow"
                primary = reason_codes[0] if reason_codes else "UNKNOWN"
            
            explanations.append(NonflagExplanation(
                asset_key=key,
                present_in_aod=True,
                decision=decision,
                reason_codes=reason_codes,
                primary_reason=primary
            ))
        
        elif rejection:
            reason_code = rejection.get("reason_code", "unknown")
            reason_detail = rejection.get("reason_detail", "")
            
            reason_codes = []
            if "discovery" in reason_code.lower() or "source" in reason_detail.lower():
                reason_codes.append("INSUFFICIENT_DISCOVERY_SOURCES")
            if "stale" in reason_detail.lower() or "activity" in reason_detail.lower():
                reason_codes.append("STALE_ACTIVITY")
            if "gate" in reason_code.lower() or "no_gate" in reason_code.lower():
                reason_codes.append("REJECTED_NO_GATE")
            if "finance" in reason_code.lower():
                reason_codes.append("NO_FINANCE")
            
            if not reason_codes:
                reason_codes.append("REJECTED_NO_GATE")
            
            primary = reason_codes[0] if reason_codes else "REJECTED_NO_GATE"
            
            explanations.append(NonflagExplanation(
                asset_key=key,
                present_in_aod=True,
                decision="not_admitted",
                reason_codes=reason_codes,
                primary_reason=primary
            ))
        
        else:
            explanations.append(NonflagExplanation(
                asset_key=key,
                present_in_aod=False,
                decision="unknown_key",
                reason_codes=["NO_CANDIDATE", "NO_EVIDENCE_INGESTED"],
                primary_reason="NO_CANDIDATE"
            ))
    
    return ExplainNonflagResponse(
        snapshot_id=request.snapshot_id,
        ask=request.ask,
        explanations=explanations
    )


class RunTestsRequest(BaseModel):
    """Request for running tests"""
    test_path: str = "tests/"


class RunTestsResponse(BaseModel):
    """Response for test run"""
    passed: bool
    total: int
    passed_count: int
    failed_count: int
    summary: str
    output: str


@router.post("/run-tests")
async def run_tests(request: RunTestsRequest) -> RunTestsResponse:
    """
    Run pytest tests and return results.
    """
    import subprocess
    
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", request.test_path, "-v", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd="/home/runner/workspace"
        )
        
        output = result.stdout + result.stderr
        
        passed_count = 0
        failed_count = 0
        total = 0
        
        for line in output.split('\n'):
            if ' passed' in line and ('failed' in line or 'passed' in line):
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == 'passed':
                        try:
                            passed_count = int(parts[i-1])
                        except:
                            pass
                    if part == 'failed':
                        try:
                            failed_count = int(parts[i-1])
                        except:
                            pass
        
        total = passed_count + failed_count
        all_passed = failed_count == 0 and passed_count > 0
        
        summary_lines = [l for l in output.split('\n') if 'passed' in l or 'failed' in l or 'error' in l.lower()]
        summary = '\n'.join(summary_lines[-5:]) if summary_lines else ''
        
        return RunTestsResponse(
            passed=all_passed,
            total=total,
            passed_count=passed_count,
            failed_count=failed_count,
            summary=summary,
            output=output[-3000:] if len(output) > 3000 else output
        )
    except subprocess.TimeoutExpired:
        return RunTestsResponse(
            passed=False,
            total=0,
            passed_count=0,
            failed_count=0,
            summary="Test run timed out after 120 seconds",
            output="Timeout"
        )
    except Exception as e:
        return RunTestsResponse(
            passed=False,
            total=0,
            passed_count=0,
            failed_count=0,
            summary=str(e),
            output=str(e)
        )


class TestRunRequest(BaseModel):
    """Request for running performance tests from UI"""
    testType: str  # 'correlation', 'database', or 'all'


class TestRunResponse(BaseModel):
    """Response for UI test run"""
    success: bool
    passed: int
    failed: int
    duration: str
    output: str


@router.post("/tests/run", response_model=TestRunResponse)
async def run_performance_tests(request: TestRunRequest) -> TestRunResponse:
    """
    Run performance tests from the UI test tab.
    Maps test types to specific test files.
    """
    import subprocess
    import re

    # Map test types to test files
    test_map = {
        'correlation': 'tests/test_correlation_performance.py',
        'database': 'tests/test_database_performance.py',
        'all': 'tests/test_correlation_performance.py tests/test_database_performance.py'
    }

    test_path = test_map.get(request.testType, 'tests/')

    try:
        # Try multiple possible project root paths (Replit, local dev, etc.)
        possible_roots = [
            '/home/user/AODv3',  # Replit development directory
            '/home/runner/workspace',  # Replit runtime directory
            os.getcwd(),  # Current working directory
        ]

        # Also try finding by pyproject.toml
        current_dir = os.path.dirname(os.path.abspath(__file__))
        search_dir = current_dir
        while search_dir != '/':
            if os.path.exists(os.path.join(search_dir, 'pyproject.toml')):
                possible_roots.insert(0, search_dir)
                break
            search_dir = os.path.dirname(search_dir)

        # Find first path that has the test files
        project_root = None
        for root in possible_roots:
            if os.path.exists(root) and os.path.exists(os.path.join(root, 'tests')):
                project_root = root
                break

        # Fallback to first existing path
        if not project_root:
            for root in possible_roots:
                if os.path.exists(root):
                    project_root = root
                    break

        if not project_root:
            project_root = os.getcwd()

        # Run pytest with verbose output
        result = subprocess.run(
            f"python -m pytest {test_path} -v -s --tb=short".split(),
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes for performance tests
            cwd=project_root
        )

        output = result.stdout + result.stderr

        # Check for database configuration errors
        if "No database configured" in output and request.testType == 'database':
            return TestRunResponse(
                success=False,
                passed=0,
                failed=0,
                duration="0.00s",
                output="⚠️ Database tests require a database connection.\n\n"
                      "Please set the SUPABASE_DB_URL or DATABASE_URL environment variable.\n\n"
                      "These tests verify database query optimizations (batched queries, WHERE clause filtering, etc.) "
                      "and need a live PostgreSQL database to run.\n\n"
                      "The correlation performance tests can run without a database connection."
            )

        # Parse test results
        passed_count = 0
        failed_count = 0
        duration_str = "0.00s"

        # Look for pytest summary line like "5 passed in 2.34s"
        summary_pattern = r'(\d+)\s+passed.*?in\s+([\d.]+s)'
        failed_pattern = r'(\d+)\s+failed'

        for line in output.split('\n'):
            passed_match = re.search(summary_pattern, line)
            if passed_match:
                passed_count = int(passed_match.group(1))
                duration_str = passed_match.group(2)

            failed_match = re.search(failed_pattern, line)
            if failed_match:
                failed_count = int(failed_match.group(1))

        success = result.returncode == 0 and failed_count == 0

        return TestRunResponse(
            success=success,
            passed=passed_count,
            failed=failed_count,
            duration=duration_str,
            output=output if len(output) < 10000 else output[-10000:]  # Last 10k chars
        )

    except subprocess.TimeoutExpired:
        return TestRunResponse(
            success=False,
            passed=0,
            failed=0,
            duration="timeout",
            output="⏱️ Test run timed out after 5 minutes"
        )
    except Exception as e:
        return TestRunResponse(
            success=False,
            passed=0,
            failed=0,
            duration="error",
            output=f"❌ Error running tests: {str(e)}"
        )


class AssetTraceRequest(BaseModel):
    """Request for single-asset trace debugging"""
    run_id: str
    asset_key: str


class DomainTraceStep(BaseModel):
    """One step in domain canonicalization trace"""
    step: str
    input_value: str
    output_value: Optional[str]
    function: str
    module: str


class AssetTraceResponse(BaseModel):
    """Response for single-asset trace debugging"""
    asset_key: str
    found_in_assets: bool
    found_in_observations: bool
    raw_evidence_domains: list[str]
    canonicalization_steps: list[DomainTraceStep]
    final_asset_key: Optional[str]
    key_source: Optional[str]
    asset_data: Optional[dict] = None
    observations: list[dict] = []


@router.post("/debug/trace-asset")
async def trace_asset(request: AssetTraceRequest) -> AssetTraceResponse:
    """
    Debug endpoint: Trace a single asset through the canonicalization pipeline.
    
    Shows:
    - Raw evidence domains extracted from observations
    - Canonicalization steps for each domain
    - Final asset key and where it was produced
    """
    from ..pipeline.vendor_inference import extract_registered_domain, DOMAIN_TO_VENDOR
    from ..pipeline.aod_agent_reconcile import _extract_registered_domain, VENDOR_TO_DOMAIN, _normalize_name_for_vendor_lookup
    
    db = await get_db()
    
    asset_row = await db.fetchrow(
        "SELECT * FROM assets WHERE run_id = $1 AND asset_id = $2",
        request.run_id, request.asset_key
    )
    
    if not asset_row:
        asset_row = await db.fetchrow(
            "SELECT * FROM assets WHERE run_id = $1 AND (name ILIKE $2 OR asset_id ILIKE $2)",
            request.run_id, f"%{request.asset_key}%"
        )
    
    obs_rows = await db.fetch(
        """SELECT * FROM observation_samples 
           WHERE run_id = $1 
           AND (name ILIKE $2 OR domain ILIKE $2 OR observation_id ILIKE $2)
           LIMIT 50""",
        request.run_id, f"%{request.asset_key}%"
    )
    
    raw_domains: list[str] = []
    observations: list[dict] = []
    
    for obs in obs_rows:
        obs_dict = dict(obs)
        observations.append(obs_dict)
        if obs_dict.get("domain"):
            raw_domains.append(obs_dict["domain"])
        name = obs_dict.get("name", "")
        if name and "." in name:
            parts = name.split(".")
            if len(parts) >= 2 and parts[-1] in ("com", "org", "net", "io", "co", "dev", "app", "us", "so"):
                raw_domains.append(name)
    
    canonicalization_steps: list[DomainTraceStep] = []
    
    for domain in set(raw_domains):
        registered = extract_registered_domain(domain)
        canonicalization_steps.append(DomainTraceStep(
            step="extract_registered_domain",
            input_value=domain,
            output_value=registered,
            function="extract_registered_domain",
            module="vendor_inference.py"
        ))
        
        if registered and registered in DOMAIN_TO_VENDOR:
            canonicalization_steps.append(DomainTraceStep(
                step="vendor_lookup",
                input_value=registered,
                output_value=DOMAIN_TO_VENDOR[registered],
                function="DOMAIN_TO_VENDOR lookup",
                module="vendor_inference.py"
            ))
    
    final_asset_key = None
    key_source = None
    asset_data = None
    
    if asset_row:
        asset_data = dict(asset_row)
        name = asset_data.get("name", "")
        identifiers = asset_data.get("identifiers", {})
        vendor = asset_data.get("vendor")
        
        domains_from_identifiers = identifiers.get("domains", []) if identifiers else []
        
        if domains_from_identifiers:
            domain = domains_from_identifiers[0]
            registered = extract_registered_domain(domain)
            final_asset_key = registered or domain
            key_source = "identifiers.domains"
            canonicalization_steps.append(DomainTraceStep(
                step="asset_key_from_identifiers",
                input_value=domain,
                output_value=final_asset_key,
                function="_extract_registered_domain",
                module="aod_agent_reconcile.py"
            ))
        elif "." in name:
            parts = name.split(".")
            if len(parts) >= 2 and parts[-1] in ("com", "org", "net", "io", "co", "dev", "app", "us", "so"):
                registered = extract_registered_domain(name)
                final_asset_key = registered or name
                key_source = "asset.name (domain-like)"
                canonicalization_steps.append(DomainTraceStep(
                    step="asset_key_from_name",
                    input_value=name,
                    output_value=final_asset_key,
                    function="_extract_registered_domain",
                    module="aod_agent_reconcile.py"
                ))
        elif vendor and vendor.lower() in VENDOR_TO_DOMAIN:
            final_asset_key = VENDOR_TO_DOMAIN[vendor.lower()]
            key_source = "vendor_to_domain_lookup"
            canonicalization_steps.append(DomainTraceStep(
                step="asset_key_from_vendor",
                input_value=vendor,
                output_value=final_asset_key,
                function="VENDOR_TO_DOMAIN lookup",
                module="aod_agent_reconcile.py"
            ))
        else:
            normalized = _normalize_name_for_vendor_lookup(name)
            if normalized in VENDOR_TO_DOMAIN:
                final_asset_key = VENDOR_TO_DOMAIN[normalized]
                key_source = "name_to_vendor_lookup"
                canonicalization_steps.append(DomainTraceStep(
                    step="asset_key_from_normalized_name",
                    input_value=name,
                    output_value=final_asset_key,
                    function="_normalize_name_for_vendor_lookup + VENDOR_TO_DOMAIN",
                    module="aod_agent_reconcile.py"
                ))
            else:
                final_asset_key = None
                key_source = "no_domain_available"
    
    return AssetTraceResponse(
        asset_key=request.asset_key,
        found_in_assets=bool(asset_row),
        found_in_observations=bool(obs_rows),
        raw_evidence_domains=list(set(raw_domains)),
        canonicalization_steps=canonicalization_steps,
        final_asset_key=final_asset_key,
        key_source=key_source,
        asset_data=asset_data,
        observations=observations
    )


class TwoPathDiffRequest(BaseModel):
    """Request for two-path diff test"""
    domains: list[str]


class PathDiffResult(BaseModel):
    """Result of comparing two canonicalization paths"""
    raw_domain: str
    vendor_inference_result: Optional[str]
    reconcile_result: Optional[str]
    match: bool


class TwoPathDiffResponse(BaseModel):
    """Response for two-path diff test"""
    results: list[PathDiffResult]
    all_match: bool
    mismatches: list[str]


@router.post("/debug/two-path-diff")
async def two_path_diff(request: TwoPathDiffRequest) -> TwoPathDiffResponse:
    """
    Debug endpoint: Compare canonicalization between vendor_inference and reconcile paths.
    
    Detects "two canonicalizers exist" bugs where different code paths
    produce different keys for the same input.
    """
    import uuid as uuid_lib
    from ..pipeline.vendor_inference import extract_registered_domain as vendor_extract
    from ..pipeline.aod_agent_reconcile import _extract_registered_domain
    from ..models.output_contracts import Asset, AssetIdentifiers, LensStatuses, LensCoverage
    
    results: list[PathDiffResult] = []
    mismatches: list[str] = []
    
    for domain in request.domains:
        vendor_result = vendor_extract(domain)
        
        asset = Asset(
            asset_id=uuid_lib.uuid4(),
            tenant_id="test-tenant",
            run_id="test",
            name=domain,
            identifiers=AssetIdentifiers(domains=[]),
            vendor=None,
            lens_status=LensStatuses(),
            lens_coverage=LensCoverage(),
        )
        reconcile_result = _extract_registered_domain(asset)
        
        is_match = vendor_result == reconcile_result
        if not is_match:
            mismatches.append(f"{domain}: vendor={vendor_result}, reconcile={reconcile_result}")
        
        results.append(PathDiffResult(
            raw_domain=domain,
            vendor_inference_result=vendor_result,
            reconcile_result=reconcile_result,
            match=is_match
        ))
    
    return TwoPathDiffResponse(
        results=results,
        all_match=len(mismatches) == 0,
        mismatches=mismatches
    )


class DecisionTraceRequest(BaseModel):
    """Request for decision trace"""
    run_id: str
    activity_window_days: int = 90


class DecisionTraceResponse(BaseModel):
    """Response with decision traces for all assets"""
    run_id: str
    traces: dict[str, dict]
    count: int
    fields: list[str]


@router.post("/debug/decision-trace", response_model=DecisionTraceResponse)
async def get_decision_traces(request: DecisionTraceRequest):
    """
    Get decision traces for all assets in a run.
    
    This produces exactly 13 fields per asset for Farm/AOD comparison:
    - asset_key_used, registered_domain, raw_domains_seen
    - is_external, is_active, activity_window_days, activity_source, latest_activity_at
    - idp_present, cmdb_present, infra_excluded, is_shadow, reason_codes
    """
    from ..pipeline.decision_trace import compute_decision_trace, decision_traces_to_dict
    
    db = await get_db()
    
    run = await db.get_run(request.run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {request.run_id} not found")
    
    assets = await db.get_assets_by_run(request.run_id)
    
    traces = [compute_decision_trace(a, request.activity_window_days) for a in assets]
    traces_dict = decision_traces_to_dict(traces)
    
    fields = [
        "asset_key_used", "registered_domain", "raw_domains_seen",
        "is_external", "is_active", "activity_window_days", "activity_source",
        "latest_activity_at", "idp_present", "cmdb_present", "infra_excluded",
        "is_shadow", "reason_codes"
    ]
    
    return DecisionTraceResponse(
        run_id=request.run_id,
        traces=traces_dict,
        count=len(traces),
        fields=fields
    )


class TriageActionRequest(BaseModel):
    """Request to record a triage action"""
    run_id: str
    item_id: str
    item_type: str
    action: str
    owner: Optional[str] = None
    defer_days: Optional[int] = None
    ignore_reason: Optional[str] = None


class TriageActionResponse(BaseModel):
    """Response for triage action"""
    success: bool
    action_id: str
    item_id: str
    item_type: str
    action: str
    state: str
    owner: Optional[str] = None
    defer_until: Optional[str] = None
    ignore_reason: Optional[str] = None


@router.post("/triage/action", response_model=TriageActionResponse)
async def record_triage_action(request: TriageActionRequest):
    """Record a triage action (acknowledge, assign, defer, ignore)"""
    from datetime import datetime, timedelta
    
    db = await get_db()
    
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


@router.get("/triage/actions/{run_id}")
async def get_triage_actions(run_id: str):
    """Get all triage actions for a run"""
    db = await get_db()
    
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    actions = await db.get_triage_actions_by_run(run_id)
    
    return {"run_id": run_id, "actions": actions}
