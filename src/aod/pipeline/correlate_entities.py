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
    """Extract name from a record (handles dict or object)."""
    if record is None:
        return ""
    if isinstance(record, dict):
        return record.get("name", "") or record.get("app_name", "") or ""
    return getattr(record, "name", "") or getattr(record, "app_name", "") or ""


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


def disambiguate_matches(
    entity: CandidateEntity,
    matched_ids: list[str],
    matched_records: list[Any],
    match_method: str
) -> tuple[AmbiguityCode, Optional[str], Optional[list[str]]]:
    """
    Analyze multiple matches and attempt to disambiguate.
    
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
    
    base_names = {}
    for i, record in enumerate(matched_records):
        record_name = _get_record_name(record)
        base = _extract_base_name(record_name)
        if base not in base_names:
            base_names[base] = []
        base_names[base].append((matched_ids[i], record_name, record))
    
    if len(base_names) == 1:
        base_name = list(base_names.keys())[0]
        records_info = base_names[base_name]
        
        legacy_records = [(rid, rname) for rid, rname, _ in records_info if _is_legacy_name(rname)]
        current_records = [(rid, rname) for rid, rname, _ in records_info if not _is_legacy_name(rname)]
        
        if legacy_records and current_records:
            best_id = current_records[0][0]
            return (
                AmbiguityCode.LEGACY,
                f"Resolved: picked current '{current_records[0][1]}' over legacy '{legacy_records[0][1]}'",
                [best_id]
            )
        
        names = [rname for _, rname, _ in records_info]
        env_detected = []
        for name in names:
            for suffix in ENV_SUFFIXES:
                if suffix in name.lower():
                    env_detected.append(suffix)
                    break
        
        if len(set(env_detected)) > 1 or (len(env_detected) > 0 and len(names) > 1):
            prod_record = None
            for rid, rname, _ in records_info:
                rname_lower = rname.lower()
                if "prod" in rname_lower or "production" in rname_lower or "prd" in rname_lower:
                    prod_record = (rid, rname)
                    break
            
            if prod_record:
                return (
                    AmbiguityCode.MULTI_ENV,
                    f"Same app in multiple environments, picked prod: {prod_record[1]}",
                    [prod_record[0]]
                )
            else:
                best_id = records_info[0][0]
                return (
                    AmbiguityCode.MULTI_ENV,
                    f"Same app in multiple environments: {names}",
                    [best_id]
                )
        
        vendors = set(_get_record_vendor(r) for _, _, r in records_info)
        if len(vendors) == 1:
            return (
                AmbiguityCode.DUPLICATE,
                f"Duplicate records for same app: {names}",
                [records_info[0][0]]
            )
    
    all_names = [_get_record_name(r) for r in matched_records]
    return (
        AmbiguityCode.UNRESOLVED,
        f"Could not disambiguate between: {all_names}",
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
            return PlaneMatch(
                status=MatchStatus.MATCHED,
                matched_ids=vendor_matches,
                matched_records=[plane_index.records.get(mid) for mid in vendor_matches],
                match_method="vendor",
                ambiguity_code=AmbiguityCode.NONE
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
