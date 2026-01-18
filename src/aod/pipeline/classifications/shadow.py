"""Shadow asset classification."""

from datetime import timedelta
from typing import Optional

from .result_types import ClassificationResult
from .time_utils import ensure_utc_aware, utc_now
from ...models.output_contracts import Asset, ProvisioningStatus
from ...core.policy import get_current_config


def classify_shadow(
    asset: Asset,
    activity_window_days: Optional[int] = None
) -> ClassificationResult:
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
    if activity_window_days is None:
        activity_window_days = get_current_config().activity_windows.default_activity_window_days

    # Check LLM exclusion
    if asset.llm_metadata and asset.llm_metadata.exclusion_reason == "asset_type_infra_tech":
        return ClassificationResult(
            is_classified=False,
            is_indeterminate=False,
            classification_type="shadow",
            reason="Asset excluded: LLM classified as INFRA_TECH (infrastructure technology)",
            evidence_summary=[
                f"LLM confidence: {asset.llm_metadata.llm_confidence}",
                f"Reason: {asset.llm_metadata.llm_reason}"
            ]
        )

    # Check provisioning status
    if asset.provisioning_status == ProvisioningStatus.QUARANTINE:
        has_cloud = asset.lens_coverage.cloud if asset.lens_coverage else False
        has_discovery = bool(getattr(asset, "discovery_sources", None))
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
            reason="Shadow Block: Asset quarantined - no IdP/CMDB governance, blocked from DCL",
            evidence_summary=[
                "Status: QUARANTINE (Shadow IT)",
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

    # Use lens_coverage for governance
    has_idp = asset.lens_coverage.idp if asset.lens_coverage else False
    has_cmdb = asset.lens_coverage.cmdb if asset.lens_coverage else False
    has_vendor_governed = asset.lens_coverage.vendor_governed if asset.lens_coverage else False

    has_cloud = asset.lens_coverage.cloud if asset.lens_coverage else False
    has_discovery = bool(getattr(asset, "discovery_sources", None))

    # GOVERNANCE: IdP OR CMDB OR vendor_governed
    if has_idp or has_cmdb or has_vendor_governed:
        return ClassificationResult(
            is_classified=False,
            is_indeterminate=False,
            classification_type="shadow",
            reason="Asset has IdP or CMDB presence - governed, not shadow",
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

    latest_activity = ensure_utc_aware(asset.activity_evidence.latest_activity_at)
    cutoff_date = utc_now() - timedelta(days=activity_window_days)

    if latest_activity is None:
        return ClassificationResult(
            is_classified=False,
            is_indeterminate=True,
            classification_type="shadow",
            reason="No activity timestamps available - cannot determine shadow status",
            evidence_summary=[
                f"Presence: {', '.join(presence_sources)}",
                "Activity: No timestamps"
            ]
        )

    if latest_activity < cutoff_date:
        return ClassificationResult(
            is_classified=False,
            is_indeterminate=False,
            classification_type="shadow",
            reason=f"Activity too old (last seen: {latest_activity.isoformat()}) - outside {activity_window_days} day window",
            evidence_summary=[
                f"Presence: {', '.join(presence_sources)}",
                f"Last activity: {latest_activity.isoformat()}"
            ]
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
