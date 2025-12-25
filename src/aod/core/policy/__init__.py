"""
Policy Engine - Configuration-Driven Admission and Classification.

This module provides a centralized, pure-function policy evaluation system
that replaces hardcoded business rules with configurable thresholds.
"""

from .schema import PolicyConfig, AdmissionConfig, ScopeConfig
from .engine import PolicyEngine, PolicyDecision
from .loader import get_current_config, load_config, reload_config

__all__ = [
    "PolicyConfig",
    "AdmissionConfig", 
    "ScopeConfig",
    "PolicyEngine",
    "PolicyDecision",
    "get_current_config",
    "load_config",
    "reload_config",
]
