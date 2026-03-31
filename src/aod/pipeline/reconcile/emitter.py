"""Main emitter for reconciliation output."""

import logging
from datetime import datetime
from typing import Optional
from collections import defaultdict

from .result_types import ActualResultsOutput, AssetActualResult, RejectionResult
from .classify import classify_actual, merge_results
from .eligibility import is_reconciliation_eligible
from .domain_helpers import resolve_domain_key
from .utils import utc_now
from ..correlate_entities import CorrelationResult
from ...models.output_contracts import Asset
from ...core.policy import get_current_config

logger = logging.getLogger(__name__)


def compute_rejection_reasons(
    correlation: CorrelationResult,
    reason: str
) -> RejectionResult:
    """
    Compute rejection details for an entity that wasn't admitted.

    Args:
        correlation: The correlation result for the entity
        reason: Primary rejection reason

    Returns:
        RejectionResult with details
    """
    entity = correlation.entity

    # Build evidence summary
    evidence = {
        "idp_status": correlation.idp.status.value if correlation.idp else "unmatched",
        "cmdb_status": correlation.cmdb.status.value if correlation.cmdb else "unmatched",
        "cloud_status": correlation.cloud.status.value if correlation.cloud else "unmatched",
        "finance_status": correlation.finance.status.value if correlation.finance else "unmatched",
    }

    return RejectionResult(
        entity_key=entity.entity_id,
        entity_name=entity.canonical_name,
        reason_code=reason,
        reason_detail=f"Entity rejected: {reason}",
        evidence_summary=evidence,
    )


def emit_actual_results(
    assets: list[Asset],
    correlations: list[CorrelationResult],
    run_id: str,
    tenant_id: str,
    activity_window_days: Optional[int] = None,
    include_rejections: bool = True,
) -> ActualResultsOutput:
    """
    Emit complete reconciliation results for a pipeline run.

    This is the main entry point for generating reconciliation output.
    It processes all assets, classifies them, aggregates by domain,
    and produces the final output structure.

    Args:
        assets: List of admitted assets from the pipeline
        correlations: Correlation results (used for rejection tracking)
        run_id: Pipeline run ID
        tenant_id: Tenant ID
        activity_window_days: Activity window for classification (default from policy)
        include_rejections: Whether to include rejection records

    Returns:
        ActualResultsOutput with all classified assets and statistics
    """
    if activity_window_days is None:
        activity_window_days = get_current_config().activity_windows.default_activity_window_days

    logger.info("emit_actual_results.start", extra={
        "aod_discovery_id": run_id,
        "asset_count": len(assets),
        "correlation_count": len(correlations),
        "activity_window_days": activity_window_days,
    })

    # Phase 1: Classify each asset
    asset_results: list[AssetActualResult] = []
    excluded_count = 0

    for asset in assets:
        # Check eligibility
        is_eligible, exclusion_reason = is_reconciliation_eligible(asset)
        if not is_eligible:
            logger.debug("Asset excluded from reconciliation", extra={
                "asset_id": str(asset.asset_id),
                "reason": exclusion_reason,
            })
            excluded_count += 1
            continue

        result = classify_actual(asset, activity_window_days)
        asset_results.append(result)

    # Phase 2: Aggregate by domain key
    domain_groups: dict[str, list[AssetActualResult]] = defaultdict(list)
    for result in asset_results:
        domain_groups[result.domain_key].append(result)

    # Phase 3: Merge results for each domain
    merged_results: list[AssetActualResult] = []
    for domain_key, results in domain_groups.items():
        merged = merge_results(results)
        merged_results.append(merged)

    # Phase 4: Sort into classification buckets
    shadow_assets: list[AssetActualResult] = []
    zombie_assets: list[AssetActualResult] = []
    parked_assets: list[AssetActualResult] = []
    active_assets: list[AssetActualResult] = []

    for result in merged_results:
        if result.classification == "shadow":
            shadow_assets.append(result)
        elif result.classification == "zombie":
            zombie_assets.append(result)
        elif result.classification == "parked":
            parked_assets.append(result)
        else:
            active_assets.append(result)

    # Phase 5: Compute rejections if requested
    rejections: list[RejectionResult] = []
    if include_rejections:
        # Build set of admitted entity IDs
        admitted_entity_ids = set()
        for asset in assets:
            # Entity ID is typically based on the domain
            if asset.identifiers and asset.identifiers.domains:
                for domain in asset.identifiers.domains:
                    admitted_entity_ids.add(f"entity:{domain}")

        # Find entities that weren't admitted
        for correlation in correlations:
            entity_id = correlation.entity.entity_id
            if entity_id not in admitted_entity_ids:
                # Determine rejection reason from admission result
                reason = "unknown"

                # Check if it was a known rejection
                if hasattr(correlation, 'admission_result'):
                    if correlation.admission_result:
                        reason = correlation.admission_result.rejection_reason or "not_admitted"
                else:
                    # Infer reason from correlation status
                    if (correlation.idp.status.value == "unmatched" and
                        correlation.cmdb.status.value == "unmatched" and
                        correlation.cloud.status.value == "unmatched" and
                        correlation.finance.status.value == "unmatched"):
                        reason = "no_evidence"
                    else:
                        reason = "admission_criteria_not_met"

                rejection = compute_rejection_reasons(correlation, reason)
                rejections.append(rejection)

    # Phase 6: Build output
    output = ActualResultsOutput(
        aod_discovery_id=run_id,
        tenant_id=tenant_id,
        generated_at=utc_now(),
        shadow_assets=shadow_assets,
        zombie_assets=zombie_assets,
        parked_assets=parked_assets,
        active_assets=active_assets,
        rejections=rejections,
        total_entities_processed=len(correlations),
        total_assets_emitted=len(merged_results),
        total_rejections=len(rejections),
        shadow_count=len(shadow_assets),
        zombie_count=len(zombie_assets),
        parked_count=len(parked_assets),
        active_count=len(active_assets),
        activity_window_days=activity_window_days,
    )

    logger.info("emit_actual_results.complete", extra={
        "aod_discovery_id": run_id,
        "shadow_count": output.shadow_count,
        "zombie_count": output.zombie_count,
        "parked_count": output.parked_count,
        "active_count": output.active_count,
        "total_rejections": output.total_rejections,
        "excluded_count": excluded_count,
    })

    return output


# Underscore alias for backwards compatibility
_compute_rejection_reasons = compute_rejection_reasons
