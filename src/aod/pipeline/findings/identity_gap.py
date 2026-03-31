"""Identity gap finding generation"""

from typing import Optional

from ...models.output_contracts import (
    Asset, Finding, FindingType, LensStatus, Severity, Confidence, Materiality
)
from ..correlate_entities import CorrelationResult
from ..deterministic_ids import deterministic_uuid
from .base import get_category, compute_triage_priority


def generate_identity_gap_finding(
    asset: Asset,
    correlation: CorrelationResult,
    tenant_id: str,
    run_id: str,
    snapshot_id: str
) -> Optional[Finding]:
    """
    Generate identity_gap finding with TIGHTER GATE (Dec 2025):

    Trigger ONLY if:
    - No IdP governance (idp_present == false)
    - Has STRONG activity evidence (any of):
      - Cloud evidence (passed cloud admission = valid resource type)
      - Finance recurring spend (passed finance admission)
      - CMDB + other plane (multi-plane corroboration)

    Uses lens_coverage which is set from direct admission checks (not propagated).
    """
    if asset.lens_status.idp != LensStatus.UNMATCHED:
        return None

    # lens_coverage is set from check_*_admission results - direct evidence only
    has_cloud = asset.lens_coverage.cloud if asset.lens_coverage else False
    has_finance = asset.lens_coverage.finance if asset.lens_coverage else False
    has_cmdb = asset.lens_coverage.cmdb if asset.lens_coverage else False
    has_discovery = asset.lens_coverage.discovery if asset.lens_coverage else False

    # Count independent planes for multi-plane corroboration
    strong_planes = sum([has_cloud, has_finance, has_cmdb])
    has_multi_plane = (has_discovery and strong_planes >= 1) or strong_planes >= 2

    # Require strong activity: cloud OR finance OR multi-plane corroboration
    if not (has_cloud or has_finance or has_multi_plane):
        return None

    # Build evidence summary
    admitted_via = []
    if has_cmdb:
        admitted_via.append("CMDB")
    if has_cloud:
        admitted_via.append("Cloud")
    if has_finance:
        admitted_via.append("Finance")
    if has_discovery:
        admitted_via.append("Discovery")

    # Determine confidence based on evidence strength
    if has_cloud and has_finance:
        confidence = Confidence.HIGH
    elif has_cloud or has_finance:
        confidence = Confidence.HIGH
    elif has_multi_plane:
        confidence = Confidence.MED
    else:
        confidence = Confidence.LOW

    # Determine materiality based on governance coverage
    if has_cmdb:
        materiality = Materiality.HIGH  # In CMDB but no SSO = significant gap
    elif has_finance:
        materiality = Materiality.HIGH  # Paying for it but no SSO = significant
    elif has_cloud:
        materiality = Materiality.MED
    else:
        materiality = Materiality.LOW

    triage = compute_triage_priority(confidence, materiality)

    return Finding(
        finding_id=deterministic_uuid(snapshot_id, run_id, asset.name, "identity_gap"),
        asset_id=asset.asset_id,
        tenant_id=tenant_id,
        aod_discovery_id=run_id,
        finding_type=FindingType.IDENTITY_GAP,
        category=get_category(FindingType.IDENTITY_GAP),
        severity=Severity.MED,
        explanation=f"Asset '{asset.name}' has strong activity evidence ({', '.join(admitted_via)}) but no identity provider governance (no SSO/SCIM)",
        evidence_refs=asset.evidence_refs,
        confidence=confidence,
        materiality=materiality,
        triage_priority=triage
    )
