"""Contains-match validation logic."""

from .constants import (
    CONTAINS_MATCH_MIN_LENGTH,
    CONTAINS_MATCH_RATIO_THRESHOLD,
    KNOWN_DISTINCT_PRODUCTS,
    ENV_SUFFIXES,
)


def is_valid_contains_match(canonical: str, indexed_name: str) -> bool:
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

    if len(shorter) >= CONTAINS_MATCH_MIN_LENGTH and len(shorter) / len(longer) >= CONTAINS_MATCH_RATIO_THRESHOLD:
        return True

    return False


# Alias with underscore prefix for backwards compatibility
_is_valid_contains_match = is_valid_contains_match
