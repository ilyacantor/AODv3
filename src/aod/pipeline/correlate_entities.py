"""Stage 4: CorrelateEntitiesToPlanes - Real-world simple matcher with disambiguation"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

from .normalize_observations import CandidateEntity, normalize_string
from .build_plane_indexes import PlaneIndexes, PlaneIndex
from .vendor_inference import DOMAIN_TO_VENDOR, VENDOR_TO_DOMAIN, extract_registered_domain
from ..config import policy
from ..models.input_contracts import PlaneRecord
from ..utils.normalization import get_normalization_token


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


def _is_fuzzy_match(
    name1: str,
    name2: str,
    max_distance: int = None,
    max_ratio: float = None
) -> bool:
    """
    Check if two names are a fuzzy match (typo tolerance).

    Handles cases like:
    - "monday" vs "mondayc" (truncation/typo)
    - "monday" vs "monady" (transposition)

    Rules:
    - Names must be at least MIN_NAME_LENGTH_FOR_FUZZY chars to avoid false positives
    - One must be a prefix of the other with ≤2 extra chars, OR
    - Edit distance ≤ max_distance AND distance/max_len ≤ max_ratio

    The ratio gate prevents short-token collisions like miro↔jira (2/4=0.50)
    and loom↔zoom (1/4=0.25) while preserving longer fuzzy matches.
    """
    if max_distance is None:
        max_distance = policy.FUZZY_MATCH_MAX_DISTANCE
    if max_ratio is None:
        max_ratio = policy.FUZZY_MATCH_MAX_RATIO

    min_len = policy.MIN_NAME_LENGTH_FOR_FUZZY
    if len(name1) < min_len or len(name2) < min_len:
        return False
    
    if name1.startswith(name2) and len(name1) - len(name2) <= 2:
        return True
    if name2.startswith(name1) and len(name2) - len(name1) <= 2:
        return True
    
    len_diff = abs(len(name1) - len(name2))
    if len_diff <= 2:
        distance = _levenshtein_distance(name1, name2)
        max_len = max(len(name1), len(name2))
        ratio = distance / max_len
        return distance <= max_distance and ratio <= max_ratio
    
    return False


@dataclass
class PlaneMatch:
    """Match result for a single plane"""
    status: MatchStatus
    matched_ids: list[str] = field(default_factory=list)
    matched_records: list[PlaneRecord] = field(default_factory=list)
    match_method: Optional[str] = None
    match_key: Optional[str] = None
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
        """Get all evidence references from matched planes.
        
        For finance plane, ALSO adds 'recurring_' prefixed refs for records
        with is_recurring=True. Original IDs are always preserved for
        downstream consumers (findings, UI).
        """
        from ..models.input_contracts import Contract, Transaction
        
        refs = list(self.entity.observation_ids)
        for plane_match in [self.idp, self.cmdb, self.cloud]:
            if plane_match.status == MatchStatus.MATCHED:
                refs.extend(plane_match.matched_ids)
        
        if self.finance.status == MatchStatus.MATCHED:
            refs.extend(self.finance.matched_ids)
            
            for i, record_id in enumerate(self.finance.matched_ids):
                record = self.finance.matched_records[i] if i < len(self.finance.matched_records) else None
                if record:
                    if isinstance(record, Contract):
                        if record.is_recurring:
                            refs.append(f"recurring_contract:{record_id}")
                    elif isinstance(record, Transaction):
                        if record.is_recurring:
                            refs.append(f"recurring_transaction:{record_id}")
        
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


def _get_record_name(record: PlaneRecord) -> str:
    """Extract name from a record (handles dict or object)."""
    if record is None:
        return ""
    if isinstance(record, dict):
        return record.get("name", "") or record.get("app_name", "") or ""
    return getattr(record, "name", "") or getattr(record, "app_name", "") or ""


def _get_record_vendor(record: PlaneRecord) -> str:
    """Extract vendor from a record (handles dict or object)."""
    if record is None:
        return ""
    if isinstance(record, dict):
        return record.get("vendor", "") or ""
    return getattr(record, "vendor", "") or ""


def _extract_domain_base_token(domain: str) -> str:
    """Extract base token from domain (e.g., 'pagerduty.com' -> 'pagerduty', 'service-now.com' -> 'servicenow')."""
    if not domain:
        return ""
    normalized = domain.lower().strip()
    normalized = normalized.removeprefix("www.")
    parts = normalized.split(".")
    if parts:
        token = parts[0]
        token = token.replace("-", "").replace("_", "")
        return token
    return ""


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


def _get_record_field(record: PlaneRecord, field: str, default=None):
    """Extract a field from a record (handles dict or object)."""
    if record is None:
        return default
    if isinstance(record, dict):
        return record.get(field, default)
    return getattr(record, field, default)


def _is_deprecated_by_field(record: PlaneRecord) -> bool:
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


def _get_environment_field(record: PlaneRecord) -> Optional[str]:
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
    
    def get_identity_tuple(record: PlaneRecord) -> tuple:
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
    use_uri: bool = False,
    use_vendor: bool = False
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
        use_uri: Enable URI-based matching
        use_vendor: Enable domain-to-vendor lookup for matching (useful for CMDB)
    
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
                match_key=entity.domain,
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
                    match_key=entity.domain,
                    ambiguity_code=code,
                    disambiguation_detail=detail
                )
            
            return PlaneMatch(
                status=MatchStatus.AMBIGUOUS,
                matched_ids=domain_matches,
                matched_records=records,
                match_method="domain",
                match_key=entity.domain,
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
                match_key=entity.uri,
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
                    match_key=entity.uri,
                    ambiguity_code=code,
                    disambiguation_detail=detail
                )
            
            return PlaneMatch(
                status=MatchStatus.AMBIGUOUS,
                matched_ids=uri_matches,
                matched_records=records,
                match_method="uri",
                match_key=entity.uri,
                ambiguity_code=code,
                disambiguation_detail=detail
            )
    
    canonical = entity.canonical_name
    name_matches = plane_index.by_canonical_name.get(canonical, [])
    
    if name_matches and use_vendor:
        expected_vendor = None
        if entity.domain:
            registered_domain = extract_registered_domain(entity.domain.lower().strip()) or entity.domain.lower().strip()
            expected_vendor = DOMAIN_TO_VENDOR.get(registered_domain)
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
    
    if len(name_matches) == 1:
        return PlaneMatch(
            status=MatchStatus.MATCHED,
            matched_ids=name_matches,
            matched_records=[plane_index.records.get(mid) for mid in name_matches],
            match_method="canonical_name",
            match_key=canonical,
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
                match_key=canonical,
                ambiguity_code=code,
                disambiguation_detail=detail
            )
        
        return PlaneMatch(
            status=MatchStatus.AMBIGUOUS,
            matched_ids=name_matches,
            matched_records=records,
            match_method="canonical_name",
            match_key=canonical,
            ambiguity_code=code,
            disambiguation_detail=detail
        )
    
    fuzzy_matches: list[str] = []
    if len(canonical) >= 4 and hasattr(plane_index, 'by_name_prefix'):
        prefix = canonical[:4]
        prefix_candidates = set(plane_index.by_name_prefix.get(prefix, []))
        for candidate_id in prefix_candidates:
            record = plane_index.records.get(candidate_id)
            if record:
                record_name = normalize_string(_get_record_name(record))
                if _is_fuzzy_match(canonical, record_name):
                    if candidate_id not in fuzzy_matches:
                        fuzzy_matches.append(candidate_id)
    else:
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
    
    contains_matches: list[str] = []
    if hasattr(plane_index, 'by_name_words') and plane_index.by_name_words:
        canonical_words = {w for w in re.split(r'[\s\-_./]+', canonical) if len(w) >= 4}
        candidate_ids = set()
        for word in canonical_words:
            candidate_ids.update(plane_index.by_name_words.get(word, []))
        for candidate_id in candidate_ids:
            record = plane_index.records.get(candidate_id)
            if record:
                record_name = normalize_string(_get_record_name(record))
                if _is_valid_contains_match(canonical, record_name):
                    if candidate_id not in contains_matches:
                        contains_matches.append(candidate_id)
    else:
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
            match_key=canonical,
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
                match_key=canonical,
                ambiguity_code=code,
                disambiguation_detail=detail
            )
        
        return PlaneMatch(
            status=MatchStatus.AMBIGUOUS,
            matched_ids=contains_matches,
            matched_records=records,
            match_method="contains",
            match_key=canonical,
            ambiguity_code=code,
            disambiguation_detail=detail
        )
    
    if entity.domain and plane_index.by_canonical_name:
        raw_domain_token = _extract_domain_base_token(entity.domain)
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
    
    if use_vendor and entity.domain and plane_index.by_vendor_product:
        normalized_domain = entity.domain.lower().strip()
        registered_domain = extract_registered_domain(normalized_domain) or normalized_domain
        domain_vendor = DOMAIN_TO_VENDOR.get(registered_domain)
        if not domain_vendor and registered_domain != normalized_domain:
            domain_vendor = DOMAIN_TO_VENDOR.get(normalized_domain)
        if domain_vendor:
            vendor_key = normalize_string(domain_vendor)
            vendor_matches = plane_index.by_vendor_product.get(vendor_key, [])
            
            if len(vendor_matches) >= 1:
                records = [plane_index.records.get(mid) for mid in vendor_matches]
                matching_ids = []
                matching_records = []
                
                for idx, record in enumerate(records):
                    if record:
                        record_name = normalize_string(_get_record_name(record))
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
    
    if use_vendor and entity.vendor and plane_index.by_vendor_product:
        entity_vendor_key = normalize_string(entity.vendor)
        vendor_matches = plane_index.by_vendor_product.get(entity_vendor_key, [])
        
        if len(vendor_matches) >= 1:
            exact_in_vendor = []
            for mid in vendor_matches:
                record = plane_index.records.get(mid)
                if record and normalize_string(_get_record_name(record)) == entity.canonical_name:
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
    
    entity_token = get_normalization_token(entity.canonical_name)
    if not entity_token and entity.domain:
        entity_token = get_normalization_token(entity.domain)
    
    if entity_token and len(entity_token) >= 3:
        token_matches: list[str] = []
        matched_vendor_tokens: set[str] = set()
        
        for record_id, record in plane_index.records.items():
            record_name = _get_record_name(record)
            record_vendor = _get_record_vendor(record)
            
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
            pass
    
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
    logger.info("correlate_entities.start", extra={
        "entity_count": len(entities),
        "idp_records": len(indexes.idp.by_canonical_name),
        "cmdb_records": len(indexes.cmdb.by_canonical_name),
        "cloud_records": len(indexes.cloud.by_canonical_name),
        "finance_records": len(indexes.finance.by_canonical_name)
    })
    
    results = []
    matched_counts = {"idp": 0, "cmdb": 0, "cloud": 0, "finance": 0}
    ambiguous_counts = {"idp": 0, "cmdb": 0, "cloud": 0, "finance": 0}
    
    for entity in sorted(entities, key=lambda e: e.entity_id):
        result = CorrelationResult(entity=entity)
        
        result.idp = correlate_to_plane(entity, indexes.idp, use_domain=True, use_vendor=True)
        result.cmdb = correlate_to_plane(entity, indexes.cmdb, use_domain=True, use_vendor=True)
        result.cloud = correlate_to_plane(entity, indexes.cloud, use_domain=False, use_uri=True)
        result.finance = correlate_to_plane(entity, indexes.finance, use_domain=False)
        
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
        
        results.append(result)
    
    logger.info("correlate_entities.complete", extra={
        "entity_count": len(entities), "result_count": len(results),
        "matched_idp": matched_counts["idp"], "matched_cmdb": matched_counts["cmdb"],
        "matched_cloud": matched_counts["cloud"], "matched_finance": matched_counts["finance"],
        "ambiguous_idp": ambiguous_counts["idp"], "ambiguous_cmdb": ambiguous_counts["cmdb"],
        "ambiguous_cloud": ambiguous_counts["cloud"], "ambiguous_finance": ambiguous_counts["finance"]
    })
    
    return results
