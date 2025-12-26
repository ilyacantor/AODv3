"""CMDB gap finding generation"""

from typing import Optional

from ...models.output_contracts import Asset, Finding, FindingType, LensStatus, Severity
from ..correlate_entities import CorrelationResult
from ..deterministic_ids import deterministic_uuid
from .base import get_category


def generate_cmdb_gap_finding(
    asset: Asset,
    correlation: CorrelationResult,
    tenant_id: str,
    run_id: str,
    snapshot_id: str
) -> Optional[Finding]:
    """
    Generate cmdb_gap finding:
    Admitted via IdP/finance but no CMDB match
    """
    if asset.lens_status.cmdb != LensStatus.UNMATCHED:
        return None

    if not (asset.lens_coverage.idp or asset.lens_coverage.finance):
        return None

    admitted_via = []
    if asset.lens_coverage.idp:
        admitted_via.append("IdP")
    if asset.lens_coverage.finance:
        admitted_via.append("Finance")

    return Finding(
        finding_id=deterministic_uuid(snapshot_id, run_id, asset.name, "cmdb_gap"),
        asset_id=asset.asset_id,
        tenant_id=tenant_id,
        run_id=run_id,
        finding_type=FindingType.CMDB_GAP,
        category=get_category(FindingType.CMDB_GAP),
        severity=Severity.MED,
        explanation=f"Asset '{asset.name}' admitted via {', '.join(admitted_via)} but not registered in CMDB",
        evidence_refs=asset.evidence_refs
    )
