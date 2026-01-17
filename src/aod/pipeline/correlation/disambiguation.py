"""Disambiguation logic for resolving multiple matches."""

from typing import Optional, Any

from .enums import AmbiguityCode
from .record_helpers import (
    extract_base_name,
    get_record_name,
    get_record_vendor,
    get_record_field,
    is_deprecated_by_field,
    get_environment_field,
)
from ..normalize_observations import CandidateEntity, normalize_string
from ...models.input_contracts import PlaneRecord


def disambiguate_matches(
    entity: CandidateEntity,
    matched_ids: list[str],
    matched_records: list[PlaneRecord],
    match_method: str
) -> tuple[AmbiguityCode, Optional[str], Optional[list[str]]]:
    """
    Analyze multiple matches and attempt to disambiguate using EVIDENCE from record fields.

    PRINCIPLE: Resolve only when CMDB fields support it; otherwise keep AMBIGUOUS.

    Evidence-driven resolution:
    - MULTI_ENV: Only if `environment` field differs between records
    - LEGACY: Only if `status`, `is_deprecated`, or `lifecycle_state` indicates deprecated
    - DUPLICATE: Only if records have identical key fields
    - PARENT_VENDOR: Vendor-only match with no product match

    Returns:
        Tuple of (ambiguity_code, detail_message, resolved_ids)
        - resolved_ids is None if ambiguity cannot be resolved
        - resolved_ids is a single-element list if disambiguation succeeded
    """
    if len(matched_ids) <= 1:
        return AmbiguityCode.NONE, None, matched_ids

    if match_method == "vendor":
        names = [get_record_name(r) for r in matched_records]
        entity_base = extract_base_name(entity.canonical_name)

        exact_matches = []
        for i, record in enumerate(matched_records):
            record_base = extract_base_name(get_record_name(record))
            if record_base == entity_base:
                exact_matches.append(matched_ids[i])

        if len(exact_matches) == 1:
            return AmbiguityCode.NONE, f"Vendor match refined by name: {entity_base}", exact_matches

        return (
            AmbiguityCode.PARENT_VENDOR,
            f"Matched vendor only, not specific product. Records: {names}",
            None
        )

    deprecated_records = []
    active_records = []
    for i, record in enumerate(matched_records):
        if is_deprecated_by_field(record):
            deprecated_records.append((matched_ids[i], get_record_name(record), record))
        else:
            active_records.append((matched_ids[i], get_record_name(record), record))

    if deprecated_records and active_records and len(active_records) == 1:
        best = active_records[0]
        deprecated_names = [r[1] for r in deprecated_records]
        return (
            AmbiguityCode.LEGACY,
            f"Evidence: picked active '{best[1]}' (status field) over deprecated: {deprecated_names}",
            [best[0]]
        )

    env_groups: dict[str, list[tuple[str, str, Any]]] = {}
    records_with_env = 0
    for i, record in enumerate(matched_records):
        env = get_environment_field(record)
        if env:
            records_with_env += 1
            if env not in env_groups:
                env_groups[env] = []
            env_groups[env].append((matched_ids[i], get_record_name(record), record))

    if records_with_env == len(matched_records) and len(env_groups) > 1:
        prod_envs = {"prod", "production", "prd", "live"}
        for env_name in prod_envs:
            if env_name in env_groups and len(env_groups[env_name]) == 1:
                best = env_groups[env_name][0]
                other_envs = [e for e in env_groups.keys() if e not in prod_envs]
                return (
                    AmbiguityCode.MULTI_ENV,
                    f"Evidence: picked prod '{best[1]}' (environment={env_name}) over envs: {other_envs}",
                    [best[0]]
                )

        all_names = [get_record_name(r) for r in matched_records]
        return (
            AmbiguityCode.UNRESOLVED,
            f"Multiple environments but no single prod: {list(env_groups.keys())}. Records: {all_names}",
            None
        )

    def get_identity_tuple(record: PlaneRecord) -> tuple:
        return (
            normalize_string(get_record_name(record)),
            normalize_string(get_record_vendor(record) or ""),
            normalize_string(str(get_record_field(record, "app_type", "") or "")),
        )

    identities = [get_identity_tuple(r) for r in matched_records]
    if len(set(identities)) == 1:
        return (
            AmbiguityCode.DUPLICATE,
            f"Evidence: true duplicates (identical name/vendor/type), picked first",
            [matched_ids[0]]
        )

    all_names = [get_record_name(r) for r in matched_records]
    return (
        AmbiguityCode.UNRESOLVED,
        f"No field-level evidence to disambiguate: {all_names}",
        None
    )
