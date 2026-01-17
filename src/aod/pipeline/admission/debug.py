"""Debug utilities for admission processing."""

from typing import Optional

from ..correlate_entities import CorrelationResult, MatchStatus
from ...models.output_contracts import MatchDebugInfo, LensMatchDebug


def _get_record_name(record) -> str:
    """Extract name from a plane record."""
    if hasattr(record, 'name'):
        return record.name
    if hasattr(record, 'app_name'):
        return record.app_name
    if hasattr(record, 'vendor_name'):
        return record.vendor_name
    return str(record) if record else ""


def build_match_debug_info(plane_match) -> Optional[MatchDebugInfo]:
    """Build debug info from a PlaneMatch for debugging CMDB/IdP matching issues."""
    if plane_match.status == MatchStatus.UNMATCHED:
        return None

    matched_record_id = plane_match.matched_ids[0] if plane_match.matched_ids else None
    matched_record_name = None
    matched_record_domain = None
    if plane_match.matched_records:
        first_record = plane_match.matched_records[0]
        if first_record:
            matched_record_name = _get_record_name(first_record)
            # Extract domain from record if available
            if hasattr(first_record, 'domain') and first_record.domain:
                matched_record_domain = first_record.domain

    return MatchDebugInfo(
        match_method=plane_match.match_method,
        match_key=plane_match.match_key,
        matched_record_id=matched_record_id,
        matched_record_name=matched_record_name,
        matched_record_domain=matched_record_domain,
        ambiguity_code=plane_match.ambiguity_code.value if plane_match.ambiguity_code else None,
        disambiguation_detail=plane_match.disambiguation_detail,
        is_authoritative=plane_match.is_authoritative
    )


def build_lens_match_debug(correlation: CorrelationResult) -> Optional[LensMatchDebug]:
    """Build lens match debug info from a correlation result."""
    idp_debug = build_match_debug_info(correlation.idp)
    cmdb_debug = build_match_debug_info(correlation.cmdb)
    cloud_debug = build_match_debug_info(correlation.cloud)
    finance_debug = build_match_debug_info(correlation.finance)

    if not any([idp_debug, cmdb_debug, cloud_debug, finance_debug]):
        return None

    return LensMatchDebug(
        idp=idp_debug,
        cmdb=cmdb_debug,
        cloud=cloud_debug,
        finance=finance_debug
    )
