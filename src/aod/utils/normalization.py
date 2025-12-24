"""
Normalization utilities for AOD.

Consolidates string normalization functions used across the codebase.
"""

import re


def normalize_key(key: str) -> str:
    """
    Normalize an asset key for matching.

    Removes special chars, lowercases, strips whitespace.

    Examples:
        "Slack.com" -> "slackcom"
        "PostgreSQL Main" -> "postgresqlmain"
        "Notion-prod" -> "notionprod"

    Args:
        key: The string to normalize

    Returns:
        Normalized lowercase alphanumeric string
    """
    return re.sub(r'[^a-z0-9]', '', key.lower())


def normalize_name_for_vendor_lookup(name: str) -> str:
    """
    Normalize asset name for vendor lookup by stripping common suffixes.

    Removes environment markers, parenthetical notes, and common suffixes
    to extract the base vendor name for lookup.

    Examples:
        "Notion-prod" -> "notion"
        "Notion (Legacy)" -> "notion"
        "Monday.com-Test" -> "monday.com"
        "Zapier Integration" -> "zapier"
        "Slack-dev" -> "slack"
        "GitHub API v2" -> "github"

    Args:
        name: The asset name to normalize

    Returns:
        Normalized name with suffixes removed
    """
    name = name.lower().strip()
    # Remove parenthetical and bracketed notes
    name = re.sub(r'\s*[\(\[].*?[\)\]]', '', name)
    # Remove hyphen/underscore + environment/version suffixes
    name = re.sub(r'[-_]\s*(prod|dev|test|staging|legacy|integration|api|v\d+).*$', '', name, flags=re.IGNORECASE)
    # Remove space + environment suffixes
    name = re.sub(r'\s+(prod|dev|test|staging|legacy|integration|api)$', '', name, flags=re.IGNORECASE)
    return name.strip()


def normalize_string(s: str) -> str:
    """
    Normalize a string for entity matching.

    Used in correlate_entities for canonical name matching.
    Lowercases, strips whitespace, and removes special characters except dots.

    Args:
        s: The string to normalize

    Returns:
        Normalized string
    """
    if not s:
        return ""
    normalized = s.lower().strip()
    # Remove special chars but preserve dots (for domains)
    normalized = re.sub(r'[^a-z0-9.]', '', normalized)
    return normalized
