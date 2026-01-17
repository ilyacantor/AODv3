"""Finance record expansion - gather all records from same vendor."""

from .enums import MatchStatus
from .result_types import PlaneMatch
from .record_helpers import get_record_name
from ..build_plane_indexes import PlaneIndex
from ..normalize_observations import normalize_string


def expand_finance_to_include_all_vendor_records(
    finance_match: PlaneMatch,
    finance_index: PlaneIndex
) -> PlaneMatch:
    """
    Expand finance matches to include ALL records from the same vendor.

    When a finance match is found (e.g., contract for "Corespace"), this function
    gathers all other finance records (contracts AND transactions) with the same
    vendor name. This ensures that if any record has is_recurring=True, the asset
    will correctly get has_ongoing_finance=True.

    This is finance-specific to avoid impacting other planes' matching semantics.
    """
    if finance_match.status not in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
        return finance_match

    if not finance_match.matched_records:
        return finance_match

    vendor_names: set[str] = set()
    for record in finance_match.matched_records:
        if record is None:
            continue
        vendor = getattr(record, 'vendor_name', None)
        if vendor:
            vendor_names.add(normalize_string(vendor))

    if not vendor_names:
        return finance_match

    all_matched_ids: set[str] = set(finance_match.matched_ids)

    for vendor_name in vendor_names:
        for indexed_vendor, record_ids in finance_index.by_vendor_product.items():
            indexed_vendor_normalized = normalize_string(indexed_vendor)
            if indexed_vendor_normalized == vendor_name:
                all_matched_ids.update(record_ids)

        for indexed_name, record_ids in finance_index.by_canonical_name.items():
            indexed_name_normalized = normalize_string(indexed_name)
            if indexed_name_normalized == vendor_name:
                all_matched_ids.update(record_ids)

    all_matched_ids_list = list(all_matched_ids)
    all_records = [finance_index.records.get(mid) for mid in all_matched_ids_list]

    if len(all_matched_ids_list) == len(finance_match.matched_ids):
        return finance_match

    return PlaneMatch(
        status=finance_match.status,
        matched_ids=all_matched_ids_list,
        matched_records=all_records,
        match_method=finance_match.match_method,
        match_key=finance_match.match_key,
        ambiguity_code=finance_match.ambiguity_code,
        disambiguation_detail=f"{finance_match.disambiguation_detail or ''} [expanded from {len(finance_match.matched_ids)} to {len(all_matched_ids_list)} records via vendor match]".strip()
    )


# Alias with underscore prefix for backwards compatibility
_expand_finance_to_include_all_vendor_records = expand_finance_to_include_all_vendor_records
