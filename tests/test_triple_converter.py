"""Tests for AOD EAV triple conversion."""

import os
import pytest
from uuid import UUID, uuid4

from src.aod.converters.triple_converter import convert_discovery_to_triples
from src.aod.converters.entity_resolver import resolve_entity_id
from src.aod.models.output_contracts import (
    Asset, Finding, AssetType, Environment, LensStatuses, LensCoverage,
    LensStatus, ProvisioningStatus, FindingType, FindingCategory, Severity,
    Confidence, Materiality, TriagePriority, SORTagging, AssetIdentifiers,
)


def _make_asset(
    name="Salesforce",
    vendor="Salesforce",
    asset_type=AssetType.SAAS,
    provisioning_status=ProvisioningStatus.ACTIVE,
    idp=True, cmdb=True, finance=True,
    sor_likelihood="high", sor_confidence=0.85,
    admission_reason="IdP+CMDB matched",
):
    """Build a minimal Asset for testing."""
    asset_id = uuid4()
    sor = None
    if sor_likelihood != "none":
        sor = SORTagging(
            likelihood=sor_likelihood,
            confidence=sor_confidence,
            evidence=["cmdb_authoritative"],
            domain="customer",
            signals_matched=["cmdb_authoritative"],
        )
    return Asset(
        asset_id=asset_id,
        tenant_id="test-tenant",
        run_id="run_test123",
        name=name,
        asset_type=asset_type,
        identifiers=AssetIdentifiers(),
        vendor=vendor,
        environment=Environment.PROD,
        lens_status=LensStatuses(
            idp=LensStatus.MATCHED if idp else LensStatus.UNMATCHED,
            cmdb=LensStatus.MATCHED if cmdb else LensStatus.UNMATCHED,
            cloud=LensStatus.UNMATCHED,
            finance=LensStatus.MATCHED if finance else LensStatus.UNMATCHED,
        ),
        lens_coverage=LensCoverage(idp=idp, cmdb=cmdb, finance=finance),
        provisioning_status=provisioning_status,
        admission_reason=admission_reason,
        sor_tagging=sor,
        evidence_refs=["discovery:obs_1"],
    )


def _make_finding(
    finding_type=FindingType.IDENTITY_GAP,
    severity=Severity.MED,
    explanation="No SSO integration detected",
    confidence=Confidence.MED,
    asset_id=None,
):
    """Build a minimal Finding for testing."""
    return Finding(
        finding_id=uuid4(),
        asset_id=asset_id,
        tenant_id="test-tenant",
        run_id="run_test123",
        finding_type=finding_type,
        category=FindingCategory.IDENTITY_ACCESS,
        severity=severity,
        explanation=explanation,
        confidence=confidence,
    )


ENTITY_ID = "test-entity-id"
TENANT_ID = "test-tenant"
RUN_ID = "run_test123"


class TestConvertDiscoveryToTriples:
    """Tests for convert_discovery_to_triples."""

    def test_basic_asset_conversion(self):
        """One asset produces expected number of triples."""
        asset = _make_asset()
        triples = convert_discovery_to_triples(
            assets=[asset], findings=[], fabric_plane_registry=[],
            entity_id=ENTITY_ID, tenant_id=TENANT_ID, run_id=RUN_ID,
        )
        # 8 asset props + 2 governance + 3 SOR = 13 triples
        assert len(triples) == 13

    def test_asset_without_sor(self):
        """Asset without SOR tagging produces fewer triples."""
        asset = _make_asset(sor_likelihood="none", sor_confidence=0.0)
        triples = convert_discovery_to_triples(
            assets=[asset], findings=[], fabric_plane_registry=[],
            entity_id=ENTITY_ID, tenant_id=TENANT_ID, run_id=RUN_ID,
        )
        # 8 asset props + 2 governance + 0 SOR = 10 triples
        assert len(triples) == 10

    def test_none_vendor_skipped(self):
        """Asset with None vendor produces one fewer triple."""
        asset = _make_asset(vendor=None)
        triples = convert_discovery_to_triples(
            assets=[asset], findings=[], fabric_plane_registry=[],
            entity_id=ENTITY_ID, tenant_id=TENANT_ID, run_id=RUN_ID,
        )
        # 7 asset props (vendor skipped) + 2 governance + 3 SOR = 12
        assert len(triples) == 12

    def test_provenance_fields(self):
        """Every triple has source_system, run_id, entity_id."""
        asset = _make_asset()
        triples = convert_discovery_to_triples(
            assets=[asset], findings=[], fabric_plane_registry=[],
            entity_id=ENTITY_ID, tenant_id=TENANT_ID, run_id=RUN_ID,
        )
        for t in triples:
            assert t["source_system"] == "AOD"
            assert t["run_id"] == RUN_ID
            assert t["entity_id"] == ENTITY_ID
            assert t["tenant_id"] == TENANT_ID

    def test_concept_prefixes(self):
        """All triples have discovery.* concept prefixes."""
        asset = _make_asset()
        finding = _make_finding()
        plane = {
            "plane_type": "IPAAS", "product": "Workato",
            "domain": "workato.com", "is_shadow": False,
            "confidence": 0.9, "detection_evidence": ["oauth_grant"],
        }
        triples = convert_discovery_to_triples(
            assets=[asset], findings=[finding], fabric_plane_registry=[plane],
            entity_id=ENTITY_ID, tenant_id=TENANT_ID, run_id=RUN_ID,
        )
        concepts = {t["concept"] for t in triples}
        assert concepts == {
            "discovery.asset", "discovery.governance",
            "discovery.sor", "discovery.finding", "discovery.fabric_plane",
        }

    def test_governance_mapping(self):
        """ProvisioningStatus maps to correct governance labels."""
        for prov, expected_gov in [
            (ProvisioningStatus.ACTIVE, "governed"),
            (ProvisioningStatus.REVIEW, "zombie"),
            (ProvisioningStatus.QUARANTINE, "shadow"),
            (ProvisioningStatus.BLOCKED, "blocked"),
            (ProvisioningStatus.RETIRED, "retired"),
        ]:
            asset = _make_asset(provisioning_status=prov, sor_likelihood="none")
            triples = convert_discovery_to_triples(
                assets=[asset], findings=[], fabric_plane_registry=[],
                entity_id=ENTITY_ID, tenant_id=TENANT_ID, run_id=RUN_ID,
            )
            gov_triples = [t for t in triples if t["concept"] == "discovery.governance"]
            gov_status = next(t for t in gov_triples if t["property"] == "governance_status")
            assert gov_status["value"] == expected_gov, (
                f"ProvisioningStatus.{prov.name} should map to '{expected_gov}', "
                f"got '{gov_status['value']}'"
            )

    def test_finding_conversion(self):
        """Findings produce 4 triples each."""
        finding = _make_finding()
        triples = convert_discovery_to_triples(
            assets=[], findings=[finding], fabric_plane_registry=[],
            entity_id=ENTITY_ID, tenant_id=TENANT_ID, run_id=RUN_ID,
        )
        assert len(triples) == 4
        properties = {t["property"] for t in triples}
        assert properties == {"finding_type", "severity", "affected_asset", "description"}

    def test_fabric_plane_conversion(self):
        """Fabric plane produces 4 triples."""
        plane = {
            "plane_type": "API_GATEWAY", "product": "Kong",
            "domain": "kong.internal", "is_shadow": True,
            "confidence": 0.7, "detection_evidence": ["network_flow"],
        }
        triples = convert_discovery_to_triples(
            assets=[], findings=[], fabric_plane_registry=[plane],
            entity_id=ENTITY_ID, tenant_id=TENANT_ID, run_id=RUN_ID,
        )
        assert len(triples) == 4
        properties = {t["property"] for t in triples}
        assert properties == {"plane_type", "vendor", "instance", "is_shadow"}

    def test_confidence_tiers(self):
        """Confidence scores map to correct tiers."""
        asset_high = _make_asset(sor_confidence=0.85)
        asset_med = _make_asset(sor_confidence=0.6)
        asset_low = _make_asset(sor_confidence=0.3)

        for asset, expected_tier in [
            (asset_high, "high"),
            (asset_med, "medium"),
            (asset_low, "low"),
        ]:
            triples = convert_discovery_to_triples(
                assets=[asset], findings=[], fabric_plane_registry=[],
                entity_id=ENTITY_ID, tenant_id=TENANT_ID, run_id=RUN_ID,
            )
            asset_triples = [t for t in triples if t["concept"] == "discovery.asset"]
            assert all(t["confidence_tier"] == expected_tier for t in asset_triples)

    def test_multiple_assets_scale(self):
        """50 assets produce proportional triples."""
        assets = [_make_asset(name=f"Asset_{i}") for i in range(50)]
        triples = convert_discovery_to_triples(
            assets=assets, findings=[], fabric_plane_registry=[],
            entity_id=ENTITY_ID, tenant_id=TENANT_ID, run_id=RUN_ID,
        )
        # 50 assets × (8 asset + 2 governance + 3 SOR) = 650
        assert len(triples) == 650

    def test_empty_input(self):
        """No input produces no triples."""
        triples = convert_discovery_to_triples(
            assets=[], findings=[], fabric_plane_registry=[],
            entity_id=ENTITY_ID, tenant_id=TENANT_ID, run_id=RUN_ID,
        )
        assert len(triples) == 0

    def test_canonical_id_populated(self):
        """Every triple has a non-empty canonical_id."""
        asset = _make_asset()
        finding = _make_finding()
        plane = {
            "plane_type": "IPAAS", "product": "Workato",
            "domain": "workato.com", "is_shadow": False,
            "confidence": 0.9, "detection_evidence": [],
        }
        triples = convert_discovery_to_triples(
            assets=[asset], findings=[finding], fabric_plane_registry=[plane],
            entity_id=ENTITY_ID, tenant_id=TENANT_ID, run_id=RUN_ID,
        )
        for t in triples:
            assert t["canonical_id"] is not None
            assert t["canonical_id"] != ""

    def test_triple_dict_has_all_19_columns(self):
        """Every triple dict has all 19 columns from the schema."""
        expected_cols = {
            "tenant_id", "entity_id", "concept", "property", "value",
            "period", "currency", "unit",
            "source_system", "source_table", "source_field",
            "pipe_id", "run_id", "source_run_tag",
            "confidence_score", "confidence_tier",
            "canonical_id", "resolution_method", "resolution_confidence",
        }
        asset = _make_asset()
        triples = convert_discovery_to_triples(
            assets=[asset], findings=[], fabric_plane_registry=[],
            entity_id=ENTITY_ID, tenant_id=TENANT_ID, run_id=RUN_ID,
        )
        for t in triples:
            assert set(t.keys()) == expected_cols


class TestResolveEntityId:
    """Tests for resolve_entity_id."""

    def test_request_entity_id_takes_priority(self):
        """Explicit request_entity_id wins over all other sources."""
        result = resolve_entity_id(
            snapshot_data={"meta": {"entity_id": "snapshot-id"}},
            request_entity_id="request-id",
        )
        assert result == "request-id"

    def test_snapshot_meta_fallback(self):
        """Snapshot meta.entity_id used when request_entity_id is None."""
        result = resolve_entity_id(
            snapshot_data={"meta": {"entity_id": "snapshot-id"}},
        )
        assert result == "snapshot-id"

    def test_env_var_fallback(self):
        """AOD_DEFAULT_ENTITY_ID env var used as last fallback."""
        os.environ["AOD_DEFAULT_ENTITY_ID"] = "env-id"
        try:
            result = resolve_entity_id(snapshot_data=None)
            assert result == "env-id"
        finally:
            del os.environ["AOD_DEFAULT_ENTITY_ID"]

    def test_fails_loudly_when_missing(self):
        """ValueError raised with clear message when no entity_id available."""
        # Make sure env var is not set
        os.environ.pop("AOD_DEFAULT_ENTITY_ID", None)
        with pytest.raises(ValueError, match="entity_id required"):
            resolve_entity_id(snapshot_data=None, request_entity_id=None)

    def test_empty_snapshot_meta(self):
        """Snapshot without meta.entity_id falls through to env var."""
        os.environ["AOD_DEFAULT_ENTITY_ID"] = "env-id"
        try:
            result = resolve_entity_id(snapshot_data={"meta": {}})
            assert result == "env-id"
        finally:
            del os.environ["AOD_DEFAULT_ENTITY_ID"]
