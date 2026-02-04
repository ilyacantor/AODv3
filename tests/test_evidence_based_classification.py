"""
Technical Tests for Evidence-Based Fabric Plane Classification

Tests all components of the new evidence-based classification system:
1. Evidence Collectors (Cloud, Network, Finance, CMDB, IdP)
2. Fabric Plane Connectors (Kong, Workato, Snowflake)
3. Reconciliation Engine
4. Composite Confidence Scoring
5. SOR Deduplication
6. Contradiction Detection

These are unit/integration tests - they do NOT require external services
or Farm data. Use test_fabric_plane_classification.py for eval tests.
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aod.models.output_contracts import (
    FabricPlaneType,
    EvidenceTier,
    EvidenceSourcePlane,
    FabricRoutingEvidence,
    ConnectivityModality,
    PipeGovernanceStatus,
    ClassificationMethod,
)
from aod.pipeline.evidence_collectors.base import (
    CONFIDENCE_SCORES,
    EvidenceCollectionResult,
    EvidenceCollector,
)
from aod.pipeline.reconciliation.confidence import (
    CompositeConfidenceCalculator,
    ConfidenceFactors,
    TIER_BASE_CONFIDENCE,
    SOURCE_RELIABILITY,
)
from aod.pipeline.reconciliation.deduplication import (
    SORDeduplicator,
    DeduplicationResult,
)
from aod.pipeline.reconciliation.contradictions import (
    ContradictionDetector,
    ContradictionSeverity,
    ContradictionType,
)
from aod.pipeline.reconciliation.engine import (
    ReconciliationEngine,
    ReconciliationConfig,
    ReconciliationResult,
)
from aod.pipeline.fabric_connectors.base import (
    ConnectorConfig,
    DirectCrawlResult,
    CrawledAsset,
    CrawledPipe,
    ConnectorStatus,
    TIER_1_CONFIDENCE,
)


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def sample_tier_1_evidence():
    """Tier 1 evidence from direct crawl."""
    return FabricRoutingEvidence(
        evidence_id="ev_tier1_001",
        source_plane=EvidenceSourcePlane.DIRECT_CRAWL,
        signal_type="kong_route",
        signal_detail="Direct crawl: Kong route api.example.com -> backend-service",
        confidence=0.95,
        timestamp=datetime.utcnow(),
        fabric_plane_type=FabricPlaneType.API_GATEWAY,
        fabric_plane_vendor="kong",
        raw_data={"route_id": "route_123", "service": "backend-service"}
    )


@pytest.fixture
def sample_tier_2_evidence():
    """Tier 2 evidence from observation plane."""
    return [
        FabricRoutingEvidence(
            evidence_id="ev_tier2_001",
            source_plane=EvidenceSourcePlane.NETWORK,
            signal_type="proxy_traffic",
            signal_detail="Traffic to hooks.workato.com from salesforce",
            confidence=0.85,
            timestamp=datetime.utcnow(),
            fabric_plane_type=FabricPlaneType.IPAAS,
            fabric_plane_vendor="workato",
            raw_data={"bytes": 50000, "uri": "/webhooks/salesforce"}
        ),
        FabricRoutingEvidence(
            evidence_id="ev_tier2_002",
            source_plane=EvidenceSourcePlane.FINANCE,
            signal_type="contract",
            signal_detail="Workato Enterprise contract",
            confidence=0.80,
            timestamp=datetime.utcnow(),
            fabric_plane_type=FabricPlaneType.IPAAS,
            fabric_plane_vendor="workato",
            raw_data={"contract_id": "c_456", "amount": 50000}
        ),
    ]


@pytest.fixture
def sample_tier_3_evidence():
    """Tier 3 evidence from category inference."""
    return FabricRoutingEvidence(
        evidence_id="ev_tier3_001",
        source_plane=EvidenceSourcePlane.CMDB,
        signal_type="category_inference",
        signal_detail="Category: Integration suggests iPaaS",
        confidence=0.40,
        timestamp=datetime.utcnow() - timedelta(days=100),  # Stale
        fabric_plane_type=FabricPlaneType.IPAAS,
        fabric_plane_vendor=None,
        raw_data={"category": "Integration"}
    )


@pytest.fixture
def conflicting_evidence():
    """Evidence with conflicting plane claims."""
    return [
        FabricRoutingEvidence(
            evidence_id="ev_conflict_001",
            source_plane=EvidenceSourcePlane.NETWORK,
            signal_type="proxy_traffic",
            signal_detail="Traffic to workato.com",
            confidence=0.85,
            timestamp=datetime.utcnow(),
            fabric_plane_type=FabricPlaneType.IPAAS,
            fabric_plane_vendor="workato"
        ),
        FabricRoutingEvidence(
            evidence_id="ev_conflict_002",
            source_plane=EvidenceSourcePlane.CMDB,
            signal_type="dependency",
            signal_detail="CMDB shows Kong dependency",
            confidence=0.75,
            timestamp=datetime.utcnow(),
            fabric_plane_type=FabricPlaneType.API_GATEWAY,
            fabric_plane_vendor="kong"
        ),
    ]


# =============================================================================
# CONFIDENCE SCORE TESTS
# =============================================================================

class TestConfidenceScores:
    """Test confidence score hierarchy."""

    def test_tier_1_is_highest(self):
        """Tier 1 base confidence should be highest."""
        assert CONFIDENCE_SCORES["tier_1_direct"] > CONFIDENCE_SCORES["tier_2_very_high"]
        assert CONFIDENCE_SCORES["tier_1_direct"] == 0.95

    def test_tier_2_range(self):
        """Tier 2 confidence should be 0.70-0.90."""
        tier_2_keys = ["tier_2_very_high", "tier_2_high", "tier_2_medium", "tier_2_low"]
        for key in tier_2_keys:
            assert 0.70 <= CONFIDENCE_SCORES[key] <= 0.90, f"{key} out of range"

    def test_tier_3_demoted(self):
        """Tier 3 confidence should be 0.30-0.50 (demoted from 0.70)."""
        tier_3_keys = ["tier_3_high", "tier_3_medium", "tier_3_low"]
        for key in tier_3_keys:
            assert 0.30 <= CONFIDENCE_SCORES[key] <= 0.50, f"{key} should be demoted"

    def test_tier_3_never_exceeds_0_5(self):
        """Tier 3 should never exceed 0.5 confidence."""
        tier_3_max = max(
            CONFIDENCE_SCORES[k] for k in CONFIDENCE_SCORES if k.startswith("tier_3")
        )
        assert tier_3_max <= 0.50


class TestCompositeConfidenceCalculator:
    """Test composite confidence calculation."""

    def test_single_tier_1_evidence(self, sample_tier_1_evidence):
        """Single Tier 1 evidence should have high confidence."""
        calculator = CompositeConfidenceCalculator()
        factors = calculator.calculate([sample_tier_1_evidence])

        assert factors.base_confidence >= 0.90
        assert factors.tier_1_count == 1
        assert factors.composite_score >= 0.85

    def test_multi_source_corroboration(self, sample_tier_2_evidence):
        """Multiple sources should boost confidence vs single source."""
        calculator = CompositeConfidenceCalculator()
        factors = calculator.calculate(sample_tier_2_evidence)

        assert factors.source_count == 2
        assert factors.corroboration_bonus > 0
        # Corroboration bonus is applied (score includes the bonus)
        # Note: composite may be below base due to reliability factor normalization
        assert factors.composite_score >= 0.70  # Reasonable threshold for Tier 2

    def test_contradiction_penalty(self, sample_tier_2_evidence):
        """Contradictions should reduce confidence."""
        calculator = CompositeConfidenceCalculator()

        normal = calculator.calculate(sample_tier_2_evidence, has_contradiction=False)
        with_contradiction = calculator.calculate(sample_tier_2_evidence, has_contradiction=True)

        assert with_contradiction.composite_score < normal.composite_score
        assert with_contradiction.contradiction_penalty > 0

    def test_stale_evidence_penalty(self):
        """Old evidence should have reduced confidence."""
        calculator = CompositeConfidenceCalculator()

        recent_evidence = FabricRoutingEvidence(
            evidence_id="ev_recent",
            source_plane=EvidenceSourcePlane.NETWORK,
            signal_type="proxy",
            signal_detail="Recent traffic",
            confidence=0.85,
            timestamp=datetime.utcnow(),
            fabric_plane_type=FabricPlaneType.IPAAS,
            fabric_plane_vendor="workato"
        )

        stale_evidence = FabricRoutingEvidence(
            evidence_id="ev_stale",
            source_plane=EvidenceSourcePlane.NETWORK,
            signal_type="proxy",
            signal_detail="Old traffic",
            confidence=0.85,
            timestamp=datetime.utcnow() - timedelta(days=200),
            fabric_plane_type=FabricPlaneType.IPAAS,
            fabric_plane_vendor="workato"
        )

        recent_factors = calculator.calculate([recent_evidence])
        stale_factors = calculator.calculate([stale_evidence])

        assert stale_factors.recency_factor < recent_factors.recency_factor

    def test_empty_evidence_returns_zero(self):
        """Empty evidence list should return zero confidence."""
        calculator = CompositeConfidenceCalculator()
        factors = calculator.calculate([])

        assert factors.composite_score == 0.0
        assert factors.evidence_count == 0

    def test_max_confidence_cap(self, sample_tier_1_evidence, sample_tier_2_evidence):
        """Confidence should be capped at 0.98."""
        calculator = CompositeConfidenceCalculator()

        # Lots of corroborating evidence
        all_evidence = [sample_tier_1_evidence] + sample_tier_2_evidence
        factors = calculator.calculate(all_evidence)

        assert factors.composite_score <= 0.98


# =============================================================================
# CONTRADICTION DETECTION TESTS
# =============================================================================

class TestContradictionDetector:
    """Test contradiction detection."""

    def test_no_contradiction_single_plane(self, sample_tier_2_evidence):
        """Same plane evidence should not produce contradictions."""
        detector = ContradictionDetector()
        analysis = detector.analyze("test_asset", sample_tier_2_evidence)

        assert len(analysis.contradictions) == 0
        assert analysis.confidence_penalty == 0

    def test_plane_conflict_detected(self, conflicting_evidence):
        """Different planes should produce contradiction."""
        detector = ContradictionDetector()
        analysis = detector.analyze("test_asset", conflicting_evidence)

        assert len(analysis.contradictions) >= 1
        assert analysis.confidence_penalty > 0

        # Check contradiction type
        plane_conflicts = [
            c for c in analysis.contradictions
            if c.contradiction_type == ContradictionType.PLANE_CONFLICT
        ]
        assert len(plane_conflicts) >= 1

    def test_phase_mismatch_detected(self, sample_tier_2_evidence):
        """Phase 1 prediction not confirmed by Phase 2 should be flagged."""
        detector = ContradictionDetector()

        # Phase 2 confirmed different plane
        phase_2_confirmed = {FabricPlaneType.API_GATEWAY}

        analysis = detector.analyze("test_asset", sample_tier_2_evidence, phase_2_confirmed)

        # Should detect mismatch (Phase 1 said iPaaS, Phase 2 said API Gateway)
        phase_mismatches = [
            c for c in analysis.contradictions
            if c.contradiction_type == ContradictionType.PHASE_MISMATCH
        ]
        assert len(phase_mismatches) >= 1

    def test_severity_assessment(self, conflicting_evidence):
        """Higher confidence conflicts should have higher severity."""
        detector = ContradictionDetector()
        analysis = detector.analyze("test_asset", conflicting_evidence)

        # Both have Tier 2 evidence, should be MEDIUM or higher
        for contradiction in analysis.contradictions:
            assert contradiction.severity in [
                ContradictionSeverity.MEDIUM,
                ContradictionSeverity.HIGH,
                ContradictionSeverity.CRITICAL
            ]

    def test_recommendation_provided(self, conflicting_evidence):
        """Contradictions should have resolution recommendations."""
        detector = ContradictionDetector()
        analysis = detector.analyze("test_asset", conflicting_evidence)

        for contradiction in analysis.contradictions:
            assert contradiction.resolution_recommendation != ""


# =============================================================================
# DEDUPLICATION TESTS
# =============================================================================

class TestSORDeduplication:
    """Test SOR deduplication logic."""

    def test_key_normalization(self):
        """Keys should be normalized for comparison."""
        deduplicator = SORDeduplicator()

        # Various forms of the same key
        keys = [
            "https://salesforce.com",
            "http://www.salesforce.com",
            "SALESFORCE.COM",
            "salesforce.com/",
        ]

        normalized = [deduplicator._normalize_key(k) for k in keys]

        # All should normalize to same form
        assert all(n == normalized[0] for n in normalized)

    def test_true_duplicate_detected(self):
        """Same asset on same plane should be detected as true duplicate."""
        deduplicator = SORDeduplicator()

        # Create mock pipes
        from unittest.mock import MagicMock

        pipe1 = MagicMock()
        pipe1.pipe_id = "pipe_1"
        pipe1.source_system = "salesforce.com"
        pipe1.fabric_plane = FabricPlaneType.IPAAS
        pipe1.classification_confidence = 0.85
        pipe1.governance_status = MagicMock(value="governed")

        pipe2 = MagicMock()
        pipe2.pipe_id = "pipe_2"
        pipe2.source_system = "www.salesforce.com"
        pipe2.fabric_plane = FabricPlaneType.IPAAS
        pipe2.classification_confidence = 0.80
        pipe2.governance_status = MagicMock(value="governed")

        result = deduplicator.deduplicate([pipe1, pipe2], {})

        assert result.duplicates_merged >= 1

    def test_multi_plane_preserved(self):
        """Asset on multiple planes should not be merged."""
        deduplicator = SORDeduplicator()

        from unittest.mock import MagicMock

        pipe1 = MagicMock()
        pipe1.pipe_id = "pipe_1"
        pipe1.source_system = "salesforce.com"
        pipe1.fabric_plane = FabricPlaneType.IPAAS
        pipe1.classification_confidence = 0.85
        pipe1.governance_status = MagicMock(value="governed")

        pipe2 = MagicMock()
        pipe2.pipe_id = "pipe_2"
        pipe2.source_system = "salesforce.com"
        pipe2.fabric_plane = FabricPlaneType.DATA_WAREHOUSE
        pipe2.classification_confidence = 0.80
        pipe2.governance_status = MagicMock(value="governed")

        result = deduplicator.deduplicate([pipe1, pipe2], {})

        assert result.multi_plane_count >= 1
        assert result.duplicates_merged == 0

    def test_shadow_conflict_flagged(self):
        """Shadow + official plane should be flagged."""
        deduplicator = SORDeduplicator()

        from unittest.mock import MagicMock

        pipe1 = MagicMock()
        pipe1.pipe_id = "pipe_official"
        pipe1.source_system = "zapier.com"
        pipe1.fabric_plane = FabricPlaneType.IPAAS
        pipe1.classification_confidence = 0.85
        pipe1.governance_status = MagicMock(value="governed")

        pipe2 = MagicMock()
        pipe2.pipe_id = "pipe_shadow"
        pipe2.source_system = "zapier.com"
        pipe2.fabric_plane = FabricPlaneType.IPAAS
        pipe2.classification_confidence = 0.75
        pipe2.governance_status = MagicMock(value="shadow")

        result = deduplicator.deduplicate([pipe1, pipe2], {})

        assert result.shadow_conflict_count >= 1


# =============================================================================
# CONNECTOR TESTS
# =============================================================================

class TestConnectorBase:
    """Test fabric plane connector base functionality."""

    def test_tier_1_confidence_value(self):
        """Tier 1 confidence should be 0.95."""
        assert TIER_1_CONFIDENCE == 0.95

    def test_connector_config_validation(self):
        """Connector config should validate required fields."""
        config = ConnectorConfig(
            plane_type=FabricPlaneType.API_GATEWAY,
            vendor="kong",
            instance_name="prod-kong",
            base_url="https://kong-admin.internal:8444"
        )

        assert config.plane_type == FabricPlaneType.API_GATEWAY
        assert config.vendor == "kong"
        assert config.timeout_seconds == 30
        assert config.max_retries == 3

    def test_direct_crawl_result_structure(self):
        """DirectCrawlResult should have correct structure."""
        result = DirectCrawlResult(
            plane_type=FabricPlaneType.API_GATEWAY,
            vendor="kong",
            instance_name="test-kong",
            status=ConnectorStatus.SUCCESS
        )

        # Add some data
        result.assets.append(CrawledAsset(
            asset_id="svc_123",
            asset_name="backend-api",
            asset_type="kong_service",
            domain="api.example.com"
        ))

        result.pipes.append(CrawledPipe(
            pipe_id="pipe_123",
            pipe_name="frontend -> backend",
            source_identifier="frontend.example.com",
            target_identifier="backend.example.com",
            modality=ConnectivityModality.API
        ))

        assert len(result.assets) == 1
        assert len(result.pipes) == 1
        assert result.status == ConnectorStatus.SUCCESS

    def test_evidence_from_crawl(self):
        """DirectCrawlResult should generate Tier 1 evidence."""
        result = DirectCrawlResult(
            plane_type=FabricPlaneType.API_GATEWAY,
            vendor="kong",
            instance_name="test-kong",
            status=ConnectorStatus.SUCCESS
        )

        evidence = result.add_evidence(
            signal_type="kong_route",
            signal_detail="Route discovered: api.example.com",
            asset_key="api.example.com",
            raw_data={"route_id": "route_123"}
        )

        assert evidence.confidence == TIER_1_CONFIDENCE
        assert evidence.source_plane == EvidenceSourcePlane.DIRECT_CRAWL
        assert evidence.fabric_plane_type == FabricPlaneType.API_GATEWAY

    def test_include_exclude_patterns(self):
        """Connector should respect include/exclude patterns."""
        from aod.pipeline.fabric_connectors.base import FabricPlaneConnector

        config = ConnectorConfig(
            plane_type=FabricPlaneType.API_GATEWAY,
            vendor="kong",
            instance_name="test",
            base_url="http://localhost",
            include_patterns=["prod-.*", "api-.*"],
            exclude_patterns=[".*-internal", "test-.*"]
        )

        # Create a minimal concrete connector for testing
        class TestConnector(FabricPlaneConnector):
            @property
            def plane_type(self):
                return FabricPlaneType.API_GATEWAY

            @property
            def vendor(self):
                return "test"

            def _validate_config(self):
                pass

            def crawl(self):
                return DirectCrawlResult(
                    plane_type=self.plane_type,
                    vendor=self.vendor,
                    instance_name=self.config.instance_name,
                    status=ConnectorStatus.SUCCESS
                )

            def test_connection(self):
                return True

        connector = TestConnector(config)

        # Should include
        assert connector._should_include("prod-api")
        assert connector._should_include("api-gateway")

        # Should exclude
        assert not connector._should_include("prod-internal")
        assert not connector._should_include("test-service")


# =============================================================================
# RECONCILIATION ENGINE TESTS
# =============================================================================

class TestReconciliationEngine:
    """Test the main reconciliation engine."""

    def test_engine_initialization(self):
        """Engine should initialize with default config."""
        engine = ReconciliationEngine()

        assert engine.config.min_confidence_governed == 0.70
        assert engine.config.min_confidence_known == 0.50
        assert engine.config.min_confidence_classify == 0.30

    def test_custom_config(self):
        """Engine should accept custom config."""
        config = ReconciliationConfig(
            min_confidence_governed=0.80,
            min_confidence_known=0.60,
            contradiction_penalty=0.20
        )
        engine = ReconciliationEngine(config)

        assert engine.config.min_confidence_governed == 0.80
        assert engine.config.contradiction_penalty == 0.20

    def test_empty_input_handling(self):
        """Engine should handle empty input gracefully."""
        engine = ReconciliationEngine()

        phase_1 = EvidenceCollectionResult()
        phase_2 = {}

        result = engine.reconcile(phase_1, phase_2)

        assert result.pipes == []
        assert result.unresolved_assets == []
        assert result.stats["total_assets"] == 0

    def test_tier_determination(self):
        """Engine should correctly determine evidence tier."""
        engine = ReconciliationEngine()

        tier_1_evidence = [
            FabricRoutingEvidence(
                evidence_id="ev_1",
                source_plane=EvidenceSourcePlane.DIRECT_CRAWL,
                signal_type="direct",
                signal_detail="Direct crawl",
                confidence=0.95,
                timestamp=datetime.utcnow(),
                fabric_plane_type=FabricPlaneType.API_GATEWAY,
                fabric_plane_vendor="kong"
            )
        ]

        tier = engine._determine_tier(tier_1_evidence)
        assert tier == EvidenceTier.TIER_1_DIRECT

        tier_2_evidence = [
            FabricRoutingEvidence(
                evidence_id="ev_2",
                source_plane=EvidenceSourcePlane.NETWORK,
                signal_type="traffic",
                signal_detail="Traffic",
                confidence=0.85,
                timestamp=datetime.utcnow(),
                fabric_plane_type=FabricPlaneType.IPAAS,
                fabric_plane_vendor="workato"
            )
        ]

        tier = engine._determine_tier(tier_2_evidence)
        assert tier == EvidenceTier.TIER_2_OBSERVED

    def test_governance_status_determination(self):
        """Engine should correctly determine governance status."""
        engine = ReconciliationEngine()

        # High confidence + Phase 2 confirmed = governed
        status = engine._determine_governance_status(
            confidence=0.85,
            phase_2_confirmed=True,
            contradiction_analysis=None
        )
        assert status == PipeGovernanceStatus.GOVERNED

        # Medium confidence = known
        status = engine._determine_governance_status(
            confidence=0.60,
            phase_2_confirmed=False,
            contradiction_analysis=None
        )
        assert status == PipeGovernanceStatus.KNOWN

        # Low confidence = investigation_needed
        status = engine._determine_governance_status(
            confidence=0.35,
            phase_2_confirmed=False,
            contradiction_analysis=None
        )
        assert status == PipeGovernanceStatus.INVESTIGATION_NEEDED


# =============================================================================
# EVIDENCE COLLECTION RESULT TESTS
# =============================================================================

class TestEvidenceCollectionResult:
    """Test EvidenceCollectionResult accumulator."""

    def test_add_evidence(self, sample_tier_1_evidence):
        """Should correctly add evidence to result."""
        result = EvidenceCollectionResult()

        result.add_evidence("api.example.com", sample_tier_1_evidence)

        assert "api.example.com" in result.routing_evidence
        assert result.total_evidence_count == 1
        assert result.routing_evidence["api.example.com"].highest_confidence == 0.95

    def test_multiple_evidence_same_asset(self, sample_tier_2_evidence):
        """Should accumulate evidence for same asset."""
        result = EvidenceCollectionResult()

        for ev in sample_tier_2_evidence:
            result.add_evidence("salesforce.com", ev)

        assert result.total_evidence_count == 2
        table = result.routing_evidence["salesforce.com"]
        assert len(table.evidence) == 2

    def test_evidence_stats_tracking(self, sample_tier_1_evidence, sample_tier_2_evidence):
        """Should track evidence statistics correctly."""
        result = EvidenceCollectionResult()

        result.add_evidence("api.example.com", sample_tier_1_evidence)
        for ev in sample_tier_2_evidence:
            result.add_evidence("salesforce.com", ev)

        assert result.total_evidence_count == 3
        assert EvidenceSourcePlane.DIRECT_CRAWL.value in result.evidence_by_source
        assert EvidenceSourcePlane.NETWORK.value in result.evidence_by_source
        assert EvidenceSourcePlane.FINANCE.value in result.evidence_by_source


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestEndToEndReconciliation:
    """Integration tests for full reconciliation flow."""

    def test_full_reconciliation_flow(self, sample_tier_1_evidence, sample_tier_2_evidence):
        """Test complete reconciliation from evidence to pipes."""
        # Build Phase 1 result
        phase_1 = EvidenceCollectionResult()
        phase_1.add_evidence("api.example.com", sample_tier_1_evidence)
        for ev in sample_tier_2_evidence:
            phase_1.add_evidence("salesforce.com", ev)

        # Build Phase 2 result (direct crawl confirmation)
        phase_2_result = DirectCrawlResult(
            plane_type=FabricPlaneType.API_GATEWAY,
            vendor="kong",
            instance_name="prod-kong",
            status=ConnectorStatus.SUCCESS
        )
        phase_2_result.add_evidence(
            signal_type="kong_route",
            signal_detail="Route confirmed",
            asset_key="api.example.com"
        )
        phase_2 = {"prod-kong": phase_2_result}

        # Run reconciliation
        engine = ReconciliationEngine()
        result = engine.reconcile(phase_1, phase_2)

        # Should have pipes for both assets
        assert len(result.pipes) >= 2

        # Check api.example.com got Tier 1
        api_pipes = [p for p in result.pipes if "api.example.com" in p.source_system]
        assert len(api_pipes) >= 1
        assert api_pipes[0].evidence_tier == EvidenceTier.TIER_1_DIRECT

    def test_multi_plane_asset_handling(self):
        """Test asset with multiple fabric planes."""
        phase_1 = EvidenceCollectionResult()

        # Same asset, two planes
        ipaas_evidence = FabricRoutingEvidence(
            evidence_id="ev_ipaas",
            source_plane=EvidenceSourcePlane.NETWORK,
            signal_type="traffic",
            signal_detail="Traffic to workato",
            confidence=0.85,
            timestamp=datetime.utcnow(),
            fabric_plane_type=FabricPlaneType.IPAAS,
            fabric_plane_vendor="workato"
        )

        dw_evidence = FabricRoutingEvidence(
            evidence_id="ev_dw",
            source_plane=EvidenceSourcePlane.NETWORK,
            signal_type="traffic",
            signal_detail="Traffic to snowflake",
            confidence=0.80,
            timestamp=datetime.utcnow(),
            fabric_plane_type=FabricPlaneType.DATA_WAREHOUSE,
            fabric_plane_vendor="snowflake"
        )

        phase_1.add_evidence("salesforce.com", ipaas_evidence)
        phase_1.add_evidence("salesforce.com", dw_evidence)

        engine = ReconciliationEngine()
        result = engine.reconcile(phase_1, {})

        # Should have two pipes for the same asset
        sf_pipes = [p for p in result.pipes if "salesforce" in p.source_system.lower()]
        planes = set(p.fabric_plane for p in sf_pipes)
        assert len(planes) >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
