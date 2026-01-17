"""Cloud admission gate - check Cloud plane criteria."""

from ...correlate_entities import CorrelationResult, MatchStatus
from ....models.input_contracts import CloudResource
from ..constants import VALID_CLOUD_RESOURCE_TYPES


def check_cloud_admission(correlation: CorrelationResult) -> tuple[bool, str]:
    """
    Check Cloud plane admission criteria:
    - Cloud match (any cloud resource is sufficient for admission)
    - Prefer: resource_type indicates real system/resource (stronger signal)
    NOTE: Both MATCHED and AMBIGUOUS count as having Cloud evidence.

    RELAXED: Any cloud match counts. Valid resource_type provides stronger confidence but is not required.
    """
    if correlation.cloud.status not in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
        return False, ""

    for record in correlation.cloud.matched_records:
        if isinstance(record, CloudResource):
            resource_type = record.resource_type.lower()
            for valid_type in VALID_CLOUD_RESOURCE_TYPES:
                if valid_type in resource_type:
                    return True, f"Cloud match: {record.resource_type}"

    if correlation.cloud.matched_records:
        return True, "Cloud match (cloud resource)"

    return False, ""
