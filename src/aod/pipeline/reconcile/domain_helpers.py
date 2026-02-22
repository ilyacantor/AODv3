"""Domain extraction and normalization helpers for reconciliation."""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

from ..vendor_inference import DOMAIN_TO_VENDOR, VENDOR_TO_DOMAIN
from ..canonical_key import (
    ALIAS_DOMAINS_TO_COLLAPSE,
    normalize_to_canonical_vendor_domain,
    compute_canonical_key,
)
from ..domain_cache import extract_domain


def extract_raw_domain(domain_input: str) -> Optional[str]:
    """
    Extract raw domain from various input formats.

    Handles URLs, email addresses, and plain domains.

    Args:
        domain_input: Raw domain string, URL, or email

    Returns:
        Cleaned domain string or None if invalid
    """
    if not domain_input:
        return None

    # Strip whitespace and lowercase
    domain = domain_input.strip().lower()

    # Handle URLs
    if "://" in domain:
        # Extract host from URL
        try:
            from urllib.parse import urlparse
            parsed = urlparse(domain)
            domain = parsed.netloc or parsed.path.split("/")[0]
        except Exception as e:
            logger.debug("URL parse failed for %r: %s", domain_input, e)

    # Handle email addresses
    if "@" in domain:
        domain = domain.split("@")[-1]

    # Remove port numbers
    if ":" in domain:
        domain = domain.split(":")[0]

    # Remove trailing dots
    domain = domain.rstrip(".")

    # Validate basic structure
    if not domain or "." not in domain:
        return None

    # Check for invalid characters
    if not re.match(r"^[a-z0-9][-a-z0-9.]*[a-z0-9]$", domain):
        return None

    return domain


def extract_registered_domain(domain: str) -> Optional[str]:
    """
    Extract registered domain (eTLD+1) from a full domain.

    e.g., mail.google.com -> google.com
         app.acme.co.uk -> acme.co.uk

    Args:
        domain: Full domain name

    Returns:
        Registered domain or None if extraction fails
    """
    if not domain:
        return None

    try:
        extracted = extract_domain(domain)
        if extracted.suffix and extracted.domain:
            return f"{extracted.domain}.{extracted.suffix}"
    except Exception as e:
        logger.debug("tldextract failed for %r: %s", domain, e)

    return None


def resolve_domain_key(
    domains: list[str],
    vendor: Optional[str] = None,
    name: str = ""
) -> tuple[str, bool, list[str]]:
    """
    Resolve the canonical domain key for reconciliation.

    This ensures consistent key resolution between reconciliation
    and the UI, preventing count mismatches.

    Args:
        domains: List of domains from asset identifiers
        vendor: Optional vendor name
        name: Asset name (fallback if no domain)

    Returns:
        Tuple of (domain_key, is_canonical, alias_keys)
        - domain_key: Canonical key for domain aggregation
        - is_canonical: True if key is from a real domain
        - alias_keys: All domain variants found
    """
    try:
        result = compute_canonical_key(domains=domains, vendor=vendor, name=name)
        return (result.primary_key, result.is_canonical, result.all_variants)
    except ValueError:
        # Fallback: sanitized name
        sanitized = re.sub(r"[^a-z0-9]", "", name.lower())
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

    registered = extract_registered_domain(domain)
    if not registered:
        return None

    if domain.lower() == registered.lower():
        return None

    return registered


# Underscore aliases for backwards compatibility
_extract_raw_domain = extract_raw_domain
_extract_registered_domain = extract_registered_domain
_normalize_to_canonical_vendor_domain = normalize_to_canonical_vendor_domain
