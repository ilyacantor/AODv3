"""
Canonical domain normalization module.

This is the SINGLE source of truth for hostname/domain normalization.
All pipeline stages MUST use these functions for consistent key generation.

Key Invariants:
- Same input always produces same output (deterministic)
- eTLD+1 extraction uses Public Suffix List via tldextract
- IPs are handled separately (return None for domain, IP as-is for hostname)
- Punycode is decoded to unicode consistently
"""

import re
from typing import Optional
from functools import lru_cache

import tldextract


@lru_cache(maxsize=10000)
def normalize_hostname(hostname: str) -> Optional[str]:
    """
    Normalize a hostname to a consistent format.
    
    Steps:
    1. Lowercase
    2. Strip scheme (http://, https://)
    3. Strip path/query/fragment
    4. Strip port (:443)
    5. Strip trailing dot
    6. Decode punycode to unicode
    
    Args:
        hostname: Raw hostname string
        
    Returns:
        Normalized hostname, or None if invalid/empty
    """
    if not hostname:
        return None
    
    h = hostname.lower().strip()
    
    h = re.sub(r'^https?://', '', h)
    
    h = h.split('/')[0]
    h = h.split('?')[0]
    h = h.split('#')[0]
    
    h = re.sub(r':\d+$', '', h)
    
    h = h.rstrip('.')
    
    if h.startswith('xn--') or '.xn--' in h:
        try:
            h = h.encode('ascii').decode('idna')
        except (UnicodeError, UnicodeDecodeError):
            pass
    
    if not h or h == 'localhost':
        return None
    
    return h


def is_ip_address(hostname: str) -> bool:
    """Check if a hostname is an IP address (v4 or v6)."""
    if not hostname:
        return False
    
    ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if re.match(ipv4_pattern, hostname):
        parts = hostname.split('.')
        return all(0 <= int(p) <= 255 for p in parts)
    
    if ':' in hostname and not '/' in hostname:
        return True
    
    return False


@lru_cache(maxsize=10000)
def extract_registered_domain(hostname: str) -> Optional[str]:
    """
    Extract the registered domain (eTLD+1) from a hostname.
    
    Uses Public Suffix List to correctly handle:
    - foo.bar.co.uk -> bar.co.uk
    - app.example.com -> example.com
    - myapp.github.io -> myapp.github.io (known service domain)
    
    Args:
        hostname: Normalized hostname
        
    Returns:
        Registered domain (eTLD+1), or None if invalid/IP
    """
    normalized = normalize_hostname(hostname)
    if not normalized:
        return None
    
    if is_ip_address(normalized):
        return None
    
    extracted = tldextract.extract(normalized)
    
    if not extracted.suffix:
        return None
    
    if extracted.domain:
        if extracted.subdomain:
            return f"{extracted.domain}.{extracted.suffix}"
        return f"{extracted.domain}.{extracted.suffix}"
    
    return None


@lru_cache(maxsize=10000)
def derive_canonical_asset_key(hostname: str) -> Optional[str]:
    """
    Derive the canonical asset key from a hostname.
    
    This is the PRIMARY function for asset key generation.
    All planes MUST use this for consistent keying.
    
    Args:
        hostname: Raw hostname or domain string
        
    Returns:
        Canonical asset key (registered domain), or None if not derivable
    """
    return extract_registered_domain(hostname)


def extract_hostname_from_url(url: str) -> Optional[str]:
    """
    Extract and normalize hostname from a URL.
    
    Handles:
    - Full URLs: https://app.example.com/path?query
    - Bare hostnames: app.example.com
    - Hostnames with ports: example.com:8080
    
    Args:
        url: URL or hostname string
        
    Returns:
        Normalized hostname, or None if invalid
    """
    if not url:
        return None
    
    return normalize_hostname(url)


def looks_like_domain(text: str) -> bool:
    """
    Check if a text string looks like a domain name.
    
    Used to detect when an observation name is actually a domain.
    
    Args:
        text: Text to check
        
    Returns:
        True if the text appears to be a domain name
    """
    if not text:
        return False
    
    text = text.lower().strip()
    
    if is_ip_address(text):
        return False
    
    if '.' not in text:
        return False
    
    parts = text.split('.')
    if len(parts) < 2:
        return False
    
    tld = parts[-1]
    if len(tld) < 2 or len(tld) > 6:
        return False
    if not tld.isalpha():
        return False
    
    domain_pattern = r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$'
    return bool(re.match(domain_pattern, text))


SERVICE_DOMAINS = {
    'github.io',
    'herokuapp.com',
    'azurewebsites.net',
    'cloudfront.net',
    'amazonaws.com',
    's3.amazonaws.com',
    'googleusercontent.com',
    'appspot.com',
    'firebaseapp.com',
    'netlify.app',
    'vercel.app',
    'pages.dev',
    'workers.dev',
    'fly.dev',
    'render.com',
    'onrender.com',
}


def is_service_domain(hostname: str) -> bool:
    """
    Check if a hostname is a known service/platform domain.
    
    These domains still produce valid asset keys even though
    the eTLD+1 might look "weird".
    
    Args:
        hostname: Normalized hostname
        
    Returns:
        True if it's a known service domain
    """
    if not hostname:
        return False
    
    normalized = normalize_hostname(hostname)
    if not normalized:
        return False
    
    for service in SERVICE_DOMAINS:
        if normalized.endswith(f'.{service}') or normalized == service:
            return True
    
    return False
