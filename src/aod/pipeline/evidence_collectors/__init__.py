"""
Fabric Plane Evidence Collectors

Phase 1 of evidence-based fabric classification: Extract fabric plane signals
from AOD's existing observation planes during the standard discovery scan.

The change from category-based inference is adding fabric-aware analysis to
existing observation plane outputs.

Evidence Tiers:
- Tier 1 (0.95): Direct plane crawl - authoritative catalog data
- Tier 2 (0.70-0.90): Observation plane signals - traffic, resources, records
- Tier 3 (0.30-0.50): Category inference - heuristic guess (demoted legacy)

Each collector extracts signals from one observation plane and produces
FabricRoutingEvidence records with appropriate confidence scores.
"""

from .base import (
    EvidenceCollector,
    EvidenceCollectionResult,
    collect_all_evidence,
)
from .cloud_evidence import CloudEvidenceCollector
from .network_evidence import NetworkEvidenceCollector
from .finance_evidence import FinanceEvidenceCollector
from .cmdb_evidence import CMDBEvidenceCollector
from .idp_evidence import IdPEvidenceCollector

__all__ = [
    "EvidenceCollector",
    "EvidenceCollectionResult",
    "collect_all_evidence",
    "CloudEvidenceCollector",
    "NetworkEvidenceCollector",
    "FinanceEvidenceCollector",
    "CMDBEvidenceCollector",
    "IdPEvidenceCollector",
]
