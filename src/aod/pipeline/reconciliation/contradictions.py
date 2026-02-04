"""
Contradiction Detection

Identifies conflicting evidence about fabric plane classification.
Contradictions occur when:
1. Different sources claim different planes for the same pipe
2. Evidence suggests impossible configurations
3. Phase 1 predictions conflict with Phase 2 confirmations

Contradictions don't necessarily mean errors - they can indicate:
- Multi-plane routing (asset uses multiple planes)
- Configuration changes (old evidence vs new)
- Data quality issues (stale CMDB, incorrect finance mappings)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

from ...models.output_contracts import (
    FabricRoutingEvidence,
    FabricPlaneType,
    EvidenceSourcePlane,
)

logger = logging.getLogger(__name__)


class ContradictionSeverity(str, Enum):
    """Severity levels for contradictions."""
    CRITICAL = "critical"  # Blocks classification, needs human review
    HIGH = "high"  # Significant conflict, reduce confidence
    MEDIUM = "medium"  # Notable conflict, flag for review
    LOW = "low"  # Minor inconsistency, informational


class ContradictionType(str, Enum):
    """Types of contradictions."""
    PLANE_CONFLICT = "plane_conflict"  # Different planes claimed
    PHASE_MISMATCH = "phase_mismatch"  # Phase 1 vs Phase 2 disagree
    STALE_EVIDENCE = "stale_evidence"  # Old evidence contradicts new
    IMPOSSIBLE_CONFIG = "impossible_config"  # Technically impossible
    SHADOW_OFFICIAL_CONFLICT = "shadow_official_conflict"  # Shadow vs governed


@dataclass
class Contradiction:
    """
    A detected contradiction in evidence.
    """
    contradiction_id: str
    asset_key: str
    contradiction_type: ContradictionType
    severity: ContradictionSeverity

    # What conflicts
    claim_a: str  # First claim (e.g., "Network evidence: iPaaS via Workato")
    claim_b: str  # Second claim (e.g., "CMDB: API Gateway via Kong")

    # Evidence supporting each claim
    evidence_a: List[FabricRoutingEvidence] = field(default_factory=list)
    evidence_b: List[FabricRoutingEvidence] = field(default_factory=list)

    # Resolution
    resolution_recommendation: str = ""
    resolved: bool = False
    resolution_notes: Optional[str] = None

    # Timestamps
    detected_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ContradictionAnalysis:
    """
    Result of contradiction analysis for an asset.
    """
    asset_key: str
    contradictions: List[Contradiction] = field(default_factory=list)

    has_critical: bool = False
    has_high: bool = False
    total_contradictions: int = 0

    # Impact on classification
    confidence_penalty: float = 0.0
    recommended_action: str = ""


class ContradictionDetector:
    """
    Detects contradictions in fabric plane evidence.

    Analyzes evidence for patterns that indicate conflicts:
    1. Same asset claimed by different planes
    2. Phase 1 predictions that Phase 2 doesn't confirm
    3. Old evidence contradicting recent evidence
    """

    def __init__(self):
        # How old is "stale" evidence (days)
        self.stale_threshold_days = 90

        # Confidence penalties by severity
        self.severity_penalties = {
            ContradictionSeverity.CRITICAL: 0.30,
            ContradictionSeverity.HIGH: 0.20,
            ContradictionSeverity.MEDIUM: 0.10,
            ContradictionSeverity.LOW: 0.05,
        }

    def analyze(
        self,
        asset_key: str,
        evidence: List[FabricRoutingEvidence],
        phase_2_planes: Optional[Set[FabricPlaneType]] = None
    ) -> ContradictionAnalysis:
        """
        Analyze evidence for contradictions.

        Args:
            asset_key: The asset being analyzed
            evidence: All evidence for this asset
            phase_2_planes: Planes confirmed by direct crawl (if any)

        Returns:
            ContradictionAnalysis with detected conflicts
        """
        analysis = ContradictionAnalysis(asset_key=asset_key)

        if len(evidence) < 2:
            return analysis  # Need at least 2 pieces to contradict

        # Group evidence by plane
        by_plane: Dict[FabricPlaneType, List[FabricRoutingEvidence]] = {}
        for e in evidence:
            if e.fabric_plane_type:
                if e.fabric_plane_type not in by_plane:
                    by_plane[e.fabric_plane_type] = []
                by_plane[e.fabric_plane_type].append(e)

        # Check for plane conflicts
        if len(by_plane) > 1:
            contradictions = self._check_plane_conflicts(asset_key, by_plane)
            analysis.contradictions.extend(contradictions)

        # Check for phase mismatch
        if phase_2_planes:
            contradictions = self._check_phase_mismatch(
                asset_key, by_plane, phase_2_planes
            )
            analysis.contradictions.extend(contradictions)

        # Check for stale evidence conflicts
        contradictions = self._check_stale_conflicts(asset_key, evidence)
        analysis.contradictions.extend(contradictions)

        # Summarize
        analysis.total_contradictions = len(analysis.contradictions)
        analysis.has_critical = any(
            c.severity == ContradictionSeverity.CRITICAL
            for c in analysis.contradictions
        )
        analysis.has_high = any(
            c.severity == ContradictionSeverity.HIGH
            for c in analysis.contradictions
        )

        # Calculate penalty
        analysis.confidence_penalty = sum(
            self.severity_penalties.get(c.severity, 0.0)
            for c in analysis.contradictions
        )
        # Cap penalty at 0.40
        analysis.confidence_penalty = min(0.40, analysis.confidence_penalty)

        # Recommend action
        analysis.recommended_action = self._recommend_action(analysis)

        return analysis

    def _check_plane_conflicts(
        self,
        asset_key: str,
        by_plane: Dict[FabricPlaneType, List[FabricRoutingEvidence]]
    ) -> List[Contradiction]:
        """Check for conflicts between different plane claims."""
        contradictions = []
        planes = list(by_plane.keys())

        for i, plane_a in enumerate(planes):
            for plane_b in planes[i + 1:]:
                evidence_a = by_plane[plane_a]
                evidence_b = by_plane[plane_b]

                # Determine severity
                severity = self._assess_plane_conflict_severity(
                    plane_a, plane_b, evidence_a, evidence_b
                )

                # Build claims
                source_a = evidence_a[0].source_plane.value if evidence_a else "unknown"
                source_b = evidence_b[0].source_plane.value if evidence_b else "unknown"

                claim_a = f"{source_a} claims {plane_a.value}"
                claim_b = f"{source_b} claims {plane_b.value}"

                contradiction = Contradiction(
                    contradiction_id=f"pc_{asset_key}_{plane_a.value}_{plane_b.value}",
                    asset_key=asset_key,
                    contradiction_type=ContradictionType.PLANE_CONFLICT,
                    severity=severity,
                    claim_a=claim_a,
                    claim_b=claim_b,
                    evidence_a=evidence_a,
                    evidence_b=evidence_b,
                    resolution_recommendation=self._plane_conflict_recommendation(
                        plane_a, plane_b, evidence_a, evidence_b
                    )
                )
                contradictions.append(contradiction)

        return contradictions

    def _check_phase_mismatch(
        self,
        asset_key: str,
        by_plane: Dict[FabricPlaneType, List[FabricRoutingEvidence]],
        phase_2_planes: Set[FabricPlaneType]
    ) -> List[Contradiction]:
        """Check for mismatches between Phase 1 predictions and Phase 2 confirmations."""
        contradictions = []

        # Phase 1 predicted planes (from observation evidence)
        phase_1_planes = set()
        for plane, evidence in by_plane.items():
            # Only count Phase 1 (non-direct-crawl) evidence
            phase_1_evidence = [
                e for e in evidence
                if e.source_plane != EvidenceSourcePlane.DIRECT_CRAWL
            ]
            if phase_1_evidence:
                phase_1_planes.add(plane)

        # Planes predicted by Phase 1 but NOT confirmed by Phase 2
        unconfirmed = phase_1_planes - phase_2_planes

        for plane in unconfirmed:
            evidence_for_plane = by_plane.get(plane, [])

            # High severity if high-confidence Phase 1 evidence wasn't confirmed
            max_confidence = max((e.confidence for e in evidence_for_plane), default=0)
            severity = (
                ContradictionSeverity.HIGH if max_confidence >= 0.80
                else ContradictionSeverity.MEDIUM
            )

            contradiction = Contradiction(
                contradiction_id=f"pm_{asset_key}_{plane.value}",
                asset_key=asset_key,
                contradiction_type=ContradictionType.PHASE_MISMATCH,
                severity=severity,
                claim_a=f"Phase 1 predicted {plane.value} (confidence {max_confidence:.2f})",
                claim_b=f"Phase 2 direct crawl did not confirm {plane.value}",
                evidence_a=evidence_for_plane,
                evidence_b=[],
                resolution_recommendation=(
                    f"Phase 1 evidence suggested {plane.value} but direct crawl didn't confirm. "
                    f"Possible causes: (1) Stale observation data, (2) Intermittent connection, "
                    f"(3) Configuration change, (4) False positive in Phase 1 signal."
                )
            )
            contradictions.append(contradiction)

        return contradictions

    def _check_stale_conflicts(
        self,
        asset_key: str,
        evidence: List[FabricRoutingEvidence]
    ) -> List[Contradiction]:
        """Check for conflicts between old and new evidence."""
        contradictions = []
        now = datetime.utcnow()
        stale_threshold = now - timedelta(days=self.stale_threshold_days)

        # Split by recency
        recent = [e for e in evidence if e.timestamp and e.timestamp > stale_threshold]
        stale = [e for e in evidence if e.timestamp and e.timestamp <= stale_threshold]

        if not recent or not stale:
            return contradictions

        # Check if stale evidence claims different plane than recent
        recent_planes = set(e.fabric_plane_type for e in recent if e.fabric_plane_type)
        stale_planes = set(e.fabric_plane_type for e in stale if e.fabric_plane_type)

        # Planes in stale but not in recent
        outdated_claims = stale_planes - recent_planes

        for plane in outdated_claims:
            stale_evidence = [e for e in stale if e.fabric_plane_type == plane]

            contradiction = Contradiction(
                contradiction_id=f"sc_{asset_key}_{plane.value}",
                asset_key=asset_key,
                contradiction_type=ContradictionType.STALE_EVIDENCE,
                severity=ContradictionSeverity.LOW,
                claim_a=f"Stale evidence (>{self.stale_threshold_days} days) claims {plane.value}",
                claim_b=f"Recent evidence does not show {plane.value} connection",
                evidence_a=stale_evidence,
                evidence_b=recent,
                resolution_recommendation=(
                    f"Old evidence claimed {plane.value} but recent data doesn't confirm. "
                    f"Likely a configuration change or decommissioned integration. "
                    f"Recommend verifying current state and updating records."
                )
            )
            contradictions.append(contradiction)

        return contradictions

    def _assess_plane_conflict_severity(
        self,
        plane_a: FabricPlaneType,
        plane_b: FabricPlaneType,
        evidence_a: List[FabricRoutingEvidence],
        evidence_b: List[FabricRoutingEvidence]
    ) -> ContradictionSeverity:
        """Assess severity of a plane conflict."""
        # Both have high-confidence Tier 1 evidence = CRITICAL
        tier_1_a = any(
            e.source_plane == EvidenceSourcePlane.DIRECT_CRAWL
            for e in evidence_a
        )
        tier_1_b = any(
            e.source_plane == EvidenceSourcePlane.DIRECT_CRAWL
            for e in evidence_b
        )

        if tier_1_a and tier_1_b:
            return ContradictionSeverity.CRITICAL

        # One has Tier 1 = HIGH
        if tier_1_a or tier_1_b:
            return ContradictionSeverity.HIGH

        # Both have high confidence Tier 2 = MEDIUM
        max_conf_a = max((e.confidence for e in evidence_a), default=0)
        max_conf_b = max((e.confidence for e in evidence_b), default=0)

        if max_conf_a >= 0.80 and max_conf_b >= 0.80:
            return ContradictionSeverity.MEDIUM

        # Otherwise LOW
        return ContradictionSeverity.LOW

    def _plane_conflict_recommendation(
        self,
        plane_a: FabricPlaneType,
        plane_b: FabricPlaneType,
        evidence_a: List[FabricRoutingEvidence],
        evidence_b: List[FabricRoutingEvidence]
    ) -> str:
        """Generate recommendation for resolving plane conflict."""
        # Check if this could be legitimate multi-plane
        if self._could_be_multi_plane(plane_a, plane_b):
            return (
                f"Asset may legitimately connect through both {plane_a.value} AND "
                f"{plane_b.value}. This is valid for multi-plane routing. "
                f"Verify both connections are intentional and create separate pipe records."
            )

        # Otherwise, need to investigate
        stronger = "A" if len(evidence_a) > len(evidence_b) else "B"
        return (
            f"Conflicting claims: {plane_a.value} vs {plane_b.value}. "
            f"Evidence set {stronger} has more supporting data. "
            f"Investigate which is current/accurate and update sources."
        )

    def _could_be_multi_plane(
        self,
        plane_a: FabricPlaneType,
        plane_b: FabricPlaneType
    ) -> bool:
        """Check if two planes could legitimately coexist for one asset."""
        # Common legitimate combinations
        valid_combos = [
            {FabricPlaneType.IPAAS, FabricPlaneType.DATA_WAREHOUSE},  # ETL pattern
            {FabricPlaneType.API_GATEWAY, FabricPlaneType.EVENT_BUS},  # API + events
            {FabricPlaneType.IPAAS, FabricPlaneType.API_GATEWAY},  # iPaaS calls API
        ]

        return {plane_a, plane_b} in valid_combos

    def _recommend_action(self, analysis: ContradictionAnalysis) -> str:
        """Recommend action based on contradiction analysis."""
        if analysis.has_critical:
            return (
                "BLOCK: Critical contradictions detected. Classification cannot proceed "
                "until conflicts are resolved. Requires human review."
            )

        if analysis.has_high:
            return (
                "REVIEW: High-severity contradictions detected. Classification will proceed "
                "with reduced confidence. Flag for operator review within 24 hours."
            )

        if analysis.total_contradictions > 0:
            return (
                "PROCEED: Minor contradictions detected. Classification will proceed "
                "with slight confidence penalty. Log for periodic review."
            )

        return "PROCEED: No contradictions detected."


def detect_contradictions(
    asset_key: str,
    evidence: List[FabricRoutingEvidence],
    phase_2_planes: Optional[Set[FabricPlaneType]] = None
) -> Tuple[List[Contradiction], float]:
    """
    Convenience function for contradiction detection.

    Args:
        asset_key: Asset to analyze
        evidence: Evidence list
        phase_2_planes: Confirmed planes from direct crawl

    Returns:
        Tuple of (contradictions list, confidence penalty)
    """
    detector = ContradictionDetector()
    analysis = detector.analyze(asset_key, evidence, phase_2_planes)
    return analysis.contradictions, analysis.confidence_penalty
