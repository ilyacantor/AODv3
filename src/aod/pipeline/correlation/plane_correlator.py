"""Core plane correlation logic - matches entities to plane records."""

import logging
import re
from typing import Optional

from .constants import (
    MIN_TOKEN_LENGTH_FOR_MATCH,
    GENERIC_TOKENS,
    GENERIC_TOKENS_FOR_FINANCE,
    VENDOR_PREFIXES,
)
from .enums import MatchStatus, AmbiguityCode
from .result_types import PlaneMatch, RelatedDomainVariant, PrecomputedEntityData
from .string_matching import is_fuzzy_match
from .record_helpers import get_record_name, extract_domain_base_token
from .contains_matching import is_valid_contains_match
from .disambiguation import disambiguate_matches
from .debug import log_match_debug
from ..normalize_observations import CandidateEntity, normalize_string, normalize_domain
from ..build_plane_indexes import PlaneIndex
from ..vendor_inference import DOMAIN_TO_VENDOR, VENDOR_TO_DOMAIN
from ...utils.normalization import get_normalization_token

logger = logging.getLogger(__name__)


def correlate_to_plane(
    entity: CandidateEntity,
    plane_index: PlaneIndex,
    use_domain: bool = True,
    use_uri: bool = False,
    use_vendor: bool = False,
    precomputed: Optional[PrecomputedEntityData] = None,
    plane_name: str = "unknown"
) -> PlaneMatch:
    """
    Correlate an entity to a plane using multi-pass matching with disambiguation.

    Pass 1: Domain match (if applicable)
    Pass 2: Exact canonical normalized name match
    Pass 3: Unique contains match (strict; if >1 candidate → try disambiguate)
    Pass 4: Vendor match (last resort, PARENT_VENDOR if multiple)
    Pass 5: Domain-to-vendor match (for CMDB - use domain to find vendor, then match)

    When multiple matches occur, disambiguation logic attempts to resolve:
    - MULTI_ENV: Same app in different environments → pick prod
    - LEGACY: Current + deprecated → pick current
    - DUPLICATE: True duplicates → pick first
    - PARENT_VENDOR: Vendor-only match → treat as UNMATCHED

    Args:
        entity: The candidate entity to correlate
        plane_index: The index to search
        use_domain: Enable domain-based matching
        plane_name: Name of the plane being correlated (idp, cmdb, cloud, finance)
        use_uri: Enable URI-based matching
        use_vendor: Enable domain-to-vendor lookup for matching (useful for CMDB)
        precomputed: Pre-computed entity data to avoid repeated calculations

    Returns matched/ambiguous/unmatched plus evidence refs.
    """

    # ============================================================
    # Pass 1: Domain matching
    # ============================================================
    if use_domain and entity.domain and plane_index.by_domain:
        # Jan 2026 FIX: Try both exact domain AND registered domain (eTLD+1) lookup
        from ..vendor_inference import extract_registered_domain

        domain_matches = plane_index.by_domain.get(entity.domain, [])
        match_key_used = entity.domain

        # If exact lookup failed, try registered domain version
        if not domain_matches:
            entity_registered = extract_registered_domain(entity.domain)
            if entity_registered and entity_registered != entity.domain:
                domain_matches = plane_index.by_domain.get(entity_registered, [])
                match_key_used = entity_registered

        if len(domain_matches) == 1:
            log_match_debug(plane_name, "domain", entity.canonical_name, domain_matches[0])
            return PlaneMatch(
                status=MatchStatus.MATCHED,
                matched_ids=domain_matches,
                matched_records=[plane_index.records.get(mid) for mid in domain_matches],
                match_method="domain",
                match_key=match_key_used,
                ambiguity_code=AmbiguityCode.NONE
            )
        elif len(domain_matches) > 1:
            records = [plane_index.records.get(mid) for mid in domain_matches]
            code, detail, resolved = disambiguate_matches(entity, domain_matches, records, "domain")

            if resolved and len(resolved) == 1:
                log_match_debug(plane_name, "domain", entity.canonical_name, resolved[0])
                return PlaneMatch(
                    status=MatchStatus.MATCHED,
                    matched_ids=resolved,
                    matched_records=[plane_index.records.get(resolved[0])],
                    match_method="domain",
                    match_key=match_key_used,
                    ambiguity_code=code,
                    disambiguation_detail=detail
                )

            log_match_debug(plane_name, "domain", entity.canonical_name, ",".join(domain_matches))
            return PlaneMatch(
                status=MatchStatus.AMBIGUOUS,
                matched_ids=domain_matches,
                matched_records=records,
                match_method="domain",
                match_key=match_key_used,
                ambiguity_code=code,
                disambiguation_detail=detail
            )

    # ============================================================
    # Jan 2026 Phase B: CMDB Authoritative Recovery Paths
    # ============================================================
    if use_domain and entity.domain and plane_name == "cmdb":
        from ..vendor_inference import extract_registered_domain
        from ..canonical_key import ALIAS_DOMAINS_TO_COLLAPSE

        # Authoritative path 1: canonical_domain == D
        if hasattr(plane_index, 'by_canonical_domain') and plane_index.by_canonical_domain:
            canonical_matches = plane_index.by_canonical_domain.get(entity.domain, [])
            if not canonical_matches:
                entity_registered = extract_registered_domain(entity.domain)
                if entity_registered and entity_registered != entity.domain:
                    canonical_matches = plane_index.by_canonical_domain.get(entity_registered, [])

            if len(canonical_matches) == 1:
                log_match_debug(plane_name, "cmdb_canonical_domain", entity.canonical_name, canonical_matches[0])
                return PlaneMatch(
                    status=MatchStatus.MATCHED,
                    matched_ids=canonical_matches,
                    matched_records=[plane_index.records.get(mid) for mid in canonical_matches],
                    match_method="cmdb_canonical_domain",
                    match_key=entity.domain,
                    ambiguity_code=AmbiguityCode.NONE
                )
            elif len(canonical_matches) > 1:
                records = [plane_index.records.get(mid) for mid in canonical_matches]
                code, detail, resolved = disambiguate_matches(entity, canonical_matches, records, "cmdb_canonical_domain")
                if resolved and len(resolved) == 1:
                    log_match_debug(plane_name, "cmdb_canonical_domain", entity.canonical_name, resolved[0])
                    return PlaneMatch(
                        status=MatchStatus.MATCHED,
                        matched_ids=resolved,
                        matched_records=[plane_index.records.get(resolved[0])],
                        match_method="cmdb_canonical_domain",
                        match_key=entity.domain,
                        ambiguity_code=code,
                        disambiguation_detail=detail
                    )

        # Authoritative path 2: D ∈ domains[]
        if hasattr(plane_index, 'by_domains_array') and plane_index.by_domains_array:
            array_matches = plane_index.by_domains_array.get(entity.domain, [])
            if not array_matches:
                entity_registered = extract_registered_domain(entity.domain)
                if entity_registered and entity_registered != entity.domain:
                    array_matches = plane_index.by_domains_array.get(entity_registered, [])

            if len(array_matches) == 1:
                log_match_debug(plane_name, "cmdb_domains_array", entity.canonical_name, array_matches[0])
                return PlaneMatch(
                    status=MatchStatus.MATCHED,
                    matched_ids=array_matches,
                    matched_records=[plane_index.records.get(mid) for mid in array_matches],
                    match_method="cmdb_domains_array",
                    match_key=entity.domain,
                    ambiguity_code=AmbiguityCode.NONE
                )
            elif len(array_matches) > 1:
                records = [plane_index.records.get(mid) for mid in array_matches]
                code, detail, resolved = disambiguate_matches(entity, array_matches, records, "cmdb_domains_array")
                if resolved and len(resolved) == 1:
                    log_match_debug(plane_name, "cmdb_domains_array", entity.canonical_name, resolved[0])
                    return PlaneMatch(
                        status=MatchStatus.MATCHED,
                        matched_ids=resolved,
                        matched_records=[plane_index.records.get(resolved[0])],
                        match_method="cmdb_domains_array",
                        match_key=entity.domain,
                        ambiguity_code=code,
                        disambiguation_detail=detail
                    )

        # Authoritative path 3: verified_alias_domain(D) == canonical_domain
        if entity.domain in ALIAS_DOMAINS_TO_COLLAPSE:
            from ..canonical_key import normalize_to_canonical_vendor_domain
            alias_canonical = normalize_to_canonical_vendor_domain(entity.domain)
            if alias_canonical and hasattr(plane_index, 'by_canonical_domain') and plane_index.by_canonical_domain:
                alias_matches = plane_index.by_canonical_domain.get(alias_canonical, [])
                if len(alias_matches) == 1:
                    log_match_debug(plane_name, "verified_alias_domain", entity.canonical_name, alias_matches[0])
                    return PlaneMatch(
                        status=MatchStatus.MATCHED,
                        matched_ids=alias_matches,
                        matched_records=[plane_index.records.get(mid) for mid in alias_matches],
                        match_method="verified_alias_domain",
                        match_key=f"{entity.domain}→{alias_canonical}",
                        ambiguity_code=AmbiguityCode.NONE
                    )

    # ============================================================
    # Jan 2026 FIX: Additional domain fallback paths (HEURISTIC)
    # ============================================================
    if use_domain and plane_index.by_domain:
        from ..vendor_inference import extract_registered_domain
        domain_matches = []
        match_key_used = None
        match_method_used = "domain"

        # Fallback 1: canonical_name looks like a domain
        if not entity.domain and entity.canonical_name and '.' in entity.canonical_name:
            canonical_as_domain = entity.canonical_name.lower().strip()
            if re.match(r'^[a-z0-9][-a-z0-9]*(\.[a-z0-9][-a-z0-9]*)+$', canonical_as_domain):
                domain_matches = plane_index.by_domain.get(canonical_as_domain, [])
                if not domain_matches:
                    registered = extract_registered_domain(canonical_as_domain)
                    if registered and registered != canonical_as_domain:
                        domain_matches = plane_index.by_domain.get(registered, [])
                        match_key_used = registered
                    else:
                        match_key_used = canonical_as_domain
                else:
                    match_key_used = canonical_as_domain
                if domain_matches:
                    match_method_used = "canonical_name_as_domain"
                    logger.debug(
                        f"CANONICAL_NAME_AS_DOMAIN entity={entity.canonical_name} "
                        f"inferred_domain={canonical_as_domain} matches={len(domain_matches)}"
                    )

        # Fallback 2: domain token in by_name_words
        if not domain_matches and entity.domain and hasattr(plane_index, 'by_name_words') and plane_index.by_name_words:
            domain_token = entity.domain.split('.')[0].lower().strip() if '.' in entity.domain else None
            if domain_token and len(domain_token) >= 4:
                word_matches = plane_index.by_name_words.get(domain_token, [])
                if word_matches:
                    domain_matches = list(word_matches)
                    match_key_used = domain_token
                    match_method_used = "domain_token_to_name"
                    logger.debug(
                        f"DOMAIN_TOKEN_FALLBACK entity={entity.canonical_name} "
                        f"domain_token={domain_token} matches={len(domain_matches)}"
                    )

        # Fallback 3: registered domain token
        if not domain_matches and entity.domain and hasattr(plane_index, 'by_name_words') and plane_index.by_name_words:
            entity_registered = extract_registered_domain(entity.domain)
            if entity_registered:
                reg_token = entity_registered.split('.')[0].lower().strip() if '.' in entity_registered else None
                if reg_token and len(reg_token) >= 4:
                    word_matches = plane_index.by_name_words.get(reg_token, [])
                    if word_matches:
                        domain_matches = list(word_matches)
                        match_key_used = reg_token
                        match_method_used = "registered_domain_token"
                        logger.debug(
                            f"REGISTERED_TOKEN_FALLBACK entity={entity.canonical_name} "
                            f"reg_token={reg_token} matches={len(domain_matches)}"
                        )

        if len(domain_matches) == 1:
            log_match_debug(plane_name, match_method_used, entity.canonical_name, domain_matches[0])
            return PlaneMatch(
                status=MatchStatus.MATCHED,
                matched_ids=domain_matches,
                matched_records=[plane_index.records.get(mid) for mid in domain_matches],
                match_method=match_method_used,
                match_key=match_key_used,
                ambiguity_code=AmbiguityCode.NONE
            )
        elif len(domain_matches) > 1:
            records = [plane_index.records.get(mid) for mid in domain_matches]
            code, detail, resolved = disambiguate_matches(entity, domain_matches, records, match_method_used)

            if resolved and len(resolved) == 1:
                log_match_debug(plane_name, match_method_used, entity.canonical_name, resolved[0])
                return PlaneMatch(
                    status=MatchStatus.MATCHED,
                    matched_ids=resolved,
                    matched_records=[plane_index.records.get(resolved[0])],
                    match_method=match_method_used,
                    match_key=match_key_used,
                    ambiguity_code=code,
                    disambiguation_detail=detail
                )

            log_match_debug(plane_name, match_method_used, entity.canonical_name, ",".join(domain_matches))
            return PlaneMatch(
                status=MatchStatus.AMBIGUOUS,
                matched_ids=domain_matches,
                matched_records=records,
                match_method=match_method_used,
                match_key=match_key_used,
                ambiguity_code=code,
                disambiguation_detail=detail
            )

    # ============================================================
    # Pass 2: URI matching
    # ============================================================
    if use_uri and entity.uri and plane_index.by_uri:
        uri_matches = plane_index.by_uri.get(entity.uri.lower().strip(), [])
        if len(uri_matches) == 1:
            log_match_debug(plane_name, "uri", entity.canonical_name, uri_matches[0])
            return PlaneMatch(
                status=MatchStatus.MATCHED,
                matched_ids=uri_matches,
                matched_records=[plane_index.records.get(mid) for mid in uri_matches],
                match_method="uri",
                match_key=entity.uri,
                ambiguity_code=AmbiguityCode.NONE
            )
        elif len(uri_matches) > 1:
            records = [plane_index.records.get(mid) for mid in uri_matches]
            code, detail, resolved = disambiguate_matches(entity, uri_matches, records, "uri")

            if resolved and len(resolved) == 1:
                log_match_debug(plane_name, "uri", entity.canonical_name, resolved[0])
                return PlaneMatch(
                    status=MatchStatus.MATCHED,
                    matched_ids=resolved,
                    matched_records=[plane_index.records.get(resolved[0])],
                    match_method="uri",
                    match_key=entity.uri,
                    ambiguity_code=code,
                    disambiguation_detail=detail
                )

            log_match_debug(plane_name, "uri", entity.canonical_name, ",".join(uri_matches))
            return PlaneMatch(
                status=MatchStatus.AMBIGUOUS,
                matched_ids=uri_matches,
                matched_records=records,
                match_method="uri",
                match_key=entity.uri,
                ambiguity_code=code,
                disambiguation_detail=detail
            )

    # ============================================================
    # Pass 3: Canonical name matching
    # ============================================================
    canonical = entity.canonical_name
    name_matches = plane_index.by_canonical_name.get(canonical, [])

    # Jan 2026 FIX: Try domain base name if canonical_name fails
    domain_base_used = False
    domain_base = None
    if not name_matches and entity.domain:
        domain_base = entity.domain.split('.')[0].lower().strip() if '.' in entity.domain else None
        if domain_base and len(domain_base) >= 3:
            name_matches = plane_index.by_canonical_name.get(domain_base, [])
            if not name_matches and hasattr(plane_index, 'by_name_words') and plane_index.by_name_words:
                name_matches = list(plane_index.by_name_words.get(domain_base, []))
            if name_matches:
                domain_base_used = True
                logger.debug(
                    f"DOMAIN_BASE_NAME_MATCH entity={entity.canonical_name} "
                    f"domain_base={domain_base} matches={len(name_matches)}"
                )

    if name_matches and use_vendor:
        expected_vendor = None
        if precomputed and precomputed.canonical_vendor:
            expected_vendor = precomputed.canonical_vendor
        elif entity.domain:
            normalized_domain = normalize_domain(entity.domain) or entity.domain.lower().strip()
            expected_vendor = DOMAIN_TO_VENDOR.get(normalized_domain)
        if not expected_vendor:
            canonical_lower = entity.canonical_name.lower().strip()
            if canonical_lower in VENDOR_TO_DOMAIN:
                expected_vendor = canonical_lower.title()
        if expected_vendor:
            expected_vendor_normalized = normalize_string(expected_vendor)
            validated_matches = []
            for mid in name_matches:
                record = plane_index.records.get(mid)
                if record:
                    record_vendor = normalize_string(str(getattr(record, 'vendor', '') or ''))
                    if record_vendor and record_vendor == expected_vendor_normalized:
                        validated_matches.append(mid)
            name_matches = validated_matches

    effective_match_key = domain_base if domain_base_used else canonical

    if len(name_matches) == 1:
        log_match_debug(plane_name, "canonical_name", entity.canonical_name, name_matches[0])
        return PlaneMatch(
            status=MatchStatus.MATCHED,
            matched_ids=name_matches,
            matched_records=[plane_index.records.get(mid) for mid in name_matches],
            match_method="canonical_name",
            match_key=effective_match_key,
            ambiguity_code=AmbiguityCode.NONE
        )
    elif len(name_matches) > 1:
        records = [plane_index.records.get(mid) for mid in name_matches]
        code, detail, resolved = disambiguate_matches(entity, name_matches, records, "canonical_name")

        if resolved and len(resolved) == 1:
            log_match_debug(plane_name, "canonical_name", entity.canonical_name, resolved[0])
            return PlaneMatch(
                status=MatchStatus.MATCHED,
                matched_ids=resolved,
                matched_records=[plane_index.records.get(resolved[0])],
                match_method="canonical_name",
                match_key=effective_match_key,
                ambiguity_code=code,
                disambiguation_detail=detail
            )

        log_match_debug(plane_name, "canonical_name", entity.canonical_name, ",".join(name_matches))
        return PlaneMatch(
            status=MatchStatus.AMBIGUOUS,
            matched_ids=name_matches,
            matched_records=records,
            match_method="canonical_name",
            match_key=effective_match_key,
            ambiguity_code=code,
            disambiguation_detail=detail
        )

    # ============================================================
    # Pass 4: Fuzzy matching
    # ============================================================
    fuzzy_matches: list[str] = []
    if len(canonical) >= 4 and hasattr(plane_index, 'by_name_prefix'):
        prefix = canonical[:4]
        prefix_candidates = set(plane_index.by_name_prefix.get(prefix, []))
        for candidate_id in prefix_candidates:
            record = plane_index.records.get(candidate_id)
            if record:
                record_name = normalize_string(get_record_name(record))
                if is_fuzzy_match(canonical, record_name):
                    if candidate_id not in fuzzy_matches:
                        fuzzy_matches.append(candidate_id)
    else:
        for indexed_name, record_ids in plane_index.by_canonical_name.items():
            if is_fuzzy_match(canonical, indexed_name):
                fuzzy_matches.extend(record_ids)

    fuzzy_matches = list(set(fuzzy_matches))

    if len(fuzzy_matches) == 1:
        return PlaneMatch(
            status=MatchStatus.MATCHED,
            matched_ids=fuzzy_matches,
            matched_records=[plane_index.records.get(mid) for mid in fuzzy_matches],
            match_method="fuzzy",
            match_key=canonical,
            ambiguity_code=AmbiguityCode.NONE
        )
    elif len(fuzzy_matches) > 1:
        records = [plane_index.records.get(mid) for mid in fuzzy_matches]
        code, detail, resolved = disambiguate_matches(entity, fuzzy_matches, records, "fuzzy")

        if resolved and len(resolved) == 1:
            return PlaneMatch(
                status=MatchStatus.MATCHED,
                matched_ids=resolved,
                matched_records=[plane_index.records.get(resolved[0])],
                match_method="fuzzy",
                match_key=canonical,
                ambiguity_code=code,
                disambiguation_detail=detail
            )

        return PlaneMatch(
            status=MatchStatus.AMBIGUOUS,
            matched_ids=fuzzy_matches,
            matched_records=records,
            match_method="fuzzy",
            match_key=canonical,
            ambiguity_code=code,
            disambiguation_detail=detail
        )

    # ============================================================
    # Pass 5: Contains matching with cross-TLD handling
    # ============================================================
    contains_matches: list[str] = []
    cross_tld_variants: list[RelatedDomainVariant] = []

    if hasattr(plane_index, 'by_name_words') and plane_index.by_name_words:
        canonical_words = {w for w in re.split(r'[\s\-_./]+', canonical) if len(w) >= 4}
        candidate_ids = set()
        for word in canonical_words:
            candidate_ids.update(plane_index.by_name_words.get(word, []))
        for candidate_id in candidate_ids:
            record = plane_index.records.get(candidate_id)
            if record:
                record_name = normalize_string(get_record_name(record))
                record_domain = getattr(record, 'domain', None)
                if not record_domain:
                    raw_data = getattr(record, 'raw_data', None)
                    if raw_data and isinstance(raw_data, dict):
                        record_domain = raw_data.get('domain')
                record_domain_normalized = normalize_string(record_domain) if record_domain else ""

                name_match = is_valid_contains_match(canonical, record_name)
                domain_match = record_domain_normalized and canonical in record_domain_normalized

                # TLD VARIANT FIX: Cross-domain brand matching
                cross_tld_match_basis = None
                if not name_match and not domain_match and record_domain:
                    entity_domain = getattr(entity, 'domain', None) or ""
                    if entity_domain and '.' in entity_domain and '.' in record_domain:
                        from ..vendor_inference import extract_registered_domain
                        entity_registered = extract_registered_domain(entity_domain)
                        record_registered = extract_registered_domain(record_domain)

                        if entity_registered and record_registered and entity_registered != record_registered:
                            entity_label = entity_domain.lower().split('.')[0]
                            record_label = record_domain.lower().split('.')[0]

                            entity_first = re.split(r'[\-_]+', entity_label)[0]
                            record_first = re.split(r'[\-_]+', record_label)[0]
                            entity_collapsed = re.sub(r'[\-_]', '', entity_label)
                            record_collapsed = re.sub(r'[\-_]', '', record_label)

                            first_match = len(entity_first) >= 4 and entity_first == record_first
                            collapsed_match = len(entity_collapsed) >= 4 and entity_collapsed == record_collapsed

                            if first_match:
                                cross_tld_match_basis = "first_token"
                            elif collapsed_match:
                                cross_tld_match_basis = "collapsed_brand"

                            if cross_tld_match_basis:
                                cross_tld_variants.append(RelatedDomainVariant(
                                    entity_domain=entity_registered,
                                    related_domain=record_registered,
                                    match_basis=cross_tld_match_basis,
                                    record_id=candidate_id,
                                    plane=plane_name
                                ))
                                logger.debug(
                                    f"CROSS_TLD_VARIANT_RECORDED entity={entity_registered} "
                                    f"related={record_registered} basis={cross_tld_match_basis} "
                                    f"record_id={candidate_id} (NOT identity merge)"
                                )
                                continue

                # Finance token matching
                token_match = False
                if not name_match and not domain_match:
                    from ...models.input_contracts import Transaction, Contract
                    if isinstance(record, (Transaction, Contract)):
                        entity_domain = getattr(entity, 'domain', None) or ""
                        domain_base_token = None
                        if entity_domain and '.' in entity_domain:
                            domain_parts = entity_domain.lower().split('.')
                            if len(domain_parts) >= 2:
                                domain_base_token = re.sub(r'[\-_]', '', domain_parts[0])
                                if domain_base_token in GENERIC_TOKENS or len(domain_base_token) < MIN_TOKEN_LENGTH_FOR_MATCH:
                                    domain_base_token = None

                        if domain_base_token:
                            vendor_tokens = [re.sub(r'[\-_]', '', w.lower()) for w in re.split(r'[\s\-_./]+', record_name) if len(w) >= 2]
                            primary_brand_token = None
                            for vt in vendor_tokens:
                                if vt not in VENDOR_PREFIXES and len(vt) >= 3:
                                    primary_brand_token = vt
                                    break
                            token_match = primary_brand_token and domain_base_token == primary_brand_token

                if name_match or domain_match or token_match:
                    if candidate_id not in contains_matches:
                        contains_matches.append(candidate_id)
    else:
        for indexed_name, record_ids in plane_index.by_canonical_name.items():
            if is_valid_contains_match(canonical, indexed_name):
                contains_matches.extend(record_ids)

    contains_matches = list(set(contains_matches))

    if len(contains_matches) == 1:
        return PlaneMatch(
            status=MatchStatus.MATCHED,
            matched_ids=contains_matches,
            matched_records=[plane_index.records.get(mid) for mid in contains_matches],
            match_method="contains",
            match_key=canonical,
            ambiguity_code=AmbiguityCode.NONE,
            related_domain_variants=cross_tld_variants
        )
    elif len(contains_matches) > 1:
        records = [plane_index.records.get(mid) for mid in contains_matches]
        code, detail, resolved = disambiguate_matches(entity, contains_matches, records, "contains")

        if resolved and len(resolved) == 1:
            return PlaneMatch(
                status=MatchStatus.MATCHED,
                matched_ids=resolved,
                matched_records=[plane_index.records.get(resolved[0])],
                match_method="contains",
                match_key=canonical,
                ambiguity_code=code,
                disambiguation_detail=detail,
                related_domain_variants=cross_tld_variants
            )

        return PlaneMatch(
            status=MatchStatus.AMBIGUOUS,
            matched_ids=contains_matches,
            matched_records=records,
            match_method="contains",
            match_key=canonical,
            ambiguity_code=code,
            disambiguation_detail=detail,
            related_domain_variants=cross_tld_variants
        )

    if cross_tld_variants:
        return PlaneMatch(
            status=MatchStatus.UNMATCHED,
            related_domain_variants=cross_tld_variants
        )

    # ============================================================
    # Pass 6: Domain token matching
    # ============================================================
    if entity.domain and plane_index.by_canonical_name:
        domain_token = precomputed.domain_token if precomputed else ""
        if not domain_token:
            raw_domain_token = extract_domain_base_token(entity.domain)
            domain_token = normalize_string(raw_domain_token) if raw_domain_token else ""
        if domain_token and len(domain_token) >= 6:
            token_matches: list[str] = []
            if hasattr(plane_index, 'by_name_words') and domain_token in plane_index.by_name_words:
                token_matches = list(plane_index.by_name_words[domain_token])
            else:
                for indexed_name, record_ids in plane_index.by_canonical_name.items():
                    if domain_token in indexed_name:
                        token_matches.extend(record_ids)

            token_matches = list(set(token_matches))

            if len(token_matches) == 1:
                return PlaneMatch(
                    status=MatchStatus.MATCHED,
                    matched_ids=token_matches,
                    matched_records=[plane_index.records.get(mid) for mid in token_matches],
                    match_method="name_contains_domain_token",
                    match_key=domain_token,
                    ambiguity_code=AmbiguityCode.NONE
                )
            elif len(token_matches) > 1:
                records = [plane_index.records.get(mid) for mid in token_matches]
                code, detail, resolved = disambiguate_matches(entity, token_matches, records, "name_contains_domain_token")

                if resolved and len(resolved) == 1:
                    return PlaneMatch(
                        status=MatchStatus.MATCHED,
                        matched_ids=resolved,
                        matched_records=[plane_index.records.get(resolved[0])],
                        match_method="name_contains_domain_token",
                        match_key=domain_token,
                        ambiguity_code=code,
                        disambiguation_detail=detail
                    )

                return PlaneMatch(
                    status=MatchStatus.AMBIGUOUS,
                    matched_ids=token_matches,
                    matched_records=records,
                    match_method="name_contains_domain_token",
                    match_key=domain_token,
                    ambiguity_code=code,
                    disambiguation_detail=detail
                )

    # ============================================================
    # Pass 7: Vendor matching
    # ============================================================
    if entity.vendor and plane_index.by_vendor_product:
        vendor_key = normalize_string(entity.vendor)
        vendor_matches = plane_index.by_vendor_product.get(vendor_key, [])

        if len(vendor_matches) == 1:
            matched_record = plane_index.records.get(vendor_matches[0])
            matched_name = normalize_string(get_record_name(matched_record)) if matched_record else ""
            entity_name = entity.canonical_name

            if matched_name == entity_name or matched_name in entity_name or entity_name in matched_name:
                return PlaneMatch(
                    status=MatchStatus.MATCHED,
                    matched_ids=vendor_matches,
                    matched_records=[matched_record],
                    match_method="vendor",
                    match_key=entity.vendor,
                    ambiguity_code=AmbiguityCode.NONE
                )
        elif len(vendor_matches) > 1:
            records = [plane_index.records.get(mid) for mid in vendor_matches]
            code, detail, resolved = disambiguate_matches(entity, vendor_matches, records, "vendor")

            if resolved and len(resolved) == 1:
                return PlaneMatch(
                    status=MatchStatus.MATCHED,
                    matched_ids=resolved,
                    matched_records=[plane_index.records.get(resolved[0])],
                    match_method="vendor",
                    match_key=entity.vendor,
                    ambiguity_code=code,
                    disambiguation_detail=detail
                )

            return PlaneMatch(
                status=MatchStatus.AMBIGUOUS,
                matched_ids=vendor_matches,
                matched_records=records,
                match_method="vendor",
                match_key=entity.vendor,
                ambiguity_code=code,
                disambiguation_detail=detail
            )

    # ============================================================
    # Pass 8: Domain-to-vendor matching
    # ============================================================
    if use_vendor and entity.domain and plane_index.by_vendor_product:
        domain_vendor = precomputed.canonical_vendor if precomputed else None
        if not domain_vendor:
            entity_normalized_domain = normalize_domain(entity.domain) or entity.domain.lower().strip()
            domain_vendor = DOMAIN_TO_VENDOR.get(entity_normalized_domain)
            if not domain_vendor and entity_normalized_domain != entity.domain.lower().strip():
                domain_vendor = DOMAIN_TO_VENDOR.get(entity.domain.lower().strip())
        if domain_vendor:
            vendor_key = normalize_string(domain_vendor)
            vendor_matches = plane_index.by_vendor_product.get(vendor_key, [])

            if len(vendor_matches) >= 1:
                records = [plane_index.records.get(mid) for mid in vendor_matches]
                matching_ids = []
                matching_records = []

                for idx, record in enumerate(records):
                    if record:
                        record_name = normalize_string(get_record_name(record))
                        entity_name = entity.canonical_name
                        if record_name == entity_name or record_name in entity_name or entity_name in record_name:
                            matching_ids.append(vendor_matches[idx])
                            matching_records.append(record)

                if len(matching_ids) == 1:
                    return PlaneMatch(
                        status=MatchStatus.MATCHED,
                        matched_ids=matching_ids,
                        matched_records=matching_records,
                        match_method="domain_vendor",
                        match_key=domain_vendor,
                        ambiguity_code=AmbiguityCode.NONE
                    )
                elif len(matching_ids) > 1:
                    code, detail, resolved = disambiguate_matches(entity, matching_ids, matching_records, "domain_vendor")
                    if resolved and len(resolved) == 1:
                        return PlaneMatch(
                            status=MatchStatus.MATCHED,
                            matched_ids=resolved,
                            matched_records=[plane_index.records.get(resolved[0])],
                            match_method="domain_vendor",
                            match_key=domain_vendor,
                            ambiguity_code=code,
                            disambiguation_detail=detail
                        )
                    return PlaneMatch(
                        status=MatchStatus.AMBIGUOUS,
                        matched_ids=matching_ids,
                        matched_records=matching_records,
                        match_method="domain_vendor",
                        match_key=domain_vendor,
                        ambiguity_code=code,
                        disambiguation_detail=detail
                    )

    # ============================================================
    # Pass 9: Vendor fallback
    # ============================================================
    if use_vendor and entity.vendor and plane_index.by_vendor_product:
        entity_vendor_key = normalize_string(entity.vendor)
        vendor_matches = plane_index.by_vendor_product.get(entity_vendor_key, [])

        if len(vendor_matches) >= 1:
            exact_in_vendor = []
            for mid in vendor_matches:
                record = plane_index.records.get(mid)
                if record and normalize_string(get_record_name(record)) == entity.canonical_name:
                    exact_in_vendor.append(mid)

            if len(exact_in_vendor) == 1:
                return PlaneMatch(
                    status=MatchStatus.MATCHED,
                    matched_ids=exact_in_vendor,
                    matched_records=[plane_index.records.get(exact_in_vendor[0])],
                    match_method="vendor_fallback",
                    match_key=entity.vendor,
                    ambiguity_code=AmbiguityCode.NONE
                )

            if len(vendor_matches) == 1:
                return PlaneMatch(
                    status=MatchStatus.MATCHED,
                    matched_ids=vendor_matches,
                    matched_records=[plane_index.records.get(vendor_matches[0])],
                    match_method="vendor_fallback",
                    match_key=entity.vendor,
                    ambiguity_code=AmbiguityCode.NONE
                )

            records = [plane_index.records.get(mid) for mid in vendor_matches]
            code, detail, resolved = disambiguate_matches(entity, vendor_matches, records, "vendor_fallback")

            if resolved and len(resolved) == 1:
                return PlaneMatch(
                    status=MatchStatus.MATCHED,
                    matched_ids=resolved,
                    matched_records=[plane_index.records.get(resolved[0])],
                    match_method="vendor_fallback",
                    match_key=entity.vendor,
                    ambiguity_code=code,
                    disambiguation_detail=detail
                )

            return PlaneMatch(
                status=MatchStatus.MATCHED,
                matched_ids=[vendor_matches[0]],
                matched_records=[plane_index.records.get(vendor_matches[0])],
                match_method="vendor_fallback",
                match_key=entity.vendor,
                ambiguity_code=AmbiguityCode.PARENT_VENDOR,
                disambiguation_detail=f"Vendor-only match: {entity.vendor}"
            )

    # ============================================================
    # Pass 10: Normalization token matching
    # ============================================================
    entity_token = precomputed.normalization_token if precomputed else ""
    if not entity_token:
        entity_token = get_normalization_token(entity.canonical_name)
        if not entity_token and entity.domain:
            entity_token = get_normalization_token(entity.domain)

    # Skip for finance plane with generic/short tokens
    is_finance_plane = hasattr(plane_index, 'by_name_words')
    skip_token_match = is_finance_plane and (entity_token in GENERIC_TOKENS_FOR_FINANCE or len(entity_token) < MIN_TOKEN_LENGTH_FOR_MATCH)

    if entity_token and len(entity_token) >= 3 and not skip_token_match:
        token_matches: list[str] = []
        matched_vendor_tokens: set[str] = set()

        for record_id, record in plane_index.records.items():
            record_name = get_record_name(record)
            record_vendor = get_record_vendor(record)

            record_name_token = get_normalization_token(record_name) if record_name else ""
            record_vendor_token = get_normalization_token(record_vendor) if record_vendor else ""

            if entity_token == record_name_token or entity_token == record_vendor_token:
                token_matches.append(record_id)
                if record_vendor_token:
                    matched_vendor_tokens.add(record_vendor_token)
                elif record_name_token:
                    matched_vendor_tokens.add(record_name_token)

        token_matches = list(set(token_matches))

        if len(token_matches) >= 1 and len(matched_vendor_tokens) == 1:
            return PlaneMatch(
                status=MatchStatus.MATCHED,
                matched_ids=token_matches,
                matched_records=[plane_index.records.get(mid) for mid in token_matches],
                match_method="normalization_token",
                match_key=entity_token,
                ambiguity_code=AmbiguityCode.NONE
            )
        elif len(token_matches) > 1 and len(matched_vendor_tokens) > 1:
            pass  # Multiple vendors matched - don't match

    return PlaneMatch(status=MatchStatus.UNMATCHED)


def get_record_vendor(record) -> str:
    """Extract vendor from a record (handles dict or object)."""
    if record is None:
        return ""
    if isinstance(record, dict):
        return record.get("vendor", "") or ""
    return getattr(record, "vendor", "") or ""
