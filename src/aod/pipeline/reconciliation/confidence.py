"""
Composite Confidence Calculator

Computes overall confidence scores from multi-source evidence.
Replaces flat confidence values with computed scores based on:
- Evidence tier (Tier 1 > Tier 2 > Tier 3)
- Number of corroborating sources
- Recency of evidence
- Source reliability
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from ...models.output_contracts import (
    FabricRoutingEvidence,
    EvidenceSourcePlane,
    EvidenceTier,
    FabricPlaneType,
)

logger = logging.getLogger(__name__)


# Base confidence by tier
TIER_BASE_CONFIDENCE = {
    EvidenceTier.TIER_1_DIRECT: 0.95,
    EvidenceTier.TIER_2_OBSERVED: 0.75,  # Base for Tier 2
    EvidenceTier.TIER_3_INFERRED: 0.35,  # Base for Tier 3
}

# Source reliability weights (how much we trust each source)
SOURCE_RELIABILITY = {
    EvidenceSourcePlane.DIRECT_CRAWL: 1.0,     # Authoritative
    EvidenceSourcePlane.NETWORK: 0.95,          # Traffic doesn't lie
    EvidenceSourcePlane.CLOUD: 0.90,            # Infrastructure truth
    EvidenceSourcePlane.FINANCE: 0.85,          # Contracts = commitment
    EvidenceSourcePlane.CMDB: 0.70,             # Often stale
    EvidenceSourcePlane.IDP: 0.75,              # Auth ≠ data flow
    EvidenceSourcePlane.ENDPOINT: 0.80,         # Observed activity
}

# Bonus for corroborating evidence from multiple sources
CORROBORATION_BONUS = {
    1: 0.0,     # Single source, no bonus
    2: 0.05,   # Two sources agree
    3: 0.08,   # Three sources
    4: 0.10,   # Four+ sources (diminishing returns)
}

# Recency decay - older evidence is less reliable
RECENCY_THRESHOLDS = {
    7: 1.0,     # Last 7 days: full weight
    30: 0.95,   # Last 30 days: slight decay
    90: 0.85,   # Last 90 days: moderate decay
    180: 0.70,  # Last 180 days: significant decay
    365: 0.50,  # Over 6 months: major decay
}

# Maximum confidence cap
MAX_CONFIDENCE = 0.98


@dataclass
class ConfidenceFactors:
    """
    Breakdown of factors contributing to confidence score.
    Useful for debugging and explaining classification decisions.
    """
    base_confidence: float  # From evidence tier
    source_reliability: float  # From source type
    corroboration_bonus: float  # From multiple sources
    recency_factor: float  # Based on evidence age
    contradiction_penalty: float  # If conflicting evidence exists

    # Final computed score
    composite_score: float

    # Evidence breakdown
    evidence_count: int
    tier_1_count: int
    tier_2_count: int
    tier_3_count: int
    source_count: int
    sources: List[str] = field(default_factory=list)

    # Oldest/newest evidence
    oldest_evidence: Optional[datetime] = None
    newest_evidence: Optional[datetime] = None


class CompositeConfidenceCalculator:
    """
    Calculates composite confidence scores from multi-source evidence.

    The algorithm:
    1. Start with base confidence from highest-tier evidence
    2. Apply source reliability weight
    3. Add corroboration bonus for multiple agreeing sources
    4. Apply recency decay
    5. Subtract contradiction penalty (if conflicts exist)
    6. Cap at MAX_CONFIDENCE
    """

    def __init__(self, contradiction_penalty: float = 0.15):
        self.contradiction_penalty = contradiction_penalty

    def calculate(
        self,
        evidence_list: List[FabricRoutingEvidence],
        has_contradiction: bool = False,
        target_plane: Optional[FabricPlaneType] = None
    ) -> ConfidenceFactors:
        """
        Calculate composite confidence from evidence list.

        Args:
            evidence_list: All evidence for an asset
            has_contradiction: Whether conflicting evidence exists
            target_plane: If specified, only consider evidence for this plane

        Returns:
            ConfidenceFactors with detailed breakdown
        """
        if not evidence_list:
            return self._empty_factors()

        # Filter to target plane if specified
        if target_plane:
            evidence_list = [e for e in evidence_list if e.fabric_plane_type == target_plane]
            if not evidence_list:
                return self._empty_factors()

        # Categorize evidence by tier
        tier_1 = [e for e in evidence_list if self._get_tier(e) == EvidenceTier.TIER_1_DIRECT]
        tier_2 = [e for e in evidence_list if self._get_tier(e) == EvidenceTier.TIER_2_OBSERVED]
        tier_3 = [e for e in evidence_list if self._get_tier(e) == EvidenceTier.TIER_3_INFERRED]

        # Get unique sources
        sources = list(set(e.source_plane.value for e in evidence_list))
        source_count = len(sources)

        # Base confidence from highest tier
        if tier_1:
            base_confidence = TIER_BASE_CONFIDENCE[EvidenceTier.TIER_1_DIRECT]
            primary_tier = EvidenceTier.TIER_1_DIRECT
        elif tier_2:
            base_confidence = TIER_BASE_CONFIDENCE[EvidenceTier.TIER_2_OBSERVED]
            primary_tier = EvidenceTier.TIER_2_OBSERVED
        else:
            base_confidence = TIER_BASE_CONFIDENCE[EvidenceTier.TIER_3_INFERRED]
            primary_tier = EvidenceTier.TIER_3_INFERRED

        # Source reliability (average of all sources)
        source_reliability = self._calculate_source_reliability(evidence_list)

        # Corroboration bonus
        corroboration_bonus = CORROBORATION_BONUS.get(
            min(source_count, 4), CORROBORATION_BONUS[4]
        )

        # Recency factor
        recency_factor, oldest, newest = self._calculate_recency_factor(evidence_list)

        # Apply formula
        # Composite = base * reliability * recency + corroboration - contradiction
        intermediate = base_confidence * source_reliability * recency_factor
        with_bonus = intermediate + corroboration_bonus

        # Apply contradiction penalty
        penalty = self.contradiction_penalty if has_contradiction else 0.0
        final_score = max(0.0, min(MAX_CONFIDENCE, with_bonus - penalty))

        return ConfidenceFactors(
            base_confidence=base_confidence,
            source_reliability=source_reliability,
            corroboration_bonus=corroboration_bonus,
            recency_factor=recency_factor,
            contradiction_penalty=penalty,
            composite_score=final_score,
            evidence_count=len(evidence_list),
            tier_1_count=len(tier_1),
            tier_2_count=len(tier_2),
            tier_3_count=len(tier_3),
            source_count=source_count,
            sources=sources,
            oldest_evidence=oldest,
            newest_evidence=newest
        )

    def _get_tier(self, evidence: FabricRoutingEvidence) -> EvidenceTier:
        """Determine tier from evidence source."""
        if evidence.source_plane == EvidenceSourcePlane.DIRECT_CRAWL:
            return EvidenceTier.TIER_1_DIRECT
        elif evidence.source_plane in (
            EvidenceSourcePlane.NETWORK,
            EvidenceSourcePlane.CLOUD,
            EvidenceSourcePlane.FINANCE,
            EvidenceSourcePlane.CMDB,
            EvidenceSourcePlane.IDP,
            EvidenceSourcePlane.ENDPOINT
        ):
            # Check confidence to distinguish Tier 2 from Tier 3
            if evidence.confidence >= 0.60:
                return EvidenceTier.TIER_2_OBSERVED
            else:
                return EvidenceTier.TIER_3_INFERRED

        return EvidenceTier.TIER_3_INFERRED

    def _calculate_source_reliability(
        self,
        evidence_list: List[FabricRoutingEvidence]
    ) -> float:
        """Calculate weighted source reliability."""
        if not evidence_list:
            return 0.5

        # Weight by individual evidence confidence
        total_weight = 0.0
        weighted_reliability = 0.0

        for evidence in evidence_list:
            reliability = SOURCE_RELIABILITY.get(evidence.source_plane, 0.5)
            weight = evidence.confidence  # Use evidence confidence as weight
            weighted_reliability += reliability * weight
            total_weight += weight

        if total_weight == 0:
            return 0.5

        return weighted_reliability / total_weight

    def _calculate_recency_factor(
        self,
        evidence_list: List[FabricRoutingEvidence]
    ) -> tuple[float, Optional[datetime], Optional[datetime]]:
        """Calculate recency factor based on evidence age."""
        from datetime import timezone
        now = datetime.now(timezone.utc)

        def normalize_timestamp(ts: datetime) -> datetime:
            """Ensure timestamp is timezone-aware (UTC)."""
            if ts.tzinfo is None:
                return ts.replace(tzinfo=timezone.utc)
            return ts

        timestamps = [normalize_timestamp(e.timestamp) for e in evidence_list if e.timestamp]

        if not timestamps:
            return 0.85, None, None  # Default if no timestamps

        oldest = min(timestamps)
        newest = max(timestamps)

        # Use newest evidence for recency calculation
        days_old = (now - newest).days

        # Find applicable threshold
        for threshold_days, factor in sorted(RECENCY_THRESHOLDS.items()):
            if days_old <= threshold_days:
                return factor, oldest, newest

        # Very old evidence
        return 0.40, oldest, newest

    def _empty_factors(self) -> ConfidenceFactors:
        """Return empty factors for no evidence."""
        return ConfidenceFactors(
            base_confidence=0.0,
            source_reliability=0.0,
            corroboration_bonus=0.0,
            recency_factor=0.0,
            contradiction_penalty=0.0,
            composite_score=0.0,
            evidence_count=0,
            tier_1_count=0,
            tier_2_count=0,
            tier_3_count=0,
            source_count=0,
            sources=[]
        )


def calculate_composite_confidence(
    evidence_list: List[FabricRoutingEvidence],
    has_contradiction: bool = False,
    target_plane: Optional[FabricPlaneType] = None
) -> float:
    """
    Convenience function to calculate composite confidence.

    Args:
        evidence_list: All evidence for an asset
        has_contradiction: Whether conflicting evidence exists
        target_plane: If specified, only consider evidence for this plane

    Returns:
        Composite confidence score (0.0 - 0.98)
    """
    calculator = CompositeConfidenceCalculator()
    factors = calculator.calculate(evidence_list, has_contradiction, target_plane)
    return factors.composite_score
