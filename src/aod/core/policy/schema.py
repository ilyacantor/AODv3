"""
PolicyConfig Schema - The Constitution.

Defines the configuration structure that drives all admission and
classification logic. This is the single source of truth for policy rules.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AdmissionConfig:
    """
    Admission gate thresholds.
    
    These values control when an entity qualifies for admission as an asset.
    """
    minimum_spend: float = 200.0
    noise_floor: int = 2
    zombie_window_days: int = 90
    require_sso_for_idp: bool = True
    require_valid_ci_type: bool = True
    require_valid_lifecycle: bool = True


@dataclass
class ScopeConfig:
    """
    Scope toggles for different operational modes.
    """
    include_infra: bool = False
    treat_directory_as_idp: bool = False


@dataclass
class PolicyConfig:
    """
    Complete policy configuration.
    
    Combines admission thresholds, scope toggles, and exclusion lists
    into a single configuration object that can be hot-reloaded.
    """
    admission: AdmissionConfig = field(default_factory=AdmissionConfig)
    scope: ScopeConfig = field(default_factory=ScopeConfig)
    exclusions: list[str] = field(default_factory=list)
    
    corporate_root_domains: set[str] = field(default_factory=set)
    infrastructure_domains: set[str] = field(default_factory=set)
    
    def to_dict(self) -> dict:
        """Serialize to dictionary for API response."""
        return {
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
            },
            "exclusions": self.exclusions,
            "seed_exclusions": {
                "corporate_root_domains": sorted(list(self.corporate_root_domains)),
                "infrastructure_domains": sorted(list(self.infrastructure_domains)),
            }
        }
