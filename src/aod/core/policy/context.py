"""
PolicyContext - Encapsulated Business Logic for Pipeline.

ARCHITECTURAL PRINCIPLE:
Instead of spreading `if score > 0.95` checks throughout the code,
the pipeline receives a PolicyContext that encapsulates all business logic.

Old code:
    if score > 0.95:
        ...

New code:
    if policy.is_confident(score):
        ...

This allows changing the definition of "confident" without searching
for every hardcoded threshold check.

Usage:
    policy = PolicyContext.for_tenant(tenant_profile)

    # Replace hardcoded checks
    if policy.is_confident(score):
        ...

    # Replace hardcoded financial thresholds
    if policy.is_material_spend(amount, currency):
        ...

    # Get strategy-specific thresholds
    thresholds = policy.preset_thresholds

Feb 2026: Added TenantStrategySelector for binding tenant -> strategy.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

from .strategies import (
    ScoringStrategy,
    BalancedStrategy,
    StrictEnterpriseStrategy,
    LooseStartupStrategy,
    StrategyProfile,
    get_strategy,
    ConfidenceResult,
    SORClassificationResult,
    PresetThresholds,
)

logger = logging.getLogger(__name__)


@dataclass
class TenantProfile:
    """
    Tenant profile determines which scoring strategy to use.

    This comes from Farm's tenant configuration.
    """
    tenant_id: str
    strategy_profile: str = StrategyProfile.BALANCED.value
    industry: Optional[str] = None
    size: Optional[str] = None  # small, medium, large
    cmdb_reliability: Optional[str] = None  # high, medium, low
    currency: str = "USD"
    tenant_type: Optional[str] = None  # BANK, STARTUP, ENTERPRISE, SMB
    custom_thresholds: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# TENANT STRATEGY SELECTOR
# =============================================================================
# This is the FACTORY that binds a tenant to the correct strategy.
# Without this, strategies are just dead code.

# Industry -> Strategy mapping
_INDUSTRY_STRATEGY_MAP: Dict[str, str] = {
    # Strict industries (regulated, SOX/HIPAA/PCI-DSS compliance)
    "finance": StrategyProfile.STRICT_ENTERPRISE.value,
    "banking": StrategyProfile.STRICT_ENTERPRISE.value,
    "insurance": StrategyProfile.STRICT_ENTERPRISE.value,
    "healthcare": StrategyProfile.STRICT_ENTERPRISE.value,
    "pharma": StrategyProfile.STRICT_ENTERPRISE.value,
    "government": StrategyProfile.STRICT_ENTERPRISE.value,

    # Loose industries (move fast, less governance)
    "tech_saas": StrategyProfile.LOOSE_STARTUP.value,
    "startup": StrategyProfile.LOOSE_STARTUP.value,
    "media": StrategyProfile.LOOSE_STARTUP.value,
    "gaming": StrategyProfile.LOOSE_STARTUP.value,

    # Balanced (default for everyone else)
    "retail": StrategyProfile.BALANCED.value,
    "manufacturing": StrategyProfile.BALANCED.value,
    "logistics": StrategyProfile.BALANCED.value,
    "energy": StrategyProfile.BALANCED.value,
}

# Tenant type -> Strategy mapping (overrides industry)
_TENANT_TYPE_STRATEGY_MAP: Dict[str, str] = {
    "BANK": StrategyProfile.STRICT_ENTERPRISE.value,
    "REGULATED": StrategyProfile.STRICT_ENTERPRISE.value,
    "ENTERPRISE": StrategyProfile.STRICT_ENTERPRISE.value,
    "STARTUP": StrategyProfile.LOOSE_STARTUP.value,
    "SMB": StrategyProfile.LOOSE_STARTUP.value,
    "MIDMARKET": StrategyProfile.BALANCED.value,
}


def select_strategy_for_tenant(profile: TenantProfile) -> ScoringStrategy:
    """
    Select the appropriate scoring strategy for a tenant.

    Resolution order:
    1. Explicit strategy_profile (if set and not "balanced")
    2. Tenant type (BANK, STARTUP, etc.)
    3. Industry vertical (finance, healthcare, etc.)
    4. CMDB reliability (low CMDB reliability -> loose strategy)
    5. Default to Balanced

    Args:
        profile: TenantProfile from Farm or database

    Returns:
        Appropriate ScoringStrategy instance
    """
    # 1. Explicit strategy override
    if profile.strategy_profile and profile.strategy_profile != StrategyProfile.BALANCED.value:
        strategy = get_strategy(profile.strategy_profile)
        logger.info("strategy.selected.explicit", extra={
            "tenant_id": profile.tenant_id,
            "strategy": strategy.name,
            "reason": "explicit_profile"
        })
        return strategy

    # 2. Tenant type override
    if profile.tenant_type:
        tenant_type_upper = profile.tenant_type.upper()
        if tenant_type_upper in _TENANT_TYPE_STRATEGY_MAP:
            strategy_name = _TENANT_TYPE_STRATEGY_MAP[tenant_type_upper]
            strategy = get_strategy(strategy_name)
            logger.info("strategy.selected.tenant_type", extra={
                "tenant_id": profile.tenant_id,
                "tenant_type": profile.tenant_type,
                "strategy": strategy.name
            })
            return strategy

    # 3. Industry-based selection
    if profile.industry:
        industry_lower = profile.industry.lower()
        if industry_lower in _INDUSTRY_STRATEGY_MAP:
            strategy_name = _INDUSTRY_STRATEGY_MAP[industry_lower]
            strategy = get_strategy(strategy_name)
            logger.info("strategy.selected.industry", extra={
                "tenant_id": profile.tenant_id,
                "industry": profile.industry,
                "strategy": strategy.name
            })
            return strategy

    # 4. CMDB reliability heuristic
    if profile.cmdb_reliability:
        cmdb_rel = profile.cmdb_reliability.lower()
        if cmdb_rel == "low":
            # Low CMDB reliability = don't trust it = loose mode
            strategy = LooseStartupStrategy()
            logger.info("strategy.selected.cmdb_reliability", extra={
                "tenant_id": profile.tenant_id,
                "cmdb_reliability": profile.cmdb_reliability,
                "strategy": strategy.name
            })
            return strategy
        elif cmdb_rel == "high":
            # High CMDB reliability = trust it = strict mode
            strategy = StrictEnterpriseStrategy()
            logger.info("strategy.selected.cmdb_reliability", extra={
                "tenant_id": profile.tenant_id,
                "cmdb_reliability": profile.cmdb_reliability,
                "strategy": strategy.name
            })
            return strategy

    # 5. Default to Balanced
    strategy = BalancedStrategy()
    logger.info("strategy.selected.default", extra={
        "tenant_id": profile.tenant_id,
        "strategy": strategy.name
    })
    return strategy


class PolicyContext:
    """
    Encapsulated business logic for a pipeline run.

    This is the SINGLE entry point for all policy decisions.
    Pass this through the pipeline instead of accessing hardcoded thresholds.
    """

    def __init__(
        self,
        strategy: ScoringStrategy,
        tenant_profile: Optional[TenantProfile] = None,
        currency: str = "USD",
    ):
        self._strategy = strategy
        self._tenant_profile = tenant_profile
        self._currency = currency

    @classmethod
    def for_tenant(cls, tenant_profile: TenantProfile) -> "PolicyContext":
        """
        Create PolicyContext for a specific tenant.

        Uses select_strategy_for_tenant() to determine the appropriate
        strategy based on tenant type, industry, and CMDB reliability.
        """
        strategy = select_strategy_for_tenant(tenant_profile)
        return cls(
            strategy=strategy,
            tenant_profile=tenant_profile,
            currency=tenant_profile.currency,
        )

    @classmethod
    def default(cls) -> "PolicyContext":
        """Create default PolicyContext (balanced strategy)."""
        return cls(strategy=BalancedStrategy())

    @classmethod
    def strict(cls) -> "PolicyContext":
        """Create strict PolicyContext for enterprise tenants."""
        return cls(strategy=StrictEnterpriseStrategy())

    @classmethod
    def loose(cls) -> "PolicyContext":
        """Create loose PolicyContext for startup tenants."""
        return cls(strategy=LooseStartupStrategy())

    # =========================================================================
    # Strategy Properties
    # =========================================================================

    @property
    def strategy_name(self) -> str:
        """Get the strategy name for logging."""
        return self._strategy.name

    @property
    def strategy_description(self) -> str:
        """Get human-readable strategy description."""
        return self._strategy.description

    @property
    def currency(self) -> str:
        """Get the tenant's default currency."""
        return self._currency

    # =========================================================================
    # Confidence Checks - Replace `if score > 0.95`
    # =========================================================================

    def is_confident(self, score: float) -> bool:
        """
        Check if score meets high confidence threshold.

        Use this instead of: if score > 0.95
        """
        return self._strategy.is_high_confidence(score).is_confident

    def is_high_confidence(self, score: float) -> ConfidenceResult:
        """Get detailed high confidence result."""
        return self._strategy.is_high_confidence(score)

    def is_medium_confidence(self, score: float) -> ConfidenceResult:
        """Get detailed medium confidence result."""
        return self._strategy.is_medium_confidence(score)

    def is_tier_1(self, score: float) -> bool:
        """Check if score qualifies as Tier 1 (direct crawl)."""
        return self._strategy.is_tier_1_confidence(score)

    def is_tier_2(self, score: float) -> bool:
        """Check if score qualifies as Tier 2 (observation)."""
        return self._strategy.is_tier_2_confidence(score)

    def is_tier_3(self, score: float) -> bool:
        """Check if score qualifies as Tier 3 (inferred)."""
        return self._strategy.is_tier_3_confidence(score)

    # =========================================================================
    # SOR Classification - Replace hardcoded weight calculations
    # =========================================================================

    def classify_sor(
        self,
        signals: Dict[str, Any],
        has_cmdb: bool = False,
        has_idp: bool = False,
        has_finance: bool = False,
    ) -> SORClassificationResult:
        """
        Classify whether an asset is a System of Record.

        Use this instead of manual weight calculations.
        """
        return self._strategy.classify_sor(signals, has_cmdb, has_idp, has_finance)

    def is_likely_sor(
        self,
        signals: Dict[str, Any],
        has_cmdb: bool = False,
        has_idp: bool = False,
        has_finance: bool = False,
    ) -> bool:
        """Quick check if asset is likely an SOR."""
        result = self.classify_sor(signals, has_cmdb, has_idp, has_finance)
        return result.is_sor

    # =========================================================================
    # Preset Inference - Replace hardcoded density thresholds
    # =========================================================================

    @property
    def preset_thresholds(self) -> PresetThresholds:
        """Get thresholds for enterprise preset inference."""
        return self._strategy.get_preset_thresholds()

    def is_ipaas_dominant(self, density: float) -> bool:
        """Check if iPaaS density triggers iPaaS-centric preset."""
        return density >= self.preset_thresholds.ipaas_dominance

    def is_warehouse_canonical(self, density: float) -> bool:
        """Check if warehouse density triggers warehouse preset."""
        return density >= self.preset_thresholds.warehouse_canonical

    def is_event_bus_primary(self, density: float) -> bool:
        """Check if event bus density triggers event-driven preset."""
        return density >= self.preset_thresholds.event_bus_primary

    def is_gateway_centric(self, density: float) -> bool:
        """Check if API gateway density triggers gateway preset."""
        return density >= self.preset_thresholds.api_gateway_centric

    def is_scrappy(self, total_fabric_density: float) -> bool:
        """Check if org is scrappy (minimal fabric plane usage)."""
        return total_fabric_density < self.preset_thresholds.scrappy_threshold

    def should_infer_fabric_plane(
        self,
        has_evidence: bool,
        evidence_confidence: float = 0.0,
    ) -> bool:
        """
        Determine if we should make a Tier 3 fabric plane inference.

        Strict mode: Never infer
        Loose mode: Always try to infer
        Balanced: Infer if no strong evidence
        """
        return self._strategy.should_infer_fabric_plane(has_evidence, evidence_confidence)

    # =========================================================================
    # Financial Thresholds - Replace hardcoded dollar amounts
    # =========================================================================

    def is_material_spend(
        self,
        amount: float,
        currency: Optional[str] = None,
    ) -> bool:
        """
        Check if spend amount is material for SOR classification.

        Use this instead of: if annual_spend >= 50000
        """
        curr = currency or self._currency
        return self._strategy.is_material_spend(amount, curr)

    def get_finance_gap_threshold(self, severity: str = "HIGH") -> float:
        """
        Get monthly threshold for finance gap findings.

        Use this instead of: FINANCE_HIGH_MATERIALITY_THRESHOLD = 1000
        """
        return self._strategy.get_finance_gap_threshold(severity)

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for logging/debugging."""
        thresholds = self.preset_thresholds
        return {
            "strategy": self._strategy.name,
            "description": self._strategy.description,
            "currency": self._currency,
            "preset_thresholds": {
                "ipaas_dominance": thresholds.ipaas_dominance,
                "warehouse_canonical": thresholds.warehouse_canonical,
                "event_bus_primary": thresholds.event_bus_primary,
                "api_gateway_centric": thresholds.api_gateway_centric,
                "scrappy_threshold": thresholds.scrappy_threshold,
            },
            "high_confidence_threshold": self._strategy.is_high_confidence(0.0).threshold_used,
            "medium_confidence_threshold": self._strategy.is_medium_confidence(0.0).threshold_used,
            "finance_gap_high": self.get_finance_gap_threshold("HIGH"),
            "finance_gap_medium": self.get_finance_gap_threshold("MEDIUM"),
        }


# Global default context (can be overridden per-request)
_default_context: Optional[PolicyContext] = None


def get_default_context() -> PolicyContext:
    """Get the default PolicyContext."""
    global _default_context
    if _default_context is None:
        _default_context = PolicyContext.default()
    return _default_context


def set_default_context(context: PolicyContext) -> None:
    """Set the default PolicyContext."""
    global _default_context
    _default_context = context
    logger.info("policy_context.default_set", extra={
        "strategy": context.strategy_name
    })
