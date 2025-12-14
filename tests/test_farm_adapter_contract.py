"""
Contract tests for Farm Adapter.

These tests verify that:
1. Real Farm snapshots normalize successfully
2. Normalized output validates against canonical Snapshot schema
3. All planes are present (even if empty)
4. Required fields are present on all record types
5. No banned adjudication fields exist
"""

import json
import pytest
from pathlib import Path

from src.aod.pipeline.farm_adapter import normalize_farm_snapshot, NormalizationError
from src.aod.models.input_contracts import Snapshot, check_banned_fields


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    """Load a JSON fixture file."""
    with open(FIXTURES_DIR / name, "r") as f:
        return json.load(f)


class TestFarmAdapterContract:
    """Contract tests using real Farm snapshot."""
    
    @pytest.fixture
    def raw_farm_snapshot(self) -> dict:
        """Load real Farm snapshot fixture."""
        return load_fixture("real_farm_snapshot.json")
    
    @pytest.fixture
    def normalized_snapshot(self, raw_farm_snapshot) -> dict:
        """Normalize the raw Farm snapshot."""
        return normalize_farm_snapshot(
            raw_farm_snapshot,
            fallback_tenant_id=raw_farm_snapshot.get("meta", {}).get("tenant_id"),
            snapshot_id=raw_farm_snapshot.get("meta", {}).get("snapshot_id")
        )
    
    def test_normalization_succeeds(self, raw_farm_snapshot):
        """Normalization should complete without error."""
        normalized = normalize_farm_snapshot(raw_farm_snapshot)
        assert isinstance(normalized, dict)
        assert "meta" in normalized
        assert "planes" in normalized
    
    def test_pydantic_validation_passes(self, normalized_snapshot):
        """Normalized snapshot should pass Pydantic validation."""
        snapshot = Snapshot.model_validate(normalized_snapshot)
        assert isinstance(snapshot, Snapshot)
    
    def test_all_planes_present(self, normalized_snapshot):
        """All planes must be present (even if empty lists)."""
        planes = normalized_snapshot["planes"]
        
        assert "discovery" in planes
        assert "observations" in planes["discovery"]
        
        assert "idp" in planes
        assert "objects" in planes["idp"]
        
        assert "cmdb" in planes
        assert "cis" in planes["cmdb"]
        
        assert "cloud" in planes
        assert "resources" in planes["cloud"]
        
        assert "endpoint" in planes
        assert "devices" in planes["endpoint"]
        assert "installed_apps" in planes["endpoint"]
        
        assert "network" in planes
        assert "dns" in planes["network"]
        assert "proxy" in planes["network"]
        assert "certs" in planes["network"]
        
        assert "finance" in planes
        assert "vendors" in planes["finance"]
        assert "contracts" in planes["finance"]
        assert "transactions" in planes["finance"]
    
    def test_meta_has_required_fields(self, normalized_snapshot):
        """Meta must have all required fields."""
        meta = normalized_snapshot["meta"]
        assert "tenant_id" in meta and meta["tenant_id"]
        assert "run_id" in meta and meta["run_id"]
        assert "generated_at" in meta and meta["generated_at"]
        assert "schema_version" in meta and meta["schema_version"]
    
    def test_observations_have_required_fields(self, normalized_snapshot):
        """Each observation must have observation_id and name."""
        observations = normalized_snapshot["planes"]["discovery"]["observations"]
        assert len(observations) > 0, "Expected at least 1 observation in fixture"
        
        for i, obs in enumerate(observations):
            assert "observation_id" in obs, f"Observation[{i}] missing observation_id"
            assert obs["observation_id"], f"Observation[{i}] has empty observation_id"
            assert "name" in obs, f"Observation[{i}] missing name"
            assert obs["name"], f"Observation[{i}] has empty name"
    
    def test_idp_objects_have_required_fields(self, normalized_snapshot):
        """Each IdP object must have idp_id and name."""
        objects = normalized_snapshot["planes"]["idp"]["objects"]
        assert len(objects) > 0, "Expected at least 1 IdP object in fixture"
        
        for i, obj in enumerate(objects):
            assert "idp_id" in obj, f"IdPObject[{i}] missing idp_id"
            assert obj["idp_id"], f"IdPObject[{i}] has empty idp_id"
            assert "name" in obj, f"IdPObject[{i}] missing name"
            assert obj["name"], f"IdPObject[{i}] has empty name"
    
    def test_cmdb_cis_have_required_fields(self, normalized_snapshot):
        """Each CMDB CI must have ci_id and name."""
        cis = normalized_snapshot["planes"]["cmdb"]["cis"]
        assert len(cis) > 0, "Expected at least 1 CMDB CI in fixture"
        
        for i, ci in enumerate(cis):
            assert "ci_id" in ci, f"CMDBConfigItem[{i}] missing ci_id"
            assert ci["ci_id"], f"CMDBConfigItem[{i}] has empty ci_id"
            assert "name" in ci, f"CMDBConfigItem[{i}] missing name"
            assert ci["name"], f"CMDBConfigItem[{i}] has empty name"
    
    def test_cloud_resources_have_required_fields(self, normalized_snapshot):
        """Each cloud resource must have resource_id, name, resource_type."""
        resources = normalized_snapshot["planes"]["cloud"]["resources"]
        assert len(resources) > 0, "Expected at least 1 cloud resource in fixture"
        
        for i, res in enumerate(resources):
            assert "resource_id" in res, f"CloudResource[{i}] missing resource_id"
            assert res["resource_id"], f"CloudResource[{i}] has empty resource_id"
            assert "name" in res, f"CloudResource[{i}] missing name"
            assert res["name"], f"CloudResource[{i}] has empty name"
            assert "resource_type" in res, f"CloudResource[{i}] missing resource_type"
            assert res["resource_type"], f"CloudResource[{i}] has empty resource_type"
    
    def test_devices_have_required_fields(self, normalized_snapshot):
        """Each device must have device_id and hostname."""
        devices = normalized_snapshot["planes"]["endpoint"]["devices"]
        assert len(devices) > 0, "Expected at least 1 device in fixture"
        
        for i, dev in enumerate(devices):
            assert "device_id" in dev, f"EndpointDevice[{i}] missing device_id"
            assert dev["device_id"], f"EndpointDevice[{i}] has empty device_id"
            assert "hostname" in dev, f"EndpointDevice[{i}] missing hostname"
            assert dev["hostname"], f"EndpointDevice[{i}] has empty hostname"
    
    def test_installed_apps_have_required_fields(self, normalized_snapshot):
        """Each installed app must have app_id, name, device_id."""
        apps = normalized_snapshot["planes"]["endpoint"]["installed_apps"]
        assert len(apps) > 0, "Expected at least 1 installed app in fixture"
        
        for i, app in enumerate(apps):
            assert "app_id" in app, f"InstalledApp[{i}] missing app_id"
            assert app["app_id"], f"InstalledApp[{i}] has empty app_id"
            assert "name" in app, f"InstalledApp[{i}] missing name"
            assert app["name"], f"InstalledApp[{i}] has empty name"
            assert "device_id" in app, f"InstalledApp[{i}] missing device_id"
            assert app["device_id"], f"InstalledApp[{i}] has empty device_id"
    
    def test_dns_records_have_required_fields(self, normalized_snapshot):
        """Each DNS record must have record_id and domain."""
        dns = normalized_snapshot["planes"]["network"]["dns"]
        assert len(dns) > 0, "Expected at least 1 DNS record in fixture"
        
        for i, rec in enumerate(dns):
            assert "record_id" in rec, f"DNSRecord[{i}] missing record_id"
            assert rec["record_id"], f"DNSRecord[{i}] has empty record_id"
            assert "domain" in rec, f"DNSRecord[{i}] missing domain"
            assert rec["domain"], f"DNSRecord[{i}] has empty domain"
    
    def test_proxy_logs_have_required_fields(self, normalized_snapshot):
        """Each proxy log must have log_id and domain."""
        proxy = normalized_snapshot["planes"]["network"]["proxy"]
        assert len(proxy) > 0, "Expected at least 1 proxy log in fixture"
        
        for i, log in enumerate(proxy):
            assert "log_id" in log, f"ProxyLog[{i}] missing log_id"
            assert log["log_id"], f"ProxyLog[{i}] has empty log_id"
            assert "domain" in log, f"ProxyLog[{i}] missing domain"
            assert log["domain"], f"ProxyLog[{i}] has empty domain"
    
    def test_certificates_have_required_fields(self, normalized_snapshot):
        """Each certificate must have cert_id and domain."""
        certs = normalized_snapshot["planes"]["network"]["certs"]
        assert len(certs) > 0, "Expected at least 1 certificate in fixture"
        
        for i, cert in enumerate(certs):
            assert "cert_id" in cert, f"Certificate[{i}] missing cert_id"
            assert cert["cert_id"], f"Certificate[{i}] has empty cert_id"
            assert "domain" in cert, f"Certificate[{i}] missing domain"
            assert cert["domain"], f"Certificate[{i}] has empty domain"
    
    def test_transactions_have_required_fields(self, normalized_snapshot):
        """Each transaction must have transaction_id."""
        transactions = normalized_snapshot["planes"]["finance"]["transactions"]
        assert len(transactions) > 0, "Expected at least 1 transaction in fixture"
        
        for i, txn in enumerate(transactions):
            assert "transaction_id" in txn, f"Transaction[{i}] missing transaction_id"
            assert txn["transaction_id"], f"Transaction[{i}] has empty transaction_id"
    
    def test_no_banned_fields(self, normalized_snapshot):
        """Normalized snapshot must not contain any banned adjudication fields."""
        violations = check_banned_fields(normalized_snapshot)
        assert violations == [], f"Found banned fields: {violations}"


class TestBeforeAfterTransformations:
    """Show diff-style before/after for key record types."""
    
    @pytest.fixture
    def raw_farm_snapshot(self) -> dict:
        return load_fixture("real_farm_snapshot.json")
    
    def test_installed_app_transformation(self, raw_farm_snapshot):
        """Verify installed_app field mapping: install_id -> app_id, app_name -> name."""
        raw_apps = raw_farm_snapshot["planes"]["endpoint"]["installed_apps"]
        assert len(raw_apps) > 0
        
        raw_sample = raw_apps[0]
        print("\n=== INSTALLED_APP BEFORE/AFTER ===")
        print(f"BEFORE (Farm wire): {json.dumps(raw_sample, indent=2)}")
        
        normalized = normalize_farm_snapshot(raw_farm_snapshot)
        normalized_apps = normalized["planes"]["endpoint"]["installed_apps"]
        normalized_sample = normalized_apps[0]
        
        print(f"AFTER (Canonical): {json.dumps(normalized_sample, indent=2)}")
        
        # Verify mapping
        assert normalized_sample["app_id"] == raw_sample["install_id"]
        assert normalized_sample["name"] == raw_sample["app_name"]
        assert normalized_sample["device_id"] == raw_sample["device_id"]
    
    def test_device_transformation(self, raw_farm_snapshot):
        """Verify device field mapping is correct."""
        raw_devices = raw_farm_snapshot["planes"]["endpoint"]["devices"]
        assert len(raw_devices) > 0
        
        raw_sample = raw_devices[0]
        print("\n=== ENDPOINT_DEVICE BEFORE/AFTER ===")
        print(f"BEFORE (Farm wire): {json.dumps(raw_sample, indent=2)}")
        
        normalized = normalize_farm_snapshot(raw_farm_snapshot)
        normalized_devices = normalized["planes"]["endpoint"]["devices"]
        normalized_sample = normalized_devices[0]
        
        print(f"AFTER (Canonical): {json.dumps(normalized_sample, indent=2)}")
        
        # Verify mapping
        assert normalized_sample["device_id"] == raw_sample["device_id"]
        assert normalized_sample["hostname"] == raw_sample["hostname"]
        assert normalized_sample["os"] == raw_sample["os"]
