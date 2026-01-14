"""
PolicyConfig Schema - The Constitution.

Defines the configuration structure that drives all admission and
classification logic. This is the single source of truth for policy rules.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ActivityWindowsConfig:
    """Time windows for activity status calculations."""
    discovery_activity_window_days: int = 90
    zombie_window_days: int = 90
    default_activity_window_days: int = 90


@dataclass
class FinanceThresholdsConfig:
    """Financial thresholds for admission and findings."""
    minimum_spend: float = 200.0
    finance_gap_monthly_threshold: float = 200.0
    finance_gap_annual_threshold: float = 2000.0


@dataclass
class AdmissionGatesConfig:
    """Admission gate thresholds and switches."""
    noise_floor: int = 1
    require_sso_for_idp: bool = True
    require_valid_ci_type: bool = True
    require_valid_lifecycle: bool = True
    min_discovery_sources_for_shadow: int = 1  # Match Farm: single source is sufficient
    allow_finance_only_admission: bool = False
    enable_vendor_propagation: bool = True
    finance_requires_discovery: bool = True
    require_corroboration: bool = False  # Match Farm: honor noise_floor=1
    stale_window_days: int = 30


@dataclass
class ScopeTogglesConfig:
    """Feature toggles for operational modes."""
    include_infra: bool = False
    treat_directory_as_idp: bool = False
    use_policy_engine: bool = True
    late_binding_domain_merge: bool = True


@dataclass
class FuzzyMatchingConfig:
    """Parameters for fuzzy name matching in correlation."""
    max_edit_distance: int = 2
    max_edit_ratio: float = 0.20
    min_name_length: int = 4


@dataclass
class VendorInferenceConfig:
    """Parameters for vendor hypothesis inference."""
    max_confidence: float = 0.9


@dataclass
class QueryLimitsConfig:
    """Database and storage limits."""
    max_observation_samples: int = 2000
    default_rejection_limit: int = 1000
    default_query_limit: int = 1000


@dataclass
class ExclusionListsConfig:
    """Domain exclusion lists for admission filtering."""
    custom_exclusions: list[str] = field(default_factory=list)
    banned_domains: list[str] = field(default_factory=list)
    infrastructure_domains: list[str] = field(default_factory=list)
    corporate_root_domains: list[str] = field(default_factory=list)


@dataclass
class FarmSyncConfig:
    """Farm synchronization settings."""
    webhook_url: str = ""
    auto_notify_on_change: bool = True
    sync_interval_seconds: int = 0


@dataclass
class AdmissionConfig:
    """
    Admission gate thresholds (legacy).
    
    These values control when an entity qualifies for admission as an asset.
    Kept for backward compatibility - maps to new structure.
    """
    minimum_spend: float = 200.0
    noise_floor: int = 1
    zombie_window_days: int = 90
    require_sso_for_idp: bool = True
    require_valid_ci_type: bool = True
    require_valid_lifecycle: bool = True


@dataclass
class ScopeConfig:
    """
    Scope toggles for different operational modes (legacy).
    Kept for backward compatibility - maps to new structure.
    """
    include_infra: bool = False
    treat_directory_as_idp: bool = False
    use_policy_engine: bool = False
    late_binding_domain_merge: bool = False


@dataclass
class PolicyConfig:
    """
    Complete policy configuration.
    
    Combines all policy sections into a single configuration object
    that can be hot-reloaded.
    """
    activity_windows: ActivityWindowsConfig = field(default_factory=ActivityWindowsConfig)
    finance_thresholds: FinanceThresholdsConfig = field(default_factory=FinanceThresholdsConfig)
    admission_gates: AdmissionGatesConfig = field(default_factory=AdmissionGatesConfig)
    scope_toggles: ScopeTogglesConfig = field(default_factory=ScopeTogglesConfig)
    fuzzy_matching: FuzzyMatchingConfig = field(default_factory=FuzzyMatchingConfig)
    vendor_inference: VendorInferenceConfig = field(default_factory=VendorInferenceConfig)
    query_limits: QueryLimitsConfig = field(default_factory=QueryLimitsConfig)
    exclusion_lists: ExclusionListsConfig = field(default_factory=ExclusionListsConfig)
    farm_sync: FarmSyncConfig = field(default_factory=FarmSyncConfig)
    
    admission: AdmissionConfig = field(default_factory=AdmissionConfig)
    scope: ScopeConfig = field(default_factory=ScopeConfig)
    exclusions: list[str] = field(default_factory=list)
    corporate_root_domains: set[str] = field(default_factory=set)
    infrastructure_domains: set[str] = field(default_factory=set)
    
    def to_dict(self) -> dict:
        """Serialize to dictionary for API response."""
        return {
            "activity_windows": {
                "discovery_activity_window_days": self.activity_windows.discovery_activity_window_days,
                "zombie_window_days": self.activity_windows.zombie_window_days,
                "default_activity_window_days": self.activity_windows.default_activity_window_days,
            },
            "finance_thresholds": {
                "minimum_spend": self.finance_thresholds.minimum_spend,
                "finance_gap_monthly_threshold": self.finance_thresholds.finance_gap_monthly_threshold,
                "finance_gap_annual_threshold": self.finance_thresholds.finance_gap_annual_threshold,
            },
            "admission_gates": {
                "noise_floor": self.admission_gates.noise_floor,
                "require_sso_for_idp": self.admission_gates.require_sso_for_idp,
                "require_valid_ci_type": self.admission_gates.require_valid_ci_type,
                "require_valid_lifecycle": self.admission_gates.require_valid_lifecycle,
                "min_discovery_sources_for_shadow": self.admission_gates.min_discovery_sources_for_shadow,
                "allow_finance_only_admission": self.admission_gates.allow_finance_only_admission,
                "enable_vendor_propagation": self.admission_gates.enable_vendor_propagation,
                "finance_requires_discovery": self.admission_gates.finance_requires_discovery,
                "require_corroboration": self.admission_gates.require_corroboration,
                "stale_window_days": self.admission_gates.stale_window_days,
            },
            "scope_toggles": {
                "include_infra": self.scope_toggles.include_infra,
                "treat_directory_as_idp": self.scope_toggles.treat_directory_as_idp,
                "use_policy_engine": self.scope_toggles.use_policy_engine,
                "late_binding_domain_merge": self.scope_toggles.late_binding_domain_merge,
            },
            "fuzzy_matching": {
                "max_edit_distance": self.fuzzy_matching.max_edit_distance,
                "max_edit_ratio": self.fuzzy_matching.max_edit_ratio,
                "min_name_length": self.fuzzy_matching.min_name_length,
            },
            "vendor_inference": {
                "max_confidence": self.vendor_inference.max_confidence,
            },
            "query_limits": {
                "max_observation_samples": self.query_limits.max_observation_samples,
                "default_rejection_limit": self.query_limits.default_rejection_limit,
                "default_query_limit": self.query_limits.default_query_limit,
            },
            "exclusion_lists": {
                "custom_exclusions": self.exclusion_lists.custom_exclusions,
                "banned_domains": self.exclusion_lists.banned_domains,
                "infrastructure_domains": self.exclusion_lists.infrastructure_domains,
                "corporate_root_domains": self.exclusion_lists.corporate_root_domains,
            },
            "farm_sync": {
                "webhook_url": self.farm_sync.webhook_url,
                "auto_notify_on_change": self.farm_sync.auto_notify_on_change,
                "sync_interval_seconds": self.farm_sync.sync_interval_seconds,
            },
            "admission": {
                "minimum_spend": self.admission.minimum_spend,
                "noise_floor": self.admission.noise_floor,
                "zombie_window_days": self.admission.zombie_window_days,
                "require_sso_for_idp": self.admission.require_sso_for_idp,
                "require_valid_ci_type": self.admission.require_valid_ci_type,
                "require_valid_lifecycle": self.admission.require_valid_lifecycle,
            },
            "scope": {
                "include_infra": self.scope.include_infra,
                "treat_directory_as_idp": self.scope.treat_directory_as_idp,
                "use_policy_engine": self.scope.use_policy_engine,
                "late_binding_domain_merge": self.scope.late_binding_domain_merge,
            },
            "exclusions": self.exclusions,
            "seed_exclusions": {
                "corporate_root_domains": sorted(list(self.corporate_root_domains)),
                "infrastructure_domains": sorted(list(self.infrastructure_domains)),
            },
            "infrastructure_seeds": sorted(list(self.infrastructure_domains)),
            "corporate_root_domains": sorted(list(self.corporate_root_domains)),
        }
