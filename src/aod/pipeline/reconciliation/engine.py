"""
Reconciliation Engine

Main Phase 3 orchestrator that reconciles evidence from all sources:
- Phase 1: Observation plane signals (Cloud, Network, Finance, CMDB, IdP)
- Phase 2: Direct fabric plane crawls (Kong, Workato, Snowflake)

The engine:
1. Cross-references Phase 1 vs Phase 2 results
2. Computes composite confidence scores
3. Deduplicates SORs appearing on multiple planes
4. Detects and handles contradictions
5. Produces final Pipe classifications with evidence chains
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from uuid import uuid4

from ...models.output_contracts import (
    FabricRoutingEvidence,
    FabricPlaneType,
    EvidenceSourcePlane,
    EvidenceTier,
    Pipe,
    PipeGovernanceStatus,
    ConnectivityModality,
    ClassificationMethod,
    FabricPlane,
    now_pst,
)
from ..evidence_collectors.base import EvidenceCollectionResult
from ..fabric_connectors.base import DirectCrawlResult
from .confidence import (
    CompositeConfidenceCalculator,
    ConfidenceFactors,
)
from .deduplication import (
    SORDeduplicator,
    DeduplicationResult,
)
from .contradictions import (
    ContradictionDetector,
    ContradictionAnalysis,
    ContradictionSeverity,
)

logger = logging.getLogger(__name__)


# Minimum confidence thresholds for classification
MIN_CONFIDENCE_GOVERNED = 0.70  # Minimum to mark as "governed"
MIN_CONFIDENCE_KNOWN = 0.50     # Minimum to mark as "known"
MIN_CONFIDENCE_CLASSIFY = 0.30  # Below this, mark as "investigation_needed"


@dataclass
class ReconciliationConfig:
    """Configuration for the reconciliation engine."""

    # Confidence thresholds
    min_confidence_governed: float = MIN_CONFIDENCE_GOVERNED
    min_confidence_known: float = MIN_CONFIDENCE_KNOWN
    min_confidence_classify: float = MIN_CONFIDENCE_CLASSIFY

    # Contradiction handling
    block_on_critical_contradiction: bool = True
    contradiction_penalty: float = 0.15

    # Deduplication
    enable_deduplication: bool = True
    merge_true_duplicates: bool = True

    # Output options
    include_evidence_chain: bool = True
    max_evidence_per_pipe: int = 10  # Limit evidence in output


@dataclass
class ReconciliationResult:
    """
    Result of the reconciliation process.
    """
    # Final pipes (classified assets)
    pipes: List[Pipe] = field(default_factory=list)

    # Fabric plane registry
    fabric_planes: List[FabricPlane] = field(default_factory=list)

    # Assets that couldn't be classified
    unresolved_assets: List[str] = field(default_factory=list)

    # Assets blocked by contradictions
    blocked_assets: List[str] = field(default_factory=list)

    # Shadow plane detections
    shadow_planes: List[FabricPlane] = field(default_factory=list)

    # Deduplication results
    deduplication_result: Optional[DeduplicationResult] = None

    # Contradictions found
    contradictions_by_asset: Dict[str, ContradictionAnalysis] = field(default_factory=dict)

    # Statistics
    stats: Dict[str, int] = field(default_factory=dict)

    # Timing
    started_at: datetime = field(default_factory=now_pst)
    completed_at: Optional[datetime] = None


class ReconciliationEngine:
    """
    Main reconciliation engine for fabric plane classification.

    Orchestrates the Phase 3 reconciliation process:
    1. Merge evidence from all sources
    2. Detect and handle contradictions
    3. Calculate composite confidence
    4. Deduplicate SORs
    5. Produce final Pipe classifications
    """

    def __init__(self, config: Optional[ReconciliationConfig] = None):
        self.config = config or ReconciliationConfig()
        self.confidence_calculator = CompositeConfidenceCalculator(
            contradiction_penalty=self.config.contradiction_penalty
        )
        self.deduplicator = SORDeduplicator()
        self.contradiction_detector = ContradictionDetector()

    def reconcile(
        self,
        phase_1_result: EvidenceCollectionResult,
        phase_2_results: Dict[str, DirectCrawlResult]
    ) -> ReconciliationResult:
        """
        Execute the reconciliation process.

        Args:
            phase_1_result: Evidence from observation planes
            phase_2_results: Results from direct fabric plane crawls

        Returns:
            ReconciliationResult with classified pipes
        """
        result = ReconciliationResult()

        logger.info("reconciliation.start", extra={
            "phase_1_assets": len(phase_1_result.routing_evidence),
            "phase_2_crawls": len(phase_2_results)
        })

        # Step 1: Merge Phase 2 evidence into consolidated view
        merged_evidence = self._merge_evidence(phase_1_result, phase_2_results)

        # Step 2: Get Phase 2 confirmed planes per asset
        phase_2_confirmed = self._get_phase_2_confirmations(phase_2_results)

        # Step 3: Analyze contradictions for each asset
        for asset_key, evidence_list in merged_evidence.items():
            confirmed_planes = phase_2_confirmed.get(asset_key, set())
            analysis = self.contradiction_detector.analyze(
                asset_key, evidence_list, confirmed_planes
            )
            if analysis.contradictions:
                result.contradictions_by_asset[asset_key] = analysis

        # Step 4: Build pipes (skipping blocked assets)
        pipes = self._build_pipes(merged_evidence, phase_2_confirmed, result)

        # Step 5: Deduplicate if enabled
        if self.config.enable_deduplication and pipes:
            pipes, result.deduplication_result = self._deduplicate(
                pipes, merged_evidence
            )

        result.pipes = pipes

        # Step 6: Collect fabric planes
        result.fabric_planes = list(phase_1_result.fabric_plane_registry.planes)
        result.shadow_planes = list(phase_1_result.shadow_plane_candidates)

        # Add planes from Phase 2
        for crawl_result in phase_2_results.values():
            plane = FabricPlane(
                plane_id=f"{crawl_result.plane_type.value}:{crawl_result.vendor}",
                plane_type=crawl_result.plane_type,
                vendor=crawl_result.vendor,
                display_name=crawl_result.instance_name,
                domain=None,
                managed_asset_count=len(crawl_result.assets),
                evidence_refs=[],
                confidence=0.95  # Tier 1
            )
            if plane not in result.fabric_planes:
                result.fabric_planes.append(plane)

        # Statistics
        result.stats = {
            "total_assets": len(merged_evidence),
            "pipes_created": len(result.pipes),
            "unresolved": len(result.unresolved_assets),
            "blocked": len(result.blocked_assets),
            "contradictions": len(result.contradictions_by_asset),
            "shadow_planes": len(result.shadow_planes),
            "fabric_planes": len(result.fabric_planes),
        }

        result.completed_at = now_pst()

        logger.info("reconciliation.complete", extra=result.stats)

        return result

    def _merge_evidence(
        self,
        phase_1: EvidenceCollectionResult,
        phase_2: Dict[str, DirectCrawlResult]
    ) -> Dict[str, List[FabricRoutingEvidence]]:
        """Merge evidence from Phase 1 and Phase 2."""
        merged: Dict[str, List[FabricRoutingEvidence]] = {}

        # Add Phase 1 evidence
        for asset_key, evidence_table in phase_1.routing_evidence.items():
            merged[asset_key] = list(evidence_table.evidence)

        # Add Phase 2 evidence
        for crawl_result in phase_2.values():
            for evidence in crawl_result.evidence:
                # Extract asset key from evidence raw_data
                asset_key = evidence.raw_data.get(
                    "asset_key",
                    evidence.raw_data.get("service_name", str(uuid4())[:8])
                )

                if asset_key not in merged:
                    merged[asset_key] = []
                merged[asset_key].append(evidence)

            # Also add pipe-derived evidence
            for pipe in crawl_result.pipes:
                source_key = pipe.source_identifier
                if source_key not in merged:
                    merged[source_key] = []

                # Create evidence from pipe
                pipe_evidence = FabricRoutingEvidence(
                    evidence_id=f"pipe_{pipe.pipe_id}",
                    source_plane=EvidenceSourcePlane.DIRECT_CRAWL,
                    signal_type=f"direct_crawl_{crawl_result.vendor}_pipe",
                    signal_detail=f"Direct crawl pipe: {pipe.pipe_name}",
                    confidence=0.95,
                    timestamp=crawl_result.crawl_started_at,
                    fabric_plane_type=crawl_result.plane_type,
                    fabric_plane_vendor=crawl_result.vendor,
                    raw_data={
                        "pipe_id": pipe.pipe_id,
                        "pipe_name": pipe.pipe_name,
                        "target": pipe.target_identifier,
                        "is_active": pipe.is_active
                    }
                )
                merged[source_key].append(pipe_evidence)

        return merged

    def _get_phase_2_confirmations(
        self,
        phase_2: Dict[str, DirectCrawlResult]
    ) -> Dict[str, Set[FabricPlaneType]]:
        """Get confirmed planes per asset from Phase 2."""
        confirmed: Dict[str, Set[FabricPlaneType]] = {}

        for crawl_result in phase_2.values():
            for pipe in crawl_result.pipes:
                source_key = pipe.source_identifier
                if source_key not in confirmed:
                    confirmed[source_key] = set()
                confirmed[source_key].add(crawl_result.plane_type)

            for asset in crawl_result.assets:
                asset_key = asset.domain or asset.asset_name
                if asset_key not in confirmed:
                    confirmed[asset_key] = set()
                confirmed[asset_key].add(crawl_result.plane_type)

        return confirmed

    def _build_pipes(
        self,
        merged_evidence: Dict[str, List[FabricRoutingEvidence]],
        phase_2_confirmed: Dict[str, Set[FabricPlaneType]],
        result: ReconciliationResult
    ) -> List[Pipe]:
        """Build Pipe records from merged evidence."""
        pipes: List[Pipe] = []

        for asset_key, evidence_list in merged_evidence.items():
            # Check for blocking contradictions
            contradiction_analysis = result.contradictions_by_asset.get(asset_key)
            if (
                contradiction_analysis
                and contradiction_analysis.has_critical
                and self.config.block_on_critical_contradiction
            ):
                result.blocked_assets.append(asset_key)
                continue

            # Group evidence by plane
            by_plane: Dict[FabricPlaneType, List[FabricRoutingEvidence]] = {}
            for evidence in evidence_list:
                if evidence.fabric_plane_type:
                    if evidence.fabric_plane_type not in by_plane:
                        by_plane[evidence.fabric_plane_type] = []
                    by_plane[evidence.fabric_plane_type].append(evidence)

            if not by_plane:
                result.unresolved_assets.append(asset_key)
                continue

            # Create a pipe for each plane (multi-plane support)
            for plane_type, plane_evidence in by_plane.items():
                # Calculate confidence
                has_contradiction = contradiction_analysis is not None
                confidence_factors = self.confidence_calculator.calculate(
                    plane_evidence,
                    has_contradiction=has_contradiction,
                    target_plane=plane_type
                )

                # Skip if below minimum threshold
                if confidence_factors.composite_score < self.config.min_confidence_classify:
                    continue

                # Determine governance status
                governance_status = self._determine_governance_status(
                    confidence_factors.composite_score,
                    plane_type in phase_2_confirmed.get(asset_key, set()),
                    contradiction_analysis
                )

                # Determine evidence tier
                evidence_tier = self._determine_tier(plane_evidence)

                # Determine classification method
                classification_method = self._determine_method(plane_evidence)

                # Determine modality (from highest-confidence evidence)
                modality = self._determine_modality(plane_evidence)

                # Get vendor
                vendors = [e.fabric_plane_vendor for e in plane_evidence if e.fabric_plane_vendor]
                vendor = vendors[0] if vendors else None

                # Limit evidence in output
                output_evidence = plane_evidence[:self.config.max_evidence_per_pipe] \
                    if self.config.include_evidence_chain else []

                pipe = Pipe(
                    pipe_id=f"pipe_{asset_key}_{plane_type.value}_{uuid4().hex[:8]}",
                    name=f"{asset_key} → {plane_type.value}",
                    source_system=asset_key,
                    target_system=vendor,
                    fabric_plane=plane_type,
                    fabric_plane_instance=vendor,
                    modality=modality,
                    classification_method=classification_method,
                    classification_evidence=output_evidence,
                    classification_confidence=confidence_factors.composite_score,
                    evidence_tier=evidence_tier,
                    governance_status=governance_status,
                    has_contradictions=has_contradiction,
                    contradiction_detail=(
                        contradiction_analysis.recommended_action
                        if contradiction_analysis else None
                    )
                )
                pipes.append(pipe)

        return pipes

    def _determine_governance_status(
        self,
        confidence: float,
        phase_2_confirmed: bool,
        contradiction_analysis: Optional[ContradictionAnalysis]
    ) -> PipeGovernanceStatus:
        """Determine governance status from confidence and evidence."""
        # Blocked by contradictions
        if contradiction_analysis and contradiction_analysis.has_critical:
            return PipeGovernanceStatus.INVESTIGATION_NEEDED

        # Phase 2 confirmed = governed
        if phase_2_confirmed and confidence >= self.config.min_confidence_governed:
            return PipeGovernanceStatus.GOVERNED

        # High confidence = known
        if confidence >= self.config.min_confidence_known:
            return PipeGovernanceStatus.KNOWN

        # Medium confidence = investigation needed
        if confidence >= self.config.min_confidence_classify:
            return PipeGovernanceStatus.INVESTIGATION_NEEDED

        return PipeGovernanceStatus.SHADOW

    def _determine_tier(
        self,
        evidence: List[FabricRoutingEvidence]
    ) -> EvidenceTier:
        """Determine evidence tier from evidence list."""
        has_tier_1 = any(
            e.source_plane == EvidenceSourcePlane.DIRECT_CRAWL
            for e in evidence
        )
        if has_tier_1:
            return EvidenceTier.TIER_1_DIRECT

        has_tier_2 = any(
            e.confidence >= 0.60 for e in evidence
        )
        if has_tier_2:
            return EvidenceTier.TIER_2_OBSERVED

        return EvidenceTier.TIER_3_INFERRED

    def _determine_method(
        self,
        evidence: List[FabricRoutingEvidence]
    ) -> ClassificationMethod:
        """Determine classification method from evidence sources."""
        sources = set(e.source_plane for e in evidence)

        if EvidenceSourcePlane.DIRECT_CRAWL in sources:
            return ClassificationMethod.DIRECT_CRAWL

        if sources & {
            EvidenceSourcePlane.NETWORK,
            EvidenceSourcePlane.CLOUD,
            EvidenceSourcePlane.FINANCE
        }:
            return ClassificationMethod.EVIDENCE_BASED

        return ClassificationMethod.INFERRED

    def _determine_modality(
        self,
        evidence: List[FabricRoutingEvidence]
    ) -> ConnectivityModality:
        """Determine modality from evidence."""
        # Check raw_data for modality hints
        for e in sorted(evidence, key=lambda x: x.confidence, reverse=True):
            if e.raw_data:
                modality_str = e.raw_data.get("modality")
                if modality_str:
                    try:
                        return ConnectivityModality(modality_str)
                    except ValueError:
                        pass

        # Default based on plane type
        # (This is a simplification - real implementation would be smarter)
        return ConnectivityModality.API

    def _deduplicate(
        self,
        pipes: List[Pipe],
        evidence_by_asset: Dict[str, List[FabricRoutingEvidence]]
    ) -> Tuple[List[Pipe], DeduplicationResult]:
        """Deduplicate pipes."""
        dedup_result = self.deduplicator.deduplicate(pipes, evidence_by_asset)

        if self.config.merge_true_duplicates:
            pipes = self.deduplicator.merge_duplicates(pipes, dedup_result)

        return pipes, dedup_result


def reconcile_all_evidence(
    phase_1_result: EvidenceCollectionResult,
    phase_2_results: Dict[str, DirectCrawlResult],
    config: Optional[ReconciliationConfig] = None
) -> ReconciliationResult:
    """
    Convenience function to run reconciliation.

    Args:
        phase_1_result: Evidence from observation planes
        phase_2_results: Results from direct fabric plane crawls
        config: Optional configuration

    Returns:
        ReconciliationResult with classified pipes
    """
    engine = ReconciliationEngine(config)
    return engine.reconcile(phase_1_result, phase_2_results)
