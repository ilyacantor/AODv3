"""Tests for Farm snapshot normalization"""

import json
import pytest
from pathlib import Path

from src.aod.pipeline.normalize_snapshot import (
    normalize_farm_snapshot,
    NormalizationError,
    _normalize_observation,
    _normalize_idp_object,
    _normalize_cmdb_ci,
    _normalize_cloud_resource,
    _normalize_transaction,
)
from src.aod.pipeline.validate_snapshot import validate_snapshot
from src.aod.models.input_contracts import Snapshot


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    """Load a JSON fixture file."""
    with open(FIXTURES_DIR / name, "r") as f:
        return json.load(f)


class TestCanonicalSnapshot:
    """Test that canonical format snapshots validate directly."""
    
    def test_canonical_snapshot_validates_without_normalization(self):
        """Canonical format should pass validation without normalization."""
        data = load_fixture("snapshot_canonical.json")
        snapshot = validate_snapshot(data, normalize=False)
        
        assert isinstance(snapshot, Snapshot)
        assert snapshot.meta.tenant_id == "test-tenant"
        assert snapshot.meta.run_id == "test-run-001"
        assert snapshot.meta.schema_version == "farm.v1"
        assert len(snapshot.planes.discovery.observations) == 2
    
    def test_canonical_snapshot_normalizes_to_same(self):
        """Canonical format should remain valid after normalization."""
        data = load_fixture("snapshot_canonical.json")
        normalized = normalize_farm_snapshot(data)
        snapshot = validate_snapshot(normalized, normalize=False)
        
        assert isinstance(snapshot, Snapshot)
        assert snapshot.meta.tenant_id == "test-tenant"
        assert len(snapshot.planes.discovery.observations) == 2


class TestFarmFormatSnapshot:
    """Test that Farm format snapshots normalize correctly."""
    
    def test_farm_format_requires_normalization(self):
        """Farm format should fail validation without normalization."""
        data = load_fixture("snapshot_farm_format.json")
        with pytest.raises(Exception):
            validate_snapshot(data, normalize=False)
    
    def test_farm_format_normalizes_successfully(self):
        """Farm format should normalize and validate successfully."""
        data = load_fixture("snapshot_farm_format.json")
        normalized = normalize_farm_snapshot(
            data,
            fallback_tenant_id="GlobalBank",
            snapshot_id="test-snapshot-001"
        )
        
        assert normalized["meta"]["tenant_id"] == "GlobalBank"
        assert normalized["meta"]["schema_version"] == "farm.v1"
        assert "run_id" in normalized["meta"]
        assert "generated_at" in normalized["meta"]
        
        observations = normalized["planes"]["discovery"]["observations"]
        assert len(observations) == 3
        
        obs_1 = observations[0]
        assert obs_1["observation_id"] == "9a267267-ca25-4eec-8152-506286489d9a"
        assert obs_1["name"] == "Workday HCM"
        assert obs_1["domain"] == "workday.com"
    
    def test_farm_format_validates_after_normalization(self):
        """Farm format should produce valid Snapshot after normalization."""
        data = load_fixture("snapshot_farm_format.json")
        snapshot = validate_snapshot(
            data,
            normalize=True,
            fallback_tenant_id="GlobalBank",
            snapshot_id="test-snapshot-001"
        )
        
        assert isinstance(snapshot, Snapshot)
        assert snapshot.meta.tenant_id == "GlobalBank"
        assert len(snapshot.planes.discovery.observations) == 3
        assert len(snapshot.planes.idp.objects) == 2
        assert len(snapshot.planes.cmdb.cis) == 1
        assert len(snapshot.planes.cloud.resources) == 1
        assert len(snapshot.planes.finance.transactions) == 1


class TestObservationNormalization:
    """Test individual observation normalization."""
    
    def test_normalize_observation_with_id_alias(self):
        """Should map 'id' to 'observation_id'."""
        raw = {"id": "obs-123", "name": "Test App"}
        normalized = _normalize_observation(raw)
        assert normalized["observation_id"] == "obs-123"
        assert normalized["name"] == "Test App"
    
    def test_normalize_observation_with_observationId_alias(self):
        """Should map 'observationId' to 'observation_id'."""
        raw = {"observationId": "obs-456", "observedName": "Another App"}
        normalized = _normalize_observation(raw)
        assert normalized["observation_id"] == "obs-456"
        assert normalized["name"] == "Another App"
    
    def test_normalize_observation_with_domain_aliases(self):
        """Should map fqdn/host to domain."""
        raw = {"id": "obs-1", "name": "App", "fqdn": "example.com"}
        normalized = _normalize_observation(raw)
        assert normalized["domain"] == "example.com"
    
    def test_normalize_observation_preserves_unknown_fields_in_raw_data(self):
        """Unknown fields should be preserved in raw_data."""
        raw = {
            "id": "obs-1",
            "name": "App",
            "custom_field": "custom_value",
            "another_unknown": 123
        }
        normalized = _normalize_observation(raw)
        assert "raw_data" in normalized
        assert normalized["raw_data"]["custom_field"] == "custom_value"
        assert normalized["raw_data"]["another_unknown"] == 123
    
    def test_normalize_observation_fails_without_id(self):
        """Should fail if no identifier present."""
        raw = {"name": "App without ID"}
        with pytest.raises(NormalizationError) as exc_info:
            _normalize_observation(raw)
        assert "observation_id" in str(exc_info.value.missing_fields)
    
    def test_normalize_observation_with_bytes_transferred(self):
        """Should map bytesTransferred to bytes_transferred."""
        raw = {"id": "obs-1", "name": "App", "bytesTransferred": 12345}
        normalized = _normalize_observation(raw)
        assert normalized["bytes_transferred"] == 12345
    
    def test_normalize_observation_with_observed_at(self):
        """Should map observedAt to observed_at."""
        raw = {"id": "obs-1", "name": "App", "observedAt": "2024-01-15T10:00:00Z"}
        normalized = _normalize_observation(raw)
        assert normalized["observed_at"] == "2024-01-15T10:00:00Z"


class TestIdPNormalization:
    """Test IdP object normalization."""
    
    def test_normalize_idp_with_idpId(self):
        """Should map 'idpId' to 'idp_id'."""
        raw = {"idpId": "app-001", "displayName": "Test SSO App"}
        normalized = _normalize_idp_object(raw)
        assert normalized["idp_id"] == "app-001"
        assert normalized["name"] == "Test SSO App"
    
    def test_normalize_idp_with_sso_aliases(self):
        """Should map ssoEnabled/hasSso to has_sso."""
        raw = {"id": "app-1", "name": "App", "ssoEnabled": True}
        normalized = _normalize_idp_object(raw)
        assert normalized["has_sso"] is True


class TestCMDBNormalization:
    """Test CMDB CI normalization."""
    
    def test_normalize_cmdb_with_sys_id(self):
        """Should map 'sys_id' to 'ci_id'."""
        raw = {"sys_id": "cmdb-001", "displayName": "My App"}
        normalized = _normalize_cmdb_ci(raw)
        assert normalized["ci_id"] == "cmdb-001"
        assert normalized["name"] == "My App"
    
    def test_normalize_cmdb_with_lifecycle_aliases(self):
        """Should map lifecycleStatus to lifecycle."""
        raw = {"id": "ci-1", "name": "App", "lifecycleStatus": "retired"}
        normalized = _normalize_cmdb_ci(raw)
        assert normalized["lifecycle"] == "retired"


class TestCloudResourceNormalization:
    """Test cloud resource normalization."""
    
    def test_normalize_cloud_with_arn(self):
        """Should map 'arn' to 'resource_id'."""
        raw = {
            "arn": "arn:aws:s3:::bucket",
            "resourceName": "My Bucket",
            "type": "s3_bucket"
        }
        normalized = _normalize_cloud_resource(raw)
        assert normalized["resource_id"] == "arn:aws:s3:::bucket"
        assert normalized["name"] == "My Bucket"
        assert normalized["resource_type"] == "s3_bucket"


class TestTransactionNormalization:
    """Test financial transaction normalization."""
    
    def test_normalize_transaction_with_txn_id(self):
        """Should map 'txn_id' to 'transaction_id'."""
        raw = {
            "txn_id": "tx-001",
            "vendor": "Acme Corp",
            "total": 1000.50,
            "recurring": True
        }
        normalized = _normalize_transaction(raw)
        assert normalized["transaction_id"] == "tx-001"
        assert normalized["vendor_name"] == "Acme Corp"
        assert normalized["amount"] == 1000.50
        assert normalized["is_recurring"] is True


class TestNormalizationErrors:
    """Test error handling in normalization."""
    
    def test_missing_tenant_id_fails(self):
        """Should fail if tenant_id cannot be derived."""
        raw = {
            "meta": {"schemaVersion": "farm.v1"},
            "planes": {"discovery": {"observations": []}}
        }
        with pytest.raises(NormalizationError) as exc_info:
            normalize_farm_snapshot(raw)
        assert "tenant_id" in str(exc_info.value)
    
    def test_missing_schema_version_fails(self):
        """Should fail if schema_version is missing."""
        raw = {
            "meta": {"tenantId": "test"},
            "planes": {"discovery": {"observations": []}}
        }
        with pytest.raises(NormalizationError) as exc_info:
            normalize_farm_snapshot(raw)
        assert "schema_version" in str(exc_info.value)
    
    def test_non_dict_input_fails(self):
        """Should fail if input is not a dict."""
        with pytest.raises(NormalizationError) as exc_info:
            normalize_farm_snapshot([])  # type: ignore
        assert "Expected dict" in str(exc_info.value)


class TestRunIdGeneration:
    """Test run_id generation when missing."""
    
    def test_run_id_generated_from_snapshot_id(self):
        """Should generate run_id from snapshot_id if missing."""
        raw = {
            "meta": {
                "tenantId": "test",
                "schemaVersion": "farm.v1",
                "createdAt": "2024-01-01T00:00:00Z"
            },
            "planes": {"discovery": {"observations": []}}
        }
        normalized = normalize_farm_snapshot(raw, snapshot_id="snap-123")
        assert normalized["meta"]["run_id"] == "farm_snap-123"
    
    def test_run_id_preserved_if_present(self):
        """Should preserve existing run_id."""
        raw = {
            "meta": {
                "tenantId": "test",
                "run_id": "existing-run-001",
                "schemaVersion": "farm.v1",
                "createdAt": "2024-01-01T00:00:00Z"
            },
            "planes": {"discovery": {"observations": []}}
        }
        normalized = normalize_farm_snapshot(raw)
        assert normalized["meta"]["run_id"] == "existing-run-001"
