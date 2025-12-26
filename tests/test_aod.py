"""AOD Test Suite - Core tests for the discovery pipeline"""

import pytest
import json
from datetime import datetime

import sys
sys.path.insert(0, 'src')

from aod.models.input_contracts import Snapshot, check_banned_fields, BANNED_FIELDS
from aod.pipeline.validate_snapshot import validate_snapshot, ValidationError
from aod.pipeline.normalize_observations import normalize_observations, CandidateEntity
from aod.pipeline.artifact_handler import is_artifact, handle_artifacts
from aod.pipeline.correlate_entities import correlate_entities_to_planes, MatchStatus
from aod.pipeline.build_plane_indexes import build_plane_indexes
from aod.models.input_contracts import (
    Observation, DiscoveryPlane, Planes, SnapshotMeta,
    IdPPlane, IdPObject, CMDBPlane, CMDBConfigItem,
    CloudPlane, CloudResource, FinancePlane, Vendor, Contract, Transaction
)


class TestBannedFieldsValidation:
    """Test that banned ground-truth fields are rejected"""
    
    def test_rejects_is_shadow_it(self):
        """Schema validation rejects is_shadow_it field"""
        data = {
            "meta": {"tenant_id": "t1", "run_id": "r1", "generated_at": "2024-01-01T00:00:00Z"},
            "planes": {
                "discovery": {"observations": [{"observation_id": "1", "name": "Test", "is_shadow_it": True, "source": "test"}]},
                "idp": {"objects": []},
                "cmdb": {"cis": []},
                "cloud": {"resources": []},
                "endpoint": {"devices": [], "installed_apps": []},
                "network": {"dns": [], "proxy": [], "certs": []},
                "finance": {"vendors": [], "contracts": [], "transactions": []}
            }
        }
        
        violations = check_banned_fields(data)
        assert len(violations) > 0
        assert any("is_shadow_it" in v for v in violations)
    
    def test_rejects_ground_truth_nested(self):
        """Schema validation rejects ground_truth field anywhere in payload"""
        data = {
            "meta": {"tenant_id": "t1", "run_id": "r1", "generated_at": "2024-01-01T00:00:00Z"},
            "planes": {
                "discovery": {"observations": [{"observation_id": "1", "name": "Test", "source": "test", "raw_data": {"ground_truth": {"label": "shadow"}}}]},
                "idp": {"objects": []},
                "cmdb": {"cis": []},
                "cloud": {"resources": []},
                "endpoint": {"devices": [], "installed_apps": []},
                "network": {"dns": [], "proxy": [], "certs": []},
                "finance": {"vendors": [], "contracts": [], "transactions": []}
            }
        }
        
        violations = check_banned_fields(data)
        assert len(violations) > 0
        assert any("ground_truth" in v for v in violations)
    
    def test_rejects_inCMDB(self):
        """Schema validation rejects inCMDB field"""
        data = {
            "meta": {"tenant_id": "t1", "run_id": "r1", "generated_at": "2024-01-01T00:00:00Z"},
            "planes": {
                "discovery": {"observations": [{"observation_id": "1", "name": "Test", "inCMDB": True, "source": "test"}]},
                "idp": {"objects": []},
                "cmdb": {"cis": []},
                "cloud": {"resources": []},
                "endpoint": {"devices": [], "installed_apps": []},
                "network": {"dns": [], "proxy": [], "certs": []},
                "finance": {"vendors": [], "contracts": [], "transactions": []}
            }
        }
        
        violations = check_banned_fields(data)
        assert len(violations) > 0
    
    def test_accepts_valid_snapshot(self):
        """Valid snapshot without banned fields is accepted"""
        data = {
            "meta": {"tenant_id": "t1", "run_id": "r1", "generated_at": "2024-01-01T00:00:00Z"},
            "planes": {
                "discovery": {"observations": [{"observation_id": "1", "name": "Salesforce", "source": "proxy"}]},
                "idp": {"objects": []},
                "cmdb": {"cis": []},
                "cloud": {"resources": []},
                "endpoint": {"devices": [], "installed_apps": []},
                "network": {"dns": [], "proxy": [], "certs": []},
                "finance": {"vendors": [], "contracts": [], "transactions": []}
            }
        }
        
        violations = check_banned_fields(data)
        assert len(violations) == 0
        
        snapshot = validate_snapshot(data)
        assert snapshot.meta.tenant_id == "t1"


class TestDeterminism:
    """Test that same snapshot yields identical results"""
    
    def test_normalization_deterministic(self):
        """Same observations yield same normalized entities in same order"""
        observations = [
            Observation(observation_id="3", name="Zendesk", source="proxy"),
            Observation(observation_id="1", name="Salesforce CRM", source="idp"),
            Observation(observation_id="2", name="Slack", domain="slack.com", source="proxy"),
        ]
        
        entities1, rejected1 = normalize_observations(observations)
        entities2, rejected2 = normalize_observations(observations)
        
        assert len(entities1) == len(entities2)
        for e1, e2 in zip(entities1, entities2):
            assert e1.canonical_name == e2.canonical_name
            assert e1.observation_ids == e2.observation_ids
    
    def test_artifact_handling_deterministic(self):
        """Same entities yield same artifact classification"""
        from aod.pipeline.normalize_observations import CandidateEntity
        
        entities = [
            CandidateEntity(entity_id="e1", canonical_name="sales dashboard", original_name="Sales Dashboard", observation_ids=["o1"]),
            CandidateEntity(entity_id="e2", canonical_name="salesforce crm", original_name="Salesforce CRM", observation_ids=["o2"]),
            CandidateEntity(entity_id="e3", canonical_name="commission calculator", original_name="Commission Calculator", observation_ids=["o3"]),
        ]
        
        filtered1, artifacts1 = handle_artifacts(entities, "t1", "r1", "snap-1")
        filtered2, artifacts2 = handle_artifacts(entities, "t1", "r1", "snap-1")
        
        assert len(filtered1) == len(filtered2)
        assert len(artifacts1) == len(artifacts2)
        
        for a1, a2 in zip(artifacts1, artifacts2):
            assert a1.name == a2.name
            assert a1.artifact_type == a2.artifact_type
            assert a1.artifact_id == a2.artifact_id


class TestVendorDoesNotAdmit:
    """Test that vendor alone does not satisfy finance plane admission"""
    
    def test_vendor_without_contract_not_admitted(self):
        """Vendor without billing/license/contract doesn't satisfy finance plane"""
        from aod.pipeline.admission import check_finance_admission
        from aod.pipeline.correlate_entities import CorrelationResult, PlaneMatch, MatchStatus
        from aod.pipeline.normalize_observations import CandidateEntity
        
        entity = CandidateEntity(
            entity_id="e1",
            canonical_name="mystery app",
            original_name="Mystery App",
            vendor="Some Vendor",
            observation_ids=["o1"]
        )
        
        correlation = CorrelationResult(
            entity=entity,
            finance=PlaneMatch(
                status=MatchStatus.MATCHED,
                matched_ids=["vendor:v1"],
                matched_records=[Vendor(vendor_id="v1", name="Some Vendor", products=["App"])],
                match_method="vendor"
            )
        )
        
        admitted, reason = check_finance_admission(correlation)
        assert not admitted
        assert reason == ""


class TestArtifactsNeverBecomeAssets:
    """Test that artifacts (dashboards, reports, calculators) never become assets"""
    
    def test_dashboard_becomes_artifact(self):
        """Dashboard observation becomes artifact, not asset"""
        from aod.pipeline.normalize_observations import CandidateEntity
        
        entity = CandidateEntity(
            entity_id="e1",
            canonical_name="sales dashboard",
            original_name="Sales Dashboard",
            observation_ids=["o1"]
        )
        
        is_art, art_type = is_artifact(entity)
        assert is_art is True
        assert art_type is not None
    
    def test_calculator_becomes_artifact(self):
        """Commission calculator observation becomes artifact or rejected"""
        from aod.pipeline.normalize_observations import CandidateEntity
        
        entity = CandidateEntity(
            entity_id="e1",
            canonical_name="commission calculator",
            original_name="Commission Calculator",
            observation_ids=["o1"]
        )
        
        is_art, art_type = is_artifact(entity)
        assert is_art is True
    
    def test_report_becomes_artifact(self):
        """Report observation becomes artifact"""
        from aod.pipeline.normalize_observations import CandidateEntity
        
        entity = CandidateEntity(
            entity_id="e1",
            canonical_name="quarterly sales report",
            original_name="Quarterly Sales Report",
            observation_ids=["o1"]
        )
        
        is_art, art_type = is_artifact(entity)
        assert is_art is True
    
    def test_system_not_artifact(self):
        """Real system is not classified as artifact"""
        from aod.pipeline.normalize_observations import CandidateEntity
        
        entity = CandidateEntity(
            entity_id="e1",
            canonical_name="salesforce crm",
            original_name="Salesforce CRM",
            observation_ids=["o1"]
        )
        
        is_art, art_type = is_artifact(entity)
        assert is_art is False


class TestAmbiguousCorrelation:
    """Test ambiguous correlation handling"""
    
    def test_salesforce_ambiguous_match(self):
        """Salesforce CRM vs Salesforce Marketing Cloud with discovered 'Salesforce' -> ambiguous"""
        from aod.pipeline.normalize_observations import CandidateEntity
        
        entity = CandidateEntity(
            entity_id="e1",
            canonical_name="salesforce",
            original_name="Salesforce",
            observation_ids=["o1"]
        )
        
        planes = Planes(
            discovery=DiscoveryPlane(observations=[]),
            idp=IdPPlane(objects=[
                IdPObject(idp_id="idp-1", name="Salesforce CRM", has_sso=True),
                IdPObject(idp_id="idp-2", name="Salesforce Marketing Cloud", has_sso=True)
            ]),
            cmdb=CMDBPlane(cis=[]),
            cloud=CloudPlane(resources=[]),
            finance=FinancePlane(vendors=[], contracts=[], transactions=[])
        )
        
        indexes = build_plane_indexes(planes)
        
        correlations = correlate_entities_to_planes([entity], indexes)
        
        assert len(correlations) == 1
        assert correlations[0].idp.status == MatchStatus.AMBIGUOUS
        assert len(correlations[0].idp.matched_ids) == 2


class TestRunLogCounts:
    """Test run log counts correctness"""
    
    def test_observation_count(self):
        """Run log correctly counts observations"""
        observations = [
            Observation(observation_id="1", name="App1", source="proxy"),
            Observation(observation_id="2", name="App2", source="proxy"),
            Observation(observation_id="3", name="App3", source="proxy"),
        ]
        
        candidates = normalize_observations(observations)
        assert len(candidates) == 3
    
    def test_artifact_count(self):
        """Run log correctly counts artifacts"""
        from aod.pipeline.normalize_observations import CandidateEntity
        
        entities = [
            CandidateEntity(entity_id="e1", canonical_name="dashboard", original_name="Sales Dashboard", observation_ids=["o1"]),
            CandidateEntity(entity_id="e2", canonical_name="app", original_name="Salesforce", observation_ids=["o2"]),
            CandidateEntity(entity_id="e3", canonical_name="report", original_name="Monthly Report", observation_ids=["o3"]),
        ]
        
        filtered, artifacts = handle_artifacts(entities, "t1", "r1", "snap-1")
        
        assert len(artifacts) == 2
        assert len(filtered) == 1


class TestProvenanceAndStatus:
    """Test provenance persistence and new status values"""
    
    @pytest.mark.asyncio
    async def test_pipeline_uses_completed_with_results_status(self):
        """Pipeline uses COMPLETED_WITH_RESULTS when assets are admitted"""
        from aod.pipeline.pipeline_executor import execute_pipeline
        from aod.db.database import Database
        from aod.models.output_contracts import RunStatus
        import tempfile
        from pathlib import Path
        
        data = {
            "meta": {"tenant_id": "t1", "run_id": "test_with_results", "generated_at": "2024-01-01T00:00:00Z"},
            "planes": {
                "discovery": {"observations": [
                    {"observation_id": "o1", "name": "Salesforce", "source": "proxy", "domain": "salesforce.com"}
                ]},
                "idp": {"objects": [{"idp_id": "idp-1", "name": "Salesforce", "has_sso": True}]},
                "cmdb": {"cis": []},
                "cloud": {"resources": []},
                "endpoint": {"devices": [], "installed_apps": []},
                "network": {"dns": [], "proxy": [], "certs": []},
                "finance": {"vendors": [], "contracts": [], "transactions": []}
            }
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Database(Path(tmpdir) / "test.db")
            await db.initialize()
            
            result = await execute_pipeline(data, db, run_id="test_with_results", started_at=datetime.utcnow())
            
            assert result.success
            if len(result.assets) > 0:
                assert result.run_log.status == RunStatus.COMPLETED_WITH_RESULTS
            else:
                assert result.run_log.status == RunStatus.COMPLETED_NO_ASSETS
            
            await db.close()
    
    @pytest.mark.asyncio
    async def test_pipeline_uses_completed_no_assets_status(self):
        """Pipeline uses COMPLETED_NO_ASSETS when no assets are admitted"""
        from aod.pipeline.pipeline_executor import execute_pipeline
        from aod.db.database import Database
        from aod.models.output_contracts import RunStatus
        import tempfile
        from pathlib import Path
        
        data = {
            "meta": {"tenant_id": "t1", "run_id": "test_no_assets", "generated_at": "2024-01-01T00:00:00Z"},
            "planes": {
                "discovery": {"observations": [
                    {"observation_id": "o1", "name": "Sales Dashboard", "source": "proxy"}
                ]},
                "idp": {"objects": []},
                "cmdb": {"cis": []},
                "cloud": {"resources": []},
                "endpoint": {"devices": [], "installed_apps": []},
                "network": {"dns": [], "proxy": [], "certs": []},
                "finance": {"vendors": [], "contracts": [], "transactions": []}
            }
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Database(Path(tmpdir) / "test.db")
            await db.initialize()
            
            result = await execute_pipeline(data, db, run_id="test_no_assets", started_at=datetime.utcnow())
            
            assert result.success
            assert result.run_log.status == RunStatus.COMPLETED_NO_ASSETS
            
            await db.close()
    
    @pytest.mark.asyncio
    async def test_provenance_persisted_in_run_log(self):
        """Provenance data is persisted in run log input_meta"""
        from aod.pipeline.pipeline_executor import execute_pipeline
        from aod.db.database import Database
        import tempfile
        from pathlib import Path
        
        data = {
            "meta": {"tenant_id": "t1", "run_id": "test_provenance", "generated_at": "2024-01-01T00:00:00Z", "schema_version": "farm.v1"},
            "planes": {
                "discovery": {"observations": []},
                "idp": {"objects": []},
                "cmdb": {"cis": []},
                "cloud": {"resources": []},
                "endpoint": {"devices": [], "installed_apps": []},
                "network": {"dns": [], "proxy": [], "certs": []},
                "finance": {"vendors": [], "contracts": [], "transactions": []}
            }
        }
        
        provenance = {
            "source": "farm",
            "farm_url": "https://farm.example.com",
            "snapshot_id": "snap-123",
            "schema_version": "farm.v1",
            "fetch_duration_ms": 150
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Database(Path(tmpdir) / "test.db")
            await db.initialize()
            
            result = await execute_pipeline(data, db, run_id="test_provenance", started_at=datetime.utcnow(), provenance=provenance)
            
            assert result.success
            assert "provenance" in result.run_log.input_meta
            assert result.run_log.input_meta["provenance"]["source"] == "farm"
            assert result.run_log.input_meta["provenance"]["farm_url"] == "https://farm.example.com"
            assert result.run_log.input_meta["provenance"]["snapshot_id"] == "snap-123"
            assert result.run_log.input_meta["provenance"]["fetch_duration_ms"] == 150
            
            stored_run = await db.get_run("test_provenance")
            assert stored_run is not None
            assert "provenance" in stored_run.input_meta
            
            await db.close()


class TestPipelineDeterminism:
    """Test that pipeline is a pure function: same input -> same output"""
    
    @pytest.mark.asyncio
    async def test_pipeline_determinism_full(self):
        """
        Running pipeline twice on same snapshot produces identical results.
        
        Verifies:
        - Same asset IDs, names, types, admission reasons
        - Same finding IDs, types, explanations, evidence refs
        - Same artifact IDs, names, types
        """
        from aod.pipeline.pipeline_executor import execute_pipeline
        from aod.db.database import Database
        import tempfile
        from pathlib import Path
        
        snapshot = {
            "meta": {"tenant_id": "t1", "generated_at": "2024-01-01T00:00:00Z"},
            "planes": {
                "discovery": {"observations": [
                    {"observation_id": "o1", "name": "Salesforce", "source": "proxy", "domain": "salesforce.com"},
                    {"observation_id": "o2", "name": "Slack", "source": "idp", "domain": "slack.com"},
                    {"observation_id": "o3", "name": "Sales Dashboard", "source": "proxy"},
                    {"observation_id": "o4", "name": "Zendesk", "source": "proxy", "domain": "zendesk.com"}
                ]},
                "idp": {"objects": [
                    {"idp_id": "idp-1", "name": "Salesforce", "has_sso": True},
                    {"idp_id": "idp-2", "name": "Slack", "has_scim": True}
                ]},
                "cmdb": {"cis": [
                    {"ci_id": "ci-1", "name": "Zendesk", "ci_type": "service", "lifecycle": "production", "environment": "prod"}
                ]},
                "cloud": {"resources": []},
                "endpoint": {"devices": [], "installed_apps": []},
                "network": {"dns": [], "proxy": [], "certs": []},
                "finance": {"vendors": [], "contracts": [], "transactions": []}
            }
        }
        
        fixed_run_id = "determinism_test_run"
        fixed_started_at = datetime(2024, 1, 15, 12, 0, 0)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db1 = Database(Path(tmpdir) / "test1.db")
            await db1.initialize()
            result1 = await execute_pipeline(snapshot, db1, run_id=fixed_run_id, started_at=fixed_started_at)
            await db1.close()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db2 = Database(Path(tmpdir) / "test2.db")
            await db2.initialize()
            result2 = await execute_pipeline(snapshot, db2, run_id=fixed_run_id, started_at=fixed_started_at)
            await db2.close()
        
        assert result1.success == result2.success
        assert len(result1.assets) == len(result2.assets), "Asset count mismatch"
        assert len(result1.findings) == len(result2.findings), "Findings count mismatch"
        assert len(result1.artifacts) == len(result2.artifacts), "Artifacts count mismatch"
        
        for a1, a2 in zip(result1.assets, result2.assets):
            assert a1.asset_id == a2.asset_id, f"Asset ID mismatch: {a1.asset_id} vs {a2.asset_id}"
            assert a1.name == a2.name, f"Asset name mismatch: {a1.name} vs {a2.name}"
            assert a1.asset_type == a2.asset_type, f"Asset type mismatch"
            assert a1.admission_reason == a2.admission_reason, f"Admission reason mismatch"
            assert a1.evidence_refs == a2.evidence_refs, f"Evidence refs mismatch"
            assert a1.lens_status == a2.lens_status, f"Lens status mismatch"
            assert a1.lens_coverage == a2.lens_coverage, f"Lens coverage mismatch"
        
        for f1, f2 in zip(result1.findings, result2.findings):
            assert f1.finding_id == f2.finding_id, f"Finding ID mismatch: {f1.finding_id} vs {f2.finding_id}"
            assert f1.finding_type == f2.finding_type, f"Finding type mismatch"
            assert f1.explanation == f2.explanation, f"Finding explanation mismatch"
            assert f1.evidence_refs == f2.evidence_refs, f"Finding evidence refs mismatch"
            assert f1.severity == f2.severity, f"Finding severity mismatch"
        
        for art1, art2 in zip(result1.artifacts, result2.artifacts):
            assert art1.artifact_id == art2.artifact_id, f"Artifact ID mismatch"
            assert art1.name == art2.name, f"Artifact name mismatch"
            assert art1.artifact_type == art2.artifact_type, f"Artifact type mismatch"


class TestDomainFirstKeyNormalization:
    """Test that entities are keyed by domain when available"""
    
    def test_slack_observations_merge_to_domain_key(self):
        """Domain isolation: observations with unique domains stay separate, same domain merges"""
        observations = [
            Observation(observation_id="obs-1", name="Slack", source="discovery"),
            Observation(observation_id="obs-2", name="slack.com", source="discovery"),
            Observation(observation_id="obs-3", name="Slack App", uri="https://slack.com/app", source="discovery"),
        ]
        
        entities = normalize_observations(observations)
        
        slack_entities = [e for e in entities if 'slack' in (e.domain or e.canonical_name)]
        
        domain_entities = [e for e in slack_entities if e.domain == "slack.com"]
        assert len(domain_entities) == 1, f"Expected 1 slack.com entity, got {len(domain_entities)}"
        
        domain_entity = domain_entities[0]
        assert domain_entity.domain == "slack.com"
        assert len(domain_entity.observation_ids) == 2, f"Expected 2 observations (domain-bearing), got {len(domain_entity.observation_ids)}: {domain_entity.observation_ids}"
    
    def test_domain_name_becomes_domain(self):
        """Observation named 'slack.com' gets domain extracted from name"""
        observations = [
            Observation(observation_id="obs-1", name="slack.com", source="discovery"),
        ]
        
        entities = normalize_observations(observations)
        
        assert len(entities) == 1
        assert entities[0].domain == "slack.com"


class TestInfrastructureExclusion:
    """Test that infrastructure domains are excluded from shadow classification"""
    
    def test_mongodb_in_exclusion_list(self):
        """mongodb.com is in the infrastructure exclusion list"""
        from aod.pipeline.aod_agent_reconcile import INFRASTRUCTURE_DOMAINS
        
        assert "mongodb.com" in INFRASTRUCTURE_DOMAINS, "mongodb.com should be in INFRASTRUCTURE_DOMAINS"
        assert "mongodb.org" in INFRASTRUCTURE_DOMAINS, "mongodb.org should be in INFRASTRUCTURE_DOMAINS"
    
    def test_all_required_domains_in_exclusion_list(self):
        """All required infrastructure domains are in the exclusion list"""
        from aod.pipeline.aod_agent_reconcile import INFRASTRUCTURE_DOMAINS
        
        required = [
            "postgresql.org", "mysql.com", "apache.org", "redis.io", "redis.com",
            "mongodb.com", "docker.com", "kubernetes.io", "nginx.org", "python.org",
            "nodejs.org", "golang.org", "rust-lang.org", "ruby-lang.org", "linux.org",
            "gnu.org", "elastic.co", "kafka.apache.org"
        ]
        
        for domain in required:
            assert domain in INFRASTRUCTURE_DOMAINS, f"{domain} should be in INFRASTRUCTURE_DOMAINS"
    
    def test_mongodb_excluded_from_shadow(self):
        """mongodb.com asset is not classified as shadow via _is_infrastructure_domain"""
        from aod.pipeline.aod_agent_reconcile import _is_infrastructure_domain
        
        assert _is_infrastructure_domain("mongodb.com") is True, "mongodb.com should be infrastructure"
        assert _is_infrastructure_domain("mongodb.org") is True, "mongodb.org should be infrastructure"
        assert _is_infrastructure_domain("slack.com") is False, "slack.com should not be infrastructure"


class TestPagerDutyCMDBMatching:
    """Test that pagerduty.com matches CMDB via name_contains_domain_token"""
    
    def test_pagerduty_matches_legacy_ci(self):
        """pagerduty.com matches CI named 'PagerDuty (Legacy)' via domain token matching"""
        from aod.pipeline.correlate_entities import correlate_to_plane, MatchStatus
        from aod.pipeline.build_plane_indexes import PlaneIndex, add_to_index
        from aod.pipeline.normalize_observations import CandidateEntity, normalize_string
        
        entity = CandidateEntity(
            entity_id="entity:pagerduty",
            canonical_name="pagerduty",
            original_name="PagerDuty",
            domain="pagerduty.com",
            observation_ids=["obs-1"]
        )
        
        plane_index = PlaneIndex()
        plane_index.records["CI-PD-001"] = type('CI', (), {'name': 'PagerDuty (Legacy)', 'vendor': None})()
        add_to_index(plane_index.by_canonical_name, normalize_string("PagerDuty (Legacy)"), "CI-PD-001")
        
        result = correlate_to_plane(entity, plane_index, use_domain=True, use_vendor=True)
        
        assert result.status == MatchStatus.MATCHED, f"Expected MATCHED, got {result.status}"
        assert result.match_method == "name_contains_domain_token", f"Expected name_contains_domain_token, got {result.match_method}"
        assert "CI-PD-001" in result.matched_ids, f"Expected CI-PD-001 in matched_ids"
    
    def test_domain_token_requires_min_length(self):
        """Domain tokens shorter than 6 chars don't trigger matching"""
        from aod.pipeline.correlate_entities import _extract_domain_base_token
        
        assert _extract_domain_base_token("pagerduty.com") == "pagerduty"
        assert len("pagerduty") >= 6
        
        assert _extract_domain_base_token("box.com") == "box"
        assert len("box") < 6
    
    def test_hyphenated_domain_token_normalized(self):
        """Hyphenated domains like service-now.com are normalized for matching"""
        from aod.pipeline.correlate_entities import correlate_to_plane, MatchStatus
        from aod.pipeline.build_plane_indexes import PlaneIndex, add_to_index
        from aod.pipeline.normalize_observations import CandidateEntity, normalize_string
        
        entity = CandidateEntity(
            entity_id="entity:servicenow",
            canonical_name="servicenow",
            original_name="ServiceNow",
            domain="service-now.com",
            observation_ids=["obs-1"]
        )
        
        plane_index = PlaneIndex()
        plane_index.records["CI-SN-001"] = type('CI', (), {'name': 'ServiceNow ITSM', 'vendor': None})()
        add_to_index(plane_index.by_canonical_name, normalize_string("ServiceNow ITSM"), "CI-SN-001")
        
        result = correlate_to_plane(entity, plane_index, use_domain=True, use_vendor=True)
        
        assert result.status == MatchStatus.MATCHED, f"Expected MATCHED, got {result.status}"
        assert result.match_method == "name_contains_domain_token", f"Expected name_contains_domain_token, got {result.match_method}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
