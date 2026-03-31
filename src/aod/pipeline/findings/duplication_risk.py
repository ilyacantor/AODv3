"""Duplication risk finding generation"""

from typing import Optional

from ...models.output_contracts import Asset, Finding, FindingType, Severity
from ..correlate_entities import CorrelationResult, MatchStatus
from ..deterministic_ids import deterministic_uuid
from .base import get_category


def generate_duplication_risk_finding(
    asset: Asset,
    correlation: CorrelationResult,
    tenant_id: str,
    run_id: str,
    snapshot_id: str
) -> Optional[Finding]:
    """
    Generate duplication_risk finding:
    Multiple entities ambiguous-match same plane record
    """
    ambiguous_planes = []

    if correlation.idp.status == MatchStatus.AMBIGUOUS:
        ambiguous_planes.append(f"IdP ({len(correlation.idp.matched_ids)} matches)")
    if correlation.cmdb.status == MatchStatus.AMBIGUOUS:
        ambiguous_planes.append(f"CMDB ({len(correlation.cmdb.matched_ids)} matches)")
    if correlation.cloud.status == MatchStatus.AMBIGUOUS:
        ambiguous_planes.append(f"Cloud ({len(correlation.cloud.matched_ids)} matches)")
    if correlation.finance.status == MatchStatus.AMBIGUOUS:
        ambiguous_planes.append(f"Finance ({len(correlation.finance.matched_ids)} matches)")

    if not ambiguous_planes:
        return None

    return Finding(
        finding_id=deterministic_uuid(snapshot_id, run_id, asset.name, "duplication_risk"),
        asset_id=asset.asset_id,
        tenant_id=tenant_id,
        aod_discovery_id=run_id,
        finding_type=FindingType.DUPLICATION_RISK,
        category=get_category(FindingType.DUPLICATION_RISK),
        severity=Severity.MED,
        explanation=f"Asset '{asset.name}' has ambiguous matches in: {', '.join(ambiguous_planes)}. Manual review recommended.",
        evidence_refs=asset.evidence_refs
    )
