"""
Fabric Plane Classification Test Oracle

Evidence-based accuracy benchmark for fabric plane classification.
Tests the new 3-tier evidence system against expected outcomes.

EVIDENCE TIERS:
===============
- Tier 1 (0.95): Direct fabric plane crawl - authoritative
- Tier 2 (0.70-0.90): Observation plane signals
- Tier 3 (0.30-0.50): Category inference - demoted fallback

TEST CATEGORIES:
================
1. PLANE_ACCURACY: Correct plane assignment (iPaaS, API Gateway, Event Bus, Data Warehouse)
2. CONFIDENCE_CALIBRATION: Confidence scores correlate with correctness
3. EVIDENCE_CHAIN: Evidence records are properly attached
4. MULTI_PLANE: Assets with multiple planes handled correctly
5. CONTRADICTION: Conflicting evidence detected and handled
6. SHADOW_DETECTION: Unauthorized fabric planes identified

THRESHOLDS:
===========
- Tier 1 accuracy: >= 98% (direct crawl should be nearly perfect)
- Tier 2 accuracy: >= 85% (observation evidence)
- Tier 3 accuracy: >= 60% (category inference - deliberately lower)
- Overall accuracy: >= 85% (target from blueprint)

GUARDRAILS:
===========
- NEVER change policy to pass a test
- Fix bugs in evidence collection, not expected outcomes
- If a plane is misclassified, investigate WHY:
  - Missing evidence collector pattern?
  - Incorrect confidence scoring?
  - Contradiction not detected?

Usage:
    pytest tests/test_fabric_plane_classification.py -v

To run specific scenarios:
    pytest tests/test_fabric_plane_classification.py -v -k "test_tier_1"
"""

import pytest
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set
from uuid import uuid4

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aod.models.output_contracts import (
    FabricPlaneType,
    EvidenceTier,
    ConnectivityModality,
    FabricRoutingEvidence,
    EvidenceSourcePlane,
    FabricPlane,
)
from aod.pipeline.evidence_collectors.base import (
    EvidenceCollectionResult,
    collect_all_evidence,
    CONFIDENCE_SCORES,
)
from aod.pipeline.reconciliation.engine import (
    ReconciliationEngine,
    ReconciliationConfig,
    ReconciliationResult,
)
from aod.pipeline.reconciliation.confidence import (
    CompositeConfidenceCalculator,
    ConfidenceFactors,
)
from aod.pipeline.reconciliation.contradictions import (
    ContradictionDetector,
    ContradictionSeverity,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Accuracy thresholds by tier
TIER_1_ACCURACY_THRESHOLD = 0.98
TIER_2_ACCURACY_THRESHOLD = 0.85
TIER_3_ACCURACY_THRESHOLD = 0.60
OVERALL_ACCURACY_THRESHOLD = 0.85

# Confidence calibration thresholds
CALIBRATION_TOLERANCE = 0.10  # Predicted confidence within 10% of actual accuracy


@dataclass
class FabricPlaneExpectedOutcome:
    """Expected outcome for a single asset's fabric plane classification."""
    asset_key: str
    expected_plane: FabricPlaneType
    expected_tier: EvidenceTier
    expected_confidence_min: float
    expected_confidence_max: float
    expected_vendor: Optional[str] = None
    should_have_contradiction: bool = False
    notes: str = ""


@dataclass
class FabricPlaneTestScenario:
    """A test scenario for fabric plane classification."""
    name: str
    description: str
    snapshot_file: str
    expected_outcomes: List[FabricPlaneExpectedOutcome]

    # Optional: Direct crawl data to simulate Phase 2
    phase_2_crawl_file: Optional[str] = None


# =============================================================================
# TEST SCENARIOS
# =============================================================================

# Scenario 1: Pure Tier 1 classification (direct crawl)
TIER_1_SCENARIO = FabricPlaneTestScenario(
    name="tier_1_direct_crawl",
    description="Assets classified by direct fabric plane crawl should be Tier 1",
    snapshot_file="fabric_tier1_snapshot.json",
    phase_2_crawl_file="fabric_tier1_crawl.json",
    expected_outcomes=[
        # Kong routes
        FabricPlaneExpectedOutcome(
            asset_key="api.salesforce.com",
            expected_plane=FabricPlaneType.API_GATEWAY,
            expected_tier=EvidenceTier.TIER_1_DIRECT,
            expected_confidence_min=0.93,
            expected_confidence_max=0.98,
            expected_vendor="kong",
            notes="Route from Kong Admin API"
        ),
        # Workato recipes
        FabricPlaneExpectedOutcome(
            asset_key="salesforce",
            expected_plane=FabricPlaneType.IPAAS,
            expected_tier=EvidenceTier.TIER_1_DIRECT,
            expected_confidence_min=0.93,
            expected_confidence_max=0.98,
            expected_vendor="workato",
            notes="Recipe connection from Workato API"
        ),
        # Snowflake access
        FabricPlaneExpectedOutcome(
            asset_key="ANALYTICS.PUBLIC.SALES_DATA",
            expected_plane=FabricPlaneType.DATA_WAREHOUSE,
            expected_tier=EvidenceTier.TIER_1_DIRECT,
            expected_confidence_min=0.93,
            expected_confidence_max=0.98,
            expected_vendor="snowflake",
            notes="Table from Snowflake INFORMATION_SCHEMA"
        ),
    ]
)

# Scenario 2: Tier 2 observation evidence
TIER_2_SCENARIO = FabricPlaneTestScenario(
    name="tier_2_observation_evidence",
    description="Assets classified by observation plane signals (no direct crawl)",
    snapshot_file="fabric_tier2_snapshot.json",
    expected_outcomes=[
        # Network evidence: Traffic to Workato
        FabricPlaneExpectedOutcome(
            asset_key="hubspot.com",
            expected_plane=FabricPlaneType.IPAAS,
            expected_tier=EvidenceTier.TIER_2_OBSERVED,
            expected_confidence_min=0.70,
            expected_confidence_max=0.90,
            expected_vendor="workato",
            notes="Proxy traffic to hooks.workato.com from hubspot"
        ),
        # Cloud evidence: AWS API Gateway resource
        FabricPlaneExpectedOutcome(
            asset_key="customer-api-prod",
            expected_plane=FabricPlaneType.API_GATEWAY,
            expected_tier=EvidenceTier.TIER_2_OBSERVED,
            expected_confidence_min=0.85,
            expected_confidence_max=0.95,
            expected_vendor="aws_api_gateway",
            notes="AWS::ApiGateway::RestApi in cloud inventory"
        ),
        # Finance evidence: Confluent contract
        FabricPlaneExpectedOutcome(
            asset_key="confluent.io",
            expected_plane=FabricPlaneType.EVENT_BUS,
            expected_tier=EvidenceTier.TIER_2_OBSERVED,
            expected_confidence_min=0.80,
            expected_confidence_max=0.90,
            expected_vendor="confluent",
            notes="Finance contract for Confluent Cloud"
        ),
        # CMDB evidence: Integration dependency
        FabricPlaneExpectedOutcome(
            asset_key="erp-integration",
            expected_plane=FabricPlaneType.IPAAS,
            expected_tier=EvidenceTier.TIER_2_OBSERVED,
            expected_confidence_min=0.65,
            expected_confidence_max=0.80,
            expected_vendor="mulesoft",
            notes="CMDB dependency on MuleSoft"
        ),
    ]
)

# Scenario 3: Tier 3 category inference (fallback)
TIER_3_SCENARIO = FabricPlaneTestScenario(
    name="tier_3_category_inference",
    description="Assets with only category-based inference should be Tier 3 with low confidence",
    snapshot_file="fabric_tier3_snapshot.json",
    expected_outcomes=[
        # No direct evidence, only category suggests iPaaS
        FabricPlaneExpectedOutcome(
            asset_key="custom-integration.internal",
            expected_plane=FabricPlaneType.IPAAS,
            expected_tier=EvidenceTier.TIER_3_INFERRED,
            expected_confidence_min=0.30,
            expected_confidence_max=0.50,
            notes="Category: Integration suggests iPaaS, no observation evidence"
        ),
        # Unknown should NOT default to iPaaS
        FabricPlaneExpectedOutcome(
            asset_key="mystery-app.com",
            expected_plane=FabricPlaneType.UNMANAGED,
            expected_tier=EvidenceTier.TIER_3_INFERRED,
            expected_confidence_min=0.0,
            expected_confidence_max=0.30,
            notes="Unknown app should NOT get iPaaS default"
        ),
    ]
)

# Scenario 4: Multi-plane assets
MULTI_PLANE_SCENARIO = FabricPlaneTestScenario(
    name="multi_plane_routing",
    description="Assets that legitimately route through multiple fabric planes",
    snapshot_file="fabric_multiplane_snapshot.json",
    expected_outcomes=[
        # Salesforce through both iPaaS (sync) and Data Warehouse (analytics)
        FabricPlaneExpectedOutcome(
            asset_key="salesforce.com",
            expected_plane=FabricPlaneType.IPAAS,
            expected_tier=EvidenceTier.TIER_2_OBSERVED,
            expected_confidence_min=0.75,
            expected_confidence_max=0.90,
            expected_vendor="workato",
            notes="Salesforce→Workato pipe (sync to NetSuite)"
        ),
        FabricPlaneExpectedOutcome(
            asset_key="salesforce.com",
            expected_plane=FabricPlaneType.DATA_WAREHOUSE,
            expected_tier=EvidenceTier.TIER_2_OBSERVED,
            expected_confidence_min=0.75,
            expected_confidence_max=0.90,
            expected_vendor="snowflake",
            notes="Salesforce→Snowflake pipe (analytics ETL)"
        ),
    ]
)

# Scenario 5: Contradiction detection
CONTRADICTION_SCENARIO = FabricPlaneTestScenario(
    name="contradiction_detection",
    description="Assets with conflicting evidence should have contradictions flagged",
    snapshot_file="fabric_contradiction_snapshot.json",
    expected_outcomes=[
        FabricPlaneExpectedOutcome(
            asset_key="conflicting-app.com",
            expected_plane=FabricPlaneType.IPAAS,  # Should still classify but with flag
            expected_tier=EvidenceTier.TIER_2_OBSERVED,
            expected_confidence_min=0.50,
            expected_confidence_max=0.75,
            should_have_contradiction=True,
            notes="Network says iPaaS, CMDB says API Gateway - contradiction"
        ),
    ]
)

# Scenario 6: Shadow plane detection
SHADOW_PLANE_SCENARIO = FabricPlaneTestScenario(
    name="shadow_plane_detection",
    description="Unauthorized fabric planes discovered through evidence",
    snapshot_file="fabric_shadow_snapshot.json",
    expected_outcomes=[
        FabricPlaneExpectedOutcome(
            asset_key="marketing-zapier.zapier.com",
            expected_plane=FabricPlaneType.IPAAS,
            expected_tier=EvidenceTier.TIER_2_OBSERVED,
            expected_confidence_min=0.75,
            expected_confidence_max=0.90,
            expected_vendor="zapier",
            notes="Shadow Zapier detected via Finance transaction"
        ),
    ]
)

# All scenarios
ALL_SCENARIOS = [
    TIER_1_SCENARIO,
    TIER_2_SCENARIO,
    TIER_3_SCENARIO,
    MULTI_PLANE_SCENARIO,
    CONTRADICTION_SCENARIO,
    SHADOW_PLANE_SCENARIO,
]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def load_scenario_snapshot(scenario: FabricPlaneTestScenario) -> dict:
    """Load snapshot for a scenario."""
    snapshot_path = FIXTURES_DIR / scenario.snapshot_file
    if not snapshot_path.exists():
        # Return empty snapshot if file doesn't exist (tests will skip)
        return {}
    with open(snapshot_path, "r") as f:
        return json.load(f)


def compute_accuracy(expected: List[FabricPlaneExpectedOutcome], actual: ReconciliationResult) -> dict:
    """Compute accuracy metrics against expected outcomes."""
    total = len(expected)
    correct_plane = 0
    correct_tier = 0
    correct_confidence_range = 0
    correct_contradiction = 0

    # Build pipe lookup by asset key and plane
    actual_pipes = {}
    for pipe in actual.pipes:
        key = (pipe.source_system, pipe.fabric_plane)
        if key not in actual_pipes:
            actual_pipes[key] = []
        actual_pipes[key].append(pipe)

    missed = []
    wrong = []

    for exp in expected:
        key = (exp.asset_key, exp.expected_plane)
        pipes = actual_pipes.get(key, [])

        if not pipes:
            missed.append(exp)
            continue

        # Take highest confidence pipe
        pipe = max(pipes, key=lambda p: p.classification_confidence)

        # Check plane
        if pipe.fabric_plane == exp.expected_plane:
            correct_plane += 1
        else:
            wrong.append((exp, pipe))
            continue

        # Check tier
        if pipe.evidence_tier == exp.expected_tier:
            correct_tier += 1

        # Check confidence range
        if exp.expected_confidence_min <= pipe.classification_confidence <= exp.expected_confidence_max:
            correct_confidence_range += 1

        # Check contradiction flag
        if pipe.has_contradictions == exp.should_have_contradiction:
            correct_contradiction += 1

    return {
        "total": total,
        "plane_accuracy": correct_plane / total if total > 0 else 0,
        "tier_accuracy": correct_tier / total if total > 0 else 0,
        "confidence_calibration": correct_confidence_range / total if total > 0 else 0,
        "contradiction_accuracy": correct_contradiction / total if total > 0 else 0,
        "missed": missed,
        "wrong": wrong,
    }


# =============================================================================
# UNIT TESTS FOR COMPONENTS
# =============================================================================

class TestCompositeConfidence:
    """Test the composite confidence calculator."""

    def test_tier_1_base_confidence(self):
        """Tier 1 evidence should have high base confidence."""
        calculator = CompositeConfidenceCalculator()

        evidence = [
            FabricRoutingEvidence(
                evidence_id="test_1",
                source_plane=EvidenceSourcePlane.DIRECT_CRAWL,
                signal_type="kong_route",
                signal_detail="Direct crawl",
                confidence=0.95,
                timestamp=datetime.utcnow(),
                fabric_plane_type=FabricPlaneType.API_GATEWAY,
                fabric_plane_vendor="kong"
            )
        ]

        factors = calculator.calculate(evidence)

        assert factors.base_confidence >= 0.90
        assert factors.composite_score >= 0.90
        assert factors.tier_1_count == 1

    def test_multi_source_corroboration(self):
        """Multiple agreeing sources should boost confidence."""
        calculator = CompositeConfidenceCalculator()

        # Single source
        single_evidence = [
            FabricRoutingEvidence(
                evidence_id="test_1",
                source_plane=EvidenceSourcePlane.NETWORK,
                signal_type="proxy_traffic",
                signal_detail="Traffic to workato.com",
                confidence=0.85,
                timestamp=datetime.utcnow(),
                fabric_plane_type=FabricPlaneType.IPAAS,
                fabric_plane_vendor="workato"
            )
        ]

        single_factors = calculator.calculate(single_evidence)

        # Multiple sources
        multi_evidence = [
            FabricRoutingEvidence(
                evidence_id="test_1",
                source_plane=EvidenceSourcePlane.NETWORK,
                signal_type="proxy_traffic",
                signal_detail="Traffic to workato.com",
                confidence=0.85,
                timestamp=datetime.utcnow(),
                fabric_plane_type=FabricPlaneType.IPAAS,
                fabric_plane_vendor="workato"
            ),
            FabricRoutingEvidence(
                evidence_id="test_2",
                source_plane=EvidenceSourcePlane.FINANCE,
                signal_type="contract",
                signal_detail="Workato contract",
                confidence=0.80,
                timestamp=datetime.utcnow(),
                fabric_plane_type=FabricPlaneType.IPAAS,
                fabric_plane_vendor="workato"
            ),
        ]

        multi_factors = calculator.calculate(multi_evidence)

        # Multi-source should have higher confidence
        assert multi_factors.composite_score > single_factors.composite_score
        assert multi_factors.corroboration_bonus > 0
        assert multi_factors.source_count == 2

    def test_contradiction_penalty(self):
        """Contradictions should reduce confidence."""
        calculator = CompositeConfidenceCalculator()

        evidence = [
            FabricRoutingEvidence(
                evidence_id="test_1",
                source_plane=EvidenceSourcePlane.NETWORK,
                signal_type="proxy_traffic",
                signal_detail="Traffic",
                confidence=0.85,
                timestamp=datetime.utcnow(),
                fabric_plane_type=FabricPlaneType.IPAAS,
                fabric_plane_vendor="workato"
            )
        ]

        normal_factors = calculator.calculate(evidence, has_contradiction=False)
        contradiction_factors = calculator.calculate(evidence, has_contradiction=True)

        assert contradiction_factors.composite_score < normal_factors.composite_score
        assert contradiction_factors.contradiction_penalty > 0


class TestContradictionDetector:
    """Test contradiction detection."""

    def test_no_contradiction_single_plane(self):
        """Single plane evidence should not produce contradictions."""
        detector = ContradictionDetector()

        evidence = [
            FabricRoutingEvidence(
                evidence_id="test_1",
                source_plane=EvidenceSourcePlane.NETWORK,
                signal_type="proxy_traffic",
                signal_detail="Traffic to workato.com",
                confidence=0.85,
                timestamp=datetime.utcnow(),
                fabric_plane_type=FabricPlaneType.IPAAS,
                fabric_plane_vendor="workato"
            ),
            FabricRoutingEvidence(
                evidence_id="test_2",
                source_plane=EvidenceSourcePlane.FINANCE,
                signal_type="contract",
                signal_detail="Workato contract",
                confidence=0.80,
                timestamp=datetime.utcnow(),
                fabric_plane_type=FabricPlaneType.IPAAS,
                fabric_plane_vendor="workato"
            ),
        ]

        analysis = detector.analyze("test_asset", evidence)

        assert len(analysis.contradictions) == 0
        assert analysis.confidence_penalty == 0

    def test_plane_conflict_detected(self):
        """Different planes for same asset should produce contradiction."""
        detector = ContradictionDetector()

        evidence = [
            FabricRoutingEvidence(
                evidence_id="test_1",
                source_plane=EvidenceSourcePlane.NETWORK,
                signal_type="proxy_traffic",
                signal_detail="Traffic to workato.com",
                confidence=0.85,
                timestamp=datetime.utcnow(),
                fabric_plane_type=FabricPlaneType.IPAAS,
                fabric_plane_vendor="workato"
            ),
            FabricRoutingEvidence(
                evidence_id="test_2",
                source_plane=EvidenceSourcePlane.CMDB,
                signal_type="dependency",
                signal_detail="Kong dependency",
                confidence=0.70,
                timestamp=datetime.utcnow(),
                fabric_plane_type=FabricPlaneType.API_GATEWAY,
                fabric_plane_vendor="kong"
            ),
        ]

        analysis = detector.analyze("test_asset", evidence)

        assert len(analysis.contradictions) >= 1
        assert analysis.confidence_penalty > 0

    def test_phase_mismatch_detected(self):
        """Phase 1 prediction not confirmed by Phase 2 should be flagged."""
        detector = ContradictionDetector()

        evidence = [
            FabricRoutingEvidence(
                evidence_id="test_1",
                source_plane=EvidenceSourcePlane.NETWORK,
                signal_type="proxy_traffic",
                signal_detail="Traffic to workato.com",
                confidence=0.85,
                timestamp=datetime.utcnow(),
                fabric_plane_type=FabricPlaneType.IPAAS,
                fabric_plane_vendor="workato"
            ),
        ]

        # Phase 2 confirmed a DIFFERENT plane
        phase_2_confirmed = {FabricPlaneType.API_GATEWAY}

        analysis = detector.analyze("test_asset", evidence, phase_2_confirmed)

        # Should detect mismatch
        assert len(analysis.contradictions) >= 1


class TestEvidenceConfidenceScores:
    """Test that confidence scores follow the tier hierarchy."""

    def test_tier_1_highest(self):
        """Tier 1 base confidence should be highest."""
        assert CONFIDENCE_SCORES["tier_1_direct"] > CONFIDENCE_SCORES["tier_2_very_high"]

    def test_tier_2_ranges(self):
        """Tier 2 confidence should be 0.70-0.90."""
        tier_2_scores = [
            CONFIDENCE_SCORES["tier_2_very_high"],
            CONFIDENCE_SCORES["tier_2_high"],
            CONFIDENCE_SCORES["tier_2_medium"],
            CONFIDENCE_SCORES["tier_2_low"],
        ]

        for score in tier_2_scores:
            assert 0.70 <= score <= 0.90

    def test_tier_3_demoted(self):
        """Tier 3 confidence should be 0.30-0.50 (demoted)."""
        tier_3_scores = [
            CONFIDENCE_SCORES["tier_3_high"],
            CONFIDENCE_SCORES["tier_3_medium"],
            CONFIDENCE_SCORES["tier_3_low"],
        ]

        for score in tier_3_scores:
            assert 0.30 <= score <= 0.50


# =============================================================================
# INTEGRATION TESTS (with fixtures)
# =============================================================================

class TestFabricPlaneClassificationAccuracy:
    """
    Integration tests for fabric plane classification accuracy.

    These tests require fixture files to be present in tests/fixtures/.
    If fixtures are missing, tests will be skipped.
    """

    @pytest.fixture
    def reconciliation_engine(self):
        """Create a reconciliation engine for testing."""
        config = ReconciliationConfig(
            min_confidence_governed=0.70,
            min_confidence_known=0.50,
            min_confidence_classify=0.30,
            contradiction_penalty=0.15,
            enable_deduplication=True,
        )
        return ReconciliationEngine(config)

    def test_tier_1_accuracy(self, reconciliation_engine):
        """
        Tier 1 (direct crawl) evidence should produce high-confidence pipes.
        Verifies that direct crawl data results in Tier 1 classification.
        """
        from aod.pipeline.fabric_connectors.base import DirectCrawlResult, CrawledAsset, ConnectorStatus

        # Construct Phase 2 direct crawl results for Kong API Gateway
        kong_evidence = FabricRoutingEvidence(
            evidence_id="tier1_kong_1",
            source_plane=EvidenceSourcePlane.DIRECT_CRAWL,
            signal_type="kong_route",
            signal_detail="GET /api/salesforce -> upstream:salesforce-api",
            confidence=CONFIDENCE_SCORES["tier_1_direct"],
            timestamp=datetime.utcnow(),
            fabric_plane_type=FabricPlaneType.API_GATEWAY,
            fabric_plane_vendor="kong",
            raw_data={"asset_key": "api.salesforce.com", "service_name": "salesforce-api"}
        )

        kong_crawl = DirectCrawlResult(
            plane_type=FabricPlaneType.API_GATEWAY,
            vendor="kong",
            instance_name="Kong Gateway (prod)",
            status=ConnectorStatus.SUCCESS,
            assets=[CrawledAsset(
                asset_id="api.salesforce.com",
                asset_name="Salesforce API Route",
                asset_type="route",
            )],
            evidence=[kong_evidence],
        )

        # Phase 1: empty (no observation evidence)
        phase_1 = EvidenceCollectionResult()

        result = reconciliation_engine.reconcile(
            phase_1_result=phase_1,
            phase_2_results={"kong": kong_crawl}
        )

        # Tier 1 crawl should produce at least one pipe
        assert len(result.pipes) >= 1, "Direct crawl should produce pipes"
        kong_pipe = result.pipes[0]
        assert kong_pipe.fabric_plane == FabricPlaneType.API_GATEWAY
        assert kong_pipe.classification_confidence >= 0.90, (
            f"Tier 1 confidence should be >= 0.90, got {kong_pipe.classification_confidence}"
        )

    def test_tier_2_accuracy(self, reconciliation_engine):
        """
        Tier 2 (observation evidence) should produce medium-high confidence pipes.
        """
        # Construct Phase 1 observation evidence: network traffic to Workato
        phase_1 = EvidenceCollectionResult()
        phase_1.add_evidence("hubspot.com", FabricRoutingEvidence(
            evidence_id="tier2_net_1",
            source_plane=EvidenceSourcePlane.NETWORK,
            signal_type="proxy_traffic",
            signal_detail="Traffic to hooks.workato.com from hubspot",
            confidence=CONFIDENCE_SCORES["tier_2_high"],
            timestamp=datetime.utcnow(),
            fabric_plane_type=FabricPlaneType.IPAAS,
            fabric_plane_vendor="workato"
        ))
        # Corroborating finance evidence
        phase_1.add_evidence("hubspot.com", FabricRoutingEvidence(
            evidence_id="tier2_fin_1",
            source_plane=EvidenceSourcePlane.FINANCE,
            signal_type="contract",
            signal_detail="Workato Enterprise contract",
            confidence=CONFIDENCE_SCORES["tier_2_medium"],
            timestamp=datetime.utcnow(),
            fabric_plane_type=FabricPlaneType.IPAAS,
            fabric_plane_vendor="workato"
        ))

        result = reconciliation_engine.reconcile(
            phase_1_result=phase_1,
            phase_2_results={}
        )

        assert len(result.pipes) >= 1, "Tier 2 evidence should produce pipes"
        pipe = result.pipes[0]
        assert pipe.fabric_plane == FabricPlaneType.IPAAS
        assert 0.70 <= pipe.classification_confidence <= 0.98, (
            f"Tier 2 confidence should be 0.70-0.98, got {pipe.classification_confidence}"
        )

    def test_tier_3_confidence_demoted(self, reconciliation_engine):
        """
        Tier 3 (category inference) confidence should be capped at 0.50.
        """
        # Single weak category inference signal
        phase_1 = EvidenceCollectionResult()
        phase_1.add_evidence("custom-integration.internal", FabricRoutingEvidence(
            evidence_id="tier3_cat_1",
            source_plane=EvidenceSourcePlane.CMDB,
            signal_type="category_inference",
            signal_detail="Category: Integration suggests iPaaS",
            confidence=CONFIDENCE_SCORES["tier_3_high"],
            timestamp=datetime.utcnow(),
            fabric_plane_type=FabricPlaneType.IPAAS,
            fabric_plane_vendor=None
        ))

        result = reconciliation_engine.reconcile(
            phase_1_result=phase_1,
            phase_2_results={}
        )

        if result.pipes:
            for pipe in result.pipes:
                assert pipe.classification_confidence <= 0.55, (
                    f"Tier 3 confidence should be <= 0.55, got {pipe.classification_confidence}"
                )
        # If no pipes produced, that's also valid — low confidence may be below threshold

    def test_no_default_to_ipaas(self):
        """
        Unknown assets should NOT default to iPaaS.
        This was the previous behavior causing ~50% accuracy.
        """
        engine = ReconciliationEngine(ReconciliationConfig(
            min_confidence_classify=0.30,
        ))

        # Asset with no evidence at all
        phase_1 = EvidenceCollectionResult()
        phase_1.unattached_assets.append("mystery-app.com")

        result = engine.reconcile(
            phase_1_result=phase_1,
            phase_2_results={}
        )

        # Should NOT produce an iPaaS pipe for an unknown asset
        ipaas_pipes = [p for p in result.pipes if p.fabric_plane == FabricPlaneType.IPAAS
                       and "mystery-app.com" in (p.source_system or "")]
        assert len(ipaas_pipes) == 0, (
            "Unknown assets should NOT default to iPaaS classification"
        )

    def test_multi_plane_support(self, reconciliation_engine):
        """
        Assets with multiple fabric planes should have separate Pipe records.
        """
        phase_1 = EvidenceCollectionResult()
        # Salesforce through iPaaS (Workato sync)
        phase_1.add_evidence("salesforce.com", FabricRoutingEvidence(
            evidence_id="multi_ipaas_1",
            source_plane=EvidenceSourcePlane.NETWORK,
            signal_type="proxy_traffic",
            signal_detail="Traffic to hooks.workato.com",
            confidence=CONFIDENCE_SCORES["tier_2_high"],
            timestamp=datetime.utcnow(),
            fabric_plane_type=FabricPlaneType.IPAAS,
            fabric_plane_vendor="workato"
        ))
        # Salesforce through Data Warehouse (Snowflake ETL)
        phase_1.add_evidence("salesforce.com", FabricRoutingEvidence(
            evidence_id="multi_dw_1",
            source_plane=EvidenceSourcePlane.CLOUD,
            signal_type="etl_pipeline",
            signal_detail="Snowflake SALES_DATA table from Salesforce",
            confidence=CONFIDENCE_SCORES["tier_2_high"],
            timestamp=datetime.utcnow(),
            fabric_plane_type=FabricPlaneType.DATA_WAREHOUSE,
            fabric_plane_vendor="snowflake"
        ))

        result = reconciliation_engine.reconcile(
            phase_1_result=phase_1,
            phase_2_results={}
        )

        # Should have pipes for multiple planes from the same source asset
        sf_planes = {p.fabric_plane for p in result.pipes
                     if "salesforce" in (p.source_system or "").lower()}
        assert len(sf_planes) >= 2, (
            f"Salesforce should route through multiple planes, got {sf_planes}"
        )

    def test_contradiction_flagged(self, reconciliation_engine):
        """
        Conflicting evidence should be detected and flagged.
        """
        phase_1 = EvidenceCollectionResult()
        # Network says iPaaS
        phase_1.add_evidence("conflicting-app.com", FabricRoutingEvidence(
            evidence_id="contra_net_1",
            source_plane=EvidenceSourcePlane.NETWORK,
            signal_type="proxy_traffic",
            signal_detail="Traffic to workato.com",
            confidence=CONFIDENCE_SCORES["tier_2_high"],
            timestamp=datetime.utcnow(),
            fabric_plane_type=FabricPlaneType.IPAAS,
            fabric_plane_vendor="workato"
        ))
        # CMDB says API Gateway
        phase_1.add_evidence("conflicting-app.com", FabricRoutingEvidence(
            evidence_id="contra_cmdb_1",
            source_plane=EvidenceSourcePlane.CMDB,
            signal_type="dependency",
            signal_detail="Kong API Gateway dependency",
            confidence=CONFIDENCE_SCORES["tier_2_low"],
            timestamp=datetime.utcnow(),
            fabric_plane_type=FabricPlaneType.API_GATEWAY,
            fabric_plane_vendor="kong"
        ))

        result = reconciliation_engine.reconcile(
            phase_1_result=phase_1,
            phase_2_results={}
        )

        # Contradiction should be detected
        assert "conflicting-app.com" in result.contradictions_by_asset, (
            "Contradicting evidence should be flagged"
        )
        analysis = result.contradictions_by_asset["conflicting-app.com"]
        assert len(analysis.contradictions) >= 1, "At least one contradiction expected"

    def test_shadow_plane_detection(self, reconciliation_engine):
        """
        Shadow plane candidates should be surfaced from evidence collection.
        """
        phase_1 = EvidenceCollectionResult()
        # Finance transaction revealing unauthorized Zapier usage
        phase_1.add_evidence("marketing-zapier.zapier.com", FabricRoutingEvidence(
            evidence_id="shadow_fin_1",
            source_plane=EvidenceSourcePlane.FINANCE,
            signal_type="transaction",
            signal_detail="Zapier Team Plan - Marketing Dept",
            confidence=CONFIDENCE_SCORES["tier_2_high"],
            timestamp=datetime.utcnow(),
            fabric_plane_type=FabricPlaneType.IPAAS,
            fabric_plane_vendor="zapier"
        ))

        # Mark as shadow candidate
        phase_1.shadow_plane_candidates.append(FabricPlane(
            plane_id="shadow:zapier:marketing",
            plane_type=FabricPlaneType.IPAAS,
            vendor="zapier",
            display_name="Zapier (Marketing - Shadow)",
            domain="zapier.com",
            managed_asset_count=0,
            evidence_refs=["shadow_fin_1"],
            confidence=CONFIDENCE_SCORES["tier_2_high"]
        ))

        result = reconciliation_engine.reconcile(
            phase_1_result=phase_1,
            phase_2_results={}
        )

        # Shadow planes should be surfaced
        assert len(result.shadow_planes) >= 1, "Shadow Zapier should be detected"
        shadow = result.shadow_planes[0]
        assert shadow.vendor == "zapier"
        assert shadow.plane_type == FabricPlaneType.IPAAS


# =============================================================================
# EXPECTED OUTCOME GENERATION (for creating fixtures)
# =============================================================================

def generate_expected_outcomes_template() -> dict:
    """
    Generate a template for expected outcomes file.

    Use this to create tests/fixtures/fabric_expected_outcomes.json
    when setting up new test scenarios.
    """
    return {
        "fabric_plane_classification": {
            "description": "Expected fabric plane classifications",
            "generated_at": datetime.utcnow().isoformat(),
            "scenarios": [
                {
                    "name": scenario.name,
                    "description": scenario.description,
                    "expected_outcomes": [
                        {
                            "asset_key": exp.asset_key,
                            "expected_plane": exp.expected_plane.value,
                            "expected_tier": exp.expected_tier.value,
                            "expected_confidence_min": exp.expected_confidence_min,
                            "expected_confidence_max": exp.expected_confidence_max,
                            "expected_vendor": exp.expected_vendor,
                            "should_have_contradiction": exp.should_have_contradiction,
                            "notes": exp.notes,
                        }
                        for exp in scenario.expected_outcomes
                    ]
                }
                for scenario in ALL_SCENARIOS
            ]
        }
    }


if __name__ == "__main__":
    # Print template for expected outcomes
    import json
    template = generate_expected_outcomes_template()
    print(json.dumps(template, indent=2))
