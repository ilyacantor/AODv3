"""
AOD Agent Reconciliation - Actual Results Emitter

This module produces ONLY structured actual results for reconciliation.
It does NOT consume Farm expected data or compute mismatches.

CRITICAL DESIGN PRINCIPLE:
- Farm owns reconciliation UI (has expected + actual + diffs)
- AOD owns its structured "actual" output (status + reason codes + admission outcome)
- Farm displays side-by-side and runs the RCA reducer

DATA FLOW:
- AOD publishes: shadow_actual, zombie_actual, admission_actual, actual_reason_codes
- Farm already has: shadow_expected, zombie_expected, expected_reason_codes
- Farm computes: extra, missed, rca_code per mismatch

HARD RULE (prevents coupling):
- AOD NEVER consumes Farm expected/rca data
- AOD ONLY emits its own "actual + reasons"

Outputs per run:
- shadow_actual[]: List of asset keys classified as shadow
- zombie_actual[]: List of asset keys classified as zombie
- admission_actual[asset_key]: "admitted" | "rejected"
- actual_reasons[asset_key]: List of reason codes (canonical enum only)
"""

from enum import Enum
from dataclasses import dataclass
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
    NOT_RECONCILIATION_ELIGIBLE = "NOT_RECONCILIATION_ELIGIBLE"


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
class ActualResultsOutput:
    """
    Complete actual results output from AOD.
    
    This is what AOD emits - Farm consumes this and computes diffs/RCA.
    """
    run_id: str
    shadow_actual: list[str]
    zombie_actual: list[str]
    admission_actual: dict[str, str]
    actual_reasons: dict[str, list[str]]
    asset_details: dict[str, dict]
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


def is_reconciliation_eligible(asset: Asset) -> bool:
    """
    Determine if an asset is eligible for shadow/zombie reconciliation.
    
    Only assets that represent external services (registered domains, known SaaS)
    should be classified. Internal identifiers like "customer", "elasticsearchlogs"
    should be excluded from shadow/zombie classification to avoid false positives.
    
    Eligibility criteria:
    1. Has at least one registered domain in identifiers.domains
    2. OR has an explicit vendor (not "unknown")
    3. OR has a domain-like name (contains "." with valid TLD pattern)
    
    NOTE: vendor_hypothesis is NOT used here as it is NON-DECISIONABLE metadata.
    Per invariant: vendor_hypothesis MUST NOT be referenced by admission, classification,
    findings, policy, scoring, or automation logic.
    
    Internal identifiers are excluded by failing all criteria above.
    """
    if asset.identifiers and asset.identifiers.domains:
        for domain in asset.identifiers.domains:
            if domain and "." in domain:
                return True
    
    if asset.vendor and asset.vendor.lower() not in ("unknown", "", "none"):
        return True
    
    name = asset.name.lower()
    if "." in name and not name.startswith("."):
        parts = name.split(".")
        if len(parts) >= 2 and len(parts[-1]) >= 2:
            return True
    
    return False


def compute_asset_reasons(asset: Asset, activity_window_days: int = 90) -> tuple[list[ReasonCode], dict]:
    """
    Compute the canonical reason codes for an asset's current state.
    
    IMPORTANT: HAS_* codes mean PRESENCE (evidence exists in plane), not admission.
    - HAS_FINANCE = finance correlation found evidence (MATCHED or AMBIGUOUS)
    - HAS_DISCOVERY = discovery observations exist (even if stale)
    
    Returns:
        Tuple of (reasons list, evidence summary dict)
    """
    reasons = []
    evidence = {}
    
    has_idp = asset.lens_status.idp in (LensStatus.MATCHED, LensStatus.AMBIGUOUS)
    has_cmdb = asset.lens_status.cmdb in (LensStatus.MATCHED, LensStatus.AMBIGUOUS)
    has_finance = asset.lens_status.finance in (LensStatus.MATCHED, LensStatus.AMBIGUOUS)
    has_cloud = asset.lens_status.cloud in (LensStatus.MATCHED, LensStatus.AMBIGUOUS)
    has_discovery = any(
        isinstance(ref, str) and ref.startswith("discovery:")
        for ref in asset.evidence_refs
    ) or asset.activity_evidence.discovery_observed_at is not None
    
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


def _extract_registered_domain(asset: Asset) -> str | None:
    """
    Extract the registered domain from asset identifiers.
    
    INVARIANT: If any entity has a resolvable registered domain, the asset_key
    MUST be that registered domain (e.g., notion.so).
    
    Returns the first valid registered domain, or None if not available.
    """
    if asset.identifiers and asset.identifiers.domains:
        for domain in asset.identifiers.domains:
            if domain and "." in domain:
                return domain.lower().strip()
    return None


def classify_actual(asset: Asset, activity_window_days: int = 90) -> AssetActualResult:
    """
    Produce the actual classification result for an asset.
    
    This is AOD's view of what the asset IS - not what it should be.
    
    IMPORTANT: Only reconciliation-eligible assets (registered domains, known SaaS)
    are classified as shadow/zombie. Internal identifiers are excluded to prevent
    false positives.
    
    KEY INVARIANT: asset_key is the registered domain when available.
    Name-derived keys are only used when no domain exists.
    """
    reasons, evidence = compute_asset_reasons(asset, activity_window_days)
    
    eligible = is_reconciliation_eligible(asset)
    evidence["reconciliation_eligible"] = eligible
    
    if not eligible:
        reasons.append(ReasonCode.NOT_RECONCILIATION_ELIGIBLE)
    
    has_idp = ReasonCode.HAS_IDP in reasons
    has_cmdb = ReasonCode.HAS_CMDB in reasons
    has_finance = ReasonCode.HAS_FINANCE in reasons
    has_cloud = ReasonCode.HAS_CLOUD in reasons
    has_discovery = ReasonCode.HAS_DISCOVERY in reasons
    has_recent_activity = ReasonCode.RECENT_ACTIVITY in reasons
    
    is_shadow = False
    is_zombie = False
    
    if eligible:
        if not has_idp and not has_cmdb:
            if (has_finance or has_cloud or has_discovery) and has_recent_activity:
                is_shadow = True
        
        if has_idp or has_cmdb:
            if not has_recent_activity:
                is_zombie = True
    
    registered_domain = _extract_registered_domain(asset)
    if registered_domain:
        asset_key = registered_domain
        evidence["key_source"] = "registered_domain"
        evidence["name_variant"] = asset.name
    else:
        asset_key = _normalize_key(asset.name)
        evidence["key_source"] = "name_derived"
    
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


def _compute_rejection_reasons(rejection: dict) -> list[str]:
    """
    Compute reason codes for a rejected candidate.
    
    Derives reason codes from rejection metadata to explain
    why the candidate was not admitted.
    """
    reasons = []
    reason_code = rejection.get("reason_code", "").lower()
    reason_detail = rejection.get("reason_detail", "").lower()
    evidence = rejection.get("evidence_summary", {})
    
    if "discovery" in reason_code or "source" in reason_detail:
        reasons.append("DISCOVERY_SOURCE_COUNT_LT_2")
    if "stale" in reason_detail or "activity" in reason_detail:
        reasons.append("STALE_ACTIVITY")
    if "no_gate" in reason_code or "gate" in reason_code:
        reasons.append("REJECTED_NO_GATE")
    
    if evidence.get("has_idp"):
        reasons.append("HAS_IDP")
    else:
        reasons.append("NO_IDP")
    
    if evidence.get("has_cmdb"):
        reasons.append("HAS_CMDB")
    else:
        reasons.append("NO_CMDB")
    
    if evidence.get("has_finance"):
        reasons.append("HAS_FINANCE")
    else:
        reasons.append("NO_FINANCE")
    
    if evidence.get("has_discovery"):
        reasons.append("HAS_DISCOVERY")
    else:
        reasons.append("NO_DISCOVERY")
    
    if not reasons:
        reasons.append("REJECTED_NO_GATE")
    
    return reasons


def emit_actual_results(
    run_id: str,
    assets: list[Asset],
    activity_window_days: int = 90,
    rejections: list[dict] | None = None
) -> ActualResultsOutput:
    """
    Emit AOD's actual results for a run.
    
    This is the ONLY output function. AOD does not consume expected data.
    Farm will take this output and compute diffs/RCA on its side.
    
    IMPORTANT: Includes BOTH admitted assets AND rejected candidates.
    This ensures Farm reconciliation always has aod_reason_codes for every
    asset it asks about.
    
    DOMAIN-LEVEL AGGREGATION: Multiple assets sharing the same registered domain
    are aggregated under one domain key with:
    - is_shadow/is_zombie: OR semantics (if any variant is shadow, domain is shadow)
    - reason_codes: union of all variant reason codes
    - aliases: list of all source asset names/IDs
    
    Args:
        run_id: The run ID
        assets: List of admitted assets from AOD
        activity_window_days: Activity window for classification
        rejections: Optional list of rejected candidates with their metadata
    
    Returns:
        ActualResultsOutput with all actual classifications and reason codes
    """
    domain_aggregates: dict[str, dict] = {}
    
    for asset in assets:
        result = classify_actual(asset, activity_window_days)
        key = result.asset_key
        
        if key not in domain_aggregates:
            domain_aggregates[key] = {
                "admission": result.admission,
                "is_shadow": result.is_shadow,
                "is_zombie": result.is_zombie,
                "reasons": set(r.value for r in result.reasons),
                "asset_ids": [result.asset_id],
                "names": [result.name],
                "evidence_summary": result.evidence_summary
            }
        else:
            agg = domain_aggregates[key]
            agg["is_shadow"] = agg["is_shadow"] or result.is_shadow
            agg["is_zombie"] = agg["is_zombie"] or result.is_zombie
            agg["reasons"].update(r.value for r in result.reasons)
            agg["asset_ids"].append(result.asset_id)
            agg["names"].append(result.name)
    
    shadow_actual = []
    zombie_actual = []
    admission_actual = {}
    actual_reasons = {}
    asset_details = {}
    
    for key, agg in domain_aggregates.items():
        admission_actual[key] = agg["admission"]
        actual_reasons[key] = sorted(list(agg["reasons"]))
        
        evidence = agg["evidence_summary"].copy()
        if len(agg["names"]) > 1:
            evidence["aliases"] = agg["names"]
            evidence["asset_ids"] = agg["asset_ids"]
        
        asset_details[key] = {
            "asset_id": agg["asset_ids"][0],
            "name": agg["names"][0],
            "is_shadow": agg["is_shadow"],
            "is_zombie": agg["is_zombie"],
            "evidence_summary": evidence
        }
        
        if agg["is_shadow"]:
            shadow_actual.append(key)
        if agg["is_zombie"]:
            zombie_actual.append(key)
    
    if rejections:
        for rej in rejections:
            entity_key = _normalize_key(rej.get("entity_name", "") or rej.get("entity_key", ""))
            if not entity_key or entity_key in admission_actual:
                continue
            
            reasons = _compute_rejection_reasons(rej)
            
            admission_actual[entity_key] = "rejected"
            actual_reasons[entity_key] = reasons
            asset_details[entity_key] = {
                "asset_id": None,
                "name": rej.get("entity_name", entity_key),
                "is_shadow": False,
                "is_zombie": False,
                "evidence_summary": {
                    "rejection_reason": rej.get("reason_code", "unknown"),
                    "rejection_detail": rej.get("reason_detail", ""),
                    "original_evidence": rej.get("evidence_summary", {})
                }
            }
    
    shadow_actual = sorted(set(shadow_actual))
    zombie_actual = sorted(set(zombie_actual))
    
    summary = {
        "total_assets": len(assets),
        "total_candidates": len(assets) + (len(rejections) if rejections else 0),
        "domain_keys": len(domain_aggregates),
        "shadow_actual_count": len(shadow_actual),
        "zombie_actual_count": len(zombie_actual),
        "admitted_count": len([v for v in admission_actual.values() if v == "admitted"]),
        "rejected_count": len([v for v in admission_actual.values() if v == "rejected"])
    }
    
    return ActualResultsOutput(
        run_id=run_id,
        shadow_actual=shadow_actual,
        zombie_actual=zombie_actual,
        admission_actual=admission_actual,
        actual_reasons=actual_reasons,
        asset_details=asset_details,
        summary=summary
    )
