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

import os
import logging
from collections import Counter
from enum import Enum
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timedelta, timezone

from ..models.output_contracts import Asset, LensStatus
from .vendor_inference import DOMAIN_TO_VENDOR, VENDOR_TO_DOMAIN, extract_registered_domain
from ..constants import INFRASTRUCTURE_DOMAINS
from ..utils.normalization import normalize_key as _normalize_key, normalize_name_for_vendor_lookup as _normalize_name_for_vendor_lookup
from .derived_classifications import _resolve_domain_key
from ..core.policy import get_current_config


class ReasonCode(str, Enum):
    """Canonical reason codes for admission and classification decisions.
    
    GOVERNANCE SEMANTICS (Jan 2026):
    - HAS_CMDB/HAS_IDP = Direct authoritative match (domain/uri/canonical_name)
    - VENDOR_GOVERNED = Governance via vendor family propagation (explicit rule, not heuristic)
    
    Classification uses: is_governed = HAS_IDP OR HAS_CMDB OR VENDOR_GOVERNED
    But reason codes distinguish the SOURCE of governance for audit trail.
    """
    HAS_IDP = "HAS_IDP"
    HAS_CMDB = "HAS_CMDB"
    HAS_FINANCE = "HAS_FINANCE"
    HAS_ONGOING_FINANCE = "HAS_ONGOING_FINANCE"
    HAS_CLOUD = "HAS_CLOUD"
    HAS_DISCOVERY = "HAS_DISCOVERY"
    VENDOR_GOVERNED = "VENDOR_GOVERNED"  # Governance via vendor family propagation
    NO_IDP = "NO_IDP"
    NO_CMDB = "NO_CMDB"
    NO_FINANCE = "NO_FINANCE"
    NO_ONGOING_FINANCE = "NO_ONGOING_FINANCE"
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
    ANCHORED = "ANCHORED"
    NOT_ANCHORED = "NOT_ANCHORED"
    FINANCIALLY_ANCHORED = "FINANCIALLY_ANCHORED"
    SHADOW_CLASSIFICATION = "SHADOW_CLASSIFICATION"
    FINANCIAL_ANCHOR_GOVERNANCE_GAP = "FINANCIAL_ANCHOR_GOVERNANCE_GAP"
    ZOMBIE_CLASSIFICATION = "ZOMBIE_CLASSIFICATION"
    PARKED_CLASSIFICATION = "PARKED_CLASSIFICATION"


class AnchorType(str, Enum):
    """
    Jan 2026: Reconciliation anchor type vocabulary.
    
    Separates anchor source from reason codes to enable Farm/AOD comparison
    without string wars. This is a RECONCILIATION OUTPUT field, not core logic.
    """
    IDP = "IDP"           # Asset anchored via IdP match
    CMDB = "CMDB"         # Asset anchored via CMDB match
    FINANCE = "FINANCE"   # Asset anchored via finance (spend evidence)
    CLOUD = "CLOUD"       # Asset anchored via cloud resource
    DISCOVERY = "DISCOVERY"  # Asset anchored via discovery only
    NONE = "NONE"         # Not anchored (ungoverned + no discovery)


@dataclass
class AssetActualResult:
    """Actual classification result for a single asset."""
    asset_key: str
    asset_id: str
    name: str
    admission: str
    is_shadow: bool
    is_zombie: bool
    is_parked: bool
    reasons: list[ReasonCode]
    evidence_summary: dict
    # Jan 2026: Reconciliation mapping layer (CTO guidance)
    # These fields normalize vocabulary for Farm/AOD comparison
    anchor_type: AnchorType = AnchorType.NONE
    absence_flags: list[str] = None  # List of NO_* flags for reconciliation
    key_strategy_version: str = "v1"
    entity_key_v2: str = None  # Preview of v2 key for comparison
    
    def __post_init__(self):
        if self.absence_flags is None:
            self.absence_flags = []


@dataclass
class ActualResultsOutput:
    """
    Complete actual results output from AOD.
    
    This is what AOD emits - Farm consumes this and computes diffs/RCA.
    """
    run_id: str
    shadow_actual: list[str]
    zombie_actual: list[str]
    parked_actual: list[str]
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


def _deduplicate_reason_codes(reasons: set) -> set:
    """
    Deduplicate contradictory reason codes when aggregating across assets.
    
    When multiple assets are aggregated under one domain key, their reason codes
    are unioned. This can result in contradictory codes like HAS_IDP + NO_IDP.
    
    Resolution: HAS_* takes precedence over NO_* (OR semantics - if any asset
    has the evidence, the domain has the evidence).
    """
    contradictions = [
        ("HAS_IDP", "NO_IDP"),
        ("HAS_CMDB", "NO_CMDB"),
        ("HAS_FINANCE", "NO_FINANCE"),
        ("HAS_ONGOING_FINANCE", "NO_ONGOING_FINANCE"),
        # NOTE: HAS_CLOUD/NO_CLOUD removed - not used in classification
        ("HAS_DISCOVERY", "NO_DISCOVERY"),
        ("RECENT_ACTIVITY", "STALE_ACTIVITY"),
        ("RECENT_ACTIVITY", "NO_ACTIVITY_TIMESTAMPS"),
        ("STALE_ACTIVITY", "NO_ACTIVITY_TIMESTAMPS"),
        ("DISCOVERY_SOURCE_COUNT_GE_2", "DISCOVERY_SOURCE_COUNT_LT_2"),
    ]
    
    result = set(reasons)
    for has_code, no_code in contradictions:
        if has_code in result and no_code in result:
            result.discard(no_code)
    
    return result


def _is_infrastructure_domain(domain: str) -> bool:
    """Check if a domain is in the infrastructure exclusion list."""
    if not domain:
        return False
    domain_lower = domain.lower().strip()
    if domain_lower in INFRASTRUCTURE_DOMAINS:
        return True
    for infra_domain in INFRASTRUCTURE_DOMAINS:
        if domain_lower.endswith(f".{infra_domain}"):
            return True
    return False


def is_reconciliation_eligible(asset: Asset, mode: str = "sprawl") -> bool:
    """
    Determine if an asset is eligible for shadow/zombie reconciliation.
    
    Mode-based eligibility:
    - "sprawl" mode: SaaS discovery - only external services (domains, known SaaS)
    - "infra" mode: Infrastructure - includes internal identifiers (elasticsearchlogs, etc)
    
    Eligibility criteria for SPRAWL mode (DOMAIN PROMOTION):
    1. Has at least one registered domain in identifiers.domains (NOT infrastructure)
    2. OR has an explicit vendor (not "unknown")
    3. OR normalized name matches a known vendor in VENDOR_TO_DOMAIN (NOT infrastructure)
    4. OR has a domain-like name (contains "." with valid TLD pattern, NOT infrastructure)
    
    EXCLUSION: Infrastructure domains (redis.io, postgresql.org, docker.com, etc.)
    are excluded from sprawl mode reconciliation as they represent tooling, not SaaS.
    
    Eligibility criteria for INFRA mode:
    - All assets are eligible (including internal identifiers)
    
    NOTE: vendor_hypothesis is NOT used here as it is NON-DECISIONABLE metadata.
    Per invariant: vendor_hypothesis MUST NOT be referenced by admission, classification,
    findings, policy, scoring, or automation logic.
    
    Internal identifiers are excluded in sprawl mode by failing all criteria above.
    """
    if mode == "infra":
        return True
    
    if asset.identifiers and asset.identifiers.domains:
        for domain in asset.identifiers.domains:
            if domain and "." in domain:
                if _is_infrastructure_domain(domain):
                    return False
                return True
    
    if asset.vendor and asset.vendor.lower() not in ("unknown", "", "none"):
        vendor_key = asset.vendor.lower().strip()
        if vendor_key in VENDOR_TO_DOMAIN:
            derived_domain = VENDOR_TO_DOMAIN[vendor_key]
            if _is_infrastructure_domain(derived_domain):
                return False
        return True
    
    normalized_name = _normalize_name_for_vendor_lookup(asset.name)
    if normalized_name in VENDOR_TO_DOMAIN:
        derived_domain = VENDOR_TO_DOMAIN[normalized_name]
        if _is_infrastructure_domain(derived_domain):
            return False
        return True
    
    name = asset.name.lower()
    if "." in name and not name.startswith("."):
        parts = name.split(".")
        if len(parts) >= 2 and len(parts[-1]) >= 2:
            if _is_infrastructure_domain(name):
                return False
            return True
    
    return False


def compute_asset_reasons(
    asset: Asset,
    activity_window_days: Optional[int] = None,
    snapshot_as_of: Optional[datetime] = None
) -> tuple[list[ReasonCode], dict]:
    """
    Compute the canonical reason codes for an asset's current state.

    IMPORTANT: HAS_CMDB/HAS_IDP codes mean GOVERNANCE GRANTED (passes gates + authoritative match).
    - HAS_CMDB = CMDB match with authoritative method (domain/uri/canonical_name) passing gates
    - HAS_IDP = IdP match with authoritative method (domain/uri/canonical_name) passing gates
    - HAS_FINANCE = finance evidence with RECURRING spend (one-time purchases excluded)
    - HAS_DISCOVERY = discovery observations exist (even if stale)

    Uses lens_coverage (governance granted) for CMDB/IDP, not lens_status (match exists).
    Heuristic matches (fuzzy, vendor, contains) appear in lens_match_debug but don't grant governance.
    Uses lens_coverage for finance/cloud to respect policy filters.

    Args:
        asset: The asset to compute reasons for
        activity_window_days: Activity window in days (default from policy)
        snapshot_as_of: Reference time for recency calculation (default: wall-clock now).
                       When processing historical snapshots, use the snapshot's generated_at
                       to avoid falsely marking active assets as stale.

    Returns:
        Tuple of (reasons list, evidence summary dict)
    """
    if activity_window_days is None:
        activity_window_days = get_current_config().activity_windows.default_activity_window_days

    reasons = []
    evidence = {}
    
    # Use lens_coverage (governance granted) not lens_status (match exists)
    # HAS_CMDB/HAS_IDP mean "passes gates + authoritative match", not "any correlation"
    has_idp = asset.lens_coverage.idp
    has_cmdb = asset.lens_coverage.cmdb
    has_finance = asset.lens_coverage.finance
    has_cloud = asset.lens_coverage.cloud
    # Source of truth: asset.discovery_sources (set by admission from footprint)
    # No longer recomputed from evidence_refs - single source of truth
    has_discovery = bool(getattr(asset, "discovery_sources", None))
    
    has_ongoing_finance = any(
        isinstance(ref, str) and (
            ref.startswith("recurring_contract:") or 
            ref.startswith("recurring_transaction:")
        )
        for ref in asset.evidence_refs
    )
    
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
    
    if has_ongoing_finance:
        reasons.append(ReasonCode.HAS_ONGOING_FINANCE)
    else:
        reasons.append(ReasonCode.NO_ONGOING_FINANCE)
    
    # NOTE: Cloud presence (HAS_CLOUD/NO_CLOUD) is NOT used in classification
    # (shadow/zombie/parked). Governance is IdP OR CMDB only. We do NOT emit
    # cloud codes to avoid confusing reconciliation reports with irrelevant info.
    
    if has_discovery:
        reasons.append(ReasonCode.HAS_DISCOVERY)
    else:
        reasons.append(ReasonCode.NO_DISCOVERY)
    
    # VENDOR_GOVERNED: Governance via vendor family propagation
    # This is an explicit governance rule (not just enrichment) - can flip classification
    # But distinct from HAS_CMDB/HAS_IDP which mean direct authoritative match
    is_vendor_governed = asset.lens_coverage.vendor_governed if asset.lens_coverage else False
    if is_vendor_governed:
        reasons.append(ReasonCode.VENDOR_GOVERNED)
    
    latest_activity = _ensure_utc_aware(asset.activity_evidence.latest_activity_at)
    reference_time = _ensure_utc_aware(snapshot_as_of) if snapshot_as_of else _utc_now()
    cutoff = reference_time - timedelta(days=activity_window_days)
    
    if latest_activity is None:
        reasons.append(ReasonCode.NO_ACTIVITY_TIMESTAMPS)
        evidence["activity"] = "none"
    elif latest_activity < cutoff:
        reasons.append(ReasonCode.STALE_ACTIVITY)
        evidence["activity"] = f"stale:{latest_activity.isoformat()}"
    else:
        reasons.append(ReasonCode.RECENT_ACTIVITY)
        evidence["activity"] = f"recent:{latest_activity.isoformat()}"
    
    evidence["snapshot_as_of"] = reference_time.isoformat() if reference_time else None
    evidence["activity_cutoff"] = cutoff.isoformat() if cutoff else None
    
    # Source of truth: asset.discovery_sources (set by admission from footprint)
    # No longer recomputed from evidence_refs - single source of truth
    discovery_sources = getattr(asset, "discovery_sources", None) or []
    
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
        "discovery": asset.lens_coverage.discovery,
        "vendor_governed": asset.lens_coverage.vendor_governed
    }
    
    return reasons, evidence


def _extract_raw_domain(asset: Asset) -> str | None:
    """
    Extract the raw domain from asset identifiers, preserving subdomains.
    
    Unlike _extract_registered_domain, this preserves the full subdomain
    so that login498.edge.com stays as login498.edge.com, not edge.com.
    
    This ensures each subdomain is treated as a separate asset key for
    shadow/zombie classification, matching Farm's host-level granularity.
    
    Priority order:
    1. asset.identifiers.domains (explicit domain from evidence) - preserved as-is
    2. Asset name if it looks like a domain - preserved as-is
    3. Vendor lookup - returns canonical vendor domain
    
    Returns the raw domain with subdomains preserved, or None if not available.
    """
    if asset.identifiers and asset.identifiers.domains:
        for domain in asset.identifiers.domains:
            if domain and "." in domain:
                return domain.lower().strip()
    
    name = asset.name.lower().strip()
    if "." in name:
        parts = name.split(".")
        if len(parts) >= 2 and len(parts[-1]) in (2, 3, 4) and parts[-1].isalpha():
            return name
    
    if asset.vendor and asset.vendor.lower() not in ("unknown", "", "none"):
        vendor_key = asset.vendor.lower().strip()
        if vendor_key in VENDOR_TO_DOMAIN:
            return VENDOR_TO_DOMAIN[vendor_key]
    
    normalized_name = _normalize_name_for_vendor_lookup(asset.name)
    if normalized_name in VENDOR_TO_DOMAIN:
        return VENDOR_TO_DOMAIN[normalized_name]
    
    return None


# Phase 1 Consolidation (Jan 2026): Import from canonical_key module (single source of truth)
from .canonical_key import ALIAS_DOMAINS_TO_COLLAPSE


def _normalize_to_canonical_vendor_domain(registered_domain: str) -> str | None:
    """
    Normalize a registered domain to its canonical vendor domain (only for known aliases).

    Phase 1 Consolidation (Jan 2026): Now delegates to canonical_key.normalize_to_canonical_vendor_domain()
    as single source of truth. This wrapper kept for backward compatibility.

    Examples:
        microsoftonline.com -> microsoft.com (known alias)
        office365.com -> microsoft.com (known alias)
        googleapis.com -> google.com (known alias)
        atlassian.net -> None (legitimate primary domain, not an alias)
    """
    from .canonical_key import normalize_to_canonical_vendor_domain
    return normalize_to_canonical_vendor_domain(registered_domain)


def _extract_registered_domain(asset: Asset) -> str | None:
    """
    Extract the canonical domain from asset identifiers or vendor.

    Phase 1 Consolidation (Jan 2026): Now uses canonical_key.compute_canonical_key()
    as single source of truth for domain normalization.

    CRITICAL BUG FIX: Vendor fallback now ONLY executes if no domain evidence exists.
    Previously, vendor lookup at lines 505-508 could override explicit domain evidence
    when extract_registered_domain() returned None (TLD parsing failure). This caused
    KEY_NORMALIZATION_MISMATCH errors.

    Example bug scenario (FIXED):
    - Input: domains=["dropboxusercontent.io"], vendor="Dropbox"
    - Old: extract_registered_domain("dropboxusercontent.io") → None → fallback to "dropbox.com"
    - New: compute_canonical_key() correctly handles all TLDs → "dropbox.com" (via alias collapse)

    Returns the first valid canonical domain, or None if not available.
    """
    from .canonical_key import compute_canonical_key

    domains = asset.identifiers.domains if asset.identifiers else []
    vendor = asset.vendor if asset.vendor else None
    name = asset.name if asset.name else ""

    try:
        result = compute_canonical_key(domains=domains, vendor=vendor, name=name)
        # Only return domain if is_canonical (not name-derived)
        return result.primary_key if result.is_canonical else None
    except ValueError:
        return None


def classify_actual(
    asset: Asset,
    activity_window_days: Optional[int] = None,
    mode: str = "sprawl",
    snapshot_as_of: Optional[datetime] = None,
    debug_keys: Optional[set[str]] = None
) -> AssetActualResult:
    """
    Produce the actual classification result for an asset.

    This is AOD's view of what the asset IS - not what it should be.

    IMPORTANT: Only reconciliation-eligible assets (registered domains, known SaaS)
    are classified as shadow/zombie/parked. Internal identifiers are excluded to prevent
    false positives.

    KEY INVARIANT: asset_key is the registered domain when available.
    Name-derived keys are only used when no domain exists.

    ALIGNED WITH POLICY ENGINE:
    Classification rules match PolicyEngine._classify() exactly:
    - is_governed = has_idp OR has_cmdb
    - is_shadow = NOT is_governed AND activity_status==RECENT
    - is_zombie = is_governed AND activity_status==STALE
    - is_parked = NOT is_governed AND activity_status==STALE

    This is the single source of truth for classification logic.

    Key rule: NO_ACTIVITY_TIMESTAMPS is indeterminate, not stale.

    Args:
        asset: The asset to classify
        activity_window_days: Activity window for classification (default from policy)
        mode: Reconciliation mode - "sprawl" (SaaS only) or "infra" (all assets)
        snapshot_as_of: Reference time for recency calculation (default: wall-clock now)
        debug_keys: Set of asset keys to dump diagnostic info for (from DEBUG_RECONCILE_ASSETS)
    """
    if activity_window_days is None:
        activity_window_days = get_current_config().activity_windows.default_activity_window_days

    reasons, evidence = compute_asset_reasons(asset, activity_window_days, snapshot_as_of)
    
    eligible = is_reconciliation_eligible(asset, mode=mode)
    evidence["reconciliation_eligible"] = eligible
    
    if not eligible:
        reasons.append(ReasonCode.NOT_RECONCILIATION_ELIGIBLE)
    
    has_idp = ReasonCode.HAS_IDP in reasons
    has_cmdb = ReasonCode.HAS_CMDB in reasons
    has_finance = ReasonCode.HAS_FINANCE in reasons
    has_ongoing_finance = ReasonCode.HAS_ONGOING_FINANCE in reasons
    has_discovery = ReasonCode.HAS_DISCOVERY in reasons
    has_recent_activity = ReasonCode.RECENT_ACTIVITY in reasons
    has_stale_activity = ReasonCode.STALE_ACTIVITY in reasons
    has_no_activity = ReasonCode.NO_ACTIVITY_TIMESTAMPS in reasons
    is_vendor_governed = ReasonCode.VENDOR_GOVERNED in reasons
    
    # Cloud presence for anchoring (not used in governance/classification)
    has_cloud = asset.lens_coverage.cloud if asset.lens_coverage else False
    
    # Domain-aligned IdP governance for zombie classification
    # IdP match counts as governance ONLY if domain-aligned.
    # Use explicit idp_governance_aligned flag set during admission.
    # Cross-domain IdP matches (name-based without domain alignment) don't count as governance.
    has_domain_aligned_idp = (
        has_idp and 
        asset.activity_evidence and 
        asset.activity_evidence.idp_governance_aligned
    )
    
    # GOVERNANCE SEMANTICS (Jan 2026):
    # - HAS_CMDB/HAS_IDP = Direct authoritative match only
    # - VENDOR_GOVERNED = Governance via vendor family propagation (explicit rule)
    #
    # Classification uses: is_governed = HAS_IDP OR HAS_CMDB OR VENDOR_GOVERNED
    # But reason codes distinguish the SOURCE of governance for audit trail.
    #
    # Governance variants:
    # - Strict: domain-aligned IdP OR CMDB OR vendor_governed (used for shadows)
    # - Broad: any IdP OR CMDB OR vendor_governed (used for zombies)
    has_governance_broad = has_idp or has_cmdb or is_vendor_governed
    has_governance_strict = has_domain_aligned_idp or has_cmdb or is_vendor_governed
    has_governance = has_governance_strict  # Default to strict for backward compatibility

    # Store both in evidence_summary for downstream use
    is_anchored = has_idp or has_cmdb or has_finance or has_cloud or is_vendor_governed
    financially_anchored = has_ongoing_finance
    
    if is_anchored:
        reasons.append(ReasonCode.ANCHORED)
    else:
        reasons.append(ReasonCode.NOT_ANCHORED)
    
    if financially_anchored:
        reasons.append(ReasonCode.FINANCIALLY_ANCHORED)
    
    evidence["is_anchored"] = is_anchored
    evidence["has_governance"] = has_governance_strict  # Shadows use this (strict)
    evidence["has_governance_broad"] = has_governance_broad  # Zombies use this (broad)
    evidence["vendor_governed"] = is_vendor_governed  # Governance via vendor family
    evidence["financially_anchored"] = financially_anchored
    
    is_shadow = False
    is_zombie = False
    is_parked = False
    
    if eligible:
        ungoverned_access_inventory = not has_governance
        
        # ALIGNED WITH POLICY ENGINE (Dec 2025):
        # Shadow = NOT is_governed AND activity_status==RECENT
        if ungoverned_access_inventory and has_recent_activity:
            is_shadow = True
            reasons.append(ReasonCode.SHADOW_CLASSIFICATION)
            
            if financially_anchored:
                reasons.append(ReasonCode.FINANCIAL_ANCHOR_GOVERNANCE_GAP)
        
        # ALIGNED WITH POLICY ENGINE (Dec 2025):
        # Zombie = is_governed AND activity_status==STALE AND has_ongoing_finance
        # "Paying for something you don't use" - requires ongoing spend
        # Without ongoing finance, stale governed assets are just inactive (not wasting money)
        #
        # Use has_governance_broad for zombie classification.
        # Farm treats cross-domain IdP matches (e.g., flowapp.app entity matched to flowapp.co IdP)
        # as governance for zombies. This differs from shadows which require exact domain matches.
        if has_stale_activity:
            if has_governance_broad and has_ongoing_finance:
                is_zombie = True
                reasons.append(ReasonCode.ZOMBIE_CLASSIFICATION)
            elif not has_governance_broad:
                is_parked = True
                reasons.append(ReasonCode.PARKED_CLASSIFICATION)
    
    domain_key, is_canonical, alias_keys = _resolve_domain_key(asset)
    
    all_domain_variants = set(alias_keys)
    
    if asset.identifiers and asset.identifiers.domains:
        for d in asset.identifiers.domains:
            if d and "." in d:
                all_domain_variants.add(d.lower().strip())
    
    name_lower = asset.name.lower().strip()
    if "." in name_lower:
        parts = name_lower.split(".")
        if len(parts) >= 2 and len(parts[-1]) in (2, 3, 4) and parts[-1].isalpha():
            all_domain_variants.add(name_lower)
    
    for ref in asset.evidence_refs:
        if isinstance(ref, str) and ":" in ref:
            parts = ref.split(":")
            if len(parts) >= 2:
                potential_domain = parts[1].lower().strip()
                if "." in potential_domain and not potential_domain.startswith("obs_"):
                    domain_parts = potential_domain.split(".")
                    if len(domain_parts) >= 2 and len(domain_parts[-1]) in (2, 3, 4) and domain_parts[-1].isalpha():
                        all_domain_variants.add(potential_domain)
    
    all_domain_variants.add(domain_key)
    
    if is_canonical:
        raw_domain = None
        if asset.identifiers and asset.identifiers.domains:
            for d in asset.identifiers.domains:
                if d and "." in d:
                    raw_domain = d.lower().strip()
                    break
        
        registered = extract_registered_domain(raw_domain) if raw_domain else domain_key
        evidence["key_source"] = "domain" if raw_domain else "vendor_canonical"
        evidence["raw_domain"] = raw_domain
        evidence["registered_domain"] = registered or domain_key
        evidence["name_variant"] = asset.name
        evidence["alias_keys"] = alias_keys
        evidence["all_domain_variants"] = sorted(all_domain_variants)
        asset_key = domain_key
    else:
        asset_key = domain_key
        evidence["key_source"] = "name_derived"
        evidence["original_name"] = asset.name
        evidence["alias_keys"] = alias_keys
        evidence["all_domain_variants"] = sorted(all_domain_variants) if all_domain_variants else []
    
    if debug_keys and (asset_key in debug_keys or any(ak in debug_keys for ak in alias_keys)):
        has_finance_flag = ReasonCode.HAS_FINANCE in reasons
        has_ongoing_finance_flag = ReasonCode.HAS_ONGOING_FINANCE in reasons
        finance_refs = [r for r in asset.evidence_refs if isinstance(r, str) and ('finance' in r.lower() or 'contract' in r.lower() or 'transaction' in r.lower())]
        recurring_refs = [r for r in asset.evidence_refs if isinstance(r, str) and (r.startswith("recurring_contract:") or r.startswith("recurring_transaction:"))]
        
        activity_status = "RECENT" if ReasonCode.RECENT_ACTIVITY in reasons else ("STALE" if ReasonCode.STALE_ACTIVITY in reasons else "NONE")
        
        print(f"\n=== DEBUG_RECONCILE_ASSETS: {asset_key} ===")
        print(f"  canonical_key: {asset_key}")
        print(f"  alias_keys: {alias_keys}")
        print(f"  first 20 evidence_refs: {asset.evidence_refs[:20]}")
        print(f"  has_finance: {has_finance_flag}")
        print(f"  has_ongoing_finance: {has_ongoing_finance_flag}")
        print(f"  finance_refs: {finance_refs}")
        print(f"  recurring_refs (triggers HAS_ONGOING_FINANCE): {recurring_refs}")
        print(f"  snapshot_as_of: {evidence.get('snapshot_as_of', 'N/A')}")
        print(f"  activity_cutoff: {evidence.get('activity_cutoff', 'N/A')}")
        print(f"  latest_activity_at: {asset.activity_evidence.latest_activity_at}")
        print(f"  activity_status: {activity_status}")
        print(f"  final_class: shadow={is_shadow}, zombie={is_zombie}, parked={is_parked}")
        print(f"  all_reasons: {[r.value for r in reasons]}")
        print(f"=== END DEBUG ===\n")
    
    # Jan 2026: Compute reconciliation mapping layer fields (CTO guidance)
    # anchor_type: Priority order IDP > CMDB > FINANCE > CLOUD > DISCOVERY > NONE
    if has_idp:
        anchor_type = AnchorType.IDP
    elif has_cmdb:
        anchor_type = AnchorType.CMDB
    elif has_finance:
        anchor_type = AnchorType.FINANCE
    elif has_cloud:
        anchor_type = AnchorType.CLOUD
    elif has_discovery:
        anchor_type = AnchorType.DISCOVERY
    else:
        anchor_type = AnchorType.NONE
    
    # absence_flags: Extract all NO_* reason codes for reconciliation
    absence_flags = [r.value for r in reasons if r.value.startswith("NO_")]
    
    # Compute v2 key for preview (uses domain_provenance if available)
    from .canonical_key import compute_canonical_key_v2
    from ..core.policy import get_current_config
    
    domain_provenance = {}
    if asset.identifiers and hasattr(asset.identifiers, 'domain_provenance'):
        domain_provenance = asset.identifiers.domain_provenance or {}
    
    domains = list(asset.identifiers.domains) if asset.identifiers and asset.identifiers.domains else []
    
    try:
        v2_result = compute_canonical_key_v2(
            domains=domains,
            domain_provenance=domain_provenance,
            vendor=asset.vendor,
            name=asset.name,
            idp_app_id=None  # TODO: Extract IdP app_id if available
        )
        entity_key_v2 = v2_result.primary_key
    except Exception:
        entity_key_v2 = asset_key  # Fall back to v1 key on error
    
    key_strategy_version = get_current_config().key_strategy_version
    
    return AssetActualResult(
        asset_key=asset_key,
        asset_id=str(asset.asset_id),
        name=asset.name,
        admission="admitted",
        is_shadow=is_shadow,
        is_zombie=is_zombie,
        is_parked=is_parked,
        reasons=reasons,
        evidence_summary=evidence,
        anchor_type=anchor_type,
        absence_flags=absence_flags,
        key_strategy_version=key_strategy_version,
        entity_key_v2=entity_key_v2
    )


def _compute_rejection_reasons(rejection: dict) -> list[str]:
    """
    Compute reason codes for a rejected candidate.
    
    Derives reason codes from rejection metadata to explain
    why the candidate was not admitted.

    Governance semantics: rejected candidates by definition do NOT have governance.
    HAS_IDP/HAS_CMDB require admission (authoritative match + passes gates).
    Raw correlation presence in rejected candidates is just enrichment, not governance.

    INVARIANT: Rejected candidates always emit NO_IDP, NO_CMDB.
    This prevents zombie classification on rejected candidates.
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
    
    # Rejected candidates NEVER have governance.
    # HAS_IDP/HAS_CMDB mean "governance granted" (authoritative match + passes gates).
    # Since this candidate was rejected, it definitionally lacks governance.
    # Use lens_coverage from evidence if available, otherwise assume no governance.
    lens_coverage = evidence.get("lens_coverage", {})
    if lens_coverage.get("idp", False):
        reasons.append("HAS_IDP")
    else:
        reasons.append("NO_IDP")
    
    if lens_coverage.get("cmdb", False):
        reasons.append("HAS_CMDB")
    else:
        reasons.append("NO_CMDB")
    
    if evidence.get("has_finance") or lens_coverage.get("finance", False):
        reasons.append("HAS_FINANCE")
    else:
        reasons.append("NO_FINANCE")
    
    if evidence.get("has_discovery") or lens_coverage.get("discovery", False):
        reasons.append("HAS_DISCOVERY")
    else:
        reasons.append("NO_DISCOVERY")
    
    if not reasons:
        reasons.append("REJECTED_NO_GATE")
    
    return reasons


def emit_actual_results(
    run_id: str,
    assets: list[Asset],
    activity_window_days: Optional[int] = None,
    rejections: list[dict] | None = None,
    mode: str = "sprawl",
    snapshot_as_of: Optional[datetime] = None
) -> ActualResultsOutput:
    """
    Emit AOD's actual results for a run.

    This is the ONLY output function. AOD does not consume expected data.
    Farm will take this output and compute diffs/RCA on its side.

    IMPORTANT: Includes BOTH admitted assets AND rejected candidates.
    This ensures Farm reconciliation always has aod_reason_codes for every
    asset it asks about.

    DOMAIN-LEVEL AGGREGATION: Assets are aggregated by registered domain key
    (e.g., app.asana.com and api.asana.com both map to asana.com key).
    Uses _resolve_domain_key() from derived_classifications for consistent
    key resolution across UI and reconciliation.

    ALIAS PROPAGATION: All original subdomains and domain variants are preserved
    in domain_aliases and alias_keys fields, enabling Farm to match against
    any key variant (canonical domain OR original subdomain).

    Shadow/zombie status is OR'd across assets sharing the same domain key.

    Args:
        run_id: The run ID
        assets: List of admitted assets from AOD
        activity_window_days: Activity window for classification (default from policy)
        rejections: Optional list of rejected candidates with their metadata
        mode: Reconciliation mode - "sprawl" (SaaS only) or "infra" (all assets)
        snapshot_as_of: Reference time for recency calculation (default: wall-clock now).
                       When processing historical snapshots, use the snapshot's generated_at
                       to avoid falsely marking active assets as stale.

    Returns:
        ActualResultsOutput with all actual classifications and reason codes
    """
    if activity_window_days is None:
        activity_window_days = get_current_config().activity_windows.default_activity_window_days
    debug_keys_env = os.environ.get("DEBUG_RECONCILE_ASSETS", "")
    debug_keys: Optional[set[str]] = None
    if debug_keys_env:
        debug_keys = set(k.strip().lower() for k in debug_keys_env.split(",") if k.strip())
        if debug_keys:
            print(f"\n=== DEBUG_RECONCILE_ASSETS enabled for: {debug_keys} ===")
            print(f"  snapshot_as_of: {snapshot_as_of.isoformat() if snapshot_as_of else 'wall-clock now'}")
            print(f"  activity_window_days: {activity_window_days}")
            print(f"  mode: {mode}")
    
    asset_results: dict[str, dict] = {}
    
    # Reference time for activity calculation
    reference_time = _ensure_utc_aware(snapshot_as_of) if snapshot_as_of else _utc_now()
    cutoff = reference_time - timedelta(days=activity_window_days)
    
    
    for asset in assets:
        result = classify_actual(asset, activity_window_days, mode=mode, snapshot_as_of=snapshot_as_of, debug_keys=debug_keys)
        key = result.asset_key
        
        registered_domain = result.evidence_summary.get("registered_domain")
        all_variants = set(result.evidence_summary.get("all_domain_variants", []))
        
        has_governance = result.evidence_summary.get("has_governance", False)  # Strict (for shadows)
        has_governance_broad_flag = result.evidence_summary.get("has_governance_broad", False)  # Broad (for zombies)
        has_ongoing_finance = result.evidence_summary.get("financially_anchored", False)
        
        # Track domain-aligned governance for zombie classification
        # Use explicit idp_governance_aligned flag from admission
        has_cmdb_governance = ReasonCode.HAS_CMDB.value in [r.value for r in result.reasons]
        has_idp = ReasonCode.HAS_IDP.value in [r.value for r in result.reasons]
        has_domain_aligned_idp = (
            has_idp and 
            asset.activity_evidence and 
            asset.activity_evidence.idp_governance_aligned
        )
        has_governance_strict = has_domain_aligned_idp or has_cmdb_governance
        
        # Extract activity timestamp from asset for aggregation
        asset_latest_activity = _ensure_utc_aware(asset.activity_evidence.latest_activity_at) if asset.activity_evidence else None
        
        if key not in asset_results:
            asset_results[key] = {
                "admission": result.admission,
                "reasons": set(r.value for r in result.reasons),
                "asset_ids": [result.asset_id],
                "names": [result.name],
                "all_domain_variants": all_variants,
                "registered_domain": registered_domain,
                "evidence_summary": result.evidence_summary,
                "shadow_candidate_exists": result.is_shadow,
                "has_governance_any": has_governance,  # Strict (for shadows)
                "has_governance_broad_any": has_governance_broad_flag,  # Broad (for zombies)
                "has_governance_strict_any": has_governance_strict,
                "has_ongoing_finance_any": has_ongoing_finance,
                "latest_activity_at": asset_latest_activity,
                "is_parked": result.is_parked,
                "is_canonical": result.evidence_summary.get("key_source") == "domain",
                "idp_governance_aligned": has_domain_aligned_idp
            }
        else:
            agg = asset_results[key]
            agg["reasons"].update(r.value for r in result.reasons)
            agg["asset_ids"].append(result.asset_id)
            agg["names"].append(result.name)
            agg["all_domain_variants"].update(all_variants)
            agg["shadow_candidate_exists"] = agg["shadow_candidate_exists"] or result.is_shadow
            agg["has_governance_any"] = agg["has_governance_any"] or has_governance  # Strict
            agg["has_governance_broad_any"] = agg.get("has_governance_broad_any", False) or has_governance_broad_flag  # Broad
            agg["has_governance_strict_any"] = agg.get("has_governance_strict_any", False) or has_governance_strict
            agg["has_ongoing_finance_any"] = agg["has_ongoing_finance_any"] or has_ongoing_finance
            # Track MAX activity timestamp across all assets for this domain
            if asset_latest_activity:
                if agg["latest_activity_at"] is None or asset_latest_activity > agg["latest_activity_at"]:
                    agg["latest_activity_at"] = asset_latest_activity
            # is_parked stays OR-based (any parked candidate)
            agg["is_parked"] = agg["is_parked"] or result.is_parked
            # OR the idp_governance_aligned flag
            agg["idp_governance_aligned"] = agg.get("idp_governance_aligned", False) or has_domain_aligned_idp
    
    for key, agg in asset_results.items():
        shadow_candidate = agg.get("shadow_candidate_exists", False)
        has_gov = agg.get("has_governance_any", False)  # Strict (for shadows)
        has_gov_broad = agg.get("has_governance_broad_any", False)  # Broad (for zombies)
        has_gov_strict = agg.get("has_governance_strict_any", False)
        has_ongoing_finance = agg.get("has_ongoing_finance_any", False)
        latest_activity = agg.get("latest_activity_at")
        
        # Recompute aggregated activity status using MAX timestamp across all assets
        aggregated_is_stale = False
        aggregated_is_recent = False
        if latest_activity is not None:
            if latest_activity < cutoff:
                aggregated_is_stale = True
            else:
                aggregated_is_recent = True
        
        # Shadow: ungoverned AND recent activity (uses broad governance)
        agg["is_shadow"] = shadow_candidate and not has_gov
        
        # DISABLED cross-domain zombie suppression
        # The previous logic incorrectly suppressed legitimate zombies when SEPARATE
        # entities happened to share a domain. Example: Linkforce (Legacy) with only
        # linkforce.io was suppressed because other distinct Linkforce products
        # (Linkforce-prod, Linkforc) claimed linkforce.io in their domain lists.
        #
        # The original intent was to prevent zombies for multi-TLD brand variants
        # (e.g., teamdesk.ai when teamdesk.dev is recent), but it caused false negatives
        # for legitimate separate products that share domains.
        #
        # TODO: Implement better entity disambiguation to distinguish:
        # - Same product with multiple TLDs (.com + .io + .ai)
        # - Different products from same company (Product-Legacy vs Product-New)
        cross_domain_is_recent = False  # Disabled

        # Zombie: governed AND stale (aggregated) AND ongoing finance
        # Use broad governance (any IdP or CMDB) for zombie classification
        # Farm treats cross-domain IdP matches as governance for zombies (e.g., flowapp.app
        # matched to flowapp.co IdP is governed), unlike shadows which require exact matches.
        agg["is_zombie"] = has_gov_broad and aggregated_is_stale and has_ongoing_finance
        
        # Parked: ungoverned (broad) AND stale (aggregated) AND NOT zombie
        # Use has_gov_broad for parked to be consistent with zombie logic
        # Assets are only parked if they're ungoverned (no IdP/CMDB at all) OR lack ongoing finance
        if not has_gov_broad and aggregated_is_stale:
            agg["is_parked"] = True
        elif has_gov_broad and aggregated_is_stale and not has_ongoing_finance:
            # Governed + stale but no ongoing finance = parked (not wasting money, just inactive)
            agg["is_parked"] = True
        elif aggregated_is_recent:
            # If domain is recent, it's not parked even if some assets were stale
            agg["is_parked"] = False
        
        reasons = agg["reasons"]
        if not agg["is_shadow"]:
            reasons.discard(ReasonCode.SHADOW_CLASSIFICATION.value)
            reasons.discard(ReasonCode.FINANCIAL_ANCHOR_GOVERNANCE_GAP.value)
        if not agg["is_zombie"]:
            reasons.discard(ReasonCode.ZOMBIE_CLASSIFICATION.value)
        
        reasons = _deduplicate_reason_codes(reasons)
        
        # FORMAT PARITY FIX (Jan 2026):
        # After aggregation and deduplication, re-assert explicit negative codes based on
        # FINAL merged state. This prevents "silent negatives" when:
        # - Asset A had HAS_IDP (from non-canonical app, now blocked)
        # - Asset B had NO_IDP
        # - Union created {HAS_IDP, NO_IDP}, dedup removed NO_IDP
        # - After blocking, HAS_IDP is gone but NO_IDP was never re-asserted
        #
        # The fix: Check final governance flags and ensure explicit negative codes exist.
        final_has_idp = ReasonCode.HAS_IDP.value in reasons
        final_has_cmdb = ReasonCode.HAS_CMDB.value in reasons
        final_has_finance = ReasonCode.HAS_FINANCE.value in reasons
        
        if not final_has_idp and ReasonCode.NO_IDP.value not in reasons:
            reasons.add(ReasonCode.NO_IDP.value)
        if not final_has_cmdb and ReasonCode.NO_CMDB.value not in reasons:
            reasons.add(ReasonCode.NO_CMDB.value)
        if not final_has_finance and ReasonCode.NO_FINANCE.value not in reasons:
            reasons.add(ReasonCode.NO_FINANCE.value)
        
        agg["reasons"] = reasons
    
    shadow_actual = []
    zombie_actual = []
    parked_actual = []
    admission_actual = {}
    actual_reasons = {}
    asset_details = {}
    
    for key, agg in asset_results.items():
        admission_actual[key] = agg["admission"]
        actual_reasons[key] = sorted(list(agg["reasons"]))
        
        evidence = agg["evidence_summary"].copy()
        if len(agg["names"]) > 1:
            evidence["aliases"] = agg["names"]
            evidence["asset_ids"] = agg["asset_ids"]
        
        domain_aliases = sorted(agg.get("all_domain_variants", set()))
        if domain_aliases:
            evidence["domain_aliases"] = domain_aliases
        if agg.get("registered_domain"):
            evidence["registered_domain"] = agg["registered_domain"]
        
        # Jan 2026 Fix for KEY_NORMALIZATION_MISMATCH:
        # Build alias_keys from ALL domain variants so Farm can look up assets
        # by any domain variant, not just the primary asset key.
        # This enables matching when AOD keys by name but has domain in identifiers.domains.
        original_alias_keys = set(evidence.get("alias_keys", []))
        all_alias_keys = original_alias_keys.copy()
        # Add all domain variants (includes identifiers.domains)
        all_alias_keys.update(domain_aliases)
        # Add registered domain
        if agg.get("registered_domain"):
            all_alias_keys.add(agg["registered_domain"])
        # Remove the primary key from alias_keys (it's the canonical key, not an alias)
        all_alias_keys.discard(key)
        alias_keys = sorted(all_alias_keys)
        
        # CRITICAL: Also update evidence["alias_keys"] so Farm can find it
        # (Farm reads evidence_summary.alias_keys for domain lookup)
        evidence["alias_keys"] = alias_keys
        
        asset_details[key] = {
            "asset_id": agg["asset_ids"][0],
            "name": agg["names"][0],
            "is_shadow": agg["is_shadow"],
            "is_zombie": agg["is_zombie"],
            "is_parked": agg["is_parked"],
            "domain_aliases": domain_aliases,
            "alias_keys": alias_keys,
            "registered_domain": agg.get("registered_domain"),
            "evidence_summary": evidence
        }
        
        if agg["is_shadow"]:
            shadow_actual.append(key)
        if agg["is_zombie"]:
            zombie_actual.append(key)
        if agg["is_parked"]:
            parked_actual.append(key)
    
    # Jan 2026 FIX: Alias expansion must not override an asset's own classification
    # Build sets of primary keys for each classification
    primary_shadow_keys = set()
    primary_zombie_keys = set()
    primary_parked_keys = set()
    all_primary_keys = set(asset_results.keys())
    
    for key, agg in asset_results.items():
        if agg["is_shadow"]:
            primary_shadow_keys.add(key)
        if agg["is_zombie"]:
            primary_zombie_keys.add(key)
        if agg["is_parked"]:
            primary_parked_keys.add(key)
    
    # Now add aliases, but ONLY if the alias is not already a primary key for another asset
    # This prevents hipchat.com (zombie) from adding atlassian.net (not-zombie) to zombie_actual
    for key, agg in asset_results.items():
        alias_keys = asset_details[key].get("alias_keys", [])
        for alias_domain in alias_keys:
            # Skip if this alias is already a primary key for another asset
            # The asset's own classification takes precedence over being an alias
            if alias_domain in all_primary_keys:
                continue
            
            # Add alias to the appropriate list based on parent's classification
            if agg["is_shadow"]:
                shadow_actual.append(alias_domain)
            if agg["is_zombie"]:
                zombie_actual.append(alias_domain)
            if agg["is_parked"]:
                parked_actual.append(alias_domain)
    
    if rejections:
        for rej in rejections:
            # CRITICAL FIX: Extract domain from entity_key (format: "entity:{domain}")
            # entity_key has the canonical domain, entity_name has the display name
            raw_entity_key = rej.get("entity_key", "")
            if raw_entity_key and raw_entity_key.startswith("entity:"):
                # Use domain from entity_key (e.g., "entity:tiktok.com" -> "tiktok.com")
                entity_key = raw_entity_key[7:].lower().strip()
            else:
                # Fallback to entity_name only if no entity_key
                entity_key = (rej.get("entity_name", "") or raw_entity_key).lower().strip()
            
            if not entity_key or entity_key in admission_actual:
                continue
            
            reasons = _compute_rejection_reasons(rej)
            
            # REJECTED assets should NOT be classified as shadows
            # Rejected assets failed admission criteria - they're not in the asset catalog
            # Farm expects "not-admitted" assets to not appear as shadows
            # Only ADMITTED assets can be shadows/zombies/parked
            evidence = rej.get("evidence_summary", {})
            
            admission_actual[entity_key] = "rejected"
            actual_reasons[entity_key] = reasons
            
            # Build alias_keys for rejected assets too
            # Extract domain variants from evidence to enable Farm lookup
            rej_alias_keys = set()
            # Check for domains in evidence (clone to avoid mutation)
            evidence_domains = evidence.get("domains")
            if evidence_domains and isinstance(evidence_domains, (list, set)):
                for d in evidence_domains:
                    if d and isinstance(d, str):
                        rej_alias_keys.add(d.lower().strip())
            evidence_identifiers = evidence.get("identifiers", {})
            if isinstance(evidence_identifiers, dict):
                id_domains = evidence_identifiers.get("domains")
                if id_domains and isinstance(id_domains, (list, set)):
                    for d in id_domains:
                        if d and isinstance(d, str):
                            rej_alias_keys.add(d.lower().strip())
            if evidence.get("domain") and isinstance(evidence.get("domain"), str):
                rej_alias_keys.add(evidence["domain"].lower().strip())
            if evidence.get("registered_domain") and isinstance(evidence.get("registered_domain"), str):
                rej_alias_keys.add(evidence["registered_domain"].lower().strip())
            # Check rejection record for domain info
            if rej.get("registered_domain") and isinstance(rej.get("registered_domain"), str):
                rej_alias_keys.add(rej["registered_domain"].lower().strip())
            if rej.get("domain") and isinstance(rej.get("domain"), str):
                rej_alias_keys.add(rej["domain"].lower().strip())
            # Filter out empty/invalid entries and remove the entity_key itself
            rej_alias_keys.discard("")
            rej_alias_keys.discard(entity_key)
            alias_keys_list = sorted(rej_alias_keys)
            
            # Clone evidence to avoid mutating shared state
            evidence_copy = {
                "rejection_reason": rej.get("reason_code", "unknown"),
                "rejection_detail": rej.get("reason_detail", ""),
                "original_evidence": dict(evidence) if evidence else {},
                "alias_keys": alias_keys_list
            }
            
            asset_details[entity_key] = {
                "asset_id": None,
                "name": rej.get("entity_name", entity_key),
                "is_shadow": False,  # Rejected assets cannot be shadows
                "is_zombie": False,
                "is_parked": False,
                "alias_keys": alias_keys_list,
                "evidence_summary": evidence_copy
            }
    
    shadow_actual = sorted(set(shadow_actual))
    zombie_actual = sorted(set(zombie_actual))
    parked_actual = sorted(set(parked_actual))
    
    # ========== INVARIANT METRICS & DOMAIN UNIQUENESS ASSERTION ==========
    # Stage 0: Track key pipeline health metrics per run
    logger = logging.getLogger("aod.reconcile")
    
    # Collect all registered domains from emitted assets (asset_results)
    all_registered_domains: list[str] = []
    for key, agg in asset_results.items():
        reg_domain = agg.get("registered_domain")
        if reg_domain:
            all_registered_domains.append(reg_domain)
    
    # Count domain occurrences to find duplicates
    domain_counts = Counter(all_registered_domains)
    unique_registered_domains = len(domain_counts)
    duplicate_domains = {d: c for d, c in domain_counts.items() if c > 1}
    domain_duplicates_count = len(duplicate_domains)
    
    # Counts for metrics
    assets_emitted = len(asset_results)  # Unique asset keys
    admitted_count = len([v for v in admission_actual.values() if v == "admitted"])
    rejected_count = len([v for v in admission_actual.values() if v == "rejected"])
    shadows_count = len(set(shadow_actual))
    zombies_count = len(set(zombie_actual))
    
    # Log invariant metrics
    logger.info(
        f"[INVARIANT_METRICS] run_id={run_id} | "
        f"assets_emitted={assets_emitted} | "
        f"unique_registered_domains={unique_registered_domains} | "
        f"domain_duplicates={domain_duplicates_count} | "
        f"admitted={admitted_count} | rejected={rejected_count} | "
        f"shadows={shadows_count} | zombies={zombies_count}"
    )
    
    # Hard assertion (warn-only for now): No registered domain in more than one asset
    if duplicate_domains:
        logger.warning(
            f"[DOMAIN_UNIQUENESS_VIOLATION] {len(duplicate_domains)} registered domains appear in >1 asset: "
            f"{list(duplicate_domains.items())[:10]}{'...' if len(duplicate_domains) > 10 else ''}"
        )
    # ========== END INVARIANT METRICS ==========
    
    summary = {
        "total_assets": len(assets),
        "total_candidates": len(assets) + (len(rejections) if rejections else 0),
        "asset_keys": len(asset_results),
        "shadow_actual_count": len(shadow_actual),
        "zombie_actual_count": len(zombie_actual),
        "parked_actual_count": len(parked_actual),
        "admitted_count": admitted_count,
        "rejected_count": rejected_count,
        # Invariant metrics (Stage 0)
        "unique_registered_domains": unique_registered_domains,
        "domain_duplicates_count": domain_duplicates_count,
        "duplicate_domains": list(duplicate_domains.keys()) if duplicate_domains else []
    }
    
    return ActualResultsOutput(
        run_id=run_id,
        shadow_actual=shadow_actual,
        zombie_actual=zombie_actual,
        parked_actual=parked_actual,
        admission_actual=admission_actual,
        actual_reasons=actual_reasons,
        asset_details=asset_details,
        summary=summary
    )
