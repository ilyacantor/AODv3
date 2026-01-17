"""String matching utilities: fuzzy matching and Levenshtein distance."""

import functools
from typing import Optional

from .constants import LRU_CACHE_SIZE
from ...core.policy import get_current_config


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Compute Levenshtein edit distance between two strings (memoized).

    Uses a wrapper to normalize argument order before caching, ensuring
    that (a, b) and (b, a) hit the same cache entry since distance is symmetric.
    """
    # Normalize order to maximize cache hits (distance is symmetric)
    if s1 > s2:
        s1, s2 = s2, s1
    return _levenshtein_distance_cached(s1, s2)


@functools.lru_cache(maxsize=LRU_CACHE_SIZE)
def _levenshtein_distance_cached(s1: str, s2: str) -> int:
    """Internal cached implementation of Levenshtein distance."""
    # Ensure s1 is the longer string for algorithm efficiency
    if len(s1) < len(s2):
        longer, shorter = s2, s1
    else:
        longer, shorter = s1, s2

    if len(shorter) == 0:
        return len(longer)

    prev_row = list(range(len(shorter) + 1))
    for i, c1 in enumerate(longer):
        curr_row = [i + 1]
        for j, c2 in enumerate(shorter):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row

    return prev_row[-1]


def is_fuzzy_match(
    name1: str,
    name2: str,
    max_distance: Optional[int] = None,
    max_ratio: Optional[float] = None
) -> bool:
    """
    Check if two names are a fuzzy match (typo tolerance).

    Handles cases like:
    - "monday" vs "mondayc" (truncation/typo)
    - "monday" vs "monady" (transposition)

    Rules:
    - Names must be at least min_name_length chars to avoid false positives
    - One must be a prefix of the other with ≤2 extra chars, OR
    - Edit distance ≤ max_distance AND distance/max_len ≤ max_ratio

    The ratio gate prevents short-token collisions like miro↔jira (2/4=0.50)
    and loom↔zoom (1/4=0.25) while preserving longer fuzzy matches.
    """
    config = get_current_config()
    if max_distance is None:
        max_distance = config.fuzzy_matching.max_edit_distance
    if max_ratio is None:
        max_ratio = config.fuzzy_matching.max_edit_ratio

    min_len = config.fuzzy_matching.min_name_length
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


# Alias for backwards compatibility
_is_fuzzy_match = is_fuzzy_match
