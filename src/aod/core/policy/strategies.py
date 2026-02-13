"""
Scoring Strategies - Strategy Pattern for Tenant-Specific Heuristics.

ARCHITECTURAL PRINCIPLE:
Thresholds are not just numbers - they are HEURISTICS.
Different tenant profiles need different scoring logic:

- StrictEnterpriseStrategy: Must be in CMDB + have 95% confidence
- LooseStartupStrategy: If it looks like a database, it's an SOR
- BalancedStrategy: Middle ground for most tenants

Instead of tuning numbers, we swap entire logic sets.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)


class StrategyProfile(str, Enum):
    """Available scoring strategy profiles."""
    STRICT_ENTERPRISE = "strict_enterprise"
    LOOSE_STARTUP = "loose_startup"
    BALANCED = "balanced"


@dataclass
class ConfidenceResult:
    """Result of a confidence check."""
    is_confident: bool
    confidence_value: float
    threshold_used: float
    rationale: str


@dataclass
class SORClassificationResult:
    """Result of SOR classification."""
    is_sor: bool
    likelihood: str  # high, medium, low, none
    confidence: float
    evidence: List[str]
    domain: Optional[str]  # customer, employee, financial, etc.


@dataclass
class PresetThresholds:
    """Thresholds for enterprise preset inference."""
    ipaas_dominance: float
    warehouse_canonical: float
    event_bus_primary: float
    api_gateway_centric: float
    scrappy_threshold: float


class ScoringStrategy(ABC):
    """
    Abstract base class for scoring strategies.

    Implement this interface to create new scoring profiles.
    The pipeline uses strategy methods instead of hardcoded thresholds.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy name for logging."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description."""
        pass

    # =========================================================================
    # Confidence Checks - Replace hardcoded `if score > 0.95`
    # =========================================================================

    @abstractmethod
    def is_high_confidence(self, score: float) -> ConfidenceResult:
        """Check if score meets high confidence threshold."""
        pass

    @abstractmethod
    def is_medium_confidence(self, score: float) -> ConfidenceResult:
        """Check if score meets medium confidence threshold."""
        pass

    @abstractmethod
    def is_tier_1_confidence(self, score: float) -> bool:
        """Check if score qualifies as Tier 1 (direct crawl)."""
        pass

    @abstractmethod
    def is_tier_2_confidence(self, score: float) -> bool:
        """Check if score qualifies as Tier 2 (observation)."""
        pass

    @abstractmethod
    def is_tier_3_confidence(self, score: float) -> bool:
        """Check if score qualifies as Tier 3 (inferred)."""
        pass

    # =========================================================================
    # SOR Classification - Replace hardcoded weight calculations
    # =========================================================================

    @abstractmethod
    def classify_sor(
        self,
        signals: Dict[str, Any],
        has_cmdb: bool,
        has_idp: bool,
        has_finance: bool,
    ) -> SORClassificationResult:
        """
        Classify whether asset is an SOR.

        Args:
            signals: Dict of signal names to values/weights
            has_cmdb: Whether asset is in CMDB
            has_idp: Whether asset has IdP coverage
            has_finance: Whether asset has finance coverage

        Returns:
            SORClassificationResult with classification decision
        """
        pass

    # =========================================================================
    # Preset Inference - Replace hardcoded density thresholds
    # =========================================================================

    @abstractmethod
    def get_preset_thresholds(self) -> PresetThresholds:
        """Get thresholds for enterprise preset inference."""
        pass

    @abstractmethod
    def should_infer_fabric_plane(
        self,
        has_evidence: bool,
        evidence_confidence: float,
    ) -> bool:
        """Determine if we should make a Tier 3 inference."""
        pass

    # =========================================================================
    # Financial Thresholds - Replace hardcoded dollar amounts
    # =========================================================================

    @abstractmethod
    def is_material_spend(self, annual_spend: float, currency: str = "USD") -> bool:
        """Check if spend is material for SOR classification."""
        pass

    @abstractmethod
    def get_finance_gap_threshold(self, severity: str) -> float:
        """Get threshold for finance gap findings (HIGH/MEDIUM)."""
        pass


class StrictEnterpriseStrategy(ScoringStrategy):
    """
    Strict scoring for mature enterprises.

    Requirements:
    - SOR must be in CMDB + have high confidence
    - Tier 3 inference is disabled
    - Higher thresholds for fabric plane assignment
    """

    @property
    def name(self) -> str:
        return "strict_enterprise"

    @property
    def description(self) -> str:
        return "Strict scoring for mature enterprises with reliable CMDB"

    def is_high_confidence(self, score: float) -> ConfidenceResult:
        threshold = 0.90
        return ConfidenceResult(
            is_confident=score >= threshold,
            confidence_value=score,
            threshold_used=threshold,
            rationale="Strict: requires 90%+ confidence"
        )

    def is_medium_confidence(self, score: float) -> ConfidenceResult:
        threshold = 0.70
        return ConfidenceResult(
            is_confident=score >= threshold,
            confidence_value=score,
            threshold_used=threshold,
            rationale="Strict: requires 70%+ for medium"
        )

    def is_tier_1_confidence(self, score: float) -> bool:
        return score >= 0.95

    def is_tier_2_confidence(self, score: float) -> bool:
        return score >= 0.75

    def is_tier_3_confidence(self, score: float) -> bool:
        # Strict mode: Tier 3 inference is disabled
        return False

    def classify_sor(
        self,
        signals: Dict[str, Any],
        has_cmdb: bool,
        has_idp: bool,
        has_finance: bool,
    ) -> SORClassificationResult:
        """Strict SOR: MUST be in CMDB with authoritative flag."""
        if not has_cmdb:
            return SORClassificationResult(
                is_sor=False,
                likelihood="none",
                confidence=0.0,
                evidence=["Strict mode: SOR must be in CMDB"],
                domain=None
            )

        cmdb_authoritative = signals.get("cmdb_authoritative", 0) > 0
        known_vendor = signals.get("known_sor_vendor", 0) > 0

        if cmdb_authoritative:
            return SORClassificationResult(
                is_sor=True,
                likelihood="high",
                confidence=0.95,
                evidence=["CMDB authoritative flag set"],
                domain=signals.get("domain")
            )

        if known_vendor and has_idp and has_finance:
            return SORClassificationResult(
                is_sor=True,
                likelihood="medium",
                confidence=0.70,
                evidence=["Known SOR vendor + IdP + Finance corroboration"],
                domain=signals.get("domain")
            )

        return SORClassificationResult(
            is_sor=False,
            likelihood="low",
            confidence=0.30,
            evidence=["Strict mode: insufficient evidence for SOR"],
            domain=None
        )

    def get_preset_thresholds(self) -> PresetThresholds:
        return PresetThresholds(
            ipaas_dominance=0.60,       # Stricter: need 60% for iPaaS preset
            warehouse_canonical=0.40,   # Stricter: need 40% for warehouse
            event_bus_primary=0.35,     # Stricter: need 35% for event bus
            api_gateway_centric=0.40,   # Stricter: need 40% for gateway
            scrappy_threshold=0.05,     # Lower: 5% is scrappy
        )

    def should_infer_fabric_plane(
        self,
        has_evidence: bool,
        evidence_confidence: float,
    ) -> bool:
        # Strict mode: Never infer, only use observed evidence
        return False

    def is_material_spend(self, annual_spend: float, currency: str = "USD") -> bool:
        # Normalize to USD (simplified - real impl would use exchange rates)
        normalized = self._normalize_to_usd(annual_spend, currency)
        # Enterprise: $100K+ is material
        return normalized >= 100_000

    def get_finance_gap_threshold(self, severity: str) -> float:
        # Enterprise: higher thresholds
        if severity.upper() == "HIGH":
            return 5000.0  # $5K/month
        return 2000.0  # $2K/month for MEDIUM

    def _normalize_to_usd(self, amount: float, currency: str) -> float:
        """Normalize amount to USD (simplified)."""
        # Real implementation would use exchange rate service
        rates = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "JPY": 0.0067}
        rate = rates.get(currency.upper(), 1.0)
        return amount * rate


class LooseStartupStrategy(ScoringStrategy):
    """
    Loose scoring for startups and scrappy orgs.

    Principles:
    - If it looks like a database, it's probably an SOR
    - CMDB is unreliable, trust pattern matching
    - Tier 3 inference is encouraged
    - Lower spend thresholds matter more
    """

    @property
    def name(self) -> str:
        return "loose_startup"

    @property
    def description(self) -> str:
        return "Loose scoring for startups without mature CMDB"

    def is_high_confidence(self, score: float) -> ConfidenceResult:
        threshold = 0.70
        return ConfidenceResult(
            is_confident=score >= threshold,
            confidence_value=score,
            threshold_used=threshold,
            rationale="Loose: 70%+ is high confidence"
        )

    def is_medium_confidence(self, score: float) -> ConfidenceResult:
        threshold = 0.50
        return ConfidenceResult(
            is_confident=score >= threshold,
            confidence_value=score,
            threshold_used=threshold,
            rationale="Loose: 50%+ is medium confidence"
        )

    def is_tier_1_confidence(self, score: float) -> bool:
        return score >= 0.90

    def is_tier_2_confidence(self, score: float) -> bool:
        return score >= 0.60

    def is_tier_3_confidence(self, score: float) -> bool:
        return score >= 0.30

    def classify_sor(
        self,
        signals: Dict[str, Any],
        has_cmdb: bool,
        has_idp: bool,
        has_finance: bool,
    ) -> SORClassificationResult:
        """Loose SOR: Pattern matching is sufficient."""
        known_vendor = signals.get("known_sor_vendor", 0) > 0
        vendor_domain = signals.get("domain")

        if known_vendor:
            confidence = 0.75
            if has_idp or has_finance:
                confidence = 0.85
            return SORClassificationResult(
                is_sor=True,
                likelihood="high" if confidence >= 0.80 else "medium",
                confidence=confidence,
                evidence=[f"Known SOR vendor pattern match: {vendor_domain}"],
                domain=vendor_domain
            )

        # Startup mode: aggressive inference
        middleware_exporter = signals.get("middleware_exporter", 0) > 0
        if middleware_exporter:
            return SORClassificationResult(
                is_sor=True,
                likelihood="medium",
                confidence=0.65,
                evidence=["Data exporter in middleware topology"],
                domain=vendor_domain
            )

        return SORClassificationResult(
            is_sor=False,
            likelihood="low",
            confidence=0.20,
            evidence=["No SOR indicators found"],
            domain=None
        )

    def get_preset_thresholds(self) -> PresetThresholds:
        return PresetThresholds(
            ipaas_dominance=0.35,       # Looser: 35% is iPaaS-centric
            warehouse_canonical=0.20,   # Looser: 20% for warehouse
            event_bus_primary=0.15,     # Looser: 15% for event bus
            api_gateway_centric=0.20,   # Looser: 20% for gateway
            scrappy_threshold=0.15,     # Higher: 15% is still scrappy
        )

    def should_infer_fabric_plane(
        self,
        has_evidence: bool,
        evidence_confidence: float,
    ) -> bool:
        # Loose mode: Always try to infer if no direct evidence
        if has_evidence and evidence_confidence >= 0.50:
            return False  # Use existing evidence
        return True  # Otherwise, infer

    def is_material_spend(self, annual_spend: float, currency: str = "USD") -> bool:
        normalized = self._normalize_to_usd(annual_spend, currency)
        # Startup: $10K+ is material
        return normalized >= 10_000

    def get_finance_gap_threshold(self, severity: str) -> float:
        # Startup: lower thresholds
        if severity.upper() == "HIGH":
            return 500.0  # $500/month
        return 200.0  # $200/month for MEDIUM

    def _normalize_to_usd(self, amount: float, currency: str) -> float:
        rates = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "JPY": 0.0067}
        rate = rates.get(currency.upper(), 1.0)
        return amount * rate


class BalancedStrategy(ScoringStrategy):
    """
    Balanced scoring for most tenants.

    Middle ground between strict and loose.
    """

    @property
    def name(self) -> str:
        return "balanced"

    @property
    def description(self) -> str:
        return "Balanced scoring for typical enterprise tenants"

    def is_high_confidence(self, score: float) -> ConfidenceResult:
        threshold = 0.75
        return ConfidenceResult(
            is_confident=score >= threshold,
            confidence_value=score,
            threshold_used=threshold,
            rationale="Balanced: 75%+ is high confidence"
        )

    def is_medium_confidence(self, score: float) -> ConfidenceResult:
        threshold = 0.50
        return ConfidenceResult(
            is_confident=score >= threshold,
            confidence_value=score,
            threshold_used=threshold,
            rationale="Balanced: 50%+ is medium confidence"
        )

    def is_tier_1_confidence(self, score: float) -> bool:
        return score >= 0.95

    def is_tier_2_confidence(self, score: float) -> bool:
        return score >= 0.70

    def is_tier_3_confidence(self, score: float) -> bool:
        return score >= 0.35

    def classify_sor(
        self,
        signals: Dict[str, Any],
        has_cmdb: bool,
        has_idp: bool,
        has_finance: bool,
    ) -> SORClassificationResult:
        """Balanced SOR classification."""
        cmdb_auth = signals.get("cmdb_authoritative", 0) > 0
        known_vendor = signals.get("known_sor_vendor", 0) > 0
        vendor_domain = signals.get("domain")

        evidence = []
        confidence = 0.0

        if cmdb_auth:
            confidence += 0.40
            evidence.append("CMDB authoritative")

        if known_vendor:
            confidence += 0.30
            evidence.append(f"Known SOR vendor: {vendor_domain}")

        if has_idp:
            confidence += 0.15
            evidence.append("IdP coverage")

        if has_finance:
            confidence += 0.15
            evidence.append("Finance coverage")

        if confidence >= 0.75:
            likelihood = "high"
        elif confidence >= 0.50:
            likelihood = "medium"
        elif confidence > 0:
            likelihood = "low"
        else:
            likelihood = "none"

        return SORClassificationResult(
            is_sor=confidence >= 0.50,
            likelihood=likelihood,
            confidence=round(confidence, 3),
            evidence=evidence or ["No SOR indicators"],
            domain=vendor_domain
        )

    def get_preset_thresholds(self) -> PresetThresholds:
        return PresetThresholds(
            ipaas_dominance=0.50,
            warehouse_canonical=0.30,
            event_bus_primary=0.25,
            api_gateway_centric=0.30,
            scrappy_threshold=0.10,
        )

    def should_infer_fabric_plane(
        self,
        has_evidence: bool,
        evidence_confidence: float,
    ) -> bool:
        if has_evidence and evidence_confidence >= 0.60:
            return False
        return True

    def is_material_spend(self, annual_spend: float, currency: str = "USD") -> bool:
        normalized = self._normalize_to_usd(annual_spend, currency)
        return normalized >= 50_000

    def get_finance_gap_threshold(self, severity: str) -> float:
        if severity.upper() == "HIGH":
            return 1000.0
        return 500.0

    def _normalize_to_usd(self, amount: float, currency: str) -> float:
        rates = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "JPY": 0.0067}
        rate = rates.get(currency.upper(), 1.0)
        return amount * rate


# Strategy registry
_STRATEGIES: Dict[str, ScoringStrategy] = {
    StrategyProfile.STRICT_ENTERPRISE.value: StrictEnterpriseStrategy(),
    StrategyProfile.LOOSE_STARTUP.value: LooseStartupStrategy(),
    StrategyProfile.BALANCED.value: BalancedStrategy(),
}


def get_strategy(profile: str) -> ScoringStrategy:
    """Get scoring strategy by profile name."""
    strategy = _STRATEGIES.get(profile.lower())
    if strategy is None:
        logger.warning("strategy.unknown_profile",
                       extra={"profile": profile, "using": "balanced"})
        return _STRATEGIES[StrategyProfile.BALANCED.value]
    return strategy


def register_strategy(name: str, strategy: ScoringStrategy) -> None:
    """Register a custom scoring strategy."""
    _STRATEGIES[name.lower()] = strategy
    logger.info("strategy.registered", extra={"name": name})
