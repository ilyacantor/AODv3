"""Correlation matching constants and thresholds."""

# =============================================================================
# CORRELATION MATCHING CONSTANTS
# =============================================================================

# Thresholds for contains-match validation
CONTAINS_MATCH_MIN_LENGTH = 8  # Minimum length for ratio-based contains matching
CONTAINS_MATCH_RATIO_THRESHOLD = 0.7  # shorter/longer ratio for valid contains match

# Token length thresholds for matching
MIN_TOKEN_LENGTH_FOR_MATCH = 4  # Minimum token length for domain/name matching (allows zoom, slack)
MIN_DOMAIN_TOKEN_LENGTH_FOR_FINANCE = 6  # Minimum domain token length for finance plane matching

# Cache sizes
LRU_CACHE_SIZE = 10000  # Standard LRU cache size for memoized functions


# Environment suffixes for disambiguation
ENV_SUFFIXES = {
    "prod", "production", "prd",
    "dev", "development",
    "staging", "stg", "stage",
    "test", "testing", "tst",
    "uat", "qa",
    "sandbox", "sbx",
    "demo"
}

# Legacy markers for disambiguation
LEGACY_MARKERS = {
    "legacy", "old", "deprecated", "v1", "v2", "archive", "archived",
    "retired", "obsolete", "backup", "previous"
}


# Match methods that are authoritative (exact matches)
AUTHORITATIVE_MATCH_METHODS = {
    "domain", "uri", "canonical_name",  # Existing
    "verified_alias_domain",  # Explicit alias mapping (hipchat.com → atlassian.com)
    "foreign_key",            # Explicit foreign key (idp_app_id, cmdb_ci_id)
    "explicit_id",            # Explicit ID match
    "cmdb_domains_array",     # CMDB record.domains[] exact match
    "cmdb_canonical_domain",  # CMDB record.canonical_domain exact match
}

# Match methods that are heuristic (cannot assert governance)
HEURISTIC_MATCH_METHODS = {
    "fuzzy", "contains", "vendor", "domain_vendor", "vendor_fallback",
    "name_contains_domain_token", "normalization_token", "cross_domain_brand",
    "domain_token_to_name", "registered_domain_token", "canonical_name_as_domain"
}

# Match methods that indicate cross-TLD correlation (must not trigger identity merge)
CROSS_TLD_MATCH_METHODS = {"cross_domain_brand"}


# Known distinct products that should NOT match via contains
# (e.g., "box" should not match "dropbox")
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


# Generic tokens to skip for finance plane matching
GENERIC_TOKENS_FOR_FINANCE = frozenset({
    'cloud', 'data', 'online', 'digital', 'software', 'service', 'services',
    'solutions', 'platform', 'systems', 'tech', 'technology', 'global',
    'enterprise', 'business', 'group', 'corp', 'corporation', 'company',
    'consulting', 'analytics', 'media', 'network', 'security', 'storage',
    'hosting', 'managed', 'professional', 'integration', 'connect'
})

# Generic tokens used in contains matching
GENERIC_TOKENS = frozenset({
    'cloud', 'data', 'online', 'digital', 'software', 'service', 'services',
    'solutions', 'platform', 'systems', 'tech', 'technology', 'global',
    'enterprise', 'business', 'group', 'corp', 'corporation', 'company',
    'consulting', 'analytics', 'media', 'network', 'security', 'storage',
    'hosting', 'managed', 'professional', 'integration', 'connect'
})

# Vendor prefixes to skip
VENDOR_PREFIXES = frozenset({'the', 'a', 'an', 'team', 'inc', 'corp', 'llc', 'ltd', 'co', 'by'})
