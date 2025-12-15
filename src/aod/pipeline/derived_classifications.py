"""
Derived Classifications Module

Computes Shadow and Zombie classifications from evidence AFTER the main pipeline.
These are computed on-read, not stored as flags.

Shadow Asset = admitted asset with:
  - finance evidence OR cloud presence OR discovery observations
  - AND no IdP match (no SSO / SCIM / service principal)
  - AND no CMDB match
  - AND has recent activity (within activity_window_days)

Zombie Asset = admitted asset with:
  - CMDB or IdP presence
  - AND no discovery observations or activity evidence (no cloud, no finance)
  - OR has no recent activity (outside activity_window_days)
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional
from ..models.output_contracts import Asset, LensStatus, ZombieClassification, ZombieClassificationResult


def _utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


def _ensure_utc_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalize a datetime to UTC-aware. Returns None if input is None."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class ClassificationResult:
    """Result of a derived classification check"""
    is_classified: bool
    is_indeterminate: bool
    classification_type: str
    reason: str
    evidence_summary: list[str]


@dataclass
class DistributionDiagnostic:
    """Diagnostic information about asset distribution"""
    total_assets: int = 0
    with_idp_match: int = 0
    with_cmdb_match: int = 0
    with_activity_last_30_days: int = 0
    with_any_activity_timestamp: int = 0
    indeterminate_count: int = 0


@dataclass
class DerivedClassificationSummary:
    """Summary of derived classifications for a run"""
    shadow_count: int
    zombie_count: int
    indeterminate_count: int
    shadow_assets: list[dict]
    zombie_assets: list[dict]
    distribution: DistributionDiagnostic = field(default_factory=DistributionDiagnostic)


def classify_shadow(asset: Asset, activity_window_days: int = 30) -> ClassificationResult:
    """
    Determine if an asset is a Shadow Asset.
    
    Shadow = has evidence of existence (finance, cloud, or discovery observations)
             but is NOT in identity systems and NOT in CMDB
             AND has recent activity within the activity window
    
    Interpretation: "We know this software is used, but it's not being
    managed through official channels."
    
    Uses lens_coverage (boolean flags indicating plane admission) to determine
    presence, not just evidence_refs.
    
    Args:
        asset: The asset to classify
        activity_window_days: Number of days to consider for recent activity (default 30)
    """
    has_idp = asset.lens_status.idp == LensStatus.MATCHED
    has_cmdb = asset.lens_status.cmdb == LensStatus.MATCHED
    
    has_finance = asset.lens_coverage.finance
    has_cloud = asset.lens_coverage.cloud
    
    has_discovery_observations = bool(asset.evidence_refs)
    
    if has_idp or has_cmdb:
        return ClassificationResult(
            is_classified=False,
            is_indeterminate=False,
            classification_type="shadow",
            reason="Asset has IdP or CMDB presence - not shadow",
            evidence_summary=[]
        )
    
    presence_sources = []
    if has_finance:
        presence_sources.append("finance evidence (spending/contracts)")
    if has_cloud:
        presence_sources.append("cloud infrastructure")
    if has_discovery_observations:
        presence_sources.append(f"discovery observations ({len(asset.evidence_refs)} refs)")
    
    if not presence_sources:
        return ClassificationResult(
            is_classified=False,
            is_indeterminate=True,
            classification_type="shadow",
            reason="No evidence of presence - cannot determine shadow status",
            evidence_summary=[]
        )
    
    latest_activity = _ensure_utc_aware(asset.activity_evidence.latest_activity_at)
    cutoff_date = _utc_now() - timedelta(days=activity_window_days)
    
    if latest_activity is None:
        return ClassificationResult(
            is_classified=False,
            is_indeterminate=True,
            classification_type="shadow",
            reason="No activity timestamps available - cannot determine shadow status",
            evidence_summary=[f"Presence: {', '.join(presence_sources)}", "Activity: No timestamps"]
        )
    
    if latest_activity < cutoff_date:
        return ClassificationResult(
            is_classified=False,
            is_indeterminate=False,
            classification_type="shadow",
            reason=f"Activity too old (last seen: {latest_activity.isoformat()}) - outside {activity_window_days} day window",
            evidence_summary=[f"Presence: {', '.join(presence_sources)}", f"Last activity: {latest_activity.isoformat()}"]
        )
    
    gaps = []
    gaps.append("No IdP match (not in SSO/SCIM/identity systems)")
    gaps.append("No CMDB match (not in configuration management)")
    
    return ClassificationResult(
        is_classified=True,
        is_indeterminate=False,
        classification_type="shadow",
        reason=f"Shadow IT: Found via {', '.join(presence_sources)} but missing from official systems",
        evidence_summary=[
            f"Presence: {', '.join(presence_sources)}",
            f"Gaps: {'; '.join(gaps)}",
            f"Last activity: {latest_activity.isoformat()}"
        ]
    )


def compute_zombie_status(asset: Asset, window_days: int) -> tuple[bool, bool, str]:
    """
    Shared zombie status computation used by BOTH KPI counts and debug explainer.
    
    Zombie = (exists in any system of record) AND (no timestamps within window)
    Systems of record: IdP, CMDB, Cloud, Finance
    If there are NO timestamps at all, that still counts as "no timestamps within window"
    
    Per Zombie Recognition Contract v1.0:
    - window_days is REQUIRED (no default)
    - Existence check includes all systems of record
    
    Args:
        asset: The asset to check
        window_days: Activity window in days - REQUIRED, no default
        
    Returns:
        Tuple of (is_zombie, is_indeterminate, reason)
    """
    from datetime import timedelta
    
    has_idp = asset.lens_status.idp == LensStatus.MATCHED
    has_cmdb = asset.lens_status.cmdb == LensStatus.MATCHED
    has_cloud = asset.lens_status.cloud == LensStatus.MATCHED
    has_finance = asset.lens_status.finance == LensStatus.MATCHED
    
    if not (has_idp or has_cmdb or has_cloud or has_finance):
        return False, False, "Not in any system of record (IdP, CMDB, Cloud, Finance) - cannot be zombie"
    
    official_sources = []
    if has_idp:
        official_sources.append("IdP")
    if has_cmdb:
        official_sources.append("CMDB")
    if has_cloud:
        official_sources.append("Cloud")
    if has_finance:
        official_sources.append("Finance")
    
    latest = _ensure_utc_aware(asset.activity_evidence.latest_activity_at)
    
    if latest is None:
        return True, False, f"Zombie: In {', '.join(official_sources)} with no activity timestamps"
    
    cutoff = _utc_now() - timedelta(days=window_days)
    
    if latest < cutoff:
        return True, False, f"Zombie: In {', '.join(official_sources)} with stale activity ({latest.isoformat()})"
    
    return False, False, f"Not zombie: Recent activity at {latest.isoformat()}"


def classify_zombie(asset: Asset, activity_window_days: int) -> ClassificationResult:
    """
    Determine if an asset is a Zombie Asset.
    
    Per Zombie Recognition Contract v1.0:
    Zombie = exists in any system of record (IdP, CMDB, Cloud, Finance)
             AND (has NO timestamped activity OR activity is outside the window)
    
    Interpretation: "This is in our official systems but we have no
    evidence anyone is actually using it."
    
    IMPORTANT: Activity is determined by timestamps, not evidence_refs.
    If no activity timestamps exist, the asset is classified as zombie
    (we cannot prove it's being used).
    
    Args:
        asset: The asset to classify
        activity_window_days: Number of days to consider for recent activity - REQUIRED
    """
    has_idp = asset.lens_status.idp == LensStatus.MATCHED
    has_cmdb = asset.lens_status.cmdb == LensStatus.MATCHED
    has_cloud = asset.lens_status.cloud == LensStatus.MATCHED
    has_finance = asset.lens_status.finance == LensStatus.MATCHED
    
    if not (has_idp or has_cmdb or has_cloud or has_finance):
        return ClassificationResult(
            is_classified=False,
            is_indeterminate=False,
            classification_type="zombie",
            reason="Asset not in any system of record (IdP, CMDB, Cloud, Finance) - cannot be zombie",
            evidence_summary=[]
        )
    
    official_presence = []
    if has_idp:
        official_presence.append("IdP/identity systems")
    if has_cmdb:
        official_presence.append("CMDB")
    if has_cloud:
        official_presence.append("Cloud")
    if has_finance:
        official_presence.append("Finance")
    
    latest_activity = _ensure_utc_aware(asset.activity_evidence.latest_activity_at)
    cutoff_date = _utc_now() - timedelta(days=activity_window_days)
    
    activity_sources = []
    if asset.activity_evidence.discovery_observed_at:
        activity_sources.append("discovery observations")
    if asset.activity_evidence.finance_last_transaction_at:
        activity_sources.append("finance activity")
    if asset.activity_evidence.cloud_observed_at:
        activity_sources.append("cloud activity")
    if asset.activity_evidence.idp_last_login_at:
        activity_sources.append("IdP login")
    if asset.activity_evidence.endpoint_last_seen_at:
        activity_sources.append("endpoint activity")
    if asset.activity_evidence.network_last_seen_at:
        activity_sources.append("network activity")
    
    if latest_activity is None:
        return ClassificationResult(
            is_classified=True,
            is_indeterminate=False,
            classification_type="zombie",
            reason=f"Zombie: Exists in {', '.join(official_presence)} but no activity timestamps to prove usage",
            evidence_summary=[
                f"Official presence: {', '.join(official_presence)}",
                "No timestamped activity evidence"
            ]
        )
    
    if latest_activity < cutoff_date:
        return ClassificationResult(
            is_classified=True,
            is_indeterminate=False,
            classification_type="zombie",
            reason=f"Zombie: Exists in {', '.join(official_presence)} with stale activity (last: {latest_activity.isoformat()}, outside {activity_window_days} day window)",
            evidence_summary=[
                f"Official presence: {', '.join(official_presence)}",
                f"Activity sources: {', '.join(activity_sources)}",
                f"Last activity: {latest_activity.isoformat()} (stale)"
            ]
        )
    
    return ClassificationResult(
        is_classified=False,
        is_indeterminate=False,
        classification_type="zombie",
        reason=f"Asset has recent activity: {', '.join(activity_sources)} (last: {latest_activity.isoformat()})",
        evidence_summary=[f"Last activity: {latest_activity.isoformat()}"]
    )


def compute_zombie_classification(
    asset: Asset,
    run_id: str,
    window_days: int
) -> ZombieClassificationResult:
    """
    Contract-compliant zombie classification per Zombie Recognition Contract v1.0.
    
    Zombie Definition (binary):
    1. Exists - Asset appears in ≥1 system of record (CMDB, Billing, IdP, Cloud inventory)
    2. No activity within window - No observed_at ≥ (now - window_days)
    3. Evidence exhaustiveness - All sources checked must be enumerated
    
    FORBIDDEN:
    - Anomaly scores, percentile cutoffs, "low usage" heuristics
    - Inferred last_seen, generated_at as activity
    - Confidence/probability outputs
    
    Args:
        asset: The asset to classify
        run_id: The run ID for this classification
        window_days: Activity window in days - REQUIRED, no default
        
    Returns:
        ZombieClassificationResult with contract-compliant output
    """
    evidence_checked: list[str] = ["IdP", "CMDB", "Cloud", "Billing", "AccessLogs"]
    existence_sources: list[str] = []
    
    has_idp = asset.lens_status.idp == LensStatus.MATCHED
    has_cmdb = asset.lens_status.cmdb == LensStatus.MATCHED
    has_cloud = asset.lens_status.cloud == LensStatus.MATCHED
    has_finance = asset.lens_status.finance == LensStatus.MATCHED
    
    if has_idp:
        existence_sources.append("IdP")
    if has_cmdb:
        existence_sources.append("CMDB")
    if has_cloud:
        existence_sources.append("Cloud")
    if has_finance:
        existence_sources.append("Billing")
    
    activity_timestamps: list[tuple[str, datetime]] = []
    
    if asset.activity_evidence.idp_last_login_at:
        ts = _ensure_utc_aware(asset.activity_evidence.idp_last_login_at)
        if ts:
            activity_timestamps.append(("IdP login", ts))
    
    if asset.activity_evidence.discovery_observed_at:
        ts = _ensure_utc_aware(asset.activity_evidence.discovery_observed_at)
        if ts:
            activity_timestamps.append(("AccessLogs", ts))
    
    if asset.activity_evidence.cloud_observed_at:
        ts = _ensure_utc_aware(asset.activity_evidence.cloud_observed_at)
        if ts:
            activity_timestamps.append(("Cloud", ts))
    
    if asset.activity_evidence.endpoint_last_seen_at:
        ts = _ensure_utc_aware(asset.activity_evidence.endpoint_last_seen_at)
        if ts:
            activity_timestamps.append(("AccessLogs", ts))
    
    if asset.activity_evidence.network_last_seen_at:
        ts = _ensure_utc_aware(asset.activity_evidence.network_last_seen_at)
        if ts:
            activity_timestamps.append(("AccessLogs", ts))
    
    if asset.activity_evidence.finance_last_transaction_at:
        ts = _ensure_utc_aware(asset.activity_evidence.finance_last_transaction_at)
        if ts:
            activity_timestamps.append(("Billing", ts))
    
    if not existence_sources:
        return ZombieClassificationResult(
            run_id=run_id,
            asset_id=str(asset.asset_id),
            classification=ZombieClassification.NOT_ZOMBIE,
            window_days=window_days,
            evidence_checked=evidence_checked,
            last_activity_observed_at=None,
            reason="Asset does not exist in any system of record (IdP, CMDB, Cloud, Finance)."
        )
    
    latest_activity: Optional[datetime] = None
    if activity_timestamps:
        latest_activity = max(ts for _, ts in activity_timestamps)
    
    cutoff = _utc_now() - timedelta(days=window_days)
    
    if latest_activity is None:
        return ZombieClassificationResult(
            run_id=run_id,
            asset_id=str(asset.asset_id),
            classification=ZombieClassification.ZOMBIE,
            window_days=window_days,
            evidence_checked=evidence_checked,
            last_activity_observed_at=None,
            reason=f"Asset exists in {', '.join(existence_sources)} but has no observed activity timestamps."
        )
    
    if latest_activity < cutoff:
        return ZombieClassificationResult(
            run_id=run_id,
            asset_id=str(asset.asset_id),
            classification=ZombieClassification.ZOMBIE,
            window_days=window_days,
            evidence_checked=evidence_checked,
            last_activity_observed_at=latest_activity,
            reason=f"Asset exists in {', '.join(existence_sources)} but last activity was {latest_activity.strftime('%Y-%m-%d')}, outside {window_days}-day window."
        )
    
    return ZombieClassificationResult(
        run_id=run_id,
        asset_id=str(asset.asset_id),
        classification=ZombieClassification.NOT_ZOMBIE,
        window_days=window_days,
        evidence_checked=evidence_checked,
        last_activity_observed_at=latest_activity,
        reason=f"Asset has activity within {window_days}-day window (last: {latest_activity.strftime('%Y-%m-%d')})."
    )


def compute_zombie_classifications(
    assets: list[Asset],
    run_id: str,
    window_days: int
) -> list[ZombieClassificationResult]:
    """
    Compute contract-compliant zombie classifications for all assets.
    
    Args:
        assets: List of assets to classify
        run_id: The run ID for this classification batch
        window_days: Activity window in days - REQUIRED, no default
        
    Returns:
        List of ZombieClassificationResult for each asset
    """
    return [
        compute_zombie_classification(asset, run_id, window_days)
        for asset in assets
    ]


def compute_derived_classifications(assets: list[Asset], activity_window_days: int = 30) -> DerivedClassificationSummary:
    """
    Compute derived classifications for all assets.
    
    Returns summary with counts and detailed lists.
    Indeterminate assets are counted but excluded from shadow/zombie lists.
    
    Args:
        assets: List of assets to classify
        activity_window_days: Number of days to consider for recent activity (default 30)
    """
    shadow_assets = []
    zombie_assets = []
    indeterminate_count = 0
    
    cutoff_date = _utc_now() - timedelta(days=activity_window_days)
    distribution = DistributionDiagnostic(total_assets=len(assets))
    
    for asset in assets:
        if asset.lens_status.idp == LensStatus.MATCHED:
            distribution.with_idp_match += 1
        if asset.lens_status.cmdb == LensStatus.MATCHED:
            distribution.with_cmdb_match += 1
        if asset.activity_evidence.latest_activity_at is not None:
            distribution.with_any_activity_timestamp += 1
            latest = _ensure_utc_aware(asset.activity_evidence.latest_activity_at)
            if latest is not None and latest > cutoff_date:
                distribution.with_activity_last_30_days += 1
        
        shadow_result = classify_shadow(asset, activity_window_days)
        zombie_result = classify_zombie(asset, activity_window_days)
        
        if shadow_result.is_indeterminate or zombie_result.is_indeterminate:
            indeterminate_count += 1
            continue
        
        if shadow_result.is_classified:
            shadow_assets.append({
                "asset_id": str(asset.asset_id),
                "name": asset.name,
                "vendor": asset.vendor,
                "asset_type": asset.asset_type.value,
                "environment": asset.environment.value,
                "classification": "shadow",
                "reason": shadow_result.reason,
                "evidence_summary": shadow_result.evidence_summary,
                "lens_status": {
                    "idp": asset.lens_status.idp.value,
                    "cmdb": asset.lens_status.cmdb.value,
                    "cloud": asset.lens_status.cloud.value,
                    "finance": asset.lens_status.finance.value
                },
                "lens_coverage": {
                    "idp": asset.lens_coverage.idp,
                    "cmdb": asset.lens_coverage.cmdb,
                    "cloud": asset.lens_coverage.cloud,
                    "finance": asset.lens_coverage.finance
                },
                "activity_evidence": {
                    "latest_activity_at": asset.activity_evidence.latest_activity_at.isoformat() if asset.activity_evidence.latest_activity_at else None
                }
            })
        elif zombie_result.is_classified:
            zombie_assets.append({
                "asset_id": str(asset.asset_id),
                "name": asset.name,
                "vendor": asset.vendor,
                "asset_type": asset.asset_type.value,
                "environment": asset.environment.value,
                "classification": "zombie",
                "reason": zombie_result.reason,
                "evidence_summary": zombie_result.evidence_summary,
                "lens_status": {
                    "idp": asset.lens_status.idp.value,
                    "cmdb": asset.lens_status.cmdb.value,
                    "cloud": asset.lens_status.cloud.value,
                    "finance": asset.lens_status.finance.value
                },
                "lens_coverage": {
                    "idp": asset.lens_coverage.idp,
                    "cmdb": asset.lens_coverage.cmdb,
                    "cloud": asset.lens_coverage.cloud,
                    "finance": asset.lens_coverage.finance
                },
                "activity_evidence": {
                    "latest_activity_at": asset.activity_evidence.latest_activity_at.isoformat() if asset.activity_evidence.latest_activity_at else None
                }
            })
    
    distribution.indeterminate_count = indeterminate_count
    
    return DerivedClassificationSummary(
        shadow_count=len(shadow_assets),
        zombie_count=len(zombie_assets),
        indeterminate_count=indeterminate_count,
        shadow_assets=shadow_assets,
        zombie_assets=zombie_assets,
        distribution=distribution
    )
