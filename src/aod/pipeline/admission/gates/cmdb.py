"""CMDB admission gate - check CMDB plane criteria."""

from ...correlate_entities import CorrelationResult, MatchStatus
from ....models.input_contracts import CMDBConfigItem
from ..constants import VALID_CI_TYPES, VALID_LIFECYCLES


def check_cmdb_admission(
    correlation: CorrelationResult,
    require_valid_ci_type: bool = True,
    require_valid_lifecycle: bool = True
) -> tuple[bool, str]:
    """
    Check CMDB plane admission criteria with policy-driven gate enforcement.

    Gate logic:
    - If require_valid_ci_type=True, ci_type must be in VALID_CI_TYPES
    - If require_valid_lifecycle=True, lifecycle must be in VALID_LIFECYCLES
    - A record must pass ALL enabled gates to be admitted
    - No fallback: if gates are enabled and all records fail, admission is denied

    This aligns with Farm's behavior where passes_gate=false means no governance.

    Jan 2026: Governance principle - only AUTHORITATIVE matches can assert governance.
    Heuristic matches (fuzzy, vendor, contains) provide enrichment but not governance.

    NOTE: Both MATCHED and AMBIGUOUS correlation status count as having CMDB evidence.
    """
    if correlation.cmdb.status not in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
        return False, ""

    # Governance principle: Only authoritative matches can assert governance.
    # Heuristic matches (fuzzy, vendor, contains) are enrichment-only.
    if not correlation.cmdb.is_authoritative:
        return False, ""

    if not correlation.cmdb.matched_records:
        return False, ""

    for record in correlation.cmdb.matched_records:
        if isinstance(record, CMDBConfigItem):
            ci_type_valid = record.ci_type.lower() in VALID_CI_TYPES
            lifecycle_valid = record.lifecycle.lower() in VALID_LIFECYCLES

            ci_passes = ci_type_valid or not require_valid_ci_type
            lifecycle_passes = lifecycle_valid or not require_valid_lifecycle

            if ci_passes and lifecycle_passes:
                return True, f"CMDB match: {record.ci_type} in {record.lifecycle}"

    return False, "CMDB match failed gate validation (ci_type/lifecycle)"
