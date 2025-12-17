"""Stage 4: CorrelateEntitiesToPlanes - Real-world simple matcher with disambiguation"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from .normalize_observations import CandidateEntity, normalize_string
from .build_plane_indexes import PlaneIndexes, PlaneIndex


class MatchStatus(str, Enum):
    """Match status for correlation"""
    MATCHED = "matched"
    AMBIGUOUS = "ambiguous"
    UNMATCHED = "unmatched"


class AmbiguityCode(str, Enum):
    """Disambiguation codes explaining why multiple matches occurred"""
    NONE = "NONE"                    # Single clear match
    MULTI_ENV = "MULTI_ENV"          # Same app in dev/staging/prod CIs
    LEGACY = "LEGACY"                # Old/deprecated CI alongside current
    DUPLICATE = "DUPLICATE"          # True duplicate records
    PARENT_VENDOR = "PARENT_VENDOR"  # Matched parent vendor, not product
    UNRESOLVED = "UNRESOLVED"        # Multiple matches, couldn't disambiguate


ENV_SUFFIXES = {
    "prod", "production", "prd",
    "dev", "development", 
    "staging", "stg", "stage",
    "test", "testing", "tst",
    "uat", "qa",
    "sandbox", "sbx",
    "demo"
}

LEGACY_MARKERS = {
    "legacy", "old", "deprecated", "v1", "v2", "archive", "archived",
    "retired", "obsolete", "backup", "previous"
}


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        s1, s2 = s2, s1
    
    if len(s2) == 0:
        return len(s1)
    
    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    
    return prev_row[-1]


def _is_fuzzy_match(name1: str, name2: str, max_distance: int = 2) -> bool:
    """
    Check if two names are a fuzzy match (typo tolerance).
    
    Handles cases like:
    - "monday" vs "mondayc" (truncation/typo)
    - "monday" vs "monady" (transposition)
    
    Rules:
    - Names must be at least 4 chars to avoid false positives
    - One must be a prefix of the other with ≤2 extra chars, OR
    - Edit distance ≤ max_distance for similar-length names
    """
    if len(name1) < 4 or len(name2) < 4:
        return False
    
    if name1.startswith(name2) and len(name1) - len(name2) <= 2:
        return True
    if name2.startswith(name1) and len(name2) - len(name1) <= 2:
        return True
    
    len_diff = abs(len(name1) - len(name2))
    if len_diff <= 2:
        distance = _levenshtein_distance(name1, name2)
        return distance <= max_distance
    
    return False


@dataclass
class PlaneMatch:
    """Match result for a single plane"""
    status: MatchStatus
    matched_ids: list[str] = field(default_factory=list)
    matched_records: list[Any] = field(default_factory=list)
    match_method: Optional[str] = None
    ambiguity_code: AmbiguityCode = AmbiguityCode.NONE
    disambiguation_detail: Optional[str] = None


@dataclass
class CorrelationResult:
    """Correlation result for an entity across all planes"""
    entity: CandidateEntity
    idp: PlaneMatch = field(default_factory=lambda: PlaneMatch(status=MatchStatus.UNMATCHED))
    cmdb: PlaneMatch = field(default_factory=lambda: PlaneMatch(status=MatchStatus.UNMATCHED))
    cloud: PlaneMatch = field(default_factory=lambda: PlaneMatch(status=MatchStatus.UNMATCHED))
    finance: PlaneMatch = field(default_factory=lambda: PlaneMatch(status=MatchStatus.UNMATCHED))
    
    def all_evidence_refs(self) -> list[str]:
        """Get all evidence references from matched planes"""
        refs = list(self.entity.observation_ids)
        for plane_match in [self.idp, self.cmdb, self.cloud, self.finance]:
            if plane_match.status == MatchStatus.MATCHED:
                refs.extend(plane_match.matched_ids)
        return refs


def _extract_base_name(name: str) -> str:
    """Extract base name by stripping environment suffixes and legacy markers."""
    normalized = normalize_string(name)
    
    for suffix in ENV_SUFFIXES | LEGACY_MARKERS:
        patterns = [
            rf"[-_]?{suffix}[-_]?$",
            rf"^{suffix}[-_]",
            rf"[-_]{suffix}[-_]",
        ]
        for pattern in patterns:
            normalized = re.sub(pattern, "", normalized, flags=re.IGNORECASE)
    
    return normalized.strip("-_")


def _is_legacy_name(name: str) -> bool:
    """Check if a name contains legacy/deprecated markers."""
    normalized = name.lower()
    return any(marker in normalized for marker in LEGACY_MARKERS)


def _get_record_name(record: Any) -> str:
    """Extract name from a record (handles dict or object).
    
    For finance records (Contract, Transaction), also checks the 'product' field
    since that's where the product name is stored (e.g., "Slack" in a Salesforce contract).
    """
    if record is None:
        return ""
    if isinstance(record, dict):
        return record.get("name", "") or record.get("app_name", "") or record.get("product", "") or ""
    return getattr(record, "name", "") or getattr(record, "app_name", "") or getattr(record, "product", "") or ""


def _get_record_vendor(record: Any) -> str:
    """Extract vendor from a record (handles dict or object)."""
    if record is None:
        return ""
    if isinstance(record, dict):
        return record.get("vendor", "") or ""
    return getattr(record, "vendor", "") or ""


KNOWN_DISTINCT_PRODUCTS = {
    ("box", "dropbox"),
    ("hub", "github"),
    ("hub", "hubspot"),
    ("git", "github"),
    ("git", "gitlab"),
    ("git", "gitea"),
    ("lab", "gitlab"),
    ("air", "airtable"),
    ("flow", "flowdock"),
    ("flow", "webflow"),
    ("flow", "overflow"),
    ("doc", "docusign"),
    ("doc", "document"),
    ("base", "basecamp"),
    ("base", "firebase"),
    ("base", "database"),
    ("cloud", "cloudflare"),
    ("cloud", "soundcloud"),
    ("cloud", "salesforce"),
    ("work", "workday"),
    ("work", "framework"),
    ("work", "network"),
    ("mail", "mailchimp"),
    ("mail", "sendmail"),
    ("mail", "gmail"),
    ("data", "datadog"),
    ("data", "database"),
    ("data", "metadata"),
    ("one", "onenote"),
    ("one", "onedrive"),
    ("note", "onenote"),
    ("note", "evernote"),
    ("drive", "onedrive"),
    ("drive", "googledrive"),
    ("team", "teams"),
    ("team", "teamwork"),
    ("zoom", "zoominfo"),
    ("sales", "salesforce"),
    ("service", "servicenow"),
    ("snow", "snowflake"),
    ("snow", "servicenow"),
}


def _is_valid_contains_match(canonical: str, indexed_name: str) -> bool:
    """
    Check if a contains match is valid (not a false positive).
    
    Prevents matches like:
    - "box" matching "dropbox" (different products)
    - "git" matching "github" (different products)
    
    Valid matches:
    - "userservice" matching "userserviceprod" (same product, env suffix)
    - "billing" matching "billingapi" (same product, function suffix)
    """
    if canonical == indexed_name:
        return True
    
    if canonical not in indexed_name and indexed_name not in canonical:
        return False
    
    shorter = canonical if len(canonical) <= len(indexed_name) else indexed_name
    longer = indexed_name if len(canonical) <= len(indexed_name) else canonical
    
    if len(shorter) < 3:
        return False
    
    for short_prod, long_prod in KNOWN_DISTINCT_PRODUCTS:
        if shorter == short_prod and longer == long_prod:
            return False
        if short_prod in shorter and long_prod == longer:
            return False
        if shorter == short_prod and long_prod in longer:
            return False
    
    if longer.startswith(shorter):
        suffix = longer[len(shorter):]
        if suffix and suffix[0] in "-_":
            return True
        
        suffix_lower = suffix.lower()
        for env_suffix in ENV_SUFFIXES:
            if suffix_lower == env_suffix or suffix_lower.startswith(env_suffix):
                return True
        
        if suffix_lower in {"api", "service", "app", "web", "backend", "frontend", "client", "server"}:
            return True
    
    if longer.endswith(shorter):
        prefix = longer[:-len(shorter)]
        if prefix and prefix[-1] in "-_":
            return True
        
        prefix_lower = prefix.lower()
        for env_prefix in ENV_SUFFIXES:
            if prefix_lower == env_prefix or prefix_lower.endswith(env_prefix):
                return True
    
    if len(shorter) >= 8 and len(shorter) / len(longer) >= 0.7:
        return True
    
    return False


def _get_record_field(record: Any, field: str, default: Any = None) -> Any:
    """Extract a field from a record (handles dict or object)."""
    if record is None:
        return default
    if isinstance(record, dict):
        return record.get(field, default)
    return getattr(record, field, default)


def _is_deprecated_by_field(record: Any) -> bool:
    """Check if a record is deprecated based on actual CMDB fields."""
    status = str(_get_record_field(record, "status", "") or "").lower()
    lifecycle = str(_get_record_field(record, "lifecycle_state", "") or "").lower()
    is_deprecated = _get_record_field(record, "is_deprecated", False)
    is_retired = _get_record_field(record, "is_retired", False)
    
    deprecated_statuses = {"deprecated", "retired", "archived", "decommissioned", "obsolete", "inactive"}
    
    if is_deprecated or is_retired:
        return True
    if status in deprecated_statuses:
        return True
    if lifecycle in deprecated_statuses:
        return True
    
    return False


def _get_environment_field(record: Any) -> Optional[str]:
    """Extract environment from actual CMDB field."""
    env = _get_record_field(record, "environment")
    if env:
        return str(env).lower()
    
    env_type = _get_record_field(record, "environment_type")
    if env_type:
        return str(env_type).lower()
    
    return None


def disambiguate_matches(
    entity: CandidateEntity,
    matched_ids: list[str],
    matched_records: list[Any],
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
        names = [_get_record_name(r) for r in matched_records]
        entity_base = _extract_base_name(entity.canonical_name)
        
        exact_matches = []
        for i, record in enumerate(matched_records):
            record_base = _extract_base_name(_get_record_name(record))
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
        if _is_deprecated_by_field(record):
            deprecated_records.append((matched_ids[i], _get_record_name(record), record))
        else:
            active_records.append((matched_ids[i], _get_record_name(record), record))
    
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
        env = _get_environment_field(record)
        if env:
            records_with_env += 1
            if env not in env_groups:
                env_groups[env] = []
            env_groups[env].append((matched_ids[i], _get_record_name(record), record))
    
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
        
        all_names = [_get_record_name(r) for r in matched_records]
        return (
            AmbiguityCode.UNRESOLVED,
            f"Multiple environments but no single prod: {list(env_groups.keys())}. Records: {all_names}",
            None
        )
    
    def get_identity_tuple(record: Any) -> tuple:
        return (
            normalize_string(_get_record_name(record)),
            normalize_string(_get_record_vendor(record) or ""),
            normalize_string(str(_get_record_field(record, "app_type", "") or "")),
        )
    
    identities = [get_identity_tuple(r) for r in matched_records]
    if len(set(identities)) == 1:
        return (
            AmbiguityCode.DUPLICATE,
            f"Evidence: true duplicates (identical name/vendor/type), picked first",
            [matched_ids[0]]
        )
    
    all_names = [_get_record_name(r) for r in matched_records]
    return (
        AmbiguityCode.UNRESOLVED,
        f"No field-level evidence to disambiguate: {all_names}",
        None
    )


def correlate_to_plane(
    entity: CandidateEntity,
    plane_index: PlaneIndex,
    use_domain: bool = True,
    use_uri: bool = False
) -> PlaneMatch:
    """
    Correlate an entity to a plane using multi-pass matching with disambiguation.
    
    Pass 1: Domain match (if applicable)
    Pass 2: Exact canonical normalized name match
    Pass 3: Unique contains match (strict; if >1 candidate → try disambiguate)
    Pass 4: Vendor match (last resort, PARENT_VENDOR if multiple)
    
    When multiple matches occur, disambiguation logic attempts to resolve:
    - MULTI_ENV: Same app in different environments → pick prod
    - LEGACY: Current + deprecated → pick current
    - DUPLICATE: True duplicates → pick first
    - PARENT_VENDOR: Vendor-only match → treat as UNMATCHED
    
    Returns matched/ambiguous/unmatched plus evidence refs.
    """
    
    if use_domain and entity.domain and plane_index.by_domain:
        domain_matches = plane_index.by_domain.get(entity.domain, [])
        if len(domain_matches) == 1:
            return PlaneMatch(
                status=MatchStatus.MATCHED,
                matched_ids=domain_matches,
                matched_records=[plane_index.records.get(mid) for mid in domain_matches],
                match_method="domain",
                ambiguity_code=AmbiguityCode.NONE
            )
        elif len(domain_matches) > 1:
            records = [plane_index.records.get(mid) for mid in domain_matches]
            code, detail, resolved = disambiguate_matches(entity, domain_matches, records, "domain")
            
            if resolved and len(resolved) == 1:
                return PlaneMatch(
                    status=MatchStatus.MATCHED,
                    matched_ids=resolved,
                    matched_records=[plane_index.records.get(resolved[0])],
                    match_method="domain",
                    ambiguity_code=code,
                    disambiguation_detail=detail
                )
            
            return PlaneMatch(
                status=MatchStatus.AMBIGUOUS,
                matched_ids=domain_matches,
                matched_records=records,
                match_method="domain",
                ambiguity_code=code,
                disambiguation_detail=detail
            )
    
    if use_uri and entity.uri and plane_index.by_uri:
        uri_matches = plane_index.by_uri.get(entity.uri.lower().strip(), [])
        if len(uri_matches) == 1:
            return PlaneMatch(
                status=MatchStatus.MATCHED,
                matched_ids=uri_matches,
                matched_records=[plane_index.records.get(mid) for mid in uri_matches],
                match_method="uri",
                ambiguity_code=AmbiguityCode.NONE
            )
        elif len(uri_matches) > 1:
            records = [plane_index.records.get(mid) for mid in uri_matches]
            code, detail, resolved = disambiguate_matches(entity, uri_matches, records, "uri")
            
            if resolved and len(resolved) == 1:
                return PlaneMatch(
                    status=MatchStatus.MATCHED,
                    matched_ids=resolved,
                    matched_records=[plane_index.records.get(resolved[0])],
                    match_method="uri",
                    ambiguity_code=code,
                    disambiguation_detail=detail
                )
            
            return PlaneMatch(
                status=MatchStatus.AMBIGUOUS,
                matched_ids=uri_matches,
                matched_records=records,
                match_method="uri",
                ambiguity_code=code,
                disambiguation_detail=detail
            )
    
    canonical = entity.canonical_name
    name_matches = plane_index.by_canonical_name.get(canonical, [])
    if len(name_matches) == 1:
        return PlaneMatch(
            status=MatchStatus.MATCHED,
            matched_ids=name_matches,
            matched_records=[plane_index.records.get(mid) for mid in name_matches],
            match_method="canonical_name",
            ambiguity_code=AmbiguityCode.NONE
        )
    elif len(name_matches) > 1:
        records = [plane_index.records.get(mid) for mid in name_matches]
        code, detail, resolved = disambiguate_matches(entity, name_matches, records, "canonical_name")
        
        if resolved and len(resolved) == 1:
            return PlaneMatch(
                status=MatchStatus.MATCHED,
                matched_ids=resolved,
                matched_records=[plane_index.records.get(resolved[0])],
                match_method="canonical_name",
                ambiguity_code=code,
                disambiguation_detail=detail
            )
        
        return PlaneMatch(
            status=MatchStatus.AMBIGUOUS,
            matched_ids=name_matches,
            matched_records=records,
            match_method="canonical_name",
            ambiguity_code=code,
            disambiguation_detail=detail
        )
    
    fuzzy_matches: list[str] = []
    for indexed_name, record_ids in plane_index.by_canonical_name.items():
        if _is_fuzzy_match(canonical, indexed_name):
            fuzzy_matches.extend(record_ids)
    
    fuzzy_matches = list(set(fuzzy_matches))
    
    if len(fuzzy_matches) == 1:
        return PlaneMatch(
            status=MatchStatus.MATCHED,
            matched_ids=fuzzy_matches,
            matched_records=[plane_index.records.get(mid) for mid in fuzzy_matches],
            match_method="fuzzy",
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
                ambiguity_code=code,
                disambiguation_detail=detail
            )
        
        return PlaneMatch(
            status=MatchStatus.AMBIGUOUS,
            matched_ids=fuzzy_matches,
            matched_records=records,
            match_method="fuzzy",
            ambiguity_code=code,
            disambiguation_detail=detail
        )
    
    contains_matches: list[str] = []
    for indexed_name, record_ids in plane_index.by_canonical_name.items():
        if _is_valid_contains_match(canonical, indexed_name):
            contains_matches.extend(record_ids)
    
    contains_matches = list(set(contains_matches))
    
    if len(contains_matches) == 1:
        return PlaneMatch(
            status=MatchStatus.MATCHED,
            matched_ids=contains_matches,
            matched_records=[plane_index.records.get(mid) for mid in contains_matches],
            match_method="contains",
            ambiguity_code=AmbiguityCode.NONE
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
                ambiguity_code=code,
                disambiguation_detail=detail
            )
        
        return PlaneMatch(
            status=MatchStatus.AMBIGUOUS,
            matched_ids=contains_matches,
            matched_records=records,
            match_method="contains",
            ambiguity_code=code,
            disambiguation_detail=detail
        )
    
    if entity.vendor and plane_index.by_vendor_product:
        vendor_key = normalize_string(entity.vendor)
        vendor_matches = plane_index.by_vendor_product.get(vendor_key, [])
        
        if len(vendor_matches) == 1:
            matched_record = plane_index.records.get(vendor_matches[0])
            matched_name = normalize_string(_get_record_name(matched_record)) if matched_record else ""
            entity_name = entity.canonical_name
            
            if matched_name == entity_name or matched_name in entity_name or entity_name in matched_name:
                return PlaneMatch(
                    status=MatchStatus.MATCHED,
                    matched_ids=vendor_matches,
                    matched_records=[matched_record],
                    match_method="vendor",
                    ambiguity_code=AmbiguityCode.NONE
                )
            else:
                return PlaneMatch(
                    status=MatchStatus.UNMATCHED,
                    matched_ids=[],
                    matched_records=[],
                    match_method="vendor",
                    ambiguity_code=AmbiguityCode.PARENT_VENDOR,
                    disambiguation_detail=f"Vendor-only match rejected: {entity.original_name} matched vendor {entity.vendor} but product name '{matched_name}' differs"
                )
        elif len(vendor_matches) > 1:
            records = [plane_index.records.get(mid) for mid in vendor_matches]
            code, detail, resolved = disambiguate_matches(entity, vendor_matches, records, "vendor")
            
            if code == AmbiguityCode.PARENT_VENDOR:
                return PlaneMatch(
                    status=MatchStatus.UNMATCHED,
                    matched_ids=[],
                    matched_records=[],
                    match_method="vendor",
                    ambiguity_code=AmbiguityCode.PARENT_VENDOR,
                    disambiguation_detail=detail
                )
            
            if resolved and len(resolved) == 1:
                return PlaneMatch(
                    status=MatchStatus.MATCHED,
                    matched_ids=resolved,
                    matched_records=[plane_index.records.get(resolved[0])],
                    match_method="vendor",
                    ambiguity_code=code,
                    disambiguation_detail=detail
                )
            
            return PlaneMatch(
                status=MatchStatus.AMBIGUOUS,
                matched_ids=vendor_matches,
                matched_records=records,
                match_method="vendor",
                ambiguity_code=code,
                disambiguation_detail=detail
            )
    
    return PlaneMatch(status=MatchStatus.UNMATCHED)


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
    results = []
    
    for entity in sorted(entities, key=lambda e: e.entity_id):
        result = CorrelationResult(entity=entity)
        
        result.idp = correlate_to_plane(entity, indexes.idp, use_domain=True)
        result.cmdb = correlate_to_plane(entity, indexes.cmdb, use_domain=False)
        result.cloud = correlate_to_plane(entity, indexes.cloud, use_domain=False, use_uri=True)
        result.finance = correlate_to_plane(entity, indexes.finance, use_domain=False)
        
        results.append(result)
    
    return results
