"""
Base Evidence Collector Interface

Defines the contract for all observation plane evidence collectors.
Each collector extracts fabric plane signals from one observation plane type.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from ...models.input_contracts import Snapshot, Planes
from ...models.output_contracts import (
    FabricRoutingEvidence,
    FabricPlaneType,
    EvidenceSourcePlane,
    FabricPlane,
    RoutingEvidenceTable,
    FabricPlaneRegistry,
    EvidenceLead,
    EvidenceLeadType,
    now_pst,
)

logger = logging.getLogger(__name__)


# Confidence scores by evidence tier and signal strength
CONFIDENCE_SCORES = {
    # Tier 1: Direct crawl (handled by plane connectors, not collectors)
    "tier_1_direct": 0.95,

    # Tier 2: Observation plane signals
    "tier_2_very_high": 0.90,   # The plane itself found in cloud inventory
    "tier_2_high": 0.85,        # Clear traffic pattern or explicit dependency
    "tier_2_medium": 0.80,      # OAuth grant or service account
    "tier_2_low": 0.70,         # Indirect signal, corroborating evidence

    # Tier 3: Category inference (demoted)
    "tier_3_high": 0.50,        # Strong category match
    "tier_3_medium": 0.40,      # Moderate category match
    "tier_3_low": 0.30,         # Weak inference, no evidence
}


@dataclass
class EvidenceCollectionResult:
    """
    Result of evidence collection from all observation planes.

    This is the Phase 1 output - used to feed Phase 2 (direct crawl)
    and Phase 3 (reconciliation).

    RACI Compliance: AOD generates evidence and evidence_leads.
    AAM validates evidence_leads via direct plane crawl.
    """
    # Per-asset evidence tables
    routing_evidence: Dict[str, RoutingEvidenceTable] = field(default_factory=dict)

    # Evidence Leads for AAM (RACI Sprint) - connection hints for AAM to validate
    evidence_leads: List[EvidenceLead] = field(default_factory=list)

    # Confirmed fabric planes (from all sources)
    fabric_plane_registry: FabricPlaneRegistry = field(
        default_factory=lambda: FabricPlaneRegistry(planes=[], shadow_plane_candidates=[])
    )

    # Shadow plane candidates (detected but not in Finance/official inventory)
    shadow_plane_candidates: List[FabricPlane] = field(default_factory=list)

    # Unattached assets (no fabric routing evidence from any plane)
    unattached_assets: List[str] = field(default_factory=list)

    # Statistics
    total_evidence_count: int = 0
    evidence_by_source: Dict[str, int] = field(default_factory=dict)
    evidence_by_plane_type: Dict[str, int] = field(default_factory=dict)
    evidence_lead_count: int = 0

    def add_evidence(
        self,
        asset_key: str,
        evidence: FabricRoutingEvidence
    ) -> None:
        """Add evidence for an asset."""
        if asset_key not in self.routing_evidence:
            self.routing_evidence[asset_key] = RoutingEvidenceTable(
                asset_key=asset_key,
                evidence=[],
                inferred_planes=[],
                highest_confidence=0.0,
                evidence_count_by_plane={}
            )

        table = self.routing_evidence[asset_key]
        table.evidence.append(evidence)

        # Update highest confidence
        if evidence.confidence > table.highest_confidence:
            table.highest_confidence = evidence.confidence

        # Track inferred planes
        if evidence.fabric_plane_type and evidence.fabric_plane_type not in table.inferred_planes:
            table.inferred_planes.append(evidence.fabric_plane_type)

        # Update counts
        source = evidence.source_plane.value
        table.evidence_count_by_plane[source] = table.evidence_count_by_plane.get(source, 0) + 1

        self.total_evidence_count += 1
        self.evidence_by_source[source] = self.evidence_by_source.get(source, 0) + 1

        if evidence.fabric_plane_type:
            plane_type = evidence.fabric_plane_type.value
            self.evidence_by_plane_type[plane_type] = self.evidence_by_plane_type.get(plane_type, 0) + 1

    def add_detected_plane(self, plane: FabricPlane, is_shadow: bool = False) -> None:
        """Add a detected fabric plane to the registry."""
        if is_shadow:
            self.shadow_plane_candidates.append(plane)
            self.fabric_plane_registry.shadow_plane_candidates.append(plane)
        else:
            # Check if already exists
            existing = [p for p in self.fabric_plane_registry.planes if p.plane_id == plane.plane_id]
            if not existing:
                self.fabric_plane_registry.planes.append(plane)

    def add_evidence_lead(self, lead: EvidenceLead) -> None:
        """
        Add an evidence lead for AAM validation.

        Evidence leads are connection hints that AAM will validate
        against actual plane crawl results.
        """
        self.evidence_leads.append(lead)
        self.evidence_lead_count += 1


class EvidenceCollector(ABC):
    """
    Abstract base class for observation plane evidence collectors.

    Each collector extracts fabric plane signals from one observation plane
    and produces FabricRoutingEvidence records.
    """

    @property
    @abstractmethod
    def source_plane(self) -> EvidenceSourcePlane:
        """Which observation plane this collector processes."""
        pass

    @abstractmethod
    def collect(
        self,
        planes: Planes,
        snapshot_timestamp: datetime,
        result: EvidenceCollectionResult
    ) -> None:
        """
        Extract fabric plane evidence from the observation plane.

        Args:
            planes: All observation planes from the snapshot
            snapshot_timestamp: When the snapshot was generated
            result: Accumulator for evidence (mutated in place)
        """
        pass

    def _create_evidence(
        self,
        signal_type: str,
        signal_detail: str,
        confidence: float,
        timestamp: datetime,
        fabric_plane_type: Optional[FabricPlaneType] = None,
        fabric_plane_vendor: Optional[str] = None,
        raw_data: Optional[dict] = None
    ) -> FabricRoutingEvidence:
        """Helper to create evidence records with consistent structure."""
        return FabricRoutingEvidence(
            evidence_id=f"ev_{uuid4().hex[:12]}",
            source_plane=self.source_plane,
            signal_type=signal_type,
            signal_detail=signal_detail,
            confidence=confidence,
            timestamp=timestamp,
            fabric_plane_type=fabric_plane_type,
            fabric_plane_vendor=fabric_plane_vendor,
            raw_data=raw_data
        )

    def _create_fabric_plane(
        self,
        plane_type: FabricPlaneType,
        vendor: str,
        display_name: str,
        domain: Optional[str] = None,
        confidence: float = 0.85
    ) -> FabricPlane:
        """Helper to create fabric plane records."""
        return FabricPlane(
            plane_id=f"{plane_type.value}:{vendor}",
            plane_type=plane_type,
            vendor=vendor,
            display_name=display_name,
            domain=domain,
            managed_asset_count=0,
            evidence_refs=[],
            confidence=confidence
        )

    def _create_evidence_lead(
        self,
        asset_id: str,
        asset_name: str,
        suggested_plane_type: FabricPlaneType,
        evidence_type: EvidenceLeadType,
        evidence_detail: str,
        confidence: float,
        suggested_plane_product: Optional[str] = None,
        asset_domain: Optional[str] = None,
        raw_data: Optional[dict] = None
    ) -> EvidenceLead:
        """
        Helper to create evidence lead records for AAM validation.

        Evidence leads are connection hints that AOD generates from
        observation plane data. AAM validates them via direct plane crawl.
        """
        return EvidenceLead(
            lead_id=f"lead_{uuid4().hex[:12]}",
            asset_id=asset_id,
            asset_name=asset_name,
            asset_domain=asset_domain,
            suggested_plane_type=suggested_plane_type,
            suggested_plane_product=suggested_plane_product,
            evidence_source=self.source_plane,
            evidence_type=evidence_type,
            evidence_detail=evidence_detail,
            confidence=confidence,
            raw_data=raw_data
        )


def collect_all_evidence(
    snapshot: Snapshot
) -> EvidenceCollectionResult:
    """
    Run all evidence collectors against a snapshot.

    This is the Phase 1 entry point - harvest fabric plane signals from
    all observation planes before direct plane crawls.

    Returns:
        EvidenceCollectionResult with all discovered evidence
    """
    result = EvidenceCollectionResult()
    timestamp = snapshot.meta.generated_at

    # Import collectors here to avoid circular imports
    from .cloud_evidence import CloudEvidenceCollector
    from .network_evidence import NetworkEvidenceCollector
    from .finance_evidence import FinanceEvidenceCollector
    from .cmdb_evidence import CMDBEvidenceCollector
    from .idp_evidence import IdPEvidenceCollector

    collectors: List[EvidenceCollector] = [
        CloudEvidenceCollector(),
        NetworkEvidenceCollector(),
        FinanceEvidenceCollector(),
        CMDBEvidenceCollector(),
        IdPEvidenceCollector(),
    ]

    for collector in collectors:
        try:
            logger.info(f"evidence_collector.start", extra={
                "source_plane": collector.source_plane.value
            })
            collector.collect(snapshot.planes, timestamp, result)
            logger.info(f"evidence_collector.complete", extra={
                "source_plane": collector.source_plane.value,
                "evidence_count": result.evidence_by_source.get(collector.source_plane.value, 0)
            })
        except Exception as e:
            logger.error(f"evidence_collector.error", extra={
                "source_plane": collector.source_plane.value,
                "error": str(e)
            })

    # Update registry summary
    result.fabric_plane_registry.evidence_summary = result.evidence_by_source.copy()
    result.fabric_plane_registry.generated_at = now_pst()

    logger.info("evidence_collection.complete", extra={
        "total_evidence": result.total_evidence_count,
        "planes_detected": len(result.fabric_plane_registry.planes),
        "shadow_candidates": len(result.shadow_plane_candidates),
        "assets_with_evidence": len(result.routing_evidence)
    })

    return result
