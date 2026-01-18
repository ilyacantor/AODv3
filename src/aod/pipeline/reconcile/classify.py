"""Classification logic for reconciliation."""

import logging
from datetime import timedelta
from typing import Optional

from .enums import ReasonCode, AnchorType
from .result_types import AssetActualResult
from .utils import ensure_utc_aware, utc_now
from .reason_codes import compute_asset_reasons
from .domain_helpers import resolve_domain_key
from ...models.output_contracts import Asset
from ...core.policy import get_current_config

logger = logging.getLogger(__name__)


def classify_actual(
    asset: Asset,
    activity_window_days: Optional[int] = None
) -> AssetActualResult:
    """
    Classify a single asset for reconciliation output.

    Determines the asset's classification (shadow/zombie/parked/active)
    based on governance signals and activity evidence.

    Args:
        asset: The asset to classify
        activity_window_days: Days to consider for activity (default from policy)

    Returns:
        AssetActualResult with complete classification information
    """
    if activity_window_days is None:
        activity_window_days = get_current_config().activity_windows.default_activity_window_days

    # Resolve domain key for aggregation
    domains = asset.identifiers.domains if asset.identifiers else []
    domain_key, is_canonical, alias_keys = resolve_domain_key(
        domains=domains,
        vendor=asset.vendor,
        name=asset.name
    )

    # Compute reason codes and classification
    reason_codes, classification, anchor_types = compute_asset_reasons(
        asset, activity_window_days
    )

    # Extract governance signals
    has_idp = asset.lens_coverage.idp if asset.lens_coverage else False
    has_cmdb = asset.lens_coverage.cmdb if asset.lens_coverage else False
    has_vendor_governed = asset.lens_coverage.vendor_governed if asset.lens_coverage else False
    has_finance = asset.lens_coverage.finance if asset.lens_coverage else False
    has_cloud = asset.lens_coverage.cloud if asset.lens_coverage else False
    has_discovery = bool(getattr(asset, "discovery_sources", None))

    # Check ongoing finance
    has_ongoing_finance = any(
        isinstance(ref, str) and (
            ref.startswith("recurring_contract:") or
            ref.startswith("recurring_transaction:")
        )
        for ref in asset.evidence_refs
    )

    # Determine activity status
    latest_activity = ensure_utc_aware(asset.activity_evidence.latest_activity_at)
    if latest_activity is None:
        activity_status = "none"
    else:
        cutoff = utc_now() - timedelta(days=activity_window_days)
        activity_status = "recent" if latest_activity >= cutoff else "stale"

    # Build match debug info if available
    match_debug = None
    if asset.lens_match_debug:
        match_debug = {
            "idp": asset.lens_match_debug.idp_debug,
            "cmdb": asset.lens_match_debug.cmdb_debug,
            "cloud": asset.lens_match_debug.cloud_debug,
            "finance": asset.lens_match_debug.finance_debug,
        }

    return AssetActualResult(
        domain_key=domain_key,
        asset_names=[asset.name],
        asset_ids=[str(asset.asset_id)],
        classification=classification,
        reason_codes=reason_codes,
        has_idp=has_idp,
        has_cmdb=has_cmdb,
        has_finance=has_finance,
        has_cloud=has_cloud,
        has_discovery=has_discovery,
        has_ongoing_finance=has_ongoing_finance,
        has_vendor_governed=has_vendor_governed,
        latest_activity_at=latest_activity,
        activity_status=activity_status,
        is_domain_canonical=is_canonical,
        anchor_types=anchor_types,
        entity_count=1,
        alias_domains=alias_keys,
        match_debug=match_debug,
    )


def merge_results(results: list[AssetActualResult]) -> AssetActualResult:
    """
    Merge multiple results for the same domain key using OR logic.

    When multiple assets share a domain key, their governance signals
    are combined: if ANY asset has IdP, the merged result has IdP.

    Args:
        results: List of results sharing the same domain_key

    Returns:
        Single merged AssetActualResult
    """
    if not results:
        raise ValueError("Cannot merge empty results list")

    if len(results) == 1:
        return results[0]

    base = results[0]

    # Merge names and IDs
    all_names = []
    all_ids = []
    for r in results:
        all_names.extend(r.asset_names)
        all_ids.extend(r.asset_ids)

    # Merge governance (OR logic)
    has_idp = any(r.has_idp for r in results)
    has_cmdb = any(r.has_cmdb for r in results)
    has_vendor_governed = any(r.has_vendor_governed for r in results)
    has_finance = any(r.has_finance for r in results)
    has_cloud = any(r.has_cloud for r in results)
    has_discovery = any(r.has_discovery for r in results)
    has_ongoing_finance = any(r.has_ongoing_finance for r in results)

    # Merge activity (latest wins)
    latest_activity = None
    for r in results:
        if r.latest_activity_at:
            if latest_activity is None or r.latest_activity_at > latest_activity:
                latest_activity = r.latest_activity_at

    # Merge alias domains
    all_aliases = set()
    for r in results:
        all_aliases.update(r.alias_domains)

    # Merge anchor types
    all_anchors = set()
    for r in results:
        all_anchors.update(r.anchor_types)

    # Re-classify based on merged signals
    is_governed = has_idp or has_cmdb or has_vendor_governed

    if latest_activity is None:
        activity_status = "none"
    else:
        cutoff = utc_now() - timedelta(days=90)  # Use default window
        activity_status = "recent" if latest_activity >= cutoff else "stale"

    if is_governed:
        if activity_status == "stale" and has_ongoing_finance:
            classification = "zombie"
        else:
            classification = "active"
    else:
        if activity_status == "recent":
            classification = "shadow"
        elif activity_status == "stale":
            classification = "parked"
        else:
            classification = "active"

    # Merge reason codes (deduplicated)
    all_codes = []
    for r in results:
        all_codes.extend(r.reason_codes)
    seen = set()
    unique_codes = []
    for code in all_codes:
        if code not in seen:
            seen.add(code)
            unique_codes.append(code)

    return AssetActualResult(
        domain_key=base.domain_key,
        asset_names=list(set(all_names)),
        asset_ids=list(set(all_ids)),
        classification=classification,
        reason_codes=unique_codes,
        has_idp=has_idp,
        has_cmdb=has_cmdb,
        has_finance=has_finance,
        has_cloud=has_cloud,
        has_discovery=has_discovery,
        has_ongoing_finance=has_ongoing_finance,
        has_vendor_governed=has_vendor_governed,
        latest_activity_at=latest_activity,
        activity_status=activity_status,
        is_domain_canonical=base.is_domain_canonical,
        anchor_types=list(all_anchors),
        entity_count=len(results),
        alias_domains=list(all_aliases),
        match_debug=base.match_debug,  # Use first result's debug
    )
