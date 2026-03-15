"""COFA Deterministic Pre-Filter.

Identifies exact matches between two entities' object lists using
string normalization and attribute comparison — no LLM, no fuzzy matching.

Runs BEFORE any LLM invocation to reduce the comparison space from
O(n*m) pairs down to only the ambiguous remainder that needs AI evaluation.
"""

import re
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Configurable suffix list — removed during name normalization
# ---------------------------------------------------------------------------
CORPORATE_SUFFIXES: frozenset[str] = frozenset({
    "inc", "llc", "ltd", "corp", "corporation", "incorporated",
    "company", "co", "plc", "gmbh", "ag", "sa", "pty", "limited",
})

# Object types that use revenue for truncation ranking
_REVENUE_RANKED: frozenset[str] = frozenset({"customer"})
# Object types that use spend for truncation ranking
_SPEND_RANKED: frozenset[str] = frozenset({"vendor"})

TRUNCATION_LIMIT = 100


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class COFAObject(BaseModel):
    """A single discoverable object belonging to one entity."""

    object_type: Literal["customer", "vendor", "people", "contract", "system"]
    entity_source: str
    name: str
    object_id: Optional[str] = None
    tax_id: Optional[str] = None
    domain: Optional[str] = None
    duns: Optional[str] = None
    address: Optional[str] = None
    contact_name: Optional[str] = None
    revenue: Optional[Decimal] = None
    spend: Optional[Decimal] = None


class COFAMatchResult(BaseModel):
    """A deterministic match produced by the pre-filter."""

    object_type: str
    entity_a_name: str
    entity_a_id: Optional[str] = None
    entity_b_name: str
    entity_b_id: Optional[str] = None
    classification: Literal["match"] = "match"
    confidence: Decimal = Field(default=Decimal("1.0"))
    match_signal: str  # "name" | "tax_id" | "duns" | "domain"
    corroborating_attributes: list[str] = Field(default_factory=list)
    source: Literal["pre-filter"] = "pre-filter"
    flags: list[str] = Field(default_factory=list)


class PreFilterResult(BaseModel):
    """Output of the deterministic pre-filter pass."""

    deterministic_matches: list[COFAMatchResult]
    ambiguous_remainder_a: list[COFAObject]
    ambiguous_remainder_b: list[COFAObject]
    truncation_flags: list[str]


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------
_PUNCTUATION_RE = re.compile(r"[,.\-'\"\(\)]+")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_name(raw: str) -> str:
    """Normalize a company/person name for exact comparison.

    Steps: lowercase → strip punctuation → collapse whitespace → trim →
    remove corporate suffixes.
    """
    s = raw.lower()
    s = _PUNCTUATION_RE.sub(" ", s)
    s = _WHITESPACE_RE.sub(" ", s).strip()
    tokens = s.split()
    tokens = [t for t in tokens if t not in CORPORATE_SUFFIXES]
    return " ".join(tokens).strip()


def normalize_domain(raw: str) -> str:
    """Normalize a domain: strip www. prefix, lowercase, trim."""
    s = raw.strip().lower()
    if s.startswith("www."):
        s = s[4:]
    return s


def normalize_tax_id(raw: str) -> str:
    """Normalize a tax ID: strip non-alphanumeric, uppercase."""
    return re.sub(r"[^A-Za-z0-9]", "", raw).upper()


def normalize_duns(raw: str) -> str:
    """Normalize a D-U-N-S number: strip non-numeric characters."""
    return re.sub(r"[^0-9]", "", raw)


# ---------------------------------------------------------------------------
# Truncation
# ---------------------------------------------------------------------------
def _truncate_objects(
    objects: list[COFAObject],
) -> tuple[list[COFAObject], list[str]]:
    """Apply per-type truncation to a list of objects.

    Returns the (possibly truncated) list and any truncation flag messages.
    """
    from collections import defaultdict

    by_type: dict[str, list[COFAObject]] = defaultdict(list)
    for obj in objects:
        by_type[obj.object_type].append(obj)

    result: list[COFAObject] = []
    flags: list[str] = []

    for obj_type, items in by_type.items():
        if len(items) <= TRUNCATION_LIMIT:
            result.extend(items)
            continue

        total = len(items)

        if obj_type in _REVENUE_RANKED:
            items.sort(key=lambda o: o.revenue if o.revenue is not None else Decimal("-Infinity"), reverse=True)
        elif obj_type in _SPEND_RANKED:
            items.sort(key=lambda o: o.spend if o.spend is not None else Decimal("-Infinity"), reverse=True)
        # else: people/contracts/systems — keep first 100 as-is

        result.extend(items[:TRUNCATION_LIMIT])
        entity_id = items[0].entity_source
        flags.append(
            f"{obj_type} list for entity {entity_id} truncated from {total} to {TRUNCATION_LIMIT}."
        )

    return result, flags


# ---------------------------------------------------------------------------
# Matching engine
# ---------------------------------------------------------------------------

# Priority order for deterministic match signals (highest → lowest)
_SIGNAL_PRIORITY = {"tax_id": 0, "duns": 1, "name": 2, "domain": 3}


def _find_corroborating(
    obj_a: COFAObject, obj_b: COFAObject, primary_signal: str
) -> list[str]:
    """Find additional attributes that agree between two matched objects.

    Checks all signal types except the primary match signal.
    """
    corroborating: list[str] = []
    checks: dict[str, tuple[Optional[str], Optional[str]]] = {
        "name": (obj_a.name, obj_b.name),
        "tax_id": (obj_a.tax_id, obj_b.tax_id),
        "duns": (obj_a.duns, obj_b.duns),
        "domain": (obj_a.domain, obj_b.domain),
    }
    normalizers = {
        "name": normalize_name,
        "tax_id": normalize_tax_id,
        "duns": normalize_duns,
        "domain": normalize_domain,
    }
    for signal, (val_a, val_b) in checks.items():
        if signal == primary_signal:
            continue
        if val_a is not None and val_b is not None:
            norm = normalizers[signal]
            if norm(val_a) == norm(val_b):
                corroborating.append(signal)
    return corroborating


def _match_pair(
    obj_a: COFAObject, obj_b: COFAObject
) -> Optional[tuple[str, int]]:
    """Check whether two objects of the same type deterministically match.

    Returns (signal_name, priority) if matched, None otherwise.
    """
    # tax_id — highest priority
    if obj_a.tax_id is not None and obj_b.tax_id is not None:
        if normalize_tax_id(obj_a.tax_id) == normalize_tax_id(obj_b.tax_id):
            return ("tax_id", _SIGNAL_PRIORITY["tax_id"])

    # duns
    if obj_a.duns is not None and obj_b.duns is not None:
        if normalize_duns(obj_a.duns) == normalize_duns(obj_b.duns):
            return ("duns", _SIGNAL_PRIORITY["duns"])

    # name
    if normalize_name(obj_a.name) == normalize_name(obj_b.name):
        return ("name", _SIGNAL_PRIORITY["name"])

    # domain — lowest priority
    if obj_a.domain is not None and obj_b.domain is not None:
        if normalize_domain(obj_a.domain) == normalize_domain(obj_b.domain):
            return ("domain", _SIGNAL_PRIORITY["domain"])

    return None


def run_prefilter(
    entity_a_objects: list[COFAObject],
    entity_b_objects: list[COFAObject],
) -> PreFilterResult:
    """Execute the COFA deterministic pre-filter.

    Compares Entity A objects against Entity B objects (same type only),
    identifies exact matches, and returns the matched pairs plus the
    ambiguous remainder for LLM evaluation.
    """
    # Step 1: truncate
    a_trunc, a_flags = _truncate_objects(entity_a_objects)
    b_trunc, b_flags = _truncate_objects(entity_b_objects)
    truncation_flags = a_flags + b_flags

    # Step 2: group by object_type
    from collections import defaultdict

    a_by_type: dict[str, list[COFAObject]] = defaultdict(list)
    b_by_type: dict[str, list[COFAObject]] = defaultdict(list)
    for obj in a_trunc:
        a_by_type[obj.object_type].append(obj)
    for obj in b_trunc:
        b_by_type[obj.object_type].append(obj)

    all_types = set(a_by_type.keys()) | set(b_by_type.keys())

    matches: list[COFAMatchResult] = []
    matched_a_indices: set[tuple[str, int]] = set()  # (type, index)
    matched_b_indices: set[tuple[str, int]] = set()

    for obj_type in all_types:
        a_list = a_by_type.get(obj_type, [])
        b_list = b_by_type.get(obj_type, [])

        for a_idx, obj_a in enumerate(a_list):
            # Collect all candidate matches for this obj_a
            candidates: list[tuple[int, str, int]] = []  # (b_idx, signal, priority)

            for b_idx, obj_b in enumerate(b_list):
                if (obj_type, b_idx) in matched_b_indices:
                    continue  # already consumed
                result = _match_pair(obj_a, obj_b)
                if result is not None:
                    signal, priority = result
                    candidates.append((b_idx, signal, priority))

            if not candidates:
                continue

            # Check for ambiguity: multiple matches at the same best priority
            best_priority = min(c[2] for c in candidates)
            best_candidates = [c for c in candidates if c[2] == best_priority]

            if len(best_candidates) > 1:
                # Ambiguous — flag and skip (route to LLM)
                b_names = ", ".join(
                    b_list[c[0]].name for c in best_candidates
                )
                matches.append(
                    COFAMatchResult(
                        object_type=obj_type,
                        entity_a_name=obj_a.name,
                        entity_a_id=obj_a.object_id,
                        entity_b_name=b_names,
                        entity_b_id=None,
                        match_signal=best_candidates[0][1],
                        corroborating_attributes=[],
                        flags=[
                            f"Ambiguous deterministic match: Entity A object "
                            f"{obj_a.name} matches multiple Entity B objects. "
                            f"Routing to LLM for resolution."
                        ],
                    )
                )
                # Do NOT mark any b objects as matched — all go to remainder
                # Do NOT mark obj_a as matched — goes to remainder too
                continue

            # Unique best match
            winner_b_idx, winner_signal, _ = best_candidates[0]
            obj_b = b_list[winner_b_idx]

            corroborating = _find_corroborating(obj_a, obj_b, winner_signal)

            matches.append(
                COFAMatchResult(
                    object_type=obj_type,
                    entity_a_name=obj_a.name,
                    entity_a_id=obj_a.object_id,
                    entity_b_name=obj_b.name,
                    entity_b_id=obj_b.object_id,
                    match_signal=winner_signal,
                    corroborating_attributes=corroborating,
                    flags=[],
                )
            )
            matched_a_indices.add((obj_type, a_idx))
            matched_b_indices.add((obj_type, winner_b_idx))

    # Step 3: build remainders — unmatched objects from truncated lists
    remainder_a: list[COFAObject] = []
    remainder_b: list[COFAObject] = []

    for obj_type in all_types:
        a_list = a_by_type.get(obj_type, [])
        b_list = b_by_type.get(obj_type, [])
        for a_idx, obj in enumerate(a_list):
            if (obj_type, a_idx) not in matched_a_indices:
                remainder_a.append(obj)
        for b_idx, obj in enumerate(b_list):
            if (obj_type, b_idx) not in matched_b_indices:
                remainder_b.append(obj)

    # Remove ambiguous "matches" from deterministic_matches — they're flags only
    deterministic = [m for m in matches if not m.flags]
    ambiguous_flags = [m for m in matches if m.flags]

    # Rebuild truncation_flags with ambiguity notices
    for m in ambiguous_flags:
        truncation_flags.extend(m.flags)

    return PreFilterResult(
        deterministic_matches=deterministic,
        ambiguous_remainder_a=remainder_a,
        ambiguous_remainder_b=remainder_b,
        truncation_flags=truncation_flags,
    )
