"""
Policy Configuration Loader with Hot-Reload Support.

Loads policy configuration from JSON file with sensible defaults,
and supports runtime reloading without restart.
"""

import json
import os
from pathlib import Path
from typing import Optional

from .schema import PolicyConfig, AdmissionConfig, ScopeConfig


_current_config: Optional[PolicyConfig] = None

CORPORATE_ROOT_DOMAINS: set[str] = set()
# Empty - SaaS vendor domains are legitimate discovery targets.
# This was incorrectly populated with major SaaS vendors (pagerduty.com,
# zendesk.com, okta.com, etc.) which caused them to be killed at admission.
# Corporate root domains are meant for MARKETING websites of a tenant's
# own company, not third-party SaaS platforms they use.


def _get_infrastructure_domains() -> set[str]:
    """Import infrastructure domains from constants module."""
    try:
        from ...constants import INFRASTRUCTURE_DOMAINS
        return INFRASTRUCTURE_DOMAINS
    except ImportError:
        return {
            "redis.io", "redis.com", "postgresql.org", "mysql.com",
            "docker.com", "kubernetes.io", "nginx.org", "apache.org",
            "golang.org", "python.org", "nodejs.org", "npmjs.com",
            "jenkins.io", "terraform.io", "hashicorp.com", "grafana.com",
            "prometheus.io", "elastic.co", "mongodb.org", "kafka.apache.org",
        }


def load_config(path: Optional[str] = None) -> PolicyConfig:
    """
    Load policy configuration from JSON file.
    
    Falls back to sensible defaults if file doesn't exist.
    
    Args:
        path: Optional path to config file. Defaults to config/policy.json
    
    Returns:
        PolicyConfig instance
    """
    global _current_config
    
    config_path = Path(path) if path else Path("config/policy.json")
    
    admission = AdmissionConfig()
    scope = ScopeConfig()
    exclusions: list[str] = []
    
    if config_path.exists():
        try:
            with open(config_path) as f:
                data = json.load(f)
            
            adm_data = data.get("admission", {})
            admission = AdmissionConfig(
                minimum_spend=adm_data.get("minimum_spend", 200.0),
                noise_floor=adm_data.get("noise_floor", 2),
                zombie_window_days=adm_data.get("zombie_window_days", 90),
                require_sso_for_idp=adm_data.get("require_sso_for_idp", True),
                require_valid_ci_type=adm_data.get("require_valid_ci_type", True),
                require_valid_lifecycle=adm_data.get("require_valid_lifecycle", True),
            )
            
            scope_data = data.get("scope", {})
            scope = ScopeConfig(
                include_infra=scope_data.get("include_infra", False),
                treat_directory_as_idp=scope_data.get("treat_directory_as_idp", False),
                use_policy_engine=scope_data.get("use_policy_engine", False),
            )
            
            exclusions = data.get("exclusions", [])
        except (json.JSONDecodeError, IOError):
            pass
    
    _current_config = PolicyConfig(
        admission=admission,
        scope=scope,
        exclusions=exclusions,
        corporate_root_domains=CORPORATE_ROOT_DOMAINS.copy(),
        infrastructure_domains=_get_infrastructure_domains().copy(),
    )
    
    return _current_config


def get_current_config() -> PolicyConfig:
    """
    Get the current policy configuration.
    
    Lazy-loads from file if not already loaded.
    
    Returns:
        Current PolicyConfig instance
    """
    global _current_config
    if _current_config is None:
        return load_config()
    return _current_config


def reload_config(path: Optional[str] = None) -> PolicyConfig:
    """
    Force reload of policy configuration.
    
    Call this when the config file has been updated to pick up changes
    without restarting the application.
    
    Args:
        path: Optional path to config file
    
    Returns:
        Newly loaded PolicyConfig instance
    """
    global _current_config
    _current_config = None
    return load_config(path)
