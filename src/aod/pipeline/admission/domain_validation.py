"""Domain validation utilities for admission gates."""

from typing import Optional

from ..vendor_inference import extract_registered_domain


def _get_excluded_domains() -> set[str]:
    """Get all excluded domains from policy config (infrastructure + custom + corporate)."""
    from ...core.policy import get_current_config
    return get_current_config().get_all_excluded_domains()


def _get_banned_domains() -> set[str]:
    """Get only explicitly banned domains from policy config.

    Gate 0.5 uses this to block domains that are absolutely forbidden.
    Infrastructure domains are NOT included here — they are handled
    separately at Gate 2 where governance (IdP/CMDB) can override.
    """
    from ...core.policy import get_current_config
    config = get_current_config()
    banned = set()
    banned.update(config.exclusion_lists.banned_domains)
    banned.update(config.custom_exclusions_config.domains)
    banned.update(config.corporate_root_domains_config.domains)
    banned.update(config.exclusions)
    banned.update(config.exclusion_lists.custom_exclusions)
    return banned


def _get_corporate_root_domains() -> set[str]:
    """Get corporate root domains from policy config."""
    from ...core.policy import get_current_config
    return get_current_config().corporate_root_domains


def _get_infrastructure_domains() -> set[str]:
    """Get infrastructure domains from policy config."""
    from ...core.policy import get_current_config
    return get_current_config().infrastructure_domains


def is_banned_domain(domain: Optional[str]) -> bool:
    """Check if domain is in the banned domains policy list.

    Banned domains are immediately blocked regardless of any governance evidence.
    Returns True if the registered domain (eTLD+1) matches a banned domain.
    """
    if not domain:
        return False
    registered = extract_registered_domain(domain)
    if not registered:
        return False
    banned_domains = _get_banned_domains()
    return registered.lower() in banned_domains


def is_corporate_root_domain(domain: Optional[str]) -> bool:
    """Check if domain is a corporate/marketing root domain that should never be admitted."""
    if not domain:
        return False
    domain_lower = domain.lower().strip()
    corporate_domains = _get_corporate_root_domains()
    return domain_lower in corporate_domains


def is_infrastructure_domain(domain: Optional[str]) -> bool:
    """Check if domain is an infrastructure/tooling domain that should not be admitted as a SaaS asset."""
    if not domain:
        return False
    registered = extract_registered_domain(domain)
    if not registered:
        return False
    infra_domains = _get_infrastructure_domains()
    return registered in infra_domains
