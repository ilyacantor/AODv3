"""FastAPI routes for AOD"""

from typing import Any, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
import json

from ..db.database import get_db
from ..pipeline.pipeline_executor import execute_pipeline
from ..models.output_contracts import RunLog, RunCounts, Asset, Finding, RunStatus
from ..farm_client import FarmClient, validate_schema_version


router = APIRouter(prefix="/api")


import os

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


class FindingsResponse(BaseModel):
    """Response for findings"""
    run_id: str
    findings: list[dict[str, Any]]
    count: int


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        version="1.0.0"
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
    
    db = await get_db()
    result = await execute_pipeline(data, db)
    
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
    db = await get_db()
    result = await execute_pipeline(snapshot, db)
    
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
    
    Returns run_id + summary counts.
    """
    farm_url = request.farm_base_url or os.environ.get("FARM_URL")
    if not farm_url:
        raise HTTPException(status_code=400, detail="No Farm URL configured. Set FARM_URL environment variable or provide farm_base_url.")
    
    farm_client = FarmClient(farm_url)
    fetch_result = await farm_client.fetch_snapshot(request.snapshot_id)
    
    if not fetch_result.success:
        raise HTTPException(
            status_code=502,
            detail=f"{fetch_result.error_type}: {fetch_result.error}"
        )
    
    snapshot_data = fetch_result.data
    
    schema_valid, schema_error = validate_schema_version(snapshot_data)
    if not schema_valid:
        raise HTTPException(
            status_code=400,
            detail=f"INVALID_INPUT_CONTRACT: {schema_error}"
        )
    
    if "meta" in snapshot_data and "tenant_id" not in snapshot_data["meta"]:
        snapshot_data["meta"]["tenant_id"] = request.tenant_id
    
    db = await get_db()
    result = await execute_pipeline(snapshot_data, db)
    
    if not result.success:
        if result.run_log.status == RunStatus.INVALID_INPUT_CONTRACT:
            raise HTTPException(status_code=400, detail=result.error)
        raise HTTPException(status_code=500, detail=result.error)
    
    return RunResponse(
        run_id=result.run_log.run_id,
        tenant_id=result.run_log.tenant_id,
        status=result.run_log.status.value,
        counts=result.run_log.counts,
        message=f"Discovery completed from Farm. {result.run_log.counts.assets_admitted} assets admitted, {result.run_log.counts.findings_generated} findings generated."
    )


@router.get("/runs", response_model=list[RunDetailResponse])
async def list_runs():
    """List all discovery runs"""
    db = await get_db()
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
                "tags": a.tags,
                "admission_reason": a.admission_reason,
                "evidence_refs": a.evidence_refs,
                "created_at": a.created_at.isoformat()
            }
            for a in assets
        ],
        count=len(assets)
    )


@router.get("/findings", response_model=FindingsResponse)
async def get_findings(run_id: str):
    """Get findings for a run"""
    db = await get_db()
    
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    findings = await db.get_findings_by_run(run_id)
    
    return FindingsResponse(
        run_id=run_id,
        findings=[
            {
                "finding_id": str(f.finding_id),
                "asset_id": str(f.asset_id) if f.asset_id else None,
                "finding_type": f.finding_type.value,
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
