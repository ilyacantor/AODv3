"""FastAPI routes for AOD - Phase 0: Presence Debug Only"""

from typing import Any, Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, UploadFile, File

from pydantic import BaseModel

PST = timezone(timedelta(hours=-8))

def now_pst() -> datetime:
    return datetime.now(PST)
import json
import os
import time
import uuid
import re

from ..db.database import get_db
from ..pipeline.pipeline_executor import execute_pipeline
from ..models.output_contracts import RunLog, RunCounts, Asset, Finding, RunStatus, SyncStatus, LensStatus
from ..farm_client import FarmClient, FarmListResult, validate_schema_version


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


class CatalogResponse(BaseModel):
    """Response for catalog"""
    run_id: str
    assets: list[dict[str, Any]]
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
        version="0.1.0-phase0"
    )


@router.get("/farm/tenants", response_model=TenantListResponse)
async def list_farm_tenants():
    """List available tenants from Farm."""
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
    """List available snapshots from Farm for a tenant."""
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
    """Create a new discovery run from file upload."""
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
        message=f"Discovery completed. {result.run_log.counts.assets_admitted} assets admitted."
    )


@router.post("/runs/from-farm", response_model=RunResponse)
async def create_run_from_farm(request: FarmRunRequest):
    """Create a new discovery run by fetching snapshot from Farm. No reconciliation."""
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
    
    return RunResponse(
        run_id=result.run_log.run_id,
        tenant_id=result.run_log.tenant_id,
        status=result.run_log.status.value,
        counts=result.run_log.counts,
        message=f"Discovery completed from Farm. {result.run_log.counts.assets_admitted} assets admitted."
    )


@router.get("/runs", response_model=list[RunDetailResponse])
async def list_runs(tenant_id: Optional[str] = None):
    """List all discovery runs, optionally filtered by tenant_id"""
    db = await get_db()
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
            failure_reasons=run.failure_reasons
        )
        for run in runs
    ]


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
        failure_reasons=run.failure_reasons
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
                "activity_evidence": a.activity_evidence.model_dump(),
                "tags": a.tags,
                "admission_reason": a.admission_reason,
                "evidence_refs": a.evidence_refs,
                "created_at": a.created_at.isoformat()
            }
            for a in assets
        ],
        count=len(assets)
    )


def derive_vendor_key(asset: Asset) -> str:
    """Derive a vendor_key from an asset: vendor or normalized name."""
    if asset.vendor:
        return asset.vendor.lower().strip()
    name = asset.name.lower().strip()
    name = re.sub(r'[^a-z0-9]', '', name)
    return name


class PresenceRow(BaseModel):
    """A single row in the presence debug table - aggregated per vendor_key."""
    vendor_key: str
    in_discovery: bool
    in_finance: bool
    in_idp: bool
    in_cmdb: bool
    latest_activity_at: Optional[str]


class PresenceDebugResponse(BaseModel):
    """Response for presence debug endpoint."""
    run_id: str
    rows: list[PresenceRow]


@router.get("/debug/presence")
async def debug_presence(run_id: str) -> PresenceDebugResponse:
    """
    Phase 0 Debug Endpoint: Show presence per vendor_key.
    
    Aggregates all assets by vendor_key. For each vendor_key shows:
    - vendor_key: derived from vendor or name
    - in_discovery: True if any asset has discovery_observed_at timestamp
    - in_finance: True if any asset has lens_status.finance == MATCHED
    - in_idp: True if any asset has lens_status.idp == MATCHED
    - in_cmdb: True if any asset has lens_status.cmdb == MATCHED
    - latest_activity_at: The most recent activity timestamp across all assets with this vendor_key
    
    No heuristics. No counts. No labels.
    """
    db = await get_db()
    
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    assets = await db.get_assets_by_run(run_id)
    
    aggregated: dict[str, dict] = {}
    
    for asset in assets:
        vendor_key = derive_vendor_key(asset)
        
        in_discovery = asset.activity_evidence.discovery_observed_at is not None
        in_finance = asset.lens_status.finance == LensStatus.MATCHED
        in_idp = asset.lens_status.idp == LensStatus.MATCHED
        in_cmdb = asset.lens_status.cmdb == LensStatus.MATCHED
        latest = asset.activity_evidence.latest_activity_at
        
        if vendor_key not in aggregated:
            aggregated[vendor_key] = {
                "in_discovery": False,
                "in_finance": False,
                "in_idp": False,
                "in_cmdb": False,
                "latest_activity_at": None
            }
        
        agg = aggregated[vendor_key]
        agg["in_discovery"] = agg["in_discovery"] or in_discovery
        agg["in_finance"] = agg["in_finance"] or in_finance
        agg["in_idp"] = agg["in_idp"] or in_idp
        agg["in_cmdb"] = agg["in_cmdb"] or in_cmdb
        
        if latest is not None:
            if agg["latest_activity_at"] is None or latest > agg["latest_activity_at"]:
                agg["latest_activity_at"] = latest
    
    rows = []
    for vendor_key in sorted(aggregated.keys()):
        agg = aggregated[vendor_key]
        latest_str = agg["latest_activity_at"].isoformat() if agg["latest_activity_at"] else None
        rows.append(PresenceRow(
            vendor_key=vendor_key,
            in_discovery=agg["in_discovery"],
            in_finance=agg["in_finance"],
            in_idp=agg["in_idp"],
            in_cmdb=agg["in_cmdb"],
            latest_activity_at=latest_str
        ))
    
    return PresenceDebugResponse(
        run_id=run_id,
        rows=rows
    )
