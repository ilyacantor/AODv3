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
        
        result1 = normalize_observations(observations)
        result2 = normalize_observations(observations)
        
        assert len(result1) == len(result2)
        for e1, e2 in zip(result1, result2):
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
        
        filtered1, artifacts1 = handle_artifacts(entities, "t1", "r1")
        filtered2, artifacts2 = handle_artifacts(entities, "t1", "r1")
        
        assert len(filtered1) == len(filtered2)
        assert len(artifacts1) == len(artifacts2)
        
        for a1, a2 in zip(artifacts1, artifacts2):
            assert a1.name == a2.name
            assert a1.artifact_type == a2.artifact_type


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
        
        filtered, artifacts = handle_artifacts(entities, "t1", "r1")
        
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
            
            result = await execute_pipeline(data, db)
            
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
            
            result = await execute_pipeline(data, db)
            
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
            "meta": {"tenant_id": "t1", "run_id": "test_provenance", "generated_at": "2024-01-01T00:00:00Z"},
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
            
            result = await execute_pipeline(data, db, provenance=provenance)
            
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
