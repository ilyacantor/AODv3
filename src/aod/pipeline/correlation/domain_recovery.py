"""Post-correlation domain recovery for name-only entities."""

import logging
from typing import Optional

from .enums import MatchStatus
from .result_types import CorrelationResult
from ..normalize_observations import normalize_domain

logger = logging.getLogger(__name__)


def recover_domain_from_planes(result: CorrelationResult) -> Optional[str]:
    """
    Post-correlation domain recovery for name-only entities.

    When a discovery observation lacks a domain (e.g., name="OpenSuite" with no domain field),
    the entity is keyed by name. If correlation later matches it to IdP/CMDB/Cloud records
    that have domains, we should adopt that domain as the entity's canonical key.

    Priority order: IdP → CMDB → Cloud → Finance

    Returns:
        Normalized domain from matched plane record, or None if no domain found
    """
    planes_to_check = [
        (result.idp, "idp"),
        (result.cmdb, "cmdb"),
        (result.cloud, "cloud"),
        (result.finance, "finance"),
    ]

    for plane_match, plane_name in planes_to_check:
        if plane_match.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
            for record in plane_match.matched_records:
                if record is None:
                    continue
                raw_domain = getattr(record, 'domain', None)
                if raw_domain:
                    normalized = normalize_domain(raw_domain)
                    if normalized:
                        logger.debug("domain_recovery.found", extra={
                            "plane": plane_name,
                            "raw_domain": raw_domain,
                            "normalized": normalized
                        })
                        return normalized

    return None


# Alias with underscore prefix for backwards compatibility
_recover_domain_from_planes = recover_domain_from_planes
