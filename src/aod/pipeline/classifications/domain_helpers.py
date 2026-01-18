"""Domain resolution helpers for derived classifications."""

import re
from typing import Optional

from ..domain_cache import extract_domain
from ..canonical_key import compute_canonical_key
from ...models.output_contracts import Asset


def resolve_domain_key(asset: Asset) -> tuple[str, bool, list[str]]:
    """
    Resolve the canonical domain key for an asset.

    Uses canonical_key.compute_canonical_key() as single source of truth
    for domain normalization.

    Args:
        asset: The asset to resolve

    Returns:
        Tuple of (domain_key, is_canonical, alias_keys) where:
        - domain_key: The canonical vendor domain
        - is_canonical: True if key is a registered domain, False if name-derived
        - alias_keys: List of ALL domain variants from identifiers.domains
    """
    domains = asset.identifiers.domains if asset.identifiers else []
    vendor = asset.vendor if asset.vendor else None
    name = asset.name if asset.name else ""

    try:
        result = compute_canonical_key(domains=domains, vendor=vendor, name=name)
        return (result.primary_key, result.is_canonical, result.all_variants)
    except ValueError:
        # Fallback: sanitized name (should rarely happen)
        sanitized = re.sub(r'[^a-z0-9]', '', name.lower())
        return (sanitized, False, [])


def get_parent_domain(domain: str) -> Optional[str]:
    """
    Extract parent domain from a subdomain.

    e.g., mail.google.com -> google.com

    Args:
        domain: Full domain name

    Returns:
        Parent (registered) domain or None if already root
    """
    if not domain:
        return None

    extracted = extract_domain(domain)
    if not extracted.suffix:
        return None

    registered_domain = f"{extracted.domain}.{extracted.suffix}"
    if domain.lower() == registered_domain.lower():
        return None

    return registered_domain


# Underscore alias for backwards compatibility
_resolve_domain_key = resolve_domain_key
_get_parent_domain = get_parent_domain
