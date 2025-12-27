"""Governance gap finding generation"""

from typing import Optional

from ...models.output_contracts import Asset, Finding, FindingType, Severity
from ..correlate_entities import CorrelationResult, MatchStatus
from ..deterministic_ids import deterministic_uuid
from .base import get_category


def generate_governance_gap_finding(
    asset: Asset,
    correlation: CorrelationResult,
    tenant_id: str,
    run_id: str,
    snapshot_id: str
) -> Optional[Finding]:
    """
    Generate governance_gap finding:
    No owner/system record found
    
    Owner can be set via:
    1. CMDB record with owner field
    2. IdP record with owner field  
    3. Triage "Assign Owner" action (sets asset.owner directly)
    """
    if asset.owner:
        return None
    
    has_owner = False

    if correlation.cmdb.status == MatchStatus.MATCHED:
        for record in correlation.cmdb.matched_records:
            if hasattr(record, 'owner') and record.owner:
                has_owner = True
                break

    if not has_owner and correlation.idp.status == MatchStatus.MATCHED:
        for record in correlation.idp.matched_records:
            if hasattr(record, 'owner') and record.owner:
                has_owner = True
                break

    if has_owner:
        return None

    return Finding(
        finding_id=deterministic_uuid(snapshot_id, run_id, asset.name, "governance_gap"),
        asset_id=asset.asset_id,
        tenant_id=tenant_id,
        run_id=run_id,
        finding_type=FindingType.GOVERNANCE_GAP,
        category=get_category(FindingType.GOVERNANCE_GAP),
        severity=Severity.MED,
        explanation=f"Asset '{asset.name}' has no designated owner in CMDB or IdP records",
        evidence_refs=asset.evidence_refs
    )
