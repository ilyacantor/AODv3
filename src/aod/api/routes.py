"""FastAPI routes for AOD"""

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
        
        assets = await db.get_assets_by_run(run_id)
        findings = await db.get_findings_by_run(run_id)
        
        success, error = await reconcile_to_farm(
            run_log=result.run_log,
            assets=assets,
            findings=findings,
            snapshot_id=request.snapshot_id,
            farm_url=farm_url
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


@router.get("/runs/latest", response_model=RunDetailResponse)
async def get_latest_run(tenant_id: str, snapshot_id: Optional[str] = None):
    """
    Get the latest run for a tenant and optionally a specific snapshot.
    
    Returns HTTP 404 if no matching run exists.
    """
    db = await get_db()
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
        failure_reasons=run.failure_reasons,
        sync_status=run.sync_status.value,
        sync_error=run.sync_error
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
            failure_reasons=run.failure_reasons,
            sync_status=run.sync_status.value,
            sync_error=run.sync_error
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


@router.get("/runs/{run_id}/ambiguous")
async def get_ambiguous(run_id: str, limit: int = 100, offset: int = 0):
    """Get ambiguous matches for a run"""
    db = await get_db()
    
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    items, total = await db.get_ambiguous_matches_by_run(run_id, limit=limit, offset=offset)
    
    return {
        "run_id": run_id,
        "items": items,
        "count": len(items),
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


@router.get("/runs/{run_id}/derived")
async def get_derived_classifications(run_id: str, activity_window_days: int = 30):
    """
    Get derived classifications (Shadow/Zombie) for a run.
    
    These are computed on-read from asset evidence, not stored as flags.
    
    Shadow Asset = has finance/cloud/discovery evidence but NO IdP or CMDB match
                   AND has recent activity within the activity window
    Zombie Asset = in CMDB or IdP but NO discovery/activity evidence
                   OR has no recent activity within the activity window
    
    Args:
        run_id: The run to get classifications for
        activity_window_days: Number of days to consider for recent activity (default 30)
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
