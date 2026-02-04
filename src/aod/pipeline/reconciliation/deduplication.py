"""
SOR Deduplication

Handles assets that appear on multiple fabric planes simultaneously.
This is valid - one SOR CAN have multiple pipes:
- Salesforce → Workato (sync to NetSuite)
- Salesforce → Snowflake (analytics)
- Salesforce → Kong (API access)

Deduplication goals:
1. Identify when the SAME asset appears multiple times (true duplicates)
2. Merge evidence for duplicates
3. Preserve legitimate multi-plane relationships
4. Flag suspicious patterns (e.g., shadow plane alongside official)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from ...models.output_contracts import (
    FabricRoutingEvidence,
    FabricPlaneType,
    Pipe,
    EvidenceTier,
)

logger = logging.getLogger(__name__)


@dataclass
class DuplicateCandidate:
    """
    A candidate duplicate - same asset appearing multiple times.
    """
    canonical_key: str  # Normalized key for the asset
    variant_keys: List[str]  # All keys that resolved to this canonical
    pipes: List[Pipe]  # All pipes for this asset
    evidence: List[FabricRoutingEvidence]  # All evidence
    planes: Set[FabricPlaneType]  # Which planes this asset connects to

    is_true_duplicate: bool = False  # Same pipe through different evidence
    is_multi_plane: bool = False  # Legitimate multi-plane (different pipes)
    is_shadow_conflict: bool = False  # Shadow plane alongside official

    merge_recommendation: str = ""  # What to do


@dataclass
class DeduplicationResult:
    """
    Result of SOR deduplication analysis.
    """
    # True duplicates that were merged
    merged_assets: Dict[str, DuplicateCandidate] = field(default_factory=dict)

    # Multi-plane assets (legitimate, kept separate)
    multi_plane_assets: Dict[str, DuplicateCandidate] = field(default_factory=dict)

    # Shadow conflicts (needs investigation)
    shadow_conflicts: Dict[str, DuplicateCandidate] = field(default_factory=dict)

    # Statistics
    total_input_assets: int = 0
    unique_assets_after_merge: int = 0
    duplicates_merged: int = 0
    multi_plane_count: int = 0
    shadow_conflict_count: int = 0


class SORDeduplicator:
    """
    Deduplicates assets appearing multiple times across fabric planes.

    Algorithm:
    1. Normalize asset keys to canonical form
    2. Group assets by canonical key
    3. Analyze each group:
       - Same plane + same evidence = true duplicate → merge
       - Different planes + legitimate evidence = multi-plane → keep separate
       - Shadow plane + official plane = conflict → flag
    """

    def __init__(self):
        # Key normalization rules
        self.normalization_rules = [
            # Remove common prefixes/suffixes
            (r"^https?://", ""),
            (r"^www\.", ""),
            (r"/$", ""),
            # Normalize case
            (r"(.+)", lambda m: m.group(1).lower()),
        ]

    def deduplicate(
        self,
        pipes: List[Pipe],
        evidence_by_asset: Dict[str, List[FabricRoutingEvidence]]
    ) -> DeduplicationResult:
        """
        Analyze and deduplicate assets.

        Args:
            pipes: All pipes from reconciliation
            evidence_by_asset: Evidence grouped by asset key

        Returns:
            DeduplicationResult with analysis
        """
        result = DeduplicationResult(total_input_assets=len(evidence_by_asset))

        # Group pipes by normalized source key
        pipes_by_source: Dict[str, List[Pipe]] = {}
        canonical_map: Dict[str, str] = {}  # original → canonical

        for pipe in pipes:
            canonical = self._normalize_key(pipe.source_system)
            canonical_map[pipe.source_system] = canonical

            if canonical not in pipes_by_source:
                pipes_by_source[canonical] = []
            pipes_by_source[canonical].append(pipe)

        # Analyze each canonical group
        for canonical_key, group_pipes in pipes_by_source.items():
            if len(group_pipes) <= 1:
                # No duplicates
                continue

            # Find all variant keys and evidence
            variant_keys = [p.source_system for p in group_pipes]
            variant_evidence: List[FabricRoutingEvidence] = []
            for vk in variant_keys:
                variant_evidence.extend(evidence_by_asset.get(vk, []))

            # Get planes involved
            planes = set(p.fabric_plane for p in group_pipes)

            candidate = DuplicateCandidate(
                canonical_key=canonical_key,
                variant_keys=list(set(variant_keys)),
                pipes=group_pipes,
                evidence=variant_evidence,
                planes=planes
            )

            # Classify the duplicate
            self._classify_candidate(candidate)

            # Route to appropriate bucket
            if candidate.is_true_duplicate:
                result.merged_assets[canonical_key] = candidate
                result.duplicates_merged += len(variant_keys) - 1
            elif candidate.is_shadow_conflict:
                result.shadow_conflicts[canonical_key] = candidate
                result.shadow_conflict_count += 1
            elif candidate.is_multi_plane:
                result.multi_plane_assets[canonical_key] = candidate
                result.multi_plane_count += 1

        result.unique_assets_after_merge = (
            result.total_input_assets - result.duplicates_merged
        )

        logger.info("sor_deduplication.complete", extra={
            "total_input": result.total_input_assets,
            "unique_after_merge": result.unique_assets_after_merge,
            "duplicates_merged": result.duplicates_merged,
            "multi_plane": result.multi_plane_count,
            "shadow_conflicts": result.shadow_conflict_count
        })

        return result

    def _normalize_key(self, key: str) -> str:
        """Normalize an asset key to canonical form."""
        import re

        result = key

        for pattern, replacement in self.normalization_rules:
            if callable(replacement):
                result = re.sub(pattern, replacement, result)
            else:
                result = re.sub(pattern, replacement, result)

        return result.strip()

    def _classify_candidate(self, candidate: DuplicateCandidate) -> None:
        """Classify a duplicate candidate."""
        # Check for shadow conflict
        has_shadow = any(
            p.governance_status.value == "shadow"
            for p in candidate.pipes
        )
        has_official = any(
            p.governance_status.value in ("governed", "known")
            for p in candidate.pipes
        )

        if has_shadow and has_official:
            candidate.is_shadow_conflict = True
            candidate.merge_recommendation = (
                "INVESTIGATE: Asset has both official and shadow fabric plane connections. "
                "Verify if shadow plane is authorized or should be consolidated."
            )
            return

        # Check if truly same pipe (same plane, merge evidence)
        if len(candidate.planes) == 1:
            candidate.is_true_duplicate = True
            candidate.merge_recommendation = (
                f"MERGE: Multiple references to same {list(candidate.planes)[0].value} pipe. "
                "Consolidate evidence and use canonical key."
            )
            return

        # Multiple planes = legitimate multi-plane
        candidate.is_multi_plane = True
        plane_list = ", ".join(p.value for p in candidate.planes)
        candidate.merge_recommendation = (
            f"KEEP SEPARATE: Asset connects through multiple planes ({plane_list}). "
            "This is valid - maintain separate pipe records per plane."
        )

    def merge_duplicates(
        self,
        pipes: List[Pipe],
        result: DeduplicationResult
    ) -> List[Pipe]:
        """
        Merge true duplicate pipes.

        Args:
            pipes: Original pipe list
            result: Deduplication analysis result

        Returns:
            Deduplicated pipe list
        """
        # Build set of pipes to remove (duplicates)
        pipes_to_remove: Set[str] = set()

        for canonical_key, candidate in result.merged_assets.items():
            if not candidate.is_true_duplicate:
                continue

            # Keep the pipe with highest confidence, remove others
            sorted_pipes = sorted(
                candidate.pipes,
                key=lambda p: p.classification_confidence,
                reverse=True
            )

            # First one stays, rest get marked for removal
            for pipe in sorted_pipes[1:]:
                pipes_to_remove.add(pipe.pipe_id)

            # Merge evidence into the keeper
            keeper = sorted_pipes[0]
            for pipe in sorted_pipes[1:]:
                keeper.classification_evidence.extend(pipe.classification_evidence)

            # Recalculate confidence after merge
            # (This would use CompositeConfidenceCalculator in practice)

        # Filter out removed pipes
        return [p for p in pipes if p.pipe_id not in pipes_to_remove]


def deduplicate_sors(
    pipes: List[Pipe],
    evidence_by_asset: Dict[str, List[FabricRoutingEvidence]]
) -> Tuple[List[Pipe], DeduplicationResult]:
    """
    Convenience function for SOR deduplication.

    Args:
        pipes: All pipes
        evidence_by_asset: Evidence grouped by asset

    Returns:
        Tuple of (deduplicated pipes, analysis result)
    """
    deduplicator = SORDeduplicator()
    result = deduplicator.deduplicate(pipes, evidence_by_asset)
    merged_pipes = deduplicator.merge_duplicates(pipes, result)
    return merged_pipes, result
