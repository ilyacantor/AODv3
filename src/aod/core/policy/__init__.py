"""
Policy Engine - Configuration-Driven Admission and Classification.

This module provides a centralized, pure-function policy evaluation system
that replaces hardcoded business rules with configurable thresholds.

Feb 2026 Additions:
- ScoringStrategy: Strategy Pattern for tenant-specific heuristics
- PolicyContext: Encapsulated business logic passed through pipeline
- TenantProfile: Tenant configuration for strategy selection
"""

from .schema import (
    PolicyConfig,
    AdmissionConfig,
    ScopeConfig,
    ActivityWindowsConfig,
    FinanceThresholdsConfig,
    AdmissionGatesConfig,
    ScopeTogglesConfig,
    FuzzyMatchingConfig,
    VendorInferenceConfig,
    QueryLimitsConfig,
    ExclusionListsConfig,
    FarmSyncConfig,
)
from .engine import PolicyEngine, PolicyDecision
from .loader import get_current_config, load_config, reload_config, save_config
from .strategies import (
    ScoringStrategy,
    StrictEnterpriseStrategy,
    LooseStartupStrategy,
    BalancedStrategy,
    StrategyProfile,
    get_strategy,
    register_strategy,
    ConfidenceResult,
    SORClassificationResult,
    PresetThresholds,
)
from .context import (
    PolicyContext,
    TenantProfile,
    get_default_context,
    set_default_context,
    select_strategy_for_tenant,
)

__all__ = [
    # Config schema
    "PolicyConfig",
    "AdmissionConfig",
    "ScopeConfig",
    "ActivityWindowsConfig",
    "FinanceThresholdsConfig",
    "AdmissionGatesConfig",
    "ScopeTogglesConfig",
    "FuzzyMatchingConfig",
    "VendorInferenceConfig",
    "QueryLimitsConfig",
    "ExclusionListsConfig",
    "FarmSyncConfig",
    # Engine
    "PolicyEngine",
    "PolicyDecision",
    # Loader
    "get_current_config",
    "load_config",
    "reload_config",
    "save_config",
    # Strategies (Feb 2026)
    "ScoringStrategy",
    "StrictEnterpriseStrategy",
    "LooseStartupStrategy",
    "BalancedStrategy",
    "StrategyProfile",
    "get_strategy",
    "register_strategy",
    "ConfidenceResult",
    "SORClassificationResult",
    "PresetThresholds",
    # Context (Feb 2026)
    "PolicyContext",
    "TenantProfile",
    "get_default_context",
    "set_default_context",
    "select_strategy_for_tenant",
]
