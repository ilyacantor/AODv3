"""
Normalization utilities for AOD.

Consolidates string normalization functions used across the codebase.
"""

import functools
import re

import tldextract


# Corporate suffixes to strip when extracting normalization tokens
CORPORATE_SUFFIXES = {
    "inc", "incorporated", "corp", "corporation", "llc", "ltd", "limited",
    "technologies", "technology", "tech", "software", "solutions", "services",
    "group", "holdings", "international", "global", "systems", "labs", "co",
    "company", "enterprise", "enterprises", "consulting", "partners"
}


# TLD suffixes to strip
TLD_SUFFIXES = {
    ".com", ".io", ".net", ".org", ".co", ".app", ".ai", ".dev", ".cloud",
    ".us", ".uk", ".de", ".fr", ".ca", ".au", ".eu", ".biz", ".info", ".so"
}


# Environment suffixes to strip from names
ENV_SUFFIXES = {
    "prod", "production", "prd",
    "dev", "development",
    "staging", "stg", "stage",
    "test", "testing", "tst",
    "uat", "qa",
    "sandbox", "sbx",
    "demo", "legacy", "old", "new"
}


@functools.lru_cache(maxsize=10000)
def get_normalization_token(name: str) -> str:
    """
    Extract a core token from a name for deterministic matching.
    
    This function strips common corporate suffixes, TLDs, environment suffixes,
    and punctuation to produce a normalized token that can match across different
    naming conventions (e.g., "Slack Technologies, Inc" -> "slack", "slack.com" -> "slack",
    "Airtable-prod" -> "airtable").
    
    Uses tldextract for proper domain handling to correctly extract base domain
    from subdomains (e.g., "api.stripe.com" -> "stripe").
    
    Args:
        name: Input string (company name, domain, product name)
        
    Returns:
        Normalized core token (lowercase, stripped of suffixes)
    """
    if not name:
        return ""
    
    token = name.lower().strip()
    
    # Remove parenthetical notes early (e.g., "Airtable (Legacy)" -> "Airtable")
    token = re.sub(r'\s*\([^)]*\)', '', token).strip()
    
    # Strip environment suffixes early (e.g., "Airtable-prod" -> "Airtable")
    # This pattern handles -prod, _staging, -dev, etc.
    env_pattern = r'[-_](' + '|'.join(ENV_SUFFIXES) + r')$'
    token = re.sub(env_pattern, '', token, flags=re.IGNORECASE).strip()
    
    # Check if it looks like a domain (contains a valid TLD)
    extracted = tldextract.extract(token)
    if extracted.suffix and extracted.domain:
        # This is a domain - extract the registered domain part
        # e.g., "api.stripe.com" -> "stripe", "service-now.com" -> "servicenow"
        token = extracted.domain
        # Remove hyphens and underscores from domain tokens
        token = token.replace("-", "").replace("_", "")
        return token
    
    # Strip TLD suffixes manually for non-recognized domains
    for tld in TLD_SUFFIXES:
        if token.endswith(tld):
            token = token[:-len(tld)]
            break
    
    # Remove www prefix
    token = re.sub(r'^(www\.)', '', token)
    
    # Check if domain-like (has hyphens but no spaces, after env suffix removal)
    is_domain_like = '.' not in token and '-' in token and not any(c.isspace() for c in token)
    
    if is_domain_like:
        # Domain-like identifier (e.g., "service-now" -> "servicenow")
        token = re.sub(r'[\-_]', '', token)
        token = re.sub(r'[^a-z0-9]', '', token)
        return token
    
    # Product/company name processing
    # Replace punctuation and whitespace with spaces
    token = re.sub(r'[,.\-_\s]+', ' ', token)
    
    # Split into words and filter out corporate suffixes and env suffixes
    words = token.split()
    filtered_words = [w for w in words if w not in CORPORATE_SUFFIXES and w not in ENV_SUFFIXES]
    
    # Take the first meaningful word
    if filtered_words:
        token = filtered_words[0]
    elif words:
        token = words[0]
    
    # Remove any remaining non-alphanumeric characters
    token = re.sub(r'[^a-z0-9]', '', token)
    
    return token


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
