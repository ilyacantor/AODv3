"""Enumerations for correlation matching."""

from enum import Enum

from .constants import AUTHORITATIVE_MATCH_METHODS, HEURISTIC_MATCH_METHODS


class MatchStatus(str, Enum):
    """Match status for correlation."""
    MATCHED = "matched"
    AMBIGUOUS = "ambiguous"
    UNMATCHED = "unmatched"


class AmbiguityCode(str, Enum):
    """Disambiguation codes explaining why multiple matches occurred."""
    NONE = "NONE"                    # Single clear match
    MULTI_ENV = "MULTI_ENV"          # Same app in dev/staging/prod CIs
    LEGACY = "LEGACY"                # Old/deprecated CI alongside current
    DUPLICATE = "DUPLICATE"          # True duplicate records
    PARENT_VENDOR = "PARENT_VENDOR"  # Matched parent vendor, not product
    UNRESOLVED = "UNRESOLVED"        # Multiple matches, couldn't disambiguate


class MatchQuality(Enum):
    """
    Distinguishes authoritative matches from heuristic matches.

    AUTHORITATIVE: Exact domain/URI/canonical_name matches - can assert governance
    HEURISTIC: Fuzzy/vendor/contains matches - enrichment only, cannot assert governance

    Per governance policy: CMDB and IdP are authoritative truth sources.
    An asset is governed only if there exists at least one CMDB or IdP record
    that explicitly passes all governance gates via an AUTHORITATIVE match.
    Heuristics may generate hypotheses and enrichment signals but may never
    assert or override governance or classification outcomes.
    """
    AUTHORITATIVE = "authoritative"
    HEURISTIC = "heuristic"
    NONE = "none"

    @staticmethod
    def from_match_method(match_method: str | None) -> "MatchQuality":
        """Determine match quality from a match method string."""
        if not match_method:
            return MatchQuality.NONE
        if match_method in AUTHORITATIVE_MATCH_METHODS:
            return MatchQuality.AUTHORITATIVE
        if match_method in HEURISTIC_MATCH_METHODS:
            return MatchQuality.HEURISTIC
        # Unknown method defaults to heuristic for safety
        return MatchQuality.HEURISTIC
