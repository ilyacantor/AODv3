"""Finance gap finding generation"""

from ...models.output_contracts import (
    Asset, Finding, FindingType, Severity, Confidence, Materiality
)
from ...models.input_contracts import Contract, Transaction
from ..correlate_entities import CorrelationResult, MatchStatus
from ..build_plane_indexes import PlaneIndexes
from ..deterministic_ids import deterministic_uuid
from .base import get_category, compute_triage_priority, FINANCE_GAP_MONTHLY_THRESHOLD


def generate_finance_gap_findings(
    indexes: PlaneIndexes,
    admitted_assets: list[Asset],
    correlations: list[CorrelationResult],
    tenant_id: str,
    run_id: str,
    snapshot_id: str
) -> list[Finding]:
    """
    Generate finance_gap findings with TIGHTER GATE (Dec 2025):

    Trigger ONLY if:
    - Recurring spend OR contract exists
    - Spend >= $200/month OR $2,000/year threshold
    - No governance visibility (no CMDB owner, no IdP app, etc.)

    DEDUPLICATION: Aggregates by vendor/product name to prevent multiple findings
    for the same vendor with many transactions.
    
    ASSET LINKAGE: If a vendor matches an existing asset by name/domain, link the finding.
    """
    matched_finance_ids = set()
    for correlation in correlations:
        if correlation.finance.status == MatchStatus.MATCHED:
            matched_finance_ids.update(correlation.finance.matched_ids)
    
    asset_lookup = {}
    for asset in admitted_assets:
        name_key = (asset.name or '').lower().strip()
        if name_key:
            asset_lookup[name_key] = asset.asset_id
        vendor_key = (asset.vendor or '').lower().strip()
        if vendor_key:
            asset_lookup[vendor_key] = asset.asset_id
        if asset.identifiers and asset.identifiers.domains:
            for domain in asset.identifiers.domains:
                domain_key = domain.lower().strip().replace('.com', '').replace('.io', '').replace('.app', '')
                asset_lookup[domain_key] = asset.asset_id

    # Aggregate unmatched finance by vendor/product name
    vendor_aggregates: dict[str, dict] = {}

    for record_id, record in indexes.finance.records.items():
        if record_id in matched_finance_ids:
            continue

        # Check if this is recurring spend
        is_recurring = False
        monthly_amount = 0.0

        if record_id.startswith("contract:"):
            is_recurring = True
            if isinstance(record, Contract):
                amount = record.amount or 0.0
                monthly_amount = amount / 12.0
        elif record_id.startswith("transaction:"):
            if hasattr(record, 'is_recurring') and record.is_recurring:
                is_recurring = True
                if isinstance(record, Transaction):
                    monthly_amount = record.amount or 0.0

        if not is_recurring:
            continue

        if monthly_amount < FINANCE_GAP_MONTHLY_THRESHOLD:
            continue

        # Get vendor/product name for aggregation
        vendor_name = getattr(record, 'vendor_name', None) or getattr(record, 'vendor', None)
        product_name = getattr(record, 'product', None)
        aggregate_key = (vendor_name or product_name or record_id).lower().strip()

        if aggregate_key not in vendor_aggregates:
            vendor_aggregates[aggregate_key] = {
                'display_name': vendor_name or product_name or record_id,
                'total_monthly': 0.0,
                'record_count': 0,
                'evidence_refs': []
            }

        vendor_aggregates[aggregate_key]['total_monthly'] += monthly_amount
        vendor_aggregates[aggregate_key]['record_count'] += 1
        vendor_aggregates[aggregate_key]['evidence_refs'].append(record_id)

    # Generate one finding per vendor/product (deduplicated)
    findings = []
    for aggregate_key, agg in vendor_aggregates.items():
        total_monthly = agg['total_monthly']
        display_name = agg['display_name']
        record_count = agg['record_count']

        # Determine confidence/materiality based on spend level
        if total_monthly >= 1000:
            confidence = Confidence.HIGH
            materiality = Materiality.HIGH
        elif total_monthly >= 500:
            confidence = Confidence.HIGH
            materiality = Materiality.MED
        else:
            confidence = Confidence.MED
            materiality = Materiality.MED

        triage = compute_triage_priority(confidence, materiality)

        if record_count > 1:
            explanation = f"Vendor '{display_name}' has ${total_monthly:.0f}/mo across {record_count} finance records with no corresponding asset. Possible undiscovered system(s)."
        else:
            explanation = f"Finance record '{display_name}' (${total_monthly:.0f}/mo) has no corresponding asset in catalog. Possible undiscovered system."

        linked_asset_id = None
        lookup_key = aggregate_key.replace('.com', '').replace('.io', '').replace('.app', '')
        if lookup_key in asset_lookup:
            linked_asset_id = asset_lookup[lookup_key]
        elif display_name.lower().strip() in asset_lookup:
            linked_asset_id = asset_lookup[display_name.lower().strip()]

        findings.append(Finding(
            finding_id=deterministic_uuid(snapshot_id, run_id, aggregate_key, "finance_gap"),
            asset_id=linked_asset_id,
            tenant_id=tenant_id,
            run_id=run_id,
            finding_type=FindingType.FINANCE_GAP,
            category=get_category(FindingType.FINANCE_GAP),
            severity=Severity.MED,
            explanation=explanation,
            evidence_refs=agg['evidence_refs'][:50],
            confidence=confidence,
            materiality=materiality,
            triage_priority=triage
        ))

    return findings
