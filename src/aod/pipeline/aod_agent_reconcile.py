"""
AOD Agent Reconciliation - Diagnostic Only

This module produces structured actual results for reconciliation and deterministic
root-cause labels for each mismatch. It does NOT change any code.

CRITICAL DIRECTIVE:
When reconciliation shows differences (extra/missed shadows/zombies), this module
diagnoses using reason-code diffs and outputs the most likely root cause code.
It NEVER proposes fixes, patches, or code adjustments. Diagnosis only.

Outputs per run:
- shadow_actual[]: List of asset keys classified as shadow
- zombie_actual[]: List of asset keys classified as zombie
- admission_actual[asset_key]: "admitted" | "rejected"
- actual_reasons[asset_key]: List of reason codes (canonical enum only)
- For each mismatch: rca[asset_key] = RCA_CODE, rca_system[asset_key] = system
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timedelta, timezone

from ..models.output_contracts import Asset, LensStatus


class ReasonCode(str, Enum):
    """Canonical reason codes for admission and classification decisions."""
    HAS_IDP = "HAS_IDP"
    HAS_CMDB = "HAS_CMDB"
    HAS_FINANCE = "HAS_FINANCE"
    HAS_CLOUD = "HAS_CLOUD"
    HAS_DISCOVERY = "HAS_DISCOVERY"
    NO_IDP = "NO_IDP"
    NO_CMDB = "NO_CMDB"
    NO_FINANCE = "NO_FINANCE"
    NO_CLOUD = "NO_CLOUD"
    NO_DISCOVERY = "NO_DISCOVERY"
    RECENT_ACTIVITY = "RECENT_ACTIVITY"
    STALE_ACTIVITY = "STALE_ACTIVITY"
    NO_ACTIVITY_TIMESTAMPS = "NO_ACTIVITY_TIMESTAMPS"
    DISCOVERY_SOURCE_COUNT_GE_2 = "DISCOVERY_SOURCE_COUNT_GE_2"
    DISCOVERY_SOURCE_COUNT_LT_2 = "DISCOVERY_SOURCE_COUNT_LT_2"
    ADMITTED_VIA_IDP = "ADMITTED_VIA_IDP"
    ADMITTED_VIA_CMDB = "ADMITTED_VIA_CMDB"
    ADMITTED_VIA_FINANCE = "ADMITTED_VIA_FINANCE"
    ADMITTED_VIA_CLOUD = "ADMITTED_VIA_CLOUD"
    ADMITTED_VIA_DISCOVERY = "ADMITTED_VIA_DISCOVERY"
    REJECTED_NO_GATE = "REJECTED_NO_GATE"


class RCACode(str, Enum):
    """Root Cause Analysis codes for mismatches."""
    ACTIVITY_TIMESTAMP_DROPPED = "ACTIVITY_TIMESTAMP_DROPPED"
    DISCOVERY_SOURCE_COUNT_MISMATCH = "DISCOVERY_SOURCE_COUNT_MISMATCH"
    DISCOVERY_ADMISSION_GATE_NOT_APPLIED = "DISCOVERY_ADMISSION_GATE_NOT_APPLIED"
    FINANCE_EVIDENCE_INGESTION_MISMATCH = "FINANCE_EVIDENCE_INGESTION_MISMATCH"
    SOR_MATCHING_MISMATCH = "SOR_MATCHING_MISMATCH"
    UNKNOWN = "UNKNOWN"


class RCASystem(str, Enum):
    """Which system is responsible for the mismatch."""
    FARM_EVIDENCE = "FARM_EVIDENCE"
    AOD_INGEST = "AOD_INGEST"
    AOD_ADMISSION = "AOD_ADMISSION"
    AOD_CLASSIFICATION = "AOD_CLASSIFICATION"


@dataclass
class AssetActualResult:
    """Actual classification result for a single asset."""
    asset_key: str
    asset_id: str
    name: str
    admission: str
    is_shadow: bool
    is_zombie: bool
    reasons: list[ReasonCode]
    evidence_summary: dict


@dataclass
class MismatchRCA:
    """Root cause analysis for a single mismatch."""
    asset_key: str
    mismatch_type: str
    expected: str
    actual: str
    rca_code: RCACode
    rca_system: RCASystem
    reason_diff: dict


@dataclass
class ReconciliationResult:
    """Complete reconciliation result."""
    run_id: str
    shadow_actual: list[str]
    zombie_actual: list[str]
    admission_actual: dict[str, str]
    actual_reasons: dict[str, list[str]]
    mismatches: list[MismatchRCA]
    summary: dict


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_utc_aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _normalize_key(key: str) -> str:
    """Normalize asset key for matching."""
    import re
    return re.sub(r'[^a-z0-9]', '', key.lower())


def compute_asset_reasons(asset: Asset, activity_window_days: int = 90) -> tuple[list[ReasonCode], dict]:
    """
    Compute the canonical reason codes for an asset's current state.
    
    Returns:
        Tuple of (reasons list, evidence summary dict)
    """
    reasons = []
    evidence = {}
    
    has_idp = asset.lens_status.idp == LensStatus.MATCHED
    has_cmdb = asset.lens_status.cmdb == LensStatus.MATCHED
    has_finance = asset.lens_coverage.finance
    has_cloud = asset.lens_coverage.cloud
    has_discovery = asset.lens_coverage.discovery
    
    if has_idp:
        reasons.append(ReasonCode.HAS_IDP)
    else:
        reasons.append(ReasonCode.NO_IDP)
    
    if has_cmdb:
        reasons.append(ReasonCode.HAS_CMDB)
    else:
        reasons.append(ReasonCode.NO_CMDB)
    
    if has_finance:
        reasons.append(ReasonCode.HAS_FINANCE)
    else:
        reasons.append(ReasonCode.NO_FINANCE)
    
    if has_cloud:
        reasons.append(ReasonCode.HAS_CLOUD)
    else:
        reasons.append(ReasonCode.NO_CLOUD)
    
    if has_discovery:
        reasons.append(ReasonCode.HAS_DISCOVERY)
    else:
        reasons.append(ReasonCode.NO_DISCOVERY)
    
    latest_activity = _ensure_utc_aware(asset.activity_evidence.latest_activity_at)
    cutoff = _utc_now() - timedelta(days=activity_window_days)
    
    if latest_activity is None:
        reasons.append(ReasonCode.NO_ACTIVITY_TIMESTAMPS)
        evidence["activity"] = "none"
    elif latest_activity < cutoff:
        reasons.append(ReasonCode.STALE_ACTIVITY)
        evidence["activity"] = f"stale:{latest_activity.isoformat()}"
    else:
        reasons.append(ReasonCode.RECENT_ACTIVITY)
        evidence["activity"] = f"recent:{latest_activity.isoformat()}"
    
    discovery_sources = set()
    for ref in asset.evidence_refs:
        if isinstance(ref, str) and ref.startswith("discovery:"):
            parts = ref.split(":")
            if len(parts) >= 2:
                discovery_sources.add(parts[1])
    
    if len(discovery_sources) >= 2:
        reasons.append(ReasonCode.DISCOVERY_SOURCE_COUNT_GE_2)
        evidence["discovery_sources"] = list(discovery_sources)
    else:
        reasons.append(ReasonCode.DISCOVERY_SOURCE_COUNT_LT_2)
        evidence["discovery_sources"] = list(discovery_sources)
    
    evidence["lens_status"] = {
        "idp": asset.lens_status.idp.value,
        "cmdb": asset.lens_status.cmdb.value,
        "cloud": asset.lens_status.cloud.value,
        "finance": asset.lens_status.finance.value
    }
    evidence["lens_coverage"] = {
        "idp": asset.lens_coverage.idp,
        "cmdb": asset.lens_coverage.cmdb,
        "cloud": asset.lens_coverage.cloud,
        "finance": asset.lens_coverage.finance,
        "discovery": asset.lens_coverage.discovery
    }
    
    return reasons, evidence


def classify_actual(asset: Asset, activity_window_days: int = 90) -> AssetActualResult:
    """
    Produce the actual classification result for an asset.
    
    This is the AOD Agent's view of what the asset IS - not what it should be.
    """
    reasons, evidence = compute_asset_reasons(asset, activity_window_days)
    
    has_idp = ReasonCode.HAS_IDP in reasons
    has_cmdb = ReasonCode.HAS_CMDB in reasons
    has_finance = ReasonCode.HAS_FINANCE in reasons
    has_cloud = ReasonCode.HAS_CLOUD in reasons
    has_discovery = ReasonCode.HAS_DISCOVERY in reasons
    has_recent_activity = ReasonCode.RECENT_ACTIVITY in reasons
    discovery_ge_2 = ReasonCode.DISCOVERY_SOURCE_COUNT_GE_2 in reasons
    
    is_shadow = False
    if not has_idp and not has_cmdb:
        if (has_finance or has_cloud or has_discovery) and has_recent_activity:
            is_shadow = True
    
    is_zombie = False
    if has_idp or has_cmdb:
        if not has_recent_activity:
            is_zombie = True
    
    asset_key = _normalize_key(asset.name)
    
    return AssetActualResult(
        asset_key=asset_key,
        asset_id=str(asset.asset_id),
        name=asset.name,
        admission="admitted",
        is_shadow=is_shadow,
        is_zombie=is_zombie,
        reasons=reasons,
        evidence_summary=evidence
    )


def compute_rca(
    asset_key: str,
    mismatch_type: str,
    expected_reasons: list[str],
    actual_reasons: list[str]
) -> MismatchRCA:
    """
    Compute the root cause analysis for a mismatch using deterministic reducer rules.
    
    RCA Reducer Rules (no prose, pick one):
    - Farm says RECENT_ACTIVITY, AOD says STALE_ACTIVITY → ACTIVITY_TIMESTAMP_DROPPED
    - Farm says HAS_DISCOVERY (≥2 sources), AOD says insufficient → DISCOVERY_SOURCE_COUNT_MISMATCH
    - Farm expects admitted via discovery-only, AOD reports REJECTED_NO_GATE → DISCOVERY_ADMISSION_GATE_NOT_APPLIED
    - Farm says NO_FINANCE, AOD says HAS_FINANCE (or vice versa) → FINANCE_EVIDENCE_INGESTION_MISMATCH
    - Farm says NO_IDP/NO_CMDB, AOD shows IdP/CMDB match (or vice versa) → SOR_MATCHING_MISMATCH
    """
    expected_set = set(expected_reasons)
    actual_set = set(actual_reasons)
    
    reason_diff = {
        "expected_only": list(expected_set - actual_set),
        "actual_only": list(actual_set - expected_set),
        "common": list(expected_set & actual_set)
    }
    
    rca_code = RCACode.UNKNOWN
    rca_system = RCASystem.AOD_CLASSIFICATION
    
    if "RECENT_ACTIVITY" in expected_set and "STALE_ACTIVITY" in actual_set:
        rca_code = RCACode.ACTIVITY_TIMESTAMP_DROPPED
        rca_system = RCASystem.AOD_INGEST
    elif "STALE_ACTIVITY" in expected_set and "RECENT_ACTIVITY" in actual_set:
        rca_code = RCACode.ACTIVITY_TIMESTAMP_DROPPED
        rca_system = RCASystem.FARM_EVIDENCE
    
    elif "DISCOVERY_SOURCE_COUNT_GE_2" in expected_set and "DISCOVERY_SOURCE_COUNT_LT_2" in actual_set:
        rca_code = RCACode.DISCOVERY_SOURCE_COUNT_MISMATCH
        rca_system = RCASystem.AOD_INGEST
    elif "DISCOVERY_SOURCE_COUNT_LT_2" in expected_set and "DISCOVERY_SOURCE_COUNT_GE_2" in actual_set:
        rca_code = RCACode.DISCOVERY_SOURCE_COUNT_MISMATCH
        rca_system = RCASystem.FARM_EVIDENCE
    
    elif "ADMITTED_VIA_DISCOVERY" in expected_set and "REJECTED_NO_GATE" in actual_set:
        rca_code = RCACode.DISCOVERY_ADMISSION_GATE_NOT_APPLIED
        rca_system = RCASystem.AOD_ADMISSION
    
    elif ("NO_FINANCE" in expected_set and "HAS_FINANCE" in actual_set) or \
         ("HAS_FINANCE" in expected_set and "NO_FINANCE" in actual_set):
        rca_code = RCACode.FINANCE_EVIDENCE_INGESTION_MISMATCH
        rca_system = RCASystem.AOD_INGEST
    
    elif ("NO_IDP" in expected_set and "HAS_IDP" in actual_set) or \
         ("HAS_IDP" in expected_set and "NO_IDP" in actual_set) or \
         ("NO_CMDB" in expected_set and "HAS_CMDB" in actual_set) or \
         ("HAS_CMDB" in expected_set and "NO_CMDB" in actual_set):
        rca_code = RCACode.SOR_MATCHING_MISMATCH
        rca_system = RCASystem.AOD_CLASSIFICATION
    
    return MismatchRCA(
        asset_key=asset_key,
        mismatch_type=mismatch_type,
        expected="shadow" if mismatch_type.startswith("shadow") else "zombie",
        actual="not_classified" if "missed" in mismatch_type else "classified",
        rca_code=rca_code,
        rca_system=rca_system,
        reason_diff=reason_diff
    )


def reconcile_run(
    run_id: str,
    assets: list[Asset],
    expected_shadow_keys: list[str],
    expected_zombie_keys: list[str],
    activity_window_days: int = 90
) -> ReconciliationResult:
    """
    Reconcile AOD actual results against Farm expectations.
    
    DIAGNOSTIC ONLY - does not change code or propose fixes.
    
    Args:
        run_id: The run ID being reconciled
        assets: List of admitted assets from AOD
        expected_shadow_keys: Asset keys Farm expects to be shadow
        expected_zombie_keys: Asset keys Farm expects to be zombie
        activity_window_days: Activity window for classification
    
    Returns:
        ReconciliationResult with actual results and RCA for mismatches
    """
    shadow_actual = []
    zombie_actual = []
    admission_actual = {}
    actual_reasons = {}
    
    asset_results = {}
    for asset in assets:
        result = classify_actual(asset, activity_window_days)
        asset_results[result.asset_key] = result
        
        admission_actual[result.asset_key] = result.admission
        actual_reasons[result.asset_key] = [r.value for r in result.reasons]
        
        if result.is_shadow:
            shadow_actual.append(result.asset_key)
        if result.is_zombie:
            zombie_actual.append(result.asset_key)
    
    expected_shadow_normalized = [_normalize_key(k) for k in expected_shadow_keys]
    expected_zombie_normalized = [_normalize_key(k) for k in expected_zombie_keys]
    
    shadow_actual_set = set(shadow_actual)
    zombie_actual_set = set(zombie_actual)
    expected_shadow_set = set(expected_shadow_normalized)
    expected_zombie_set = set(expected_zombie_normalized)
    
    missed_shadows = expected_shadow_set - shadow_actual_set
    extra_shadows = shadow_actual_set - expected_shadow_set
    missed_zombies = expected_zombie_set - zombie_actual_set
    extra_zombies = zombie_actual_set - expected_zombie_set
    
    mismatches = []
    
    for key in missed_shadows:
        if key in asset_results:
            result = asset_results[key]
            expected_reasons = ["NO_IDP", "NO_CMDB", "HAS_FINANCE", "RECENT_ACTIVITY"]
            mismatch = compute_rca(
                key, 
                "shadow_missed", 
                expected_reasons,
                [r.value for r in result.reasons]
            )
            mismatches.append(mismatch)
    
    for key in extra_shadows:
        if key in asset_results:
            result = asset_results[key]
            expected_reasons = ["HAS_IDP"]
            mismatch = compute_rca(
                key,
                "shadow_extra",
                expected_reasons,
                [r.value for r in result.reasons]
            )
            mismatches.append(mismatch)
    
    for key in missed_zombies:
        if key in asset_results:
            result = asset_results[key]
            expected_reasons = ["HAS_IDP", "STALE_ACTIVITY"]
            mismatch = compute_rca(
                key,
                "zombie_missed",
                expected_reasons,
                [r.value for r in result.reasons]
            )
            mismatches.append(mismatch)
    
    for key in extra_zombies:
        if key in asset_results:
            result = asset_results[key]
            expected_reasons = ["HAS_IDP", "RECENT_ACTIVITY"]
            mismatch = compute_rca(
                key,
                "zombie_extra",
                expected_reasons,
                [r.value for r in result.reasons]
            )
            mismatches.append(mismatch)
    
    rca_by_code = {}
    rca_by_system = {}
    for m in mismatches:
        rca_by_code[m.rca_code.value] = rca_by_code.get(m.rca_code.value, 0) + 1
        rca_by_system[m.rca_system.value] = rca_by_system.get(m.rca_system.value, 0) + 1
    
    summary = {
        "total_assets": len(assets),
        "shadow_actual_count": len(shadow_actual),
        "zombie_actual_count": len(zombie_actual),
        "expected_shadow_count": len(expected_shadow_keys),
        "expected_zombie_count": len(expected_zombie_keys),
        "missed_shadows": len(missed_shadows),
        "extra_shadows": len(extra_shadows),
        "missed_zombies": len(missed_zombies),
        "extra_zombies": len(extra_zombies),
        "total_mismatches": len(mismatches),
        "rca_by_code": rca_by_code,
        "rca_by_system": rca_by_system
    }
    
    return ReconciliationResult(
        run_id=run_id,
        shadow_actual=shadow_actual,
        zombie_actual=zombie_actual,
        admission_actual=admission_actual,
        actual_reasons=actual_reasons,
        mismatches=mismatches,
        summary=summary
    )
