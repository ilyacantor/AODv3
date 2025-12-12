"""
Unit tests for breach mapper, evidence gates, and normalization.

Covers:
- Breach taxonomy mapping
- Shadow IT evidence gate (presence + absence)
- SoR conflict evidence gate
- Schema drift evidence gate
- Data conflict evidence gate
- Output schema stability
"""
import pytest
from src.aod.breaches import (
    BREACH_TAXONOMY,
    RULE_TO_BREACH_MAP,
    NEVER_SHADOW_CATEGORIES,
    SeverityBase,
    validate_shadow_evidence,
    validate_sor_conflict_evidence,
    validate_schema_drift_evidence,
    validate_data_conflict_evidence,
    assemble_observed_breaches,
    get_breach_summary
)


class TestBreachTaxonomy:
    """Tests for breach ID mapping."""
    
    def test_blocker_breaches_exist(self):
        """All blocker breach IDs are defined."""
        blocker_ids = ["B-ONT-001", "B-DATA-001", "B-ID-001", "B-ID-002"]
        for bid in blocker_ids:
            assert bid in BREACH_TAXONOMY
            assert BREACH_TAXONOMY[bid]["severity_base"] == SeverityBase.BLOCKER
    
    def test_non_blocking_breaches_exist(self):
        """All non-blocking breach IDs are defined."""
        non_blocking_ids = ["S-SHADOW-001", "S-GOV-001", "S-DATA-001"]
        for bid in non_blocking_ids:
            assert bid in BREACH_TAXONOMY
            assert BREACH_TAXONOMY[bid]["severity_base"] == SeverityBase.NON_BLOCKING
    
    def test_rule_to_breach_mapping(self):
        """Blocking rules map to correct breach IDs."""
        assert RULE_TO_BREACH_MAP["SOR_CONFLICT"] == "B-ONT-001"
        assert RULE_TO_BREACH_MAP["ONT_SOR_CONFLICT"] == "B-ONT-001"
        assert RULE_TO_BREACH_MAP["SCHEMA_MISMATCH"] == "B-DATA-001"
        assert RULE_TO_BREACH_MAP["ID_COLLISION"] == "B-ID-001"
        assert RULE_TO_BREACH_MAP["MISSING_PRIMARY_ID"] == "B-ID-002"
        assert RULE_TO_BREACH_MAP["SHADOW_DETECTED"] == "S-SHADOW-001"


class TestShadowEvidenceGate:
    """Tests for Shadow IT evidence gate (presence + absence required)."""
    
    def test_shadow_valid_with_browser_and_no_idp(self):
        """Shadow is valid when seen in browser telemetry but not in IdP."""
        lens_coverage = {"browser": True, "idp": False}
        signals = {"shadow_reasons": ["no_idp_evidence"]}
        
        is_valid, evidence = validate_shadow_evidence(lens_coverage, signals)
        
        assert is_valid is True
        assert "browser" in evidence["presence_source"]
        assert "idp" in evidence["absence_source"]
    
    def test_shadow_valid_with_billing_and_no_cmdb(self):
        """Shadow is valid when seen in billing but not in CMDB."""
        lens_coverage = {"billing": True, "cmdb": False}
        signals = {}
        
        is_valid, evidence = validate_shadow_evidence(lens_coverage, signals)
        
        assert is_valid is True
        assert "billing" in evidence["presence_source"]
        assert "cmdb" in evidence["absence_source"]
    
    def test_shadow_invalid_no_presence(self):
        """Shadow is invalid without presence evidence."""
        lens_coverage = {"idp": False, "cmdb": False}  # No telemetry sources
        signals = {}
        
        is_valid, evidence = validate_shadow_evidence(lens_coverage, signals)
        
        assert is_valid is False
        assert evidence["presence_source"] is None
    
    def test_shadow_invalid_no_absence(self):
        """Shadow is invalid without absence evidence (asset is registered)."""
        lens_coverage = {"browser": True, "idp": True, "cmdb": True}  # Registered everywhere
        signals = {}
        
        is_valid, evidence = validate_shadow_evidence(lens_coverage, signals)
        
        assert is_valid is False
        assert evidence["absence_source"] is None or len(evidence["absence_source"]) == 0
    
    def test_shadow_requires_both_presence_and_absence(self):
        """Shadow requires BOTH presence AND absence evidence."""
        lens_coverage = {"browser": False, "idp": False}
        signals = {}
        
        is_valid, evidence = validate_shadow_evidence(lens_coverage, signals)
        
        assert is_valid is False


class TestSoRConflictEvidenceGate:
    """Tests for SoR Conflict evidence gate (fail closed)."""
    
    def test_sor_valid_with_conflict_types(self):
        """SoR conflict is valid when conflict_types exist."""
        signals = {
            "conflict_types": ["owner_mismatch"],
            "rules_triggered": ["SOR_CONFLICT"]
        }
        
        is_valid, evidence = validate_sor_conflict_evidence(signals)
        
        assert is_valid is True
        assert "conflicting_sots" in evidence
        assert "field_diffs" in evidence
        assert "owner_mismatch" in evidence["field_diffs"]
    
    def test_sor_valid_with_conflict_types_only(self):
        """SoR conflict is valid when conflict_types exist (concrete evidence)."""
        signals = {
            "rules_triggered": [],
            "conflict_types": ["field_x"]
        }
        
        is_valid, evidence = validate_sor_conflict_evidence(signals)
        
        assert is_valid is True
        assert "field_x" in evidence["field_diffs"]
    
    def test_sor_invalid_rule_trigger_alone(self):
        """SoR conflict is INVALID with only rule trigger (no parked_reason or conflict_types)."""
        signals = {
            "rules_triggered": ["SOR_CONFLICT"],
            "conflict_types": []
        }
        
        is_valid, evidence = validate_sor_conflict_evidence(signals)
        
        assert is_valid is False
        assert evidence == {}
    
    def test_sor_invalid_rule_and_parked_reason_without_field_diffs(self):
        """SoR conflict is INVALID with rule+parked_reason but no concrete field evidence."""
        signals = {
            "parked_reason": "SoR Conflict",
            "rules_triggered": ["SOR_CONFLICT"],
            "conflict_types": []
        }
        
        is_valid, evidence = validate_sor_conflict_evidence(signals)
        
        assert is_valid is False
        assert evidence == {}
    
    def test_sor_invalid_parked_reason_alone(self):
        """SoR conflict needs concrete evidence - parked_reason alone is not enough."""
        signals = {
            "parked_reason": "SoR Conflict",
            "rules_triggered": [],
            "conflict_types": []
        }
        
        is_valid, evidence = validate_sor_conflict_evidence(signals)
        
        assert is_valid is False
        assert evidence == {}
    
    def test_sor_invalid_without_any_evidence(self):
        """SoR conflict is invalid without any evidence."""
        signals = {
            "rules_triggered": [],
            "conflict_types": []
        }
        
        is_valid, evidence = validate_sor_conflict_evidence(signals)
        
        assert is_valid is False
        assert evidence == {}


class TestSchemaDriftEvidenceGate:
    """Tests for Schema Drift evidence gate (fail closed)."""
    
    def test_schema_valid_with_rule_triggered(self):
        """Schema drift is valid when SCHEMA_MISMATCH rule is triggered."""
        signals = {"rules_triggered": ["SCHEMA_MISMATCH"]}
        
        is_valid, evidence = validate_schema_drift_evidence(signals)
        
        assert is_valid is True
        assert "SCHEMA_MISMATCH" in evidence["rules_triggered"]
        assert evidence["has_rule_trigger"] is True
    
    def test_schema_valid_with_parked_reason(self):
        """Schema drift is valid when parked_reason is 'Schema Mismatch'."""
        signals = {
            "parked_reason": "Schema Mismatch",
            "rules_triggered": [],
            "conflict_types": []
        }
        
        is_valid, evidence = validate_schema_drift_evidence(signals)
        
        assert is_valid is True
        assert evidence["parked_reason_match"] is True
        assert evidence["rules_triggered"] == []
    
    def test_schema_invalid_without_rule_or_parked_reason(self):
        """Schema drift is invalid without rule trigger or parked_reason."""
        signals = {
            "conflict_types": ["structure_mismatch"],
            "rules_triggered": []
        }
        
        is_valid, evidence = validate_schema_drift_evidence(signals)
        
        assert is_valid is False
        assert evidence == {}


class TestDataConflictEvidenceGate:
    """Tests for Data Conflict evidence gate."""
    
    def test_data_conflict_valid_with_flag(self):
        """Data conflict is valid when has_data_conflicts is True."""
        signals = {"has_data_conflicts": True, "conflict_types": ["field_mismatch"]}
        
        is_valid, evidence = validate_data_conflict_evidence(signals)
        
        assert is_valid is True
        assert "field_mismatch" in evidence["conflict_types"]
    
    def test_data_conflict_invalid_empty(self):
        """Data conflict is invalid with no evidence."""
        signals = {"has_data_conflicts": False, "conflict_types": []}
        
        is_valid, evidence = validate_data_conflict_evidence(signals)
        
        assert is_valid is False


class TestAssembleObservedBreaches:
    """Tests for full breach assembly."""
    
    def test_blocker_breach_for_parked_asset(self):
        """Parked asset with SoR Conflict gets B-ONT-001 breach."""
        asset_data = {
            "parked_reason": "SoR Conflict",
            "is_shadow_it": False,
            "lifecycle_state": "PARKED",
            "farm_asset_id": "test-123"
        }
        signals = {
            "rules_triggered": ["SOR_CONFLICT"],
            "conflict_types": ["owner_mismatch"],
            "owner": "Alice"
        }
        lens_coverage = {}
        
        breaches = assemble_observed_breaches(asset_data, signals, lens_coverage)
        
        breach_ids = [b["breach_id"] for b in breaches]
        assert "B-ONT-001" in breach_ids
        
        sor_breach = next(b for b in breaches if b["breach_id"] == "B-ONT-001")
        assert sor_breach["is_breached"] is True
        assert sor_breach["severity_base"] == "BLOCKER"
    
    def test_shadow_breach_with_valid_evidence(self):
        """Shadow IT asset with valid evidence gets S-SHADOW-001 breach."""
        asset_data = {
            "is_shadow_it": True,
            "asset_kind": "saas",
            "tech_domain": "crm"
        }
        signals = {
            "shadow_reasons": ["no_idp_evidence"],
            "owner": "Bob"
        }
        lens_coverage = {"browser": True, "idp": False, "cmdb": False}
        
        breaches = assemble_observed_breaches(asset_data, signals, lens_coverage)
        
        breach_ids = [b["breach_id"] for b in breaches]
        assert "S-SHADOW-001" in breach_ids
    
    def test_shadow_not_emitted_without_evidence(self):
        """Shadow IT asset without valid evidence does NOT get S-SHADOW-001."""
        asset_data = {
            "is_shadow_it": True,
            "asset_kind": "saas",
            "tech_domain": "crm"
        }
        signals = {}
        lens_coverage = {}  # No presence or absence evidence
        
        breaches = assemble_observed_breaches(asset_data, signals, lens_coverage)
        
        breach_ids = [b["breach_id"] for b in breaches]
        assert "S-SHADOW-001" not in breach_ids
    
    def test_shadow_not_emitted_for_never_shadow_category(self):
        """Assets in never-shadow categories don't get shadow breach."""
        asset_data = {
            "is_shadow_it": True,
            "asset_kind": "infrastructure",  # Never shadow
            "tech_domain": "cloud"
        }
        signals = {"shadow_reasons": ["no_idp_evidence"]}
        lens_coverage = {"browser": True, "idp": False}
        
        breaches = assemble_observed_breaches(asset_data, signals, lens_coverage)
        
        breach_ids = [b["breach_id"] for b in breaches]
        assert "S-SHADOW-001" not in breach_ids
    
    def test_governance_breach_for_missing_owner(self):
        """Asset without owner info gets S-GOV-001 breach."""
        asset_data = {"is_shadow_it": False}
        signals = {"owner": None, "owner_email": None, "owner_team": None}
        lens_coverage = {}
        
        breaches = assemble_observed_breaches(asset_data, signals, lens_coverage)
        
        breach_ids = [b["breach_id"] for b in breaches]
        assert "S-GOV-001" in breach_ids
        
        gov_breach = next(b for b in breaches if b["breach_id"] == "S-GOV-001")
        assert "owner" in gov_breach["evidence"]["missing_fields"]
    
    def test_low_confidence_tag(self):
        """Asset with low prob_kind gets T-CONF-001 tag."""
        asset_data = {"is_shadow_it": False}
        signals = {"prob_kind": 0.3, "owner": "Alice"}
        lens_coverage = {}
        
        breaches = assemble_observed_breaches(asset_data, signals, lens_coverage)
        
        breach_ids = [b["breach_id"] for b in breaches]
        assert "T-CONF-001" in breach_ids
        
        conf_breach = next(b for b in breaches if b["breach_id"] == "T-CONF-001")
        assert conf_breach["severity_base"] == "TAG"
        assert conf_breach["evidence"]["confidence_score"] == 0.3


class TestBreachOutputSchema:
    """Tests for output schema stability."""
    
    def test_breach_has_required_fields(self):
        """Every breach has all required fields."""
        asset_data = {
            "parked_reason": "ID Collision",
            "is_shadow_it": False,
            "farm_asset_id": "test-456"
        }
        signals = {"rules_triggered": ["ID_COLLISION"], "owner": "Test"}
        lens_coverage = {}
        
        breaches = assemble_observed_breaches(asset_data, signals, lens_coverage)
        
        for breach in breaches:
            assert "breach_id" in breach
            assert "name" in breach
            assert "is_breached" in breach
            assert "severity_base" in breach
            assert "evidence" in breach
            assert "source" in breach
            
            assert isinstance(breach["breach_id"], str)
            assert isinstance(breach["is_breached"], bool)
            assert breach["severity_base"] in ["BLOCKER", "NON_BLOCKING", "TAG"]
            assert isinstance(breach["evidence"], dict)
    
    def test_breach_summary_counts(self):
        """Breach summary correctly counts by severity."""
        breaches = [
            {"breach_id": "B-ONT-001", "severity_base": "BLOCKER"},
            {"breach_id": "B-ID-001", "severity_base": "BLOCKER"},
            {"breach_id": "S-GOV-001", "severity_base": "NON_BLOCKING"},
            {"breach_id": "T-CONF-001", "severity_base": "TAG"}
        ]
        
        summary = get_breach_summary(breaches)
        
        assert summary["total"] == 4
        assert summary["blocker"] == 2
        assert summary["non_blocking"] == 1
        assert summary["tag"] == 1
