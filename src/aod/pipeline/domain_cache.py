"""Cached tldextract operations for performance optimization"""

from functools import lru_cache
import tldextract


@lru_cache(maxsize=10000)
def extract_domain(domain: str) -> tldextract.ExtractResult:
    """
    Cached tldextract.extract() call.
    
    Uses LRU cache to avoid repeated DNS lookups and parsing
    for the same domain. Caches up to 10,000 unique domains.
    """
    return tldextract.extract(domain)


def get_registered_domain(domain: str) -> str:
    """Get the registered domain (e.g., 'google.com' from 'mail.google.com')"""
    extracted = extract_domain(domain)
    if extracted.domain and extracted.suffix:
        return f"{extracted.domain}.{extracted.suffix}"
    return domain


def get_subdomain(domain: str) -> str:
    """Get the subdomain portion"""
    return extract_domain(domain).subdomain


def get_suffix(domain: str) -> str:
    """Get the public suffix (e.g., 'com', 'co.uk')"""
    return extract_domain(domain).suffix


def clear_cache():
    """Clear the domain extraction cache"""
    extract_domain.cache_clear()
