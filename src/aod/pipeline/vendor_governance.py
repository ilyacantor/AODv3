"""
Vendor Governance Propagation

Propagates governance signals (IdP, CMDB presence) across entities sharing the same vendor.
If any entity for a vendor has IdP/CMDB match, all entities for that vendor inherit governance.

Example:
- zoom.us has IdP match (SSO enabled)
- zoom-video.com has same vendor "zoom" but no direct IdP match
- After propagation, zoom-video.com inherits idp_present=True from zoom.us
"""

from dataclasses import dataclass
from typing import Optional

from .correlate_entities import CorrelationResult, MatchStatus
from .normalize_observations import CandidateEntity
from .vendor_inference import infer_vendor_from_domain, DOMAIN_TO_VENDOR


@dataclass
class PropagatedGovernance:
    """Governance signals propagated from vendor siblings.

    Jan 2026 Fix: Include metadata fields so policy engine can evaluate strict requirements.
    """
    idp_present: bool = False
    cmdb_present: bool = False
    source_entity: Optional[str] = None
    propagation_reason: Optional[str] = None
    # IdP metadata (for policy engine strict requirements)
    has_sso: bool = False
    has_scim: bool = False
    idp_type: Optional[str] = None
    # CMDB metadata (for policy engine strict requirements)
    ci_type: Optional[str] = None
    lifecycle: Optional[str] = None


def get_effective_vendor(entity: CandidateEntity) -> Optional[str]:
    """Get vendor from entity or infer from domain."""
    if entity.vendor:
        return entity.vendor.lower().strip()
    
    if entity.domain:
        domain = entity.domain.lower().strip()
        if domain in DOMAIN_TO_VENDOR:
            return DOMAIN_TO_VENDOR[domain].lower()
        
        hypothesis = infer_vendor_from_domain(domain)
        if hypothesis:
            return hypothesis.value.lower()
    
    return None


def propagate_vendor_governance(
    correlations: list[CorrelationResult]
) -> dict[str, PropagatedGovernance]:
    """
    Propagate governance across entities sharing the same vendor.
    
    Returns dict mapping entity_id -> PropagatedGovernance
    """
    vendor_to_entities: dict[str, list[CorrelationResult]] = {}
    
    for corr in correlations:
        vendor = get_effective_vendor(corr.entity)
        if vendor:
            if vendor not in vendor_to_entities:
                vendor_to_entities[vendor] = []
            vendor_to_entities[vendor].append(corr)
    
    propagated: dict[str, PropagatedGovernance] = {}
    
    for vendor, vendor_correlations in vendor_to_entities.items():
        idp_source: Optional[CorrelationResult] = None
        cmdb_source: Optional[CorrelationResult] = None

        for corr in vendor_correlations:
            if corr.idp.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
                if idp_source is None:
                    idp_source = corr
            if corr.cmdb.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
                if cmdb_source is None:
                    cmdb_source = corr

        if idp_source or cmdb_source:
            for corr in vendor_correlations:
                has_direct_idp = corr.idp.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS)
                has_direct_cmdb = corr.cmdb.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS)

                needs_idp = not has_direct_idp and idp_source is not None
                needs_cmdb = not has_direct_cmdb and cmdb_source is not None

                if needs_idp or needs_cmdb:
                    reasons = []
                    source_name = None

                    # Jan 2026: Extract metadata from source records for policy engine
                    has_sso = False
                    has_scim = False
                    idp_type = None
                    ci_type = None
                    lifecycle = None

                    if needs_idp and idp_source and idp_source.idp.matched_records:
                        reasons.append(f"IdP from {idp_source.entity.original_name}")
                        source_name = idp_source.entity.original_name
                        # Extract IdP metadata from first matched record
                        idp_record = idp_source.idp.matched_records[0]
                        has_sso = getattr(idp_record, 'has_sso', False)
                        has_scim = getattr(idp_record, 'has_scim', False)
                        idp_type = getattr(idp_record, 'idp_type', None)

                    if needs_cmdb and cmdb_source and cmdb_source.cmdb.matched_records:
                        reasons.append(f"CMDB from {cmdb_source.entity.original_name}")
                        source_name = source_name or cmdb_source.entity.original_name
                        # Extract CMDB metadata from first matched record
                        cmdb_record = cmdb_source.cmdb.matched_records[0]
                        ci_type = getattr(cmdb_record, 'ci_type', None)
                        lifecycle = getattr(cmdb_record, 'lifecycle', None)

                    propagated[corr.entity.entity_id] = PropagatedGovernance(
                        idp_present=needs_idp or has_direct_idp,
                        cmdb_present=needs_cmdb or has_direct_cmdb,
                        source_entity=source_name,
                        propagation_reason=f"Vendor '{vendor}': " + ", ".join(reasons),
                        has_sso=has_sso,
                        has_scim=has_scim,
                        idp_type=idp_type,
                        ci_type=ci_type,
                        lifecycle=lifecycle
                    )
    
    return propagated
