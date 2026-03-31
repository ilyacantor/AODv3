"""Zombie classification debug API routes"""

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, HTTPException

from ...utils.normalization import normalize_key
from ..schemas import (
    ZombieExplainRequest,
    KeyExplanation,
    ZombieExplainResponse,
    ZombieReconcileRequest,
    ZombieReconcileResponse,
)
from ...db.database import get_db_direct
from ..deps import now_pst
from ...models.output_contracts import Asset, LensStatus


router = APIRouter(prefix="")


@router.post("/debug/zombie-explain", response_model=ZombieExplainResponse)
async def debug_zombie_explain(request: ZombieExplainRequest):
    """
    Debug endpoint to explain zombie classification decisions.

    For each key provided, finds matching assets and explains
    why each was or wasn't classified as a zombie.

    Keys are normalized (lowercase, alphanumeric only) for matching.
    """
    from ...pipeline.derived_classifications import compute_zombie_status

    db = await get_db_direct()

    run = await db.get_run(request.aod_discovery_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {request.aod_discovery_id} not found")

    if run.tenant_id != request.tenant_id:
        raise HTTPException(status_code=400, detail=f"Run {request.aod_discovery_id} belongs to tenant {run.tenant_id}, not {request.tenant_id}")

    assets = await db.get_assets_by_run(request.aod_discovery_id)

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
        aod_discovery_id=request.aod_discovery_id,
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
    db = await get_db_direct()

    run = await db.get_run(request.aod_discovery_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {request.aod_discovery_id} not found")

    assets = await db.get_assets_by_run(request.aod_discovery_id)

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
        f"Run: {request.aod_discovery_id}",
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
        aod_discovery_id=request.aod_discovery_id,
        tenant_id=request.tenant_id,
        window_days=request.window_days,
        expected_count=len(request.expected_zombie_keys),
        extra_count=len(request.extra_zombie_keys),
        missed_zombies_summary=missed_summary,
        extra_zombies_summary=extra_summary,
        compact_report="\n".join(report_lines),
        sample_explanation=sample
    )
