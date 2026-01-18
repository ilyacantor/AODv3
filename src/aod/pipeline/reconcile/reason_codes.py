"""Reason code computation for reconciliation."""

from datetime import timedelta
from typing import Optional

from .enums import ReasonCode, AnchorType
from .utils import ensure_utc_aware, utc_now, deduplicate_reason_codes
from ...models.output_contracts import Asset
from ...core.policy import get_current_config


def compute_asset_reasons(
    asset: Asset,
    activity_window_days: Optional[int] = None
) -> tuple[list[ReasonCode], str, list[AnchorType]]:
    """
    Compute reason codes explaining an asset's classification.

    This function determines WHY an asset is classified as shadow,
    zombie, parked, or active based on its evidence signals.

    Args:
        asset: The asset to analyze
        activity_window_days: Days to consider for activity recency (default from policy)

    Returns:
        Tuple of (reason_codes, classification, anchor_types)
        - reason_codes: List of ReasonCode explaining the decision
        - classification: "shadow", "zombie", "parked", or "active"
        - anchor_types: List of AnchorType showing where asset is tracked
    """
    if activity_window_days is None:
        activity_window_days = get_current_config().activity_windows.default_activity_window_days

    codes: list[ReasonCode] = []
    anchor_types: list[AnchorType] = []

    # Governance signals - use lens_coverage (gate-validated)
    has_idp = asset.lens_coverage.idp if asset.lens_coverage else False
    has_cmdb = asset.lens_coverage.cmdb if asset.lens_coverage else False
    has_vendor_governed = asset.lens_coverage.vendor_governed if asset.lens_coverage else False

    codes.append(ReasonCode.HAS_IDP if has_idp else ReasonCode.NO_IDP)
    codes.append(ReasonCode.HAS_CMDB if has_cmdb else ReasonCode.NO_CMDB)
    codes.append(ReasonCode.HAS_VENDOR_GOVERNED if has_vendor_governed else ReasonCode.NO_VENDOR_GOVERNED)

    if has_idp:
        anchor_types.append(AnchorType.IDP)
    if has_cmdb:
        anchor_types.append(AnchorType.CMDB)

    # Presence signals
    has_finance = asset.lens_coverage.finance if asset.lens_coverage else False
    has_cloud = asset.lens_coverage.cloud if asset.lens_coverage else False
    has_discovery = bool(getattr(asset, "discovery_sources", None))

    codes.append(ReasonCode.HAS_FINANCE if has_finance else ReasonCode.NO_FINANCE)
    codes.append(ReasonCode.HAS_CLOUD if has_cloud else ReasonCode.NO_CLOUD)
    codes.append(ReasonCode.HAS_DISCOVERY if has_discovery else ReasonCode.NO_DISCOVERY)

    if has_finance:
        anchor_types.append(AnchorType.FINANCE)
    if has_cloud:
        anchor_types.append(AnchorType.CLOUD)

    # Check ongoing finance
    has_ongoing_finance = any(
        isinstance(ref, str) and (
            ref.startswith("recurring_contract:") or
            ref.startswith("recurring_transaction:")
        )
        for ref in asset.evidence_refs
    )
    if has_ongoing_finance:
        codes.append(ReasonCode.HAS_ONGOING_FINANCE)

    # Activity signals
    latest_activity = ensure_utc_aware(asset.activity_evidence.latest_activity_at)

    if latest_activity is None:
        codes.append(ReasonCode.NO_ACTIVITY_TIMESTAMPS)
        activity_status = "none"
    else:
        cutoff = utc_now() - timedelta(days=activity_window_days)
        if latest_activity >= cutoff:
            codes.append(ReasonCode.RECENT_ACTIVITY)
            activity_status = "recent"
        else:
            codes.append(ReasonCode.STALE_ACTIVITY)
            activity_status = "stale"

    # Determine classification
    is_governed = has_idp or has_cmdb or has_vendor_governed

    if is_governed:
        if activity_status == "stale" and has_ongoing_finance:
            classification = "zombie"
            codes.append(ReasonCode.ZOMBIE_CLASSIFICATION)
        else:
            classification = "active"
            codes.append(ReasonCode.ACTIVE_CLASSIFICATION)
    else:
        if activity_status == "recent":
            classification = "shadow"
            codes.append(ReasonCode.SHADOW_CLASSIFICATION)
        elif activity_status == "stale":
            classification = "parked"
            codes.append(ReasonCode.PARKED_CLASSIFICATION)
        else:
            # No activity timestamps - default to active (indeterminate)
            classification = "active"
            codes.append(ReasonCode.ACTIVE_CLASSIFICATION)

    if not anchor_types:
        anchor_types.append(AnchorType.NONE)

    return deduplicate_reason_codes(codes), classification, anchor_types
