"""Zombie asset classification."""

from datetime import timedelta
from typing import Optional

from .enums import ActivityStatus
from .result_types import ClassificationResult
from .time_utils import ensure_utc_aware, utc_now, get_activity_status
from ...models.output_contracts import Asset, ProvisioningStatus
from ...core.policy import get_current_config


def compute_zombie_status(
    asset: Asset,
    window_days: int = 90
) -> tuple[bool, bool, str]:
    """
    Shared zombie status computation used by BOTH KPI counts and debug explainer.

    ALIGNED WITH POLICY ENGINE (Dec 2025, Stage 3 Jan 2026 update):
    Zombie = is_governed AND activity_status==STALE AND has_ongoing_finance

    Where:
    - is_governed = has_idp OR has_cmdb OR vendor_governed
    - activity_status==STALE means we have timestamps outside the window
    - has_ongoing_finance = recurring contracts/subscriptions
    - NO_ACTIVITY_TIMESTAMPS does NOT count as zombie (indeterminate)

    Args:
        asset: The asset to check
        window_days: Activity window in days (default 90)

    Returns:
        Tuple of (is_zombie, is_indeterminate, reason)
    """
    # Use lens_coverage for governance (gate-validated admission)
    has_idp = asset.lens_coverage.idp if asset.lens_coverage else False
    has_cmdb = asset.lens_coverage.cmdb if asset.lens_coverage else False
    has_vendor_governed = asset.lens_coverage.vendor_governed if asset.lens_coverage else False

    is_governed = has_idp or has_cmdb or has_vendor_governed

    if not is_governed:
        return False, False, "Not governed (no IdP, CMDB, or vendor propagation) - cannot be zombie"

    # Check for ongoing finance (recurring spend)
    has_ongoing_finance = any(
        isinstance(ref, str) and (
            ref.startswith("recurring_contract:") or
            ref.startswith("recurring_transaction:")
        )
        for ref in asset.evidence_refs
    )

    if not has_ongoing_finance:
        return False, False, "No ongoing finance - stale but not wasting money (not zombie)"

    governance_sources = []
    if has_idp:
        governance_sources.append("IdP")
    if has_cmdb:
        governance_sources.append("CMDB")

    latest = ensure_utc_aware(asset.activity_evidence.latest_activity_at)
    activity_status = get_activity_status(latest, window_days)

    if activity_status == ActivityStatus.NONE:
        return False, True, f"Indeterminate: Governed in {', '.join(governance_sources)} but no activity timestamps (cannot prove stale)"

    if activity_status == ActivityStatus.STALE:
        return True, False, f"Zombie: Governed in {', '.join(governance_sources)} with ongoing finance but stale activity ({latest.isoformat() if latest else 'unknown'})"

    return False, False, f"Not zombie: Recent activity at {latest.isoformat() if latest else 'unknown'}"


def classify_zombie(
    asset: Asset,
    activity_window_days: Optional[int] = None
) -> ClassificationResult:
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
    if activity_window_days is None:
        activity_window_days = get_current_config().activity_windows.default_activity_window_days

    # Check LLM exclusion
    if asset.llm_metadata and asset.llm_metadata.exclusion_reason == "asset_type_infra_tech":
        return ClassificationResult(
            is_classified=False,
            is_indeterminate=False,
            classification_type="zombie",
            reason="Asset excluded: LLM classified as INFRA_TECH (infrastructure technology)",
            evidence_summary=[
                f"LLM confidence: {asset.llm_metadata.llm_confidence}",
                f"Reason: {asset.llm_metadata.llm_reason}"
            ]
        )

    # Check provisioning status - REVIEW means zombie candidate
    if asset.provisioning_status == ProvisioningStatus.REVIEW:
        has_idp = asset.lens_coverage.idp if asset.lens_coverage else False
        has_cmdb = asset.lens_coverage.cmdb if asset.lens_coverage else False

        official_sources = []
        if has_idp:
            official_sources.append("IdP")
        if has_cmdb:
            official_sources.append("CMDB")

        latest_activity = ensure_utc_aware(asset.activity_evidence.latest_activity_at)
        activity_info = f"Last activity: {latest_activity.isoformat()}" if latest_activity else "No activity timestamps"

        return ClassificationResult(
            is_classified=True,
            is_indeterminate=False,
            classification_type="zombie",
            reason=f"Zombie Review: Asset flagged for cleanup - in {', '.join(official_sources) if official_sources else 'governance'} but stale activity",
            evidence_summary=[
                "Status: REVIEW (Zombie candidate)",
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

    # Use lens_coverage for governance
    has_idp = asset.lens_coverage.idp if asset.lens_coverage else False
    has_cmdb = asset.lens_coverage.cmdb if asset.lens_coverage else False

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

    latest_activity = ensure_utc_aware(asset.activity_evidence.latest_activity_at)
    cutoff_date = utc_now() - timedelta(days=activity_window_days)

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
