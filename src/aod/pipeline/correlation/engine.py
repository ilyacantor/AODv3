"""Main correlation engine - coordinates entity correlation across all planes."""

import logging
import time

from .enums import MatchStatus
from .result_types import CorrelationResult, PrecomputedEntityData
from .plane_correlator import correlate_to_plane
from .domain_recovery import recover_domain_from_planes
from .finance_expander import expand_finance_to_include_all_vendor_records
from .record_helpers import extract_domain_base_token
from ..normalize_observations import CandidateEntity, normalize_string, normalize_domain
from ..build_plane_indexes import PlaneIndexes
from ..vendor_inference import DOMAIN_TO_VENDOR
from ...utils.normalization import get_normalization_token

logger = logging.getLogger(__name__)


def precompute_entity_data(entity: CandidateEntity) -> PrecomputedEntityData:
    """
    Pre-compute normalized tokens and lookups for an entity.

    This avoids repeated calls to expensive normalization functions
    when correlating the same entity across multiple planes.
    """
    data = PrecomputedEntityData()

    if entity.domain:
        domain_normalized = normalize_domain(entity.domain) or entity.domain.lower().strip()
        data.registered_domain = domain_normalized
        data.domain_token = normalize_string(extract_domain_base_token(entity.domain))

        if data.registered_domain:
            data.canonical_vendor = DOMAIN_TO_VENDOR.get(data.registered_domain)
        if not data.canonical_vendor:
            data.canonical_vendor = DOMAIN_TO_VENDOR.get(entity.domain.lower().strip())

    data.normalization_token = get_normalization_token(entity.canonical_name)
    if not data.normalization_token and entity.domain:
        data.normalization_token = get_normalization_token(entity.domain)

    return data


def correlate_entities_to_planes(
    entities: list[CandidateEntity],
    indexes: PlaneIndexes
) -> list[CorrelationResult]:
    """
    Correlate all entities to all planes with disambiguation.

    Per plane, per entity:
    - Pass 1: domain match (if applicable)
    - Pass 2: exact canonical normalized name match
    - Pass 3: unique contains match
    - Pass 4: vendor match (with PARENT_VENDOR detection)

    When multiple matches occur, disambiguation attempts to resolve to single match.
    PARENT_VENDOR matches are treated as UNMATCHED (not specific enough).

    Returns matched/ambiguous/unmatched plus evidence refs.
    No shared IDs across planes. No truth keys.

    Args:
        entities: Candidate entities from normalization stage
        indexes: Plane indexes from indexing stage

    Returns:
        List of correlation results for each entity
    """
    t_total_start = time.perf_counter()

    logger.info("correlate_entities.start", extra={
        "entity_count": len(entities),
        "idp_records": len(indexes.idp.by_canonical_name),
        "cmdb_records": len(indexes.cmdb.by_canonical_name),
        "cloud_records": len(indexes.cloud.by_canonical_name),
        "finance_records": len(indexes.finance.by_canonical_name)
    })

    t_precompute_start = time.perf_counter()
    sorted_entities = sorted(entities, key=lambda e: e.entity_id)
    precomputed = {e.entity_id: precompute_entity_data(e) for e in sorted_entities}
    t_precompute = time.perf_counter() - t_precompute_start

    results = []
    matched_counts = {"idp": 0, "cmdb": 0, "cloud": 0, "finance": 0}
    ambiguous_counts = {"idp": 0, "cmdb": 0, "cloud": 0, "finance": 0}

    t_idp, t_cmdb, t_cloud, t_finance = 0.0, 0.0, 0.0, 0.0

    for entity in sorted_entities:
        result = CorrelationResult(entity=entity)
        entity_precomputed = precomputed[entity.entity_id]

        t_start = time.perf_counter()
        result.idp = correlate_to_plane(entity, indexes.idp, use_domain=True, use_vendor=True, precomputed=entity_precomputed, plane_name="idp")
        t_idp += time.perf_counter() - t_start

        t_start = time.perf_counter()
        result.cmdb = correlate_to_plane(entity, indexes.cmdb, use_domain=True, use_vendor=True, precomputed=entity_precomputed, plane_name="cmdb")
        t_cmdb += time.perf_counter() - t_start

        t_start = time.perf_counter()
        result.cloud = correlate_to_plane(entity, indexes.cloud, use_domain=False, use_uri=True, precomputed=entity_precomputed, plane_name="cloud")
        t_cloud += time.perf_counter() - t_start

        t_start = time.perf_counter()
        result.finance = correlate_to_plane(entity, indexes.finance, use_domain=False, precomputed=entity_precomputed, plane_name="finance")
        result.finance = expand_finance_to_include_all_vendor_records(result.finance, indexes.finance)
        t_finance += time.perf_counter() - t_start

        if result.idp.status == MatchStatus.MATCHED:
            matched_counts["idp"] += 1
        elif result.idp.status == MatchStatus.AMBIGUOUS:
            ambiguous_counts["idp"] += 1

        if result.cmdb.status == MatchStatus.MATCHED:
            matched_counts["cmdb"] += 1
        elif result.cmdb.status == MatchStatus.AMBIGUOUS:
            ambiguous_counts["cmdb"] += 1

        if result.cloud.status == MatchStatus.MATCHED:
            matched_counts["cloud"] += 1
        elif result.cloud.status == MatchStatus.AMBIGUOUS:
            ambiguous_counts["cloud"] += 1

        if result.finance.status == MatchStatus.MATCHED:
            matched_counts["finance"] += 1
        elif result.finance.status == MatchStatus.AMBIGUOUS:
            ambiguous_counts["finance"] += 1

        if not entity.domain:
            recovered_domain = recover_domain_from_planes(result)
            if recovered_domain:
                entity.domain = recovered_domain
                entity.entity_id = f"entity:{recovered_domain}"
                entity.canonical_name = recovered_domain
                logger.debug("correlate_entities.domain_recovered", extra={
                    "original_name": entity.original_name,
                    "recovered_domain": recovered_domain
                })

        results.append(result)

    t_total = time.perf_counter() - t_total_start

    logger.info("correlate_entities.complete", extra={
        "entity_count": len(entities), "result_count": len(results),
        "matched_idp": matched_counts["idp"], "matched_cmdb": matched_counts["cmdb"],
        "matched_cloud": matched_counts["cloud"], "matched_finance": matched_counts["finance"],
        "ambiguous_idp": ambiguous_counts["idp"], "ambiguous_cmdb": ambiguous_counts["cmdb"],
        "ambiguous_cloud": ambiguous_counts["cloud"], "ambiguous_finance": ambiguous_counts["finance"],
        "timing_precompute_sec": round(t_precompute, 4),
        "timing_idp_sec": round(t_idp, 4),
        "timing_cmdb_sec": round(t_cmdb, 4),
        "timing_cloud_sec": round(t_cloud, 4),
        "timing_finance_sec": round(t_finance, 4),
        "timing_total_sec": round(t_total, 4)
    })

    return results


# Alias with underscore prefix for backwards compatibility
_precompute_entity_data = precompute_entity_data
