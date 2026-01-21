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
class IdpGovernanceConfig:
    """
    IdP governance matching policy - controls how IdP matches assert governance.
    
    This is a risk-appetite policy. Different customers have different tolerances:
    
    STRICT (trust_heuristic_matches=False, Farm's approach):
    - Only domain-based matches grant governance
    - Heuristic matches (fuzzy, name, vendor) are enrichment-only
    - Never miss shadow IT, but may create more alerts
    
    LOOSE (trust_heuristic_matches=True):
    - Heuristic matches CAN grant governance
    - Reduces noise for customers with messy IdP data
    - May hide shadow IT risks (false negatives)
    """
    trust_heuristic_matches: bool = False  # Default: strict (Farm's approach)
    heuristic_requires_sso: bool = True    # When loose, still require SSO


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
class InfrastructureDomainHandlingConfig:
    """
    Policy for handling infrastructure and vendor root domains.
    
    Infrastructure domains are shared multi-tenant services that are NOT
    enterprise-owned assets. Excluding them is a modeling choice, not a shortcut.
    """
    mode: str = "exclude"  # "exclude" or "observe_only"
    shared_infrastructure_domains: list[str] = field(default_factory=list)
    vendor_root_portals: list[str] = field(default_factory=list)
    dev_build_infrastructure: list[str] = field(default_factory=list)
    # Jan 2026: Generic collision roots - high-collision eTLD+1 domains
    # that are likely extraction artifacts, not owned assets
    # Examples: cdn.com, edge.com, global.com, assets.com, static.com
    # Behavior: If unanchored (no CMDB/IdP/Finance/Cloud) -> suppress
    # If anchored -> allow but tag RISK_GENERIC_DOMAIN=true
    generic_collision_roots: list[str] = field(default_factory=list)
    
    def get_all_excluded_domains(self) -> set[str]:
        """Get all domains that should be excluded based on current mode."""
        if self.mode == "exclude":
            return set(self.shared_infrastructure_domains + 
                      self.vendor_root_portals + 
                      self.dev_build_infrastructure)
        return set()
    
    def get_all_infrastructure_domains(self) -> set[str]:
        """Get all infrastructure domains regardless of mode."""
        return set(self.shared_infrastructure_domains + 
                  self.vendor_root_portals + 
                  self.dev_build_infrastructure)
    
    def is_generic_collision_root(self, domain: str) -> bool:
        """Check if domain is a generic collision root (high-collision eTLD+1)."""
        return domain.lower() in [d.lower() for d in self.generic_collision_roots]


@dataclass
class CustomExclusionsConfig:
    """Operator-managed domain exclusions."""
    domains: list[str] = field(default_factory=list)


@dataclass
class CorporateRootDomainsConfig:
    """Customer corporate domains to exclude from shadow classification."""
    domains: list[str] = field(default_factory=list)


@dataclass
class ExclusionListsConfig:
    """Domain exclusion lists for admission filtering (legacy compatibility)."""
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
class SORScoringConfig:
    """
    System of Record (SOR) scoring configuration.
    
    SOR tagging identifies assets that serve as authoritative data sources
    for specific data domains (customer, employee, financial, etc.).
    
    SOR is ORTHOGONAL to Shadow/Zombie/Governed classifications.
    """
    enabled: bool = True
    weights: dict = field(default_factory=lambda: {
        "cmdb_authoritative": 40,
        "known_sor_vendor": 30,
        "middleware_exporter": 25,
        "enterprise_sso_scim": 20,
        "enterprise_contract": 15,
        "multi_department": 15,
        "high_corroboration": 10,
        "edge_app_penalty": -20
    })
    confidence_thresholds: dict = field(default_factory=lambda: {
        "high": 0.75,
        "medium": 0.50
    })
    known_sor_vendors: dict = field(default_factory=lambda: {
        "customer": ["salesforce.com", "hubspot.com", "dynamics.com"],
        "employee": ["workday.com", "adp.com", "bamboohr.com"],
        "financial": ["netsuite.com", "quickbooks.com", "xero.com"],
        "product": ["sap.com", "oracle.com"]
    })


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
    idp_governance: IdpGovernanceConfig = field(default_factory=IdpGovernanceConfig)
    fuzzy_matching: FuzzyMatchingConfig = field(default_factory=FuzzyMatchingConfig)
    vendor_inference: VendorInferenceConfig = field(default_factory=VendorInferenceConfig)
    query_limits: QueryLimitsConfig = field(default_factory=QueryLimitsConfig)
    exclusion_lists: ExclusionListsConfig = field(default_factory=ExclusionListsConfig)
    farm_sync: FarmSyncConfig = field(default_factory=FarmSyncConfig)
    
    # New semantic infrastructure domain handling (Jan 2026)
    infrastructure_domain_handling: InfrastructureDomainHandlingConfig = field(
        default_factory=InfrastructureDomainHandlingConfig
    )
    custom_exclusions_config: CustomExclusionsConfig = field(default_factory=CustomExclusionsConfig)
    corporate_root_domains_config: CorporateRootDomainsConfig = field(default_factory=CorporateRootDomainsConfig)
    
    # Jan 2026: Key strategy versioning for reconciliation compatibility
    # v1 = current (domains[0] based), v2 = new (provenance-aware priority)
    key_strategy_version: str = "v1"
    
    # Jan 2026: SOR (System of Record) scoring configuration
    sor_scoring: SORScoringConfig = field(default_factory=SORScoringConfig)
    
    # Legacy fields for backward compatibility
    admission: AdmissionConfig = field(default_factory=AdmissionConfig)
    scope: ScopeConfig = field(default_factory=ScopeConfig)
    exclusions: list[str] = field(default_factory=list)
    corporate_root_domains: set[str] = field(default_factory=set)
    infrastructure_domains: set[str] = field(default_factory=set)
    
    def get_all_excluded_domains(self) -> set[str]:
        """Get all domains that should be excluded from admission."""
        excluded = set()
        # Add infrastructure domains based on handling mode
        excluded.update(self.infrastructure_domain_handling.get_all_excluded_domains())
        # Add custom exclusions
        excluded.update(self.custom_exclusions_config.domains)
        # Add corporate root domains
        excluded.update(self.corporate_root_domains_config.domains)
        # Add legacy exclusions for backward compatibility
        excluded.update(self.exclusions)
        excluded.update(self.exclusion_lists.custom_exclusions)
        excluded.update(self.exclusion_lists.banned_domains)
        return excluded
    
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
            "idp_governance": {
                "trust_heuristic_matches": self.idp_governance.trust_heuristic_matches,
                "heuristic_requires_sso": self.idp_governance.heuristic_requires_sso,
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
            "infrastructure_domain_handling": {
                "mode": self.infrastructure_domain_handling.mode,
                "shared_infrastructure_domains": self.infrastructure_domain_handling.shared_infrastructure_domains,
                "vendor_root_portals": self.infrastructure_domain_handling.vendor_root_portals,
                "dev_build_infrastructure": self.infrastructure_domain_handling.dev_build_infrastructure,
                "generic_collision_roots": self.infrastructure_domain_handling.generic_collision_roots,
            },
            "key_strategy_version": self.key_strategy_version,
            "custom_exclusions": {
                "domains": self.custom_exclusions_config.domains,
            },
            "corporate_root_domains_config": {
                "domains": self.corporate_root_domains_config.domains,
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
            "sor_scoring": {
                "enabled": self.sor_scoring.enabled,
                "weights": self.sor_scoring.weights,
                "confidence_thresholds": self.sor_scoring.confidence_thresholds,
                "known_sor_vendors": self.sor_scoring.known_sor_vendors,
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
            "all_excluded_domains": sorted(list(self.get_all_excluded_domains())),
            "seed_exclusions": {
                "corporate_root_domains": sorted(list(self.corporate_root_domains)),
                "infrastructure_domains": sorted(list(self.infrastructure_domains)),
            },
            "infrastructure_seeds": sorted(list(self.infrastructure_domains)),
            "corporate_root_domains": sorted(list(self.corporate_root_domains)),
        }
