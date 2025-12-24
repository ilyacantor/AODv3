"""Debug and reconcile API routes for AOD"""

import subprocess
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from fastapi import APIRouter, HTTPException

from ...utils.normalization import normalize_key
from ..schemas import (
    ZombieExplainRequest,
    KeyExplanation,
    ZombieExplainResponse,
    ZombieReconcileRequest,
    ZombieReconcileResponse,
    TimestampCoverageRequest,
    PlaneCoverage,
    TimestampCoverageResponse,
    AODActualResultsRequest,
    AODActualResultsResponse,
    ExplainNonflagRequest,
    NonflagExplanation,
    ExplainNonflagResponse,
    RunTestsRequest,
    RunTestsResponse,
    AssetTraceRequest,
    DomainTraceStep,
    AssetTraceResponse,
    TwoPathDiffRequest,
    PathDiffResult,
    TwoPathDiffResponse,
    DecisionTraceRequest,
    DecisionTraceResponse,
)
from ...db.database import get_db
from ..deps import now_pst
from ...models.output_contracts import Asset, LensStatus


router = APIRouter(prefix="")


TIMESTAMP_FIELD_VARIANTS = {
    "discovery": ["observed_at", "observedAt", "timestamp", "ts", "created_at", "createdAt"],
    "idp": ["last_login_at", "lastLoginAt", "lastLogin", "last_activity", "lastActivity"],
    "cloud": ["observed_at", "observedAt", "timestamp", "ts", "created_at"],
    "finance_transactions": ["date", "datetime", "timestamp", "ts", "transaction_date", "transactionDate"],
    "endpoint_apps": ["last_seen_at", "lastSeenAt", "lastSeen", "observed_at"],
    "network_dns": ["timestamp", "observed_at", "observedAt", "ts"],
    "network_proxy": ["timestamp", "observed_at", "observedAt", "ts"],
}


@router.post("/debug/zombie-explain", response_model=ZombieExplainResponse)
async def debug_zombie_explain(request: ZombieExplainRequest):
    """
    Debug endpoint to explain zombie classification decisions.
    
    For each key provided, finds matching assets and explains
    why each was or wasn't classified as a zombie.
    
    Keys are normalized (lowercase, alphanumeric only) for matching.
    """
    from ...pipeline.derived_classifications import compute_zombie_status
    
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
    
    from ...pipeline.farm_adapter import normalize_farm_snapshot
    from ...models.input_contracts import Snapshot
    
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
    from ...pipeline.aod_agent_reconcile import emit_actual_results
    
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


@router.post("/run-tests")
async def run_tests(request: RunTestsRequest) -> RunTestsResponse:
    """
    Run pytest tests and return results.
    """
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


@router.post("/debug/trace-asset")
async def trace_asset(request: AssetTraceRequest) -> AssetTraceResponse:
    """
    Debug endpoint: Trace a single asset through the canonicalization pipeline.
    
    Shows:
    - Raw evidence domains extracted from observations
    - Canonicalization steps for each domain
    - Final asset key and where it was produced
    """
    from ...pipeline.vendor_inference import extract_registered_domain, DOMAIN_TO_VENDOR, VENDOR_TO_DOMAIN
    from ...pipeline.aod_agent_reconcile import _extract_registered_domain
    from ...utils.normalization import normalize_name_for_vendor_lookup as _normalize_name_for_vendor_lookup
    
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


@router.post("/debug/two-path-diff")
async def two_path_diff(request: TwoPathDiffRequest) -> TwoPathDiffResponse:
    """
    Debug endpoint: Compare canonicalization between vendor_inference and reconcile paths.
    
    Detects "two canonicalizers exist" bugs where different code paths
    produce different keys for the same input.
    """
    import uuid as uuid_lib
    from ...pipeline.vendor_inference import extract_registered_domain as vendor_extract
    from ...pipeline.aod_agent_reconcile import _extract_registered_domain
    from ...models.output_contracts import Asset, AssetIdentifiers, LensStatuses, LensCoverage
    
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


@router.post("/debug/decision-trace", response_model=DecisionTraceResponse)
async def get_decision_traces(request: DecisionTraceRequest):
    """
    Get decision traces for all assets in a run.
    
    This produces exactly 13 fields per asset for Farm/AOD comparison:
    - asset_key_used, registered_domain, raw_domains_seen
    - is_external, is_active, activity_window_days, activity_source, latest_activity_at
    - idp_present, cmdb_present, infra_excluded, is_shadow, reason_codes
    """
    from ...pipeline.decision_trace import compute_decision_trace, decision_traces_to_dict
    
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
