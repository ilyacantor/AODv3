"""
Reconciliation Engine

Phase 3 of the evidence pipeline - reconciles evidence from:
- Phase 1: Observation plane signals (Cloud, Network, Finance, CMDB, IdP)
- Phase 2: Direct fabric plane crawls (Kong, Workato, Snowflake)

Key responsibilities:
1. Cross-reference Phase 1 predictions vs Phase 2 confirmations
2. Compute composite confidence scores from multi-source evidence
3. Deduplicate SORs appearing on multiple planes
4. Detect contradictions (conflicting evidence)
5. Flag unresolved assets for investigation
"""

from .engine import (
    ReconciliationEngine,
    ReconciliationResult,
    ReconciliationConfig,
    reconcile_all_evidence,
)
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
    Contradiction,
    ContradictionSeverity,
)

__all__ = [
    "ReconciliationEngine",
    "ReconciliationResult",
    "ReconciliationConfig",
    "reconcile_all_evidence",
    "CompositeConfidenceCalculator",
    "ConfidenceFactors",
    "SORDeduplicator",
    "DeduplicationResult",
    "ContradictionDetector",
    "Contradiction",
    "ContradictionSeverity",
]
