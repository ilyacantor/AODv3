"""Eligibility checks for reconciliation."""

import logging
import re
from typing import Optional

from ...models.output_contracts import Asset, AssetType

logger = logging.getLogger(__name__)

# Domains that represent infrastructure rather than SaaS products
INFRASTRUCTURE_DOMAIN_PATTERNS = [
    r"^cdn\.",
    r"^static\.",
    r"^assets\.",
    r"^img\.",
    r"^images\.",
    r"\.cdn\.",
    r"\.static\.",
    r"cloudfront\.net$",
    r"cloudflare\.com$",
    r"akamai\.net$",
    r"fastly\.net$",
    r"edgecast\.net$",
]

# Compiled patterns for efficiency
_INFRA_PATTERNS = [re.compile(p, re.IGNORECASE) for p in INFRASTRUCTURE_DOMAIN_PATTERNS]


def is_infrastructure_domain(domain: str) -> bool:
    """
    Check if a domain represents infrastructure (CDN, static assets, etc.).

    Infrastructure domains are excluded from reconciliation because they
    represent delivery mechanisms, not SaaS applications.

    Args:
        domain: The domain to check

    Returns:
        True if domain matches infrastructure patterns
    """
    if not domain:
        return False

    for pattern in _INFRA_PATTERNS:
        if pattern.search(domain):
            return True
    return False


def is_reconciliation_eligible(
    asset: Asset,
    check_infrastructure: bool = True
) -> tuple[bool, Optional[str]]:
    """
    Check if an asset is eligible for reconciliation output.

    Eligible assets are SaaS applications that should be classified
    as shadow, zombie, parked, or active. Infrastructure, internal
    tools, and certain asset types are excluded.

    Args:
        asset: The asset to check
        check_infrastructure: Whether to check infrastructure domain patterns

    Returns:
        Tuple of (is_eligible, exclusion_reason)
        - is_eligible: True if asset should be included in reconciliation
        - exclusion_reason: Human-readable reason if excluded, None otherwise
    """
    # Check asset type - only SaaS and certain types are eligible
    ineligible_types = {
        AssetType.INFRASTRUCTURE,
        AssetType.INTERNAL_TOOL,
        AssetType.UNKNOWN,
    }

    if asset.asset_type in ineligible_types:
        return False, f"Asset type {asset.asset_type.value} is not eligible for reconciliation"

    # Check for infrastructure domains
    if check_infrastructure and asset.identifiers:
        for domain in asset.identifiers.domains:
            if is_infrastructure_domain(domain):
                return False, f"Infrastructure domain detected: {domain}"

    # Check for LLM exclusion
    if hasattr(asset, 'llm_metadata') and asset.llm_metadata:
        if asset.llm_metadata.exclusion_reason:
            return False, f"LLM excluded: {asset.llm_metadata.exclusion_reason}"

    return True, None


# Underscore alias for backwards compatibility
_is_infrastructure_domain = is_infrastructure_domain
