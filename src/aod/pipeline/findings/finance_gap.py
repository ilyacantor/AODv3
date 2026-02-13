"""
Finance gap finding generation.

Feb 2026: Refactored to use PolicyContext for financial thresholds.
Thresholds now come from the tenant's ScoringStrategy, supporting:
- Multi-currency normalization (amounts normalized to USD before comparison)
- Tenant-specific materiality thresholds
- Strategy-based scaling (enterprise vs startup)
"""

from typing import Optional

from ...models.output_contracts import (
    Asset, Finding, FindingType, Severity, Confidence, Materiality
)
from ...models.input_contracts import Contract, Transaction
from ..correlate_entities import CorrelationResult, MatchStatus
from ..build_plane_indexes import PlaneIndexes
from ..deterministic_ids import deterministic_uuid
from .base import get_category, compute_triage_priority, get_finance_gap_monthly_threshold
from ...core.policy import PolicyContext, get_default_context
from ...core.currency import normalize_to_usd

# DEPRECATED: Use policy.get_finance_gap_threshold() instead
# Kept for backward compatibility with code that imports these directly
FINANCE_HIGH_MATERIALITY_THRESHOLD = 1000  # ≥$1000/mo → HIGH confidence + HIGH materiality
FINANCE_MED_MATERIALITY_THRESHOLD = 500    # ≥$500/mo → HIGH confidence + MED materiality


def generate_finance_gap_findings(
    indexes: PlaneIndexes,
    admitted_assets: list[Asset],
    correlations: list[CorrelationResult],
    tenant_id: str,
    run_id: str,
    snapshot_id: str,
    policy: Optional[PolicyContext] = None,
    currency: str = "USD",
) -> list[Finding]:
    """
    Generate finance_gap findings with TIGHTER GATE (Dec 2025):

    Trigger ONLY if:
    - Recurring spend OR contract exists
    - Spend >= $200/month OR $2,000/year threshold
    - No governance visibility (no CMDB owner, no IdP app, etc.)

    DEDUPLICATION: Aggregates by vendor/product name to prevent multiple findings
    for the same vendor with many transactions.

    Feb 2026: Now accepts PolicyContext for strategy-specific thresholds.
    Use policy.get_finance_gap_threshold() instead of hardcoded values.
    """
    # Use provided policy or default
    policy = policy or get_default_context()

    # Get thresholds from policy (strategy-specific)
    high_threshold = policy.get_finance_gap_threshold("HIGH")
    med_threshold = policy.get_finance_gap_threshold("MEDIUM")

    matched_finance_ids = set()
    for correlation in correlations:
        if correlation.finance.status == MatchStatus.MATCHED:
            matched_finance_ids.update(correlation.finance.matched_ids)

    # Aggregate unmatched finance by vendor/product name
    vendor_aggregates: dict[str, dict] = {}

    for record_id, record in indexes.finance.records.items():
        if record_id in matched_finance_ids:
            continue

        # Check if this is recurring spend
        is_recurring = False
        monthly_amount = 0.0
        record_currency = "USD"  # Default to USD if not specified

        if record_id.startswith("contract:"):
            is_recurring = True
            if isinstance(record, Contract):
                amount = record.amount or 0.0
                monthly_amount = amount / 12.0
                # Get currency from contract if available
                record_currency = getattr(record, 'currency', None) or currency
        elif record_id.startswith("transaction:"):
            if hasattr(record, 'is_recurring') and record.is_recurring:
                is_recurring = True
                if isinstance(record, Transaction):
                    monthly_amount = record.amount or 0.0
                    # Get currency from transaction if available
                    record_currency = getattr(record, 'currency', None) or currency

        if not is_recurring:
            continue

        # CRITICAL: Normalize to USD BEFORE comparing against thresholds
        # This fixes the "Currency Ghost" bug where €900 was compared against $1000
        monthly_amount_usd = normalize_to_usd(monthly_amount, record_currency)

        if monthly_amount_usd < get_finance_gap_monthly_threshold():
            continue

        # Get vendor/product name for aggregation
        vendor_name = getattr(record, 'vendor_name', None) or getattr(record, 'vendor', None)
        product_name = getattr(record, 'product', None)
        aggregate_key = (vendor_name or product_name or record_id).lower().strip()

        if aggregate_key not in vendor_aggregates:
            vendor_aggregates[aggregate_key] = {
                'display_name': vendor_name or product_name or record_id,
                'total_monthly_usd': 0.0,  # Always in USD for threshold comparison
                'record_count': 0,
                'evidence_refs': []
            }

        # Aggregate using normalized USD amounts
        vendor_aggregates[aggregate_key]['total_monthly_usd'] += monthly_amount_usd
        vendor_aggregates[aggregate_key]['record_count'] += 1
        vendor_aggregates[aggregate_key]['evidence_refs'].append(record_id)

    # Generate one finding per vendor/product (deduplicated)
    findings = []
    for aggregate_key, agg in vendor_aggregates.items():
        total_monthly_usd = agg['total_monthly_usd']
        display_name = agg['display_name']
        record_count = agg['record_count']

        # Determine confidence/materiality based on spend level
        # Uses policy-derived thresholds (strategy-specific)
        # Comparison is always in USD (amounts were normalized above)
        if total_monthly_usd >= high_threshold:
            confidence = Confidence.HIGH
            materiality = Materiality.HIGH
        elif total_monthly_usd >= med_threshold:
            confidence = Confidence.HIGH
            materiality = Materiality.MED
        else:
            confidence = Confidence.MED
            materiality = Materiality.MED

        triage = compute_triage_priority(confidence, materiality)

        if record_count > 1:
            explanation = f"Vendor '{display_name}' has ${total_monthly_usd:.0f}/mo (USD) across {record_count} finance records with no corresponding asset. Possible undiscovered system(s)."
        else:
            explanation = f"Finance record '{display_name}' (${total_monthly_usd:.0f}/mo USD) has no corresponding asset in catalog. Possible undiscovered system."

        findings.append(Finding(
            finding_id=deterministic_uuid(snapshot_id, run_id, aggregate_key, "finance_gap"),
            asset_id=None,
            tenant_id=tenant_id,
            run_id=run_id,
            finding_type=FindingType.FINANCE_GAP,
            category=get_category(FindingType.FINANCE_GAP),
            severity=Severity.MED,
            explanation=explanation,
            evidence_refs=agg['evidence_refs'][:50],  # Limit refs
            confidence=confidence,
            materiality=materiality,
            triage_priority=triage
        ))

    return findings
