"""Reconciliation API routes for Farm/AOD comparison"""

from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException

from ...core.policy import get_current_config
from ..schemas import (
    AODActualResultsRequest,
    AODActualResultsResponse,
    ExplainNonflagRequest,
    NonflagExplanation,
    ExplainNonflagResponse,
)
from ...db.database import get_db_direct
from ..deps import get_farm_url


router = APIRouter(prefix="")


def _parse_iso_datetime(ts_str: str | None) -> datetime | None:
    """Parse ISO datetime string to timezone-aware datetime object.
    
    Always returns a timezone-aware datetime (UTC) to ensure consistent
    activity status calculation relative to snapshot time.
    """
    if not ts_str:
        return None
    try:
        if ts_str.endswith('Z'):
            ts_str = ts_str[:-1] + '+00:00'
        parsed = datetime.fromisoformat(ts_str)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except (ValueError, TypeError):
        return None


def _get_run_snapshot_as_of(run) -> datetime | None:
    """Extract snapshot_as_of from run.input_meta for activity recency calculation.
    
    Critical for zombie detection accuracy: ensures activity status (RECENT/STALE)
    is calculated relative to the snapshot's generated_at time, not wall-clock now.
    
    Checks multiple sources in priority order:
    1. provenance.snapshot_generated_at (set during Farm run)
    2. generated_at (Farm adapter normalized field)
    3. created_at (raw Farm meta field)
    """
    if not run or not hasattr(run, 'input_meta') or not run.input_meta:
        return None
    
    provenance = run.input_meta.get("provenance", {})
    snapshot_generated_at = provenance.get("snapshot_generated_at") if provenance else None
    if snapshot_generated_at:
        if isinstance(snapshot_generated_at, datetime):
            return snapshot_generated_at
        if isinstance(snapshot_generated_at, str):
            return _parse_iso_datetime(snapshot_generated_at)
    
    generated_at = run.input_meta.get("generated_at")
    if generated_at:
        if isinstance(generated_at, datetime):
            return generated_at
        if isinstance(generated_at, str):
            return _parse_iso_datetime(generated_at)
    
    created_at = run.input_meta.get("created_at")
    if created_at:
        if isinstance(created_at, datetime):
            return created_at
        if isinstance(created_at, str):
            return _parse_iso_datetime(created_at)
    
    return None


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
    
    NOTE: Uses snapshot_as_of from run.input_meta to ensure activity status is
    calculated relative to snapshot generation time, not wall-clock time.
    """
    from ...pipeline.aod_agent_reconcile import emit_actual_results

    db = await get_db_direct()

    run = await db.get_run(request.run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run not found: {request.run_id}")

    assets = await db.get_assets_by_run(request.run_id)

    rejections_result = await db.get_rejections_by_run(request.run_id, limit=get_current_config().query_limits.default_rejection_limit)
    rejections = rejections_result[0] if isinstance(rejections_result, tuple) else rejections_result

    if not assets and not rejections:
        raise HTTPException(status_code=404, detail=f"No assets or rejections found for run_id: {request.run_id}")

    snapshot_as_of = _get_run_snapshot_as_of(run)

    result = emit_actual_results(
        run_id=request.run_id,
        assets=assets or [],
        activity_window_days=request.activity_window_days,
        rejections=rejections,
        snapshot_as_of=snapshot_as_of
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
    from ...pipeline.derived_classifications import classify_shadow, compute_zombie_status

    db = await get_db_direct()

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


@router.get("/debug/catalog-invariant-check")
async def catalog_invariant_check(run_id: str):
    """
    Clean-room invariant check: Find assets in catalog that violate admission criteria.
    
    INVARIANT: Every cataloged asset MUST have at least one of:
    - num_observations > 0 (discovery evidence)
    - has_idp (IdP governance)
    - has_cmdb (CMDB governance)  
    - has_finance (finance evidence)
    - has_cloud (cloud evidence)
    
    Assets violating this invariant are "ghost assets" that shouldn't be in the catalog.
    """
    db = await get_db_direct()
    
    runs = await db.get_all_runs()
    run = None
    for r in runs:
        r_run_id = getattr(r, 'run_id', None) if hasattr(r, 'run_id') else (r.get("run_id") if isinstance(r, dict) else None)
        if r_run_id == run_id:
            run = r
            break
    
    if not run:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    
    assets = await db.get_assets_by_run(run_id)
    if not assets:
        return {"run_id": run_id, "status": "NO_ASSETS", "violations": []}
    
    violations = []
    valid_count = 0
    
    for asset in assets:
        # Count observations from evidence_refs
        evidence_refs = asset.evidence_refs if asset.evidence_refs else []
        num_observations = len([ref for ref in evidence_refs if isinstance(ref, str) and "observation" in ref.lower()])
        
        # Check governance gates - use lens_coverage as source of truth
        has_idp = asset.lens_coverage.idp if asset.lens_coverage else False
        has_cmdb = asset.lens_coverage.cmdb if asset.lens_coverage else False
        has_finance = asset.lens_coverage.finance if asset.lens_coverage else False
        has_cloud = asset.lens_coverage.cloud if asset.lens_coverage else False
        # Use lens_coverage.discovery as the source of truth (not discovery_sources which may be None)
        has_discovery = asset.lens_coverage.discovery if asset.lens_coverage else False
        # Also check discovery_sources as a backup
        has_discovery_sources = bool(getattr(asset, "discovery_sources", None))
        has_discovery = has_discovery or has_discovery_sources
        
        # Check invariant
        is_valid = has_discovery or has_idp or has_cmdb or has_finance or has_cloud or num_observations > 0
        
        if is_valid:
            valid_count += 1
        else:
            # Get domain for identification
            domain = None
            if asset.identifiers and asset.identifiers.domains:
                domain = asset.identifiers.domains[0] if asset.identifiers.domains else None
            
            violations.append({
                "asset_id": asset.asset_id,
                "name": asset.name,
                "domain": domain,
                "vendor": asset.vendor,
                "num_observations": num_observations,
                "evidence_refs_count": len(evidence_refs),
                "has_idp": has_idp,
                "has_cmdb": has_cmdb,
                "has_finance": has_finance,
                "has_cloud": has_cloud,
                "has_discovery": has_discovery,
                "lens_status": {
                    "idp": asset.lens_status.idp.value if asset.lens_status else None,
                    "cmdb": asset.lens_status.cmdb.value if asset.lens_status else None,
                },
                "discovery_sources": list(getattr(asset, "discovery_sources", []) or []),
            })
    
    # Sort by name and take top 20
    violations = sorted(violations, key=lambda x: x.get("name", ""))[:20]
    
    return {
        "run_id": run_id,
        "status": "VIOLATIONS_FOUND" if violations else "ALL_VALID",
        "total_assets": len(assets),
        "valid_count": valid_count,
        "violation_count": len(violations),
        "top_20_violations": violations,
        "invariant": "Every cataloged asset MUST have: discovery OR idp OR cmdb OR finance OR cloud"
    }


@router.get("/debug/snapshot-drift-check")
async def snapshot_drift_check(run_id: str):
    """
    Detect if a run's source snapshot has changed since ingestion.
    
    Compares stored snapshot fingerprint against current Farm snapshot fingerprint.
    If they differ, the run's assets may be stale (based on old snapshot data).
    
    This is critical for detecting Farm snapshot regeneration which invalidates
    correlated plane matches (IdP, CMDB, etc.) stored in asset records.
    """
    import os
    import httpx
    
    db = await get_db_direct()
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    
    input_meta = run.input_meta if hasattr(run, 'input_meta') else {}
    snapshot_id = input_meta.get("snapshot_id")
    stored_fingerprint = input_meta.get("provenance", {}).get("snapshot_fingerprint")
    
    if not snapshot_id:
        return {
            "run_id": run_id,
            "status": "NO_SNAPSHOT_ID",
            "detail": "Run has no snapshot_id in input_meta"
        }
    
    farm_url = get_farm_url()
    if not farm_url:
        return {
            "run_id": run_id,
            "status": "NO_FARM_URL",
            "detail": "FARM_URL not configured"
        }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{farm_url.rstrip('/')}/api/snapshots?snapshot_id={snapshot_id}")
            if resp.status_code != 200:
                return {
                    "run_id": run_id,
                    "status": "FARM_ERROR",
                    "detail": f"Farm returned {resp.status_code}"
                }
            
            snapshots = resp.json()
            if isinstance(snapshots, dict):
                snapshots = snapshots.get("snapshots", [])
            
            current_snapshot = None
            for s in snapshots:
                if s.get("snapshot_id") == snapshot_id:
                    current_snapshot = s
                    break
            
            if not current_snapshot:
                return {
                    "run_id": run_id,
                    "status": "SNAPSHOT_NOT_FOUND",
                    "detail": f"Snapshot {snapshot_id} not found in Farm"
                }
            
            current_fingerprint = current_snapshot.get("snapshot_fingerprint")
            
            if not stored_fingerprint:
                return {
                    "run_id": run_id,
                    "status": "NO_STORED_FINGERPRINT",
                    "stored_fingerprint": None,
                    "current_fingerprint": current_fingerprint,
                    "detail": "Run was created before fingerprint tracking was added"
                }
            
            if stored_fingerprint == current_fingerprint:
                return {
                    "run_id": run_id,
                    "status": "OK",
                    "stored_fingerprint": stored_fingerprint,
                    "current_fingerprint": current_fingerprint,
                    "detail": "Snapshot has not changed since ingestion"
                }
            else:
                return {
                    "run_id": run_id,
                    "status": "DRIFT_DETECTED",
                    "stored_fingerprint": stored_fingerprint,
                    "current_fingerprint": current_fingerprint,
                    "detail": "CRITICAL: Farm snapshot has been regenerated since this run was created. Assets may have stale correlation data (IdP/CMDB matches that no longer exist)."
                }
                
    except Exception as e:
        return {
            "run_id": run_id,
            "status": "ERROR",
            "detail": f"Failed to check Farm: {str(e)}"
        }
