"""
Policy Configuration Loader with Hot-Reload Support.

Loads policy configuration from JSON file with sensible defaults,
and supports runtime reloading without restart.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .schema import (
    PolicyConfig,
    AdmissionConfig,
    ScopeConfig,
    ActivityWindowsConfig,
    FinanceThresholdsConfig,
    AdmissionGatesConfig,
    ScopeTogglesConfig,
    IdpGovernanceConfig,
    FuzzyMatchingConfig,
    VendorInferenceConfig,
    QueryLimitsConfig,
    ExclusionListsConfig,
    FarmSyncConfig,
    InfrastructureDomainHandlingConfig,
    CustomExclusionsConfig,
    CorporateRootDomainsConfig,
)


_current_config: Optional[PolicyConfig] = None
_master_config_data: Optional[dict] = None

logger = logging.getLogger(__name__)

# Anchor to project root so path works regardless of cwd (Render does cd src/)
_PROJECT_CONFIG_DIR = Path(__file__).resolve().parents[4] / "config"

CORPORATE_ROOT_DOMAINS: set[str] = set()


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


def _extract_value(section: dict, key: str, default: Any) -> Any:
    """Extract the 'value' field from a policy_master.json setting."""
    setting = section.get(key, {})
    if isinstance(setting, dict) and "value" in setting:
        return setting["value"]
    return default


def _load_from_master(data: dict) -> PolicyConfig:
    """Load PolicyConfig from policy_master.json format."""
    global _master_config_data
    _master_config_data = data
    
    aw_section = data.get("activity_windows", {})
    activity_windows = ActivityWindowsConfig(
        discovery_activity_window_days=_extract_value(aw_section, "discovery_activity_window_days", 90),
        zombie_window_days=_extract_value(aw_section, "zombie_window_days", 90),
        default_activity_window_days=_extract_value(aw_section, "default_activity_window_days", 90),
    )
    
    ft_section = data.get("finance_thresholds", {})
    finance_thresholds = FinanceThresholdsConfig(
        minimum_spend=_extract_value(ft_section, "minimum_spend", 200.0),
        finance_gap_monthly_threshold=_extract_value(ft_section, "finance_gap_monthly_threshold", 200.0),
        finance_gap_annual_threshold=_extract_value(ft_section, "finance_gap_annual_threshold", 2000.0),
    )
    
    ag_section = data.get("admission_gates", {})
    admission_gates = AdmissionGatesConfig(
        noise_floor=_extract_value(ag_section, "noise_floor", 1),
        require_sso_for_idp=_extract_value(ag_section, "require_sso_for_idp", True),
        require_valid_ci_type=_extract_value(ag_section, "require_valid_ci_type", True),
        require_valid_lifecycle=_extract_value(ag_section, "require_valid_lifecycle", True),
        min_discovery_sources_for_shadow=_extract_value(ag_section, "min_discovery_sources_for_shadow", 1),  # Match Farm
        allow_finance_only_admission=_extract_value(ag_section, "allow_finance_only_admission", False),
        enable_vendor_propagation=_extract_value(ag_section, "enable_vendor_propagation", True),
        finance_requires_discovery=_extract_value(ag_section, "finance_requires_discovery", True),
        require_corroboration=_extract_value(ag_section, "require_corroboration", False),  # Match Farm
        stale_window_days=_extract_value(ag_section, "stale_window_days", 30),
    )
    
    st_section = data.get("scope_toggles", {})
    scope_toggles = ScopeTogglesConfig(
        include_infra=_extract_value(st_section, "include_infra", False),
        treat_directory_as_idp=_extract_value(st_section, "treat_directory_as_idp", False),
        use_policy_engine=_extract_value(st_section, "use_policy_engine", True),
        late_binding_domain_merge=_extract_value(st_section, "late_binding_domain_merge", True),
    )
    
    ig_section = data.get("idp_governance", {})
    idp_governance = IdpGovernanceConfig(
        trust_heuristic_matches=_extract_value(ig_section, "trust_heuristic_matches", False),
        heuristic_requires_sso=_extract_value(ig_section, "heuristic_requires_sso", True),
    )
    
    fm_section = data.get("fuzzy_matching", {})
    fuzzy_matching = FuzzyMatchingConfig(
        max_edit_distance=_extract_value(fm_section, "max_edit_distance", 2),
        max_edit_ratio=_extract_value(fm_section, "max_edit_ratio", 0.20),
        min_name_length=_extract_value(fm_section, "min_name_length", 4),
    )
    
    vi_section = data.get("vendor_inference", {})
    vendor_inference = VendorInferenceConfig(
        max_confidence=_extract_value(vi_section, "max_confidence", 0.9),
    )
    
    ql_section = data.get("query_limits", {})
    query_limits = QueryLimitsConfig(
        max_observation_samples=_extract_value(ql_section, "max_observation_samples", 2000),
        default_rejection_limit=_extract_value(ql_section, "default_rejection_limit", 1000),
        default_query_limit=_extract_value(ql_section, "default_query_limit", 1000),
    )
    
    # New infrastructure domain handling (Jan 2026)
    idh_section = data.get("infrastructure_domain_handling", {})
    infrastructure_domain_handling = InfrastructureDomainHandlingConfig(
        mode=_extract_value(idh_section, "mode", "exclude"),
        shared_infrastructure_domains=_extract_value(idh_section, "shared_infrastructure_domains", []),
        vendor_root_portals=_extract_value(idh_section, "vendor_root_portals", []),
        dev_build_infrastructure=_extract_value(idh_section, "dev_build_infrastructure", []),
        generic_collision_roots=_extract_value(idh_section, "generic_collision_roots", []),
    )
    
    # Jan 2026: Key strategy versioning for reconciliation compatibility
    key_strategy_version = _extract_value(data.get("key_strategy_version", {}), "value", "v1")
    if not key_strategy_version or key_strategy_version not in ("v1", "v2"):
        key_strategy_version = "v1"
    
    # New custom exclusions (Jan 2026)
    ce_section = data.get("custom_exclusions", {})
    custom_exclusions_config = CustomExclusionsConfig(
        domains=_extract_value(ce_section, "domains", []),
    )
    
    # New corporate root domains (Jan 2026)
    crd_section = data.get("corporate_root_domains", {})
    corporate_root_domains_config = CorporateRootDomainsConfig(
        domains=_extract_value(crd_section, "domains", []),
    )
    
    # Legacy exclusion_lists for backward compatibility
    el_section = data.get("exclusion_lists", {})
    exclusion_lists = ExclusionListsConfig(
        custom_exclusions=_extract_value(el_section, "custom_exclusions", []),
        banned_domains=_extract_value(el_section, "banned_domains", []),
        infrastructure_domains=_extract_value(el_section, "infrastructure_domains", []),
        corporate_root_domains=_extract_value(el_section, "corporate_root_domains", []),
    )
    
    fs_section = data.get("farm_sync", {})
    farm_sync = FarmSyncConfig(
        webhook_url=_extract_value(fs_section, "webhook_url", ""),
        auto_notify_on_change=_extract_value(fs_section, "auto_notify_on_change", True),
        sync_interval_seconds=_extract_value(fs_section, "sync_interval_seconds", 0),
    )
    
    admission = AdmissionConfig(
        minimum_spend=finance_thresholds.minimum_spend,
        noise_floor=admission_gates.noise_floor,
        zombie_window_days=activity_windows.zombie_window_days,
        require_sso_for_idp=admission_gates.require_sso_for_idp,
        require_valid_ci_type=admission_gates.require_valid_ci_type,
        require_valid_lifecycle=admission_gates.require_valid_lifecycle,
    )
    
    scope = ScopeConfig(
        include_infra=scope_toggles.include_infra,
        treat_directory_as_idp=scope_toggles.treat_directory_as_idp,
        use_policy_engine=scope_toggles.use_policy_engine,
        late_binding_domain_merge=scope_toggles.late_binding_domain_merge,
    )
    
    # Combine all exclusions for legacy compatibility
    exclusions = custom_exclusions_config.domains.copy() if custom_exclusions_config.domains else exclusion_lists.custom_exclusions.copy()
    
    # Build infrastructure_domains set from new structure or legacy
    if infrastructure_domain_handling.dev_build_infrastructure:
        infra_domains = set(infrastructure_domain_handling.dev_build_infrastructure)
    elif exclusion_lists.infrastructure_domains:
        infra_domains = set(exclusion_lists.infrastructure_domains)
    else:
        infra_domains = _get_infrastructure_domains()
    
    # Build corporate_root_domains set from new structure or legacy
    if corporate_root_domains_config.domains:
        corp_domains = set(corporate_root_domains_config.domains)
    elif exclusion_lists.corporate_root_domains:
        corp_domains = set(exclusion_lists.corporate_root_domains)
    else:
        corp_domains = CORPORATE_ROOT_DOMAINS.copy()
    
    return PolicyConfig(
        activity_windows=activity_windows,
        finance_thresholds=finance_thresholds,
        admission_gates=admission_gates,
        scope_toggles=scope_toggles,
        idp_governance=idp_governance,
        fuzzy_matching=fuzzy_matching,
        vendor_inference=vendor_inference,
        query_limits=query_limits,
        exclusion_lists=exclusion_lists,
        farm_sync=farm_sync,
        infrastructure_domain_handling=infrastructure_domain_handling,
        custom_exclusions_config=custom_exclusions_config,
        corporate_root_domains_config=corporate_root_domains_config,
        key_strategy_version=key_strategy_version,
        admission=admission,
        scope=scope,
        exclusions=exclusions,
        corporate_root_domains=corp_domains,
        infrastructure_domains=infra_domains,
    )


def _load_from_legacy(data: dict) -> PolicyConfig:
    """Load PolicyConfig from legacy policy.json format."""
    adm_data = data.get("admission", {})
    admission = AdmissionConfig(
        minimum_spend=adm_data.get("minimum_spend", 200.0),
        noise_floor=adm_data.get("noise_floor", 1),
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
        late_binding_domain_merge=scope_data.get("late_binding_domain_merge", False),
    )
    
    exclusions = data.get("exclusions", [])
    
    activity_windows = ActivityWindowsConfig(
        zombie_window_days=admission.zombie_window_days,
    )
    
    finance_thresholds = FinanceThresholdsConfig(
        minimum_spend=admission.minimum_spend,
    )
    
    admission_gates = AdmissionGatesConfig(
        noise_floor=admission.noise_floor,
        require_sso_for_idp=admission.require_sso_for_idp,
        require_valid_ci_type=admission.require_valid_ci_type,
        require_valid_lifecycle=admission.require_valid_lifecycle,
    )
    
    scope_toggles = ScopeTogglesConfig(
        include_infra=scope.include_infra,
        treat_directory_as_idp=scope.treat_directory_as_idp,
        use_policy_engine=scope.use_policy_engine,
        late_binding_domain_merge=scope.late_binding_domain_merge,
    )
    
    return PolicyConfig(
        activity_windows=activity_windows,
        finance_thresholds=finance_thresholds,
        admission_gates=admission_gates,
        scope_toggles=scope_toggles,
        fuzzy_matching=FuzzyMatchingConfig(),
        vendor_inference=VendorInferenceConfig(),
        query_limits=QueryLimitsConfig(),
        exclusion_lists=ExclusionListsConfig(custom_exclusions=exclusions),
        farm_sync=FarmSyncConfig(),
        admission=admission,
        scope=scope,
        exclusions=exclusions,
        corporate_root_domains=CORPORATE_ROOT_DOMAINS.copy(),
        infrastructure_domains=_get_infrastructure_domains().copy(),
    )


def load_config(path: Optional[str] = None) -> PolicyConfig:
    """
    Load policy configuration from JSON file.
    
    Checks for config/policy_master.json first, falls back to config/policy.json.
    
    Args:
        path: Optional path to config file.
    
    Returns:
        PolicyConfig instance
    """
    global _current_config
    
    if path:
        config_path = Path(path)
        master_path = None
    else:
        master_path = _PROJECT_CONFIG_DIR / "policy_master.json"
        config_path = _PROJECT_CONFIG_DIR / "policy.json"
    
    if master_path and master_path.exists():
        try:
            with open(master_path) as f:
                data = json.load(f)
            _current_config = _load_from_master(data)
            return _current_config
        except (json.JSONDecodeError, IOError) as e:
            logger.warning("Failed to load policy from %s: %s", master_path, e)
    
    if config_path.exists():
        try:
            with open(config_path) as f:
                data = json.load(f)
            
            if "activity_windows" in data or "admission_gates" in data:
                _current_config = _load_from_master(data)
            else:
                _current_config = _load_from_legacy(data)
            return _current_config
        except (json.JSONDecodeError, IOError) as e:
            logger.warning("Failed to load policy from %s: %s", config_path, e)
    
    _current_config = PolicyConfig(
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
    global _current_config, _master_config_data
    _current_config = None
    _master_config_data = None
    return load_config(path)


def _update_setting_value(section: dict, key: str, value: Any) -> None:
    """Update a setting's value while preserving metadata."""
    if key in section and isinstance(section[key], dict):
        section[key]["value"] = value
    else:
        section[key] = {"value": value}


def save_config(config: PolicyConfig, path: Optional[str] = None) -> bool:
    """
    Save policy configuration to policy_master.json.
    
    Preserves the full metadata structure (type, min, max, description).
    Updates the last_modified timestamp.
    
    Args:
        config: PolicyConfig instance to save
        path: Optional path to config file. Defaults to config/policy_master.json
    
    Returns:
        True if save was successful, False otherwise
    """
    global _master_config_data
    
    config_path = Path(path) if path else _PROJECT_CONFIG_DIR / "policy_master.json"
    
    if _master_config_data is None:
        if config_path.exists():
            try:
                with open(config_path) as f:
                    _master_config_data = json.load(f)
            except (json.JSONDecodeError, IOError):
                _master_config_data = {}
        else:
            _master_config_data = {}
    
    data = _master_config_data.copy()
    
    data["last_modified"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    if "activity_windows" not in data:
        data["activity_windows"] = {"description": "Time windows for activity status calculations"}
    aw = data["activity_windows"]
    _update_setting_value(aw, "discovery_activity_window_days", config.activity_windows.discovery_activity_window_days)
    _update_setting_value(aw, "zombie_window_days", config.activity_windows.zombie_window_days)
    _update_setting_value(aw, "default_activity_window_days", config.activity_windows.default_activity_window_days)
    
    if "finance_thresholds" not in data:
        data["finance_thresholds"] = {"description": "Financial thresholds for admission and findings"}
    ft = data["finance_thresholds"]
    _update_setting_value(ft, "minimum_spend", config.finance_thresholds.minimum_spend)
    _update_setting_value(ft, "finance_gap_monthly_threshold", config.finance_thresholds.finance_gap_monthly_threshold)
    _update_setting_value(ft, "finance_gap_annual_threshold", config.finance_thresholds.finance_gap_annual_threshold)
    
    if "admission_gates" not in data:
        data["admission_gates"] = {"description": "Switches controlling admission gate behavior"}
    ag = data["admission_gates"]
    _update_setting_value(ag, "noise_floor", config.admission_gates.noise_floor)
    _update_setting_value(ag, "require_sso_for_idp", config.admission_gates.require_sso_for_idp)
    _update_setting_value(ag, "require_valid_ci_type", config.admission_gates.require_valid_ci_type)
    _update_setting_value(ag, "require_valid_lifecycle", config.admission_gates.require_valid_lifecycle)
    _update_setting_value(ag, "min_discovery_sources_for_shadow", config.admission_gates.min_discovery_sources_for_shadow)
    _update_setting_value(ag, "allow_finance_only_admission", config.admission_gates.allow_finance_only_admission)
    _update_setting_value(ag, "enable_vendor_propagation", config.admission_gates.enable_vendor_propagation)
    _update_setting_value(ag, "finance_requires_discovery", config.admission_gates.finance_requires_discovery)
    _update_setting_value(ag, "require_corroboration", config.admission_gates.require_corroboration)
    _update_setting_value(ag, "stale_window_days", config.admission_gates.stale_window_days)
    
    if "scope_toggles" not in data:
        data["scope_toggles"] = {"description": "Feature toggles for operational modes"}
    st = data["scope_toggles"]
    _update_setting_value(st, "include_infra", config.scope_toggles.include_infra)
    _update_setting_value(st, "treat_directory_as_idp", config.scope_toggles.treat_directory_as_idp)
    _update_setting_value(st, "use_policy_engine", config.scope_toggles.use_policy_engine)
    _update_setting_value(st, "late_binding_domain_merge", config.scope_toggles.late_binding_domain_merge)
    
    if "fuzzy_matching" not in data:
        data["fuzzy_matching"] = {"description": "Parameters for fuzzy name matching in correlation"}
    fm = data["fuzzy_matching"]
    _update_setting_value(fm, "max_edit_distance", config.fuzzy_matching.max_edit_distance)
    _update_setting_value(fm, "max_edit_ratio", config.fuzzy_matching.max_edit_ratio)
    _update_setting_value(fm, "min_name_length", config.fuzzy_matching.min_name_length)
    
    if "vendor_inference" not in data:
        data["vendor_inference"] = {"description": "Parameters for vendor hypothesis inference"}
    vi = data["vendor_inference"]
    _update_setting_value(vi, "max_confidence", config.vendor_inference.max_confidence)
    
    if "query_limits" not in data:
        data["query_limits"] = {"description": "Database and storage limits"}
    ql = data["query_limits"]
    _update_setting_value(ql, "max_observation_samples", config.query_limits.max_observation_samples)
    _update_setting_value(ql, "default_rejection_limit", config.query_limits.default_rejection_limit)
    _update_setting_value(ql, "default_query_limit", config.query_limits.default_query_limit)
    
    if "exclusion_lists" not in data:
        data["exclusion_lists"] = {"description": "Domain exclusion lists for admission filtering"}
    el = data["exclusion_lists"]
    _update_setting_value(el, "custom_exclusions", config.exclusion_lists.custom_exclusions)
    _update_setting_value(el, "banned_domains", config.exclusion_lists.banned_domains)
    _update_setting_value(el, "infrastructure_domains", config.exclusion_lists.infrastructure_domains)
    _update_setting_value(el, "corporate_root_domains", config.exclusion_lists.corporate_root_domains)
    
    if "farm_sync" not in data:
        data["farm_sync"] = {"description": "Farm synchronization settings"}
    fs = data["farm_sync"]
    _update_setting_value(fs, "webhook_url", config.farm_sync.webhook_url)
    _update_setting_value(fs, "auto_notify_on_change", config.farm_sync.auto_notify_on_change)
    _update_setting_value(fs, "sync_interval_seconds", config.farm_sync.sync_interval_seconds)
    
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(data, f, indent=2)
        _master_config_data = data
        return True
    except IOError:
        return False
