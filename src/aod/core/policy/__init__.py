"""
Policy Engine - Configuration-Driven Admission and Classification.

This module provides a centralized, pure-function policy evaluation system
that replaces hardcoded business rules with configurable thresholds.
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

__all__ = [
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
    "PolicyEngine",
    "PolicyDecision",
    "get_current_config",
    "load_config",
    "reload_config",
    "save_config",
]
