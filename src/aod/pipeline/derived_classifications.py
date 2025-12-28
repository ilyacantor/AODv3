"""
Derived Classifications Module

Computes Shadow, Zombie, and Parked classifications from evidence AFTER the main pipeline.
These are computed on-read, not stored as flags.

GOVERNANCE POLICY (Dec 2025):
The Governance Trinity defines "governed":
  - Visibility: Registered in CMDB
  - Validation: Present in IdP (sanctioned/SSO)
  - Control: Managed lifecycle tied to owner

Finance presence does NOT equal governance. An organization can pay for
unsanctioned tools. There is no "Grey IT" - binary classification only.

Activity Status (ActivityStatus enum):
  - RECENT = has activity timestamp within activity_window_days (default 90)
  - STALE = has activity timestamp outside activity_window_days
  - NONE = no activity timestamps at all (indeterminate)

Anchored Predicate (for zombie classification):
  - anchored = has_idp OR has_cmdb OR has_finance OR has_cloud
  - Used to determine zombie eligibility - only anchored assets can be zombies

Shadow Asset = admitted asset with:
  - ungoverned (NOT has_idp AND NOT has_cmdb)
  - AND activity_status == RECENT
  - Interpretation: Active ungoverned SaaS that needs to be sanctioned or banned
  - NOTE: Finance does NOT exempt from shadow - pay doesn't equal governance

Zombie Asset = admitted asset with:
  - anchored (has_idp OR has_cmdb OR has_finance OR has_cloud)
  - AND activity_status == STALE (NOT NONE - "no evidence" ≠ "stale evidence")
  - Interpretation: Governed/tracked asset with stale activity that may need deprovisioning

Parked Asset = admitted asset with:
  - NOT anchored (ungoverned AND no finance AND no cloud)
  - AND activity_status == STALE
  - Interpretation: Non-actionable - can't deprovision what isn't managed
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional
from enum import Enum
import re
from ..models.output_contracts import Asset, LensStatus, ProvisioningStatus
from .vendor_inference import DOMAIN_TO_VENDOR, VENDOR_TO_DOMAIN
from ..utils.normalization import normalize_name_for_vendor_lookup as _normalize_name_for_vendor_lookup
from .cache import get_domain_rollups_cache


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


class ActivityStatus(str, Enum):
    """
    Activity status for an asset based on timestamp evidence.
    
    RECENT = has activity timestamp within activity_window_days (active)
    STALE = has activity timestamp outside activity_window_days (inactive)
    NONE = no activity timestamps at all (indeterminate - we don't know)
    
    Key distinction: NONE means "no evidence" which is different from STALE ("evidence of staleness").
    This matters for zombie classification - we only classify as zombie when we KNOW it's stale.
    """
    RECENT = "recent"
    STALE = "stale"
    NONE = "none"


def get_activity_status(
    latest_activity_at: Optional[datetime],
    activity_window_days: int = 90,
    snapshot_as_of: Optional[datetime] = None
) -> ActivityStatus:
    """
    Determine the activity status based on the latest activity timestamp.
    
    Args:
        latest_activity_at: The latest activity timestamp (may be None)
        activity_window_days: Number of days for the activity window (default 90)
        snapshot_as_of: Reference time for recency calculation (default: wall-clock now).
                       When processing historical snapshots, use the snapshot's generated_at
                       to avoid falsely marking active assets as stale.
    
    Returns:
        ActivityStatus.RECENT if activity is within window
        ActivityStatus.STALE if activity is outside window
        ActivityStatus.NONE if no activity timestamp exists
    """
    if latest_activity_at is None:
        return ActivityStatus.NONE
    
    latest = _ensure_utc_aware(latest_activity_at)
    if latest is None:
        return ActivityStatus.NONE
    
    reference_time = _ensure_utc_aware(snapshot_as_of) if snapshot_as_of else _utc_now()
    cutoff = reference_time - timedelta(days=activity_window_days)
    
    if latest >= cutoff:
        return ActivityStatus.RECENT
    else:
        return ActivityStatus.STALE


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
class DomainRollup:
    """Aggregated governance signals for a domain (OR logic across entities)"""
    domain_key: str
    has_idp: bool
    has_cmdb: bool
    has_finance: bool
    has_cloud: bool
    has_discovery: bool
    latest_activity_at: Optional[datetime]
    entity_names: list[str]
    entity_count: int
    is_domain_canonical: bool = True
    alias_keys: list[str] = field(default_factory=list)
    
    def get_activity_status(self, activity_window_days: int = 90, snapshot_as_of: Optional[datetime] = None) -> ActivityStatus:
        """Get the activity status for this domain rollup."""
        return get_activity_status(self.latest_activity_at, activity_window_days, snapshot_as_of)
    
    def is_anchored(self) -> bool:
        """
        Anchored predicate: asset is tracked/governed in at least one system.
        
        anchored = has_idp OR has_cmdb OR has_finance OR has_cloud
        
        This is broader than just governance (IdP/CMDB) - it includes any
        evidence that the asset is being tracked in an authoritative system:
        - IdP = identity/SSO integration exists
        - CMDB = configuration management entry exists
        - Finance = recurring financial spend tracked
        - Cloud = cloud resource present (AWS/Azure/GCP etc)
        
        Used to determine zombie eligibility - only anchored assets can be zombies
        because you can only deprovision what's tracked somewhere.
        """
        return self.has_idp or self.has_cmdb or self.has_finance or self.has_cloud
    
    def is_shadow(self, activity_window_days: int = 90, snapshot_as_of: Optional[datetime] = None) -> bool:
        """
        Domain-level shadow: ungoverned AND activity_status==RECENT.
        
        Shadow = NOT has_idp AND NOT has_cmdb AND activity_status==RECENT
        
        INVARIANT: Only domain-canonical assets count as shadow.
        Internal identifiers (name-derived keys) are excluded from shadow counts.
        
        INVARIANT: activity_status must be RECENT. NONE (no timestamps) is indeterminate.
        """
        if not self.is_domain_canonical:
            return False
        
        has_governance = self.has_idp or self.has_cmdb
        has_existence = self.has_cloud or self.has_discovery
        
        if has_governance or not has_existence:
            return False
        
        activity_status = self.get_activity_status(activity_window_days, snapshot_as_of)
        return activity_status == ActivityStatus.RECENT
    
    def is_zombie(self, activity_window_days: int = 90, snapshot_as_of: Optional[datetime] = None) -> bool:
        """
        Domain-level zombie: anchored AND activity_status==STALE.
        
        Zombie = (has_idp OR has_cmdb OR has_finance OR has_cloud) AND activity_status==STALE
        
        INVARIANT: Only domain-canonical assets count as zombie.
        Internal identifiers (name-derived keys) are excluded from zombie counts.
        
        INVARIANT: activity_status must be STALE (proven stale). NONE (no timestamps)
        is indeterminate and does NOT count as zombie per design principle:
        "no evidence" ≠ "stale evidence"
        """
        if not self.is_domain_canonical:
            return False
        
        if not self.is_anchored():
            return False
        
        activity_status = self.get_activity_status(activity_window_days, snapshot_as_of)
        return activity_status == ActivityStatus.STALE
    
    def is_parked(self, activity_window_days: int = 90, snapshot_as_of: Optional[datetime] = None) -> bool:
        """
        Domain-level parked: NOT anchored AND activity_status==STALE.
        
        Parked = NOT is_anchored() AND activity_status==STALE
        
        Parked assets are non-actionable - they have stale activity but no governance
        or tracking, so there's nothing to deprovision. These are explicitly excluded
        from zombie counts.
        
        INVARIANT: Only domain-canonical assets count as parked.
        Internal identifiers (name-derived keys) are excluded.
        
        INVARIANT: activity_status must be STALE (proven stale). NONE (no timestamps)
        is indeterminate and does NOT count as parked.
        """
        if not self.is_domain_canonical:
            return False
        
        if self.is_anchored():
            return False
        
        activity_status = self.get_activity_status(activity_window_days, snapshot_as_of)
        return activity_status == ActivityStatus.STALE
    
    def get_reason_codes(self) -> list[str]:
        """Generate canonical reason codes for this domain"""
        codes = []
        codes.append("HAS_IDP" if self.has_idp else "NO_IDP")
        codes.append("HAS_CMDB" if self.has_cmdb else "NO_CMDB")
        codes.append("HAS_FINANCE" if self.has_finance else "NO_FINANCE")
        codes.append("HAS_CLOUD" if self.has_cloud else "NO_CLOUD")
        codes.append("HAS_DISCOVERY" if self.has_discovery else "NO_DISCOVERY")
        
        activity_status = self.get_activity_status()
        if activity_status == ActivityStatus.RECENT:
            codes.append("RECENT_ACTIVITY")
        elif activity_status == ActivityStatus.STALE:
            codes.append("STALE_ACTIVITY")
        else:
            codes.append("NO_ACTIVITY_TIMESTAMPS")
        
        if self.is_anchored():
            codes.append("ANCHORED")
        else:
            codes.append("NOT_ANCHORED")
        
        if self.is_shadow():
            codes.append("SHADOW_CLASSIFICATION")
        elif self.is_zombie():
            codes.append("ZOMBIE_CLASSIFICATION")
        elif self.is_parked():
            codes.append("PARKED_CLASSIFICATION")
        
        return codes


@dataclass
class DerivedClassificationSummary:
    """Summary of derived classifications for a run"""
    shadow_count: int
    zombie_count: int
    parked_count: int
    indeterminate_count: int
    shadow_assets: list[dict]
    zombie_assets: list[dict]
    parked_assets: list[dict]
    distribution: DistributionDiagnostic = field(default_factory=DistributionDiagnostic)
    domain_rollups: dict[str, DomainRollup] = field(default_factory=dict)


def classify_shadow(asset: Asset, activity_window_days: int = 90) -> ClassificationResult:
    """
    Determine if an asset is a Shadow Asset.
    
    POLICY (Dec 2025): Uses Traffic Light provisioning_status as primary source of truth.
    - QUARANTINE → Shadow Block (Tier 1 triage item)
    - ACTIVE/REVIEW/BLOCKED/RETIRED → Not shadow
    
    Interpretation: "Shadow IT blocked from DCL, needs user approval to sanction."
    
    Args:
        asset: The asset to classify
        activity_window_days: Number of days to consider for recent activity (default 90)
    """
    if asset.llm_metadata and asset.llm_metadata.exclusion_reason == "asset_type_infra_tech":
        return ClassificationResult(
            is_classified=False,
            is_indeterminate=False,
            classification_type="shadow",
            reason="Asset excluded: LLM classified as INFRA_TECH (infrastructure technology)",
            evidence_summary=[f"LLM confidence: {asset.llm_metadata.llm_confidence}", f"Reason: {asset.llm_metadata.llm_reason}"]
        )
    
    if asset.provisioning_status == ProvisioningStatus.QUARANTINE:
        has_cloud = asset.lens_coverage.cloud if asset.lens_coverage else False
        has_discovery = asset.lens_coverage.discovery if asset.lens_coverage else False
        has_finance = asset.lens_coverage.finance if asset.lens_coverage else False
        
        presence_sources = []
        if has_cloud:
            presence_sources.append("cloud infrastructure")
        if has_discovery:
            presence_sources.append("discovery")
        if has_finance:
            presence_sources.append("finance")
        
        return ClassificationResult(
            is_classified=True,
            is_indeterminate=False,
            classification_type="shadow",
            reason=f"Shadow Block: Asset quarantined - no IdP/CMDB governance, blocked from DCL",
            evidence_summary=[
                f"Status: QUARANTINE (Shadow IT)",
                f"Presence: {', '.join(presence_sources) if presence_sources else 'discovery-only'}",
                "Action required: SANCTION to approve, or BAN to reject"
            ]
        )
    
    if asset.provisioning_status != ProvisioningStatus.QUARANTINE:
        return ClassificationResult(
            is_classified=False,
            is_indeterminate=False,
            classification_type="shadow",
            reason=f"Asset status is {asset.provisioning_status.value} - not shadow",
            evidence_summary=[f"Provisioning status: {asset.provisioning_status.value}"]
        )
    
    has_idp = asset.lens_status.idp in (LensStatus.MATCHED, LensStatus.AMBIGUOUS)
    has_cmdb = asset.lens_status.cmdb in (LensStatus.MATCHED, LensStatus.AMBIGUOUS)
    
    has_cloud = asset.lens_coverage.cloud
    has_discovery = asset.lens_coverage.discovery
    
    if has_idp or has_cmdb:
        return ClassificationResult(
            is_classified=False,
            is_indeterminate=False,
            classification_type="shadow",
            reason="Asset has IdP or CMDB presence - not shadow",
            evidence_summary=[]
        )
    
    presence_sources = []
    if has_cloud:
        presence_sources.append("cloud infrastructure")
    if has_discovery:
        presence_sources.append("discovery (corroborated usage)")
    
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


def compute_zombie_status(asset: Asset, window_days: int = 90) -> tuple[bool, bool, str]:
    """
    Shared zombie status computation used by BOTH KPI counts and debug explainer.
    
    NEW LOGIC (Dec 2025):
    Zombie = anchored AND activity_status==STALE
    
    Where:
    - anchored = has_idp OR has_cmdb OR has_finance OR has_cloud
    - activity_status==STALE means we have timestamps outside the window
    - NO_ACTIVITY_TIMESTAMPS does NOT count as zombie (indeterminate, not proven stale)
    
    This is a key semantic change: "no evidence" ≠ "stale evidence"
    
    Args:
        asset: The asset to check
        window_days: Activity window in days (default 90)
        
    Returns:
        Tuple of (is_zombie, is_indeterminate, reason)
    """
    has_idp = asset.lens_status.idp in (LensStatus.MATCHED, LensStatus.AMBIGUOUS)
    has_cmdb = asset.lens_status.cmdb in (LensStatus.MATCHED, LensStatus.AMBIGUOUS)
    has_finance = asset.lens_coverage.finance
    has_cloud = asset.lens_coverage.cloud
    
    is_anchored = has_idp or has_cmdb or has_finance or has_cloud
    
    if not is_anchored:
        return False, False, "Not anchored (no IdP, CMDB, Finance, or Cloud) - cannot be zombie"
    
    anchored_sources = []
    if has_idp:
        anchored_sources.append("IdP")
    if has_cmdb:
        anchored_sources.append("CMDB")
    if has_finance:
        anchored_sources.append("Finance")
    if has_cloud:
        anchored_sources.append("Cloud")
    
    latest = _ensure_utc_aware(asset.activity_evidence.latest_activity_at)
    activity_status = get_activity_status(latest, window_days)
    
    if activity_status == ActivityStatus.NONE:
        return False, True, f"Indeterminate: Anchored in {', '.join(anchored_sources)} but no activity timestamps (cannot prove stale)"
    
    if activity_status == ActivityStatus.STALE:
        return True, False, f"Zombie: Anchored in {', '.join(anchored_sources)} with stale activity ({latest.isoformat() if latest else 'unknown'})"
    
    return False, False, f"Not zombie: Recent activity at {latest.isoformat() if latest else 'unknown'}"


def classify_zombie(asset: Asset, activity_window_days: int = 90) -> ClassificationResult:
    """
    Determine if an asset is a Zombie Asset.
    
    POLICY (Dec 2025): Uses Traffic Light provisioning_status as primary source of truth.
    - REVIEW → Zombie Review (Tier 2 triage item)
    - ACTIVE/QUARANTINE/BLOCKED/RETIRED → Not zombie
    
    Interpretation: "Zombie candidate needs cleanup - has governance but stale activity."
    
    Args:
        asset: The asset to classify
        activity_window_days: Number of days to consider for recent activity (default 90)
    """
    if asset.llm_metadata and asset.llm_metadata.exclusion_reason == "asset_type_infra_tech":
        return ClassificationResult(
            is_classified=False,
            is_indeterminate=False,
            classification_type="zombie",
            reason="Asset excluded: LLM classified as INFRA_TECH (infrastructure technology)",
            evidence_summary=[f"LLM confidence: {asset.llm_metadata.llm_confidence}", f"Reason: {asset.llm_metadata.llm_reason}"]
        )
    
    if asset.provisioning_status == ProvisioningStatus.REVIEW:
        has_idp = asset.lens_status.idp in (LensStatus.MATCHED, LensStatus.AMBIGUOUS)
        has_cmdb = asset.lens_status.cmdb in (LensStatus.MATCHED, LensStatus.AMBIGUOUS)
        
        official_sources = []
        if has_idp:
            official_sources.append("IdP")
        if has_cmdb:
            official_sources.append("CMDB")
        
        latest_activity = _ensure_utc_aware(asset.activity_evidence.latest_activity_at)
        activity_info = f"Last activity: {latest_activity.isoformat()}" if latest_activity else "No activity timestamps"
        
        return ClassificationResult(
            is_classified=True,
            is_indeterminate=False,
            classification_type="zombie",
            reason=f"Zombie Review: Asset flagged for cleanup - in {', '.join(official_sources) if official_sources else 'governance'} but stale activity",
            evidence_summary=[
                f"Status: REVIEW (Zombie candidate)",
                f"Official presence: {', '.join(official_sources) if official_sources else 'CMDB'}",
                activity_info,
                "Action required: DEPROVISION to retire, or update activity evidence"
            ]
        )
    
    if asset.provisioning_status != ProvisioningStatus.REVIEW:
        return ClassificationResult(
            is_classified=False,
            is_indeterminate=False,
            classification_type="zombie",
            reason=f"Asset status is {asset.provisioning_status.value} - not zombie",
            evidence_summary=[f"Provisioning status: {asset.provisioning_status.value}"]
        )
    
    has_idp = asset.lens_status.idp in (LensStatus.MATCHED, LensStatus.AMBIGUOUS)
    has_cmdb = asset.lens_status.cmdb in (LensStatus.MATCHED, LensStatus.AMBIGUOUS)
    
    if not (has_idp or has_cmdb):
        return ClassificationResult(
            is_classified=False,
            is_indeterminate=False,
            classification_type="zombie",
            reason="Asset not in CMDB or IdP - cannot be zombie",
            evidence_summary=[]
        )
    
    official_presence = []
    if has_idp:
        official_presence.append("IdP/identity systems")
    if has_cmdb:
        official_presence.append("CMDB")
    
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


def compute_derived_classifications(
    assets: list[Asset],
    activity_window_days: int = 90,
    run_id: Optional[str] = None,
    snapshot_as_of: Optional[datetime] = None
) -> DerivedClassificationSummary:
    """
    Compute derived classifications for all assets.

    Returns summary with counts and detailed lists.

    IMPORTANT: Both counts AND drilldown lists use DOMAIN-AGGREGATED assets.
    This ensures KPI count (16) matches drilldown count (16), not individual
    asset count (49). Multiple assets sharing the same domain are merged.

    Note: vendor_hypothesis is included in output dicts for UI DISPLAY ONLY.
    It is NOT used in classification logic.
    Inference decorates reality; it does not redefine it.

    Args:
        assets: List of assets to classify
        activity_window_days: Number of days to consider for recent activity (default 90)
        run_id: Optional run ID for caching (recommended for API routes)
        snapshot_as_of: Reference time for recency calculation (default: wall-clock now).
                       When processing historical snapshots, use the snapshot's generated_at
                       to avoid falsely marking active assets as stale.
    """
    reference_time = _ensure_utc_aware(snapshot_as_of) if snapshot_as_of else _utc_now()
    cutoff_date = reference_time - timedelta(days=activity_window_days)
    distribution = DistributionDiagnostic(total_assets=len(assets))
    
    domain_to_assets: dict[str, list[Asset]] = {}
    
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
        
        domain_key, _, _ = _resolve_domain_key(asset)
        if domain_key not in domain_to_assets:
            domain_to_assets[domain_key] = []
        domain_to_assets[domain_key].append(asset)

    domain_rollups = compute_domain_rollups(assets, activity_window_days, run_id=run_id)
    
    shadow_assets = []
    zombie_assets = []
    parked_assets = []
    indeterminate_count = 0
    
    for domain_key in sorted(domain_rollups.keys()):
        rollup = domain_rollups[domain_key]
        domain_assets = domain_to_assets.get(domain_key, [])
        if not domain_assets:
            continue
        
        representative = domain_assets[0]
        
        vendor_hyp = None
        for a in domain_assets:
            if a.vendor_hypothesis:
                vendor_hyp = {
                    "value": a.vendor_hypothesis.value,
                    "confidence": a.vendor_hypothesis.confidence,
                    "basis": a.vendor_hypothesis.basis
                }
                break
        
        all_domains = set()
        all_hostnames = set()
        all_uris = set()
        for a in domain_assets:
            if a.identifiers:
                all_domains.update(a.identifiers.domains)
                all_hostnames.update(a.identifiers.hostnames)
                all_uris.update(a.identifiers.uris)
        
        activity_status = rollup.get_activity_status(activity_window_days, snapshot_as_of)
        
        base_entry = {
            "asset_id": str(representative.asset_id),
            "name": domain_key if rollup.is_domain_canonical else representative.name,
            "vendor": representative.vendor,
            "vendor_hypothesis": vendor_hyp,
            "asset_type": representative.asset_type.value,
            "environment": representative.environment.value,
            "identifiers": {
                "domains": sorted(all_domains),
                "hostnames": sorted(all_hostnames),
                "uris": sorted(all_uris)
            },
            "lens_status": {
                "idp": representative.lens_status.idp.value,
                "cmdb": representative.lens_status.cmdb.value,
                "cloud": representative.lens_status.cloud.value,
                "finance": representative.lens_status.finance.value
            },
            "lens_coverage": {
                "idp": representative.lens_coverage.idp,
                "cmdb": representative.lens_coverage.cmdb,
                "cloud": representative.lens_coverage.cloud,
                "finance": representative.lens_coverage.finance,
                "discovery": representative.lens_coverage.discovery
            },
            "activity_evidence": {
                "latest_activity_at": rollup.latest_activity_at.isoformat() if rollup.latest_activity_at else None,
                "activity_status": activity_status.value
            },
            "entity_count": rollup.entity_count,
            "aliases": rollup.entity_names if rollup.entity_count > 1 else [],
            "aggregated_evidence": {
                "has_idp": rollup.has_idp,
                "has_cmdb": rollup.has_cmdb,
                "has_finance": rollup.has_finance,
                "has_cloud": rollup.has_cloud,
                "has_discovery": rollup.has_discovery,
                "is_anchored": rollup.is_anchored()
            }
        }
        
        if rollup.is_shadow(activity_window_days, snapshot_as_of):
            shadow_assets.append({
                **base_entry,
                "classification": "shadow",
                "reason": f"Shadow IT: {domain_key} found via evidence but missing from official systems",
                "evidence_summary": [
                    f"Presence: {', '.join(filter(None, ['finance' if rollup.has_finance else None, 'cloud' if rollup.has_cloud else None, 'discovery' if rollup.has_discovery else None]))}",
                    "Gaps: No IdP match; No CMDB match",
                    f"Last activity: {rollup.latest_activity_at.isoformat() if rollup.latest_activity_at else 'unknown'}",
                    f"Activity status: {activity_status.value}"
                ]
            })
        elif rollup.is_zombie(activity_window_days, snapshot_as_of):
            anchored_sources = filter(None, [
                'IdP' if rollup.has_idp else None, 
                'CMDB' if rollup.has_cmdb else None,
                'Finance' if rollup.has_finance else None,
                'Cloud' if rollup.has_cloud else None
            ])
            zombie_assets.append({
                **base_entry,
                "classification": "zombie",
                "reason": f"Zombie: {domain_key} anchored in systems but has stale activity",
                "evidence_summary": [
                    f"Anchored in: {', '.join(anchored_sources)}",
                    f"Last activity: {rollup.latest_activity_at.isoformat() if rollup.latest_activity_at else 'unknown'}",
                    f"Activity status: {activity_status.value}"
                ]
            })
        elif rollup.is_parked(activity_window_days, snapshot_as_of):
            parked_assets.append({
                **base_entry,
                "classification": "parked",
                "reason": f"Parked: {domain_key} not anchored in any system and has stale activity - non-actionable",
                "evidence_summary": [
                    "Not anchored: No IdP, CMDB, Finance, or Cloud presence",
                    f"Last activity: {rollup.latest_activity_at.isoformat() if rollup.latest_activity_at else 'unknown'}",
                    f"Activity status: {activity_status.value}",
                    "Non-actionable: Cannot deprovision what isn't managed"
                ]
            })
        elif not rollup.is_domain_canonical:
            indeterminate_count += 1
    
    distribution.indeterminate_count = indeterminate_count
    
    return DerivedClassificationSummary(
        shadow_count=len(shadow_assets),
        zombie_count=len(zombie_assets),
        parked_count=len(parked_assets),
        indeterminate_count=indeterminate_count,
        shadow_assets=shadow_assets,
        zombie_assets=zombie_assets,
        parked_assets=parked_assets,
        distribution=distribution,
        domain_rollups=domain_rollups
    )


def _resolve_domain_key(asset: Asset) -> tuple[str, bool, list[str]]:
    """
    Resolve the canonical domain key for an asset.
    
    Returns:
        Tuple of (domain_key, is_canonical, alias_keys) where:
        - domain_key: The canonical registered domain (e.g., asana.com)
        - is_canonical: True if key is a registered domain, False if name-derived
        - alias_keys: List of original domains/subdomains that map to this canonical key
    
    Priority order (DOMAIN PROMOTION):
    1. asset.identifiers.domains (explicit domain from evidence) -> extract registered domain
    2. VENDOR_TO_DOMAIN[asset.vendor] (reverse lookup from vendor name) -> canonical
    3. NAME-BASED PROMOTION: Normalize name and look up in VENDOR_TO_DOMAIN -> canonical
    4. Asset name if it looks like a domain -> extract registered domain
    5. Fallback: normalized name -> NOT canonical
    
    INVARIANT: This must match the key resolution in aod_agent_reconcile.py
    to ensure UI counts match reconciliation counts.
    
    INVARIANT: If raw domain != registered domain, both are preserved in alias_keys.
    """
    from .vendor_inference import extract_registered_domain
    
    alias_keys = []
    
    if asset.identifiers and asset.identifiers.domains:
        for domain in asset.identifiers.domains:
            if domain and "." in domain:
                raw_domain = domain.lower().strip()
                alias_keys.append(raw_domain)
                registered = extract_registered_domain(raw_domain)
                if registered and registered != raw_domain:
                    alias_keys.append(registered)
                    return (registered, True, alias_keys)
                return (raw_domain, True, alias_keys)
    
    if asset.vendor and asset.vendor.lower() not in ("unknown", "", "none"):
        vendor_key = asset.vendor.lower().strip()
        if vendor_key in VENDOR_TO_DOMAIN:
            canonical = VENDOR_TO_DOMAIN[vendor_key]
            return (canonical, True, [canonical])
    
    normalized_name = _normalize_name_for_vendor_lookup(asset.name)
    if normalized_name in VENDOR_TO_DOMAIN:
        canonical = VENDOR_TO_DOMAIN[normalized_name]
        return (canonical, True, [canonical])
    
    name = asset.name.lower().strip()
    if "." in name:
        parts = name.split(".")
        if len(parts) >= 2 and len(parts[-1]) in (2, 3, 4) and parts[-1].isalpha():
            alias_keys.append(name)
            registered = extract_registered_domain(name)
            if registered and registered != name:
                alias_keys.append(registered)
                return (registered, True, alias_keys)
            return (name, True, alias_keys)
    
    return (re.sub(r'[^a-z0-9]', '', name.lower()), False, [])


def _get_parent_domain(domain: str) -> Optional[str]:
    """
    Extract parent domain from a subdomain.
    e.g., mail.google.com -> google.com
    Returns None if already a root domain or invalid.
    """
    from .domain_cache import extract_domain
    extracted = extract_domain(domain)
    if not extracted.suffix:
        return None
    registered_domain = f"{extracted.domain}.{extracted.suffix}"
    if domain.lower() == registered_domain.lower():
        return None
    return registered_domain


def compute_domain_rollups(
    assets: list[Asset],
    activity_window_days: int = 90,
    run_id: Optional[str] = None
) -> dict[str, DomainRollup]:
    """
    Compute domain-level rollups using OR logic across entities.

    For reconciliation, governance signals are aggregated at domain level:
    - has_idp = OR(all entities with this domain)
    - has_cmdb = OR(all entities with this domain)
    - etc.

    IMPORTANT: HAS_* means PRESENCE (evidence exists), not admission gate passed.
    - has_finance = True if finance correlation found evidence (MATCHED/AMBIGUOUS)
    - has_discovery = True if discovery observations exist (even if stale)

    This ensures that if ANY entity under a domain has evidence,
    the domain is considered to have that evidence for reconciliation purposes.

    ACTIVITY ROLLUP (Zombie Cure): Activity from subdomains is propagated to parent domains.
    e.g., activity on mail.google.com counts as activity for google.com

    INVARIANT: Domain key resolution matches aod_agent_reconcile.py to ensure
    UI counts match reconciliation counts (eliminating IRL breach).

    Args:
        assets: List of assets to aggregate
        activity_window_days: Activity window for zombie classification (default 90)
        run_id: Optional run ID for caching (recommended for API routes)

    Returns:
        Dictionary mapping domain keys to DomainRollup objects
    """
    # Check cache if run_id is provided
    cache = get_domain_rollups_cache()
    if run_id:
        cache_key = f"run:{run_id}:window:{activity_window_days}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    rollups: dict[str, DomainRollup] = {}
    
    for asset in assets:
        domain_key, is_canonical, alias_keys = _resolve_domain_key(asset)
        
        has_idp = asset.lens_status.idp in (LensStatus.MATCHED, LensStatus.AMBIGUOUS)
        has_cmdb = asset.lens_status.cmdb in (LensStatus.MATCHED, LensStatus.AMBIGUOUS)
        has_finance = asset.lens_status.finance in (LensStatus.MATCHED, LensStatus.AMBIGUOUS)
        has_cloud = asset.lens_status.cloud in (LensStatus.MATCHED, LensStatus.AMBIGUOUS)
        has_discovery = any(
            isinstance(ref, str) and ref.startswith("discovery:")
            for ref in asset.evidence_refs
        ) or asset.activity_evidence.discovery_observed_at is not None
        latest_activity = _ensure_utc_aware(asset.activity_evidence.latest_activity_at)
        
        if domain_key in rollups:
            r = rollups[domain_key]
            r.has_idp = r.has_idp or has_idp
            r.has_cmdb = r.has_cmdb or has_cmdb
            r.has_finance = r.has_finance or has_finance
            r.has_cloud = r.has_cloud or has_cloud
            r.has_discovery = r.has_discovery or has_discovery
            r.entity_names.append(asset.name)
            r.entity_count += 1
            for ak in alias_keys:
                if ak not in r.alias_keys:
                    r.alias_keys.append(ak)
            if latest_activity is not None:
                if r.latest_activity_at is None or latest_activity > r.latest_activity_at:
                    r.latest_activity_at = latest_activity
        else:
            rollups[domain_key] = DomainRollup(
                domain_key=domain_key,
                has_idp=has_idp,
                has_cmdb=has_cmdb,
                has_finance=has_finance,
                has_cloud=has_cloud,
                has_discovery=has_discovery,
                latest_activity_at=latest_activity,
                entity_names=[asset.name],
                entity_count=1,
                is_domain_canonical=is_canonical,
                alias_keys=list(alias_keys)
            )
    
    # ACTIVITY ROLLUP (Zombie Cure): Propagate activity from subdomains to parent domains
    # e.g., activity on mail.google.com should count as activity for google.com
    for domain_key, rollup in list(rollups.items()):
        parent_domain = _get_parent_domain(domain_key)
        if parent_domain and parent_domain in rollups:
            parent_rollup = rollups[parent_domain]
            # Propagate activity: if subdomain has more recent activity, use it for parent
            if rollup.latest_activity_at is not None:
                subdomain_activity = _ensure_utc_aware(rollup.latest_activity_at)
                parent_activity = _ensure_utc_aware(parent_rollup.latest_activity_at)
                if parent_activity is None or (subdomain_activity and subdomain_activity > parent_activity):
                    parent_rollup.latest_activity_at = subdomain_activity

    # Store in cache if run_id is provided
    if run_id:
        cache_key = f"run:{run_id}:window:{activity_window_days}"
        cache.set(cache_key, rollups)

    return rollups
