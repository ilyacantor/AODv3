"""
AOD Observed Breach Ledger - Canonical Breach Taxonomy

This module defines the standardized breach IDs and mapping from AOD findings
to Farm's expected breach schema. No anomaly_score in contract outputs.
"""
from typing import Dict, Any, List, Optional
from enum import Enum


class SeverityBase(str, Enum):
    BLOCKER = "BLOCKER"
    NON_BLOCKING = "NON_BLOCKING"
    TAG = "TAG"


BREACH_TAXONOMY = {
    "B-ONT-001": {
        "name": "SOR_CONFLICT_CRITICAL_FIELD",
        "severity_base": SeverityBase.BLOCKER,
        "description": "System of Record conflict on critical field",
        "source_rules": ["SOR_CONFLICT", "ONT_SOR_CONFLICT"],
        "required_evidence": ["conflicting_sots", "field_name"]
    },
    "B-DATA-001": {
        "name": "SCHEMA_DRIFT_BREAKING",
        "severity_base": SeverityBase.BLOCKER,
        "description": "Breaking schema drift detected",
        "source_rules": ["SCHEMA_MISMATCH", "SCHEMA_OR_SHAPE_MISMATCH", "DATA_SCHEMA_DRIFT", "ONT_AMBIGUOUS_TYPE"],
        "required_evidence": ["schema_diff"]
    },
    "B-ID-001": {
        "name": "ID_COLLISION",
        "severity_base": SeverityBase.BLOCKER,
        "description": "Multiple assets share the same identifier",
        "source_rules": ["ID_COLLISION"],
        "required_evidence": ["colliding_ids"]
    },
    "B-ID-002": {
        "name": "MISSING_REQUIRED_ID",
        "severity_base": SeverityBase.BLOCKER,
        "description": "Asset missing required primary identifier",
        "source_rules": ["MISSING_PRIMARY_ID"],
        "required_evidence": ["missing_id_type"]
    },
    "S-SHADOW-001": {
        "name": "OBSERVED_NOT_REGISTERED",
        "severity_base": SeverityBase.NON_BLOCKING,
        "description": "Asset observed in telemetry but not registered in IdP/CMDB",
        "source_rules": ["SHADOW_DETECTED"],
        "required_evidence": ["presence_source", "absence_source"]
    },
    "S-GOV-001": {
        "name": "MISSING_OWNER",
        "severity_base": SeverityBase.NON_BLOCKING,
        "description": "Asset lacks ownership information",
        "source_rules": ["GOV_MISSING_INFO"],
        "required_evidence": ["missing_fields"]
    },
    "S-DATA-001": {
        "name": "NONBLOCKING_CONFLICT",
        "severity_base": SeverityBase.NON_BLOCKING,
        "description": "Non-blocking data conflict detected",
        "source_rules": ["DATA_CONFLICT_DETECTED"],
        "required_evidence": ["conflict_types"]
    },
    "S-SEC-001": {
        "name": "SECURITY_VULNERABILITY",
        "severity_base": SeverityBase.NON_BLOCKING,
        "description": "Security vulnerability detected",
        "source_rules": ["SEC_VULN_DETECTED"],
        "required_evidence": ["vuln_id", "severity"]
    },
    "S-SEC-002": {
        "name": "MISSING_SECURITY_CONTROLS",
        "severity_base": SeverityBase.NON_BLOCKING,
        "description": "Required security controls not present",
        "source_rules": ["SEC_CONTROLS_MISSING"],
        "required_evidence": ["missing_controls"]
    },
    "S-SEC-003": {
        "name": "COMPLIANCE_GAP",
        "severity_base": SeverityBase.NON_BLOCKING,
        "description": "Compliance requirement not met",
        "source_rules": ["SEC_COMPLIANCE_GAP"],
        "required_evidence": ["compliance_framework", "gap_details"]
    },
    "T-CONF-001": {
        "name": "LOW_CLASSIFICATION_CONFIDENCE",
        "severity_base": SeverityBase.TAG,
        "description": "Low confidence in asset classification",
        "source_rules": ["LOW_CLASSIFICATION_CONFIDENCE"],
        "required_evidence": ["confidence_score"]
    }
}

RULE_TO_BREACH_MAP = {}
for breach_id, config in BREACH_TAXONOMY.items():
    for rule in config["source_rules"]:
        RULE_TO_BREACH_MAP[rule] = breach_id

NEVER_SHADOW_CATEGORIES = frozenset([
    "infrastructure",
    "internal_tool",
    "approved_saas"
])


def validate_shadow_evidence(
    lens_coverage: Dict[str, bool],
    signals: Dict[str, Any]
) -> tuple[bool, Dict[str, Any]]:
    """
    Validate Shadow IT evidence gate.
    
    Requirements:
    - Presence evidence: Asset observed in telemetry/spend (browser, network, billing, etc.)
    - Absence evidence: Asset NOT in core registries (IdP AND/OR CMDB)
    
    Returns: (is_valid, evidence_dict)
    """
    presence_sources = []
    absence_sources = []
    
    presence_lenses = ["browser", "network", "billing", "observability", "saas_api", "edr"]
    for lens in presence_lenses:
        if lens_coverage.get(lens, False):
            presence_sources.append(lens)
    
    core_registries = ["idp", "cmdb"]
    for registry in core_registries:
        if not lens_coverage.get(registry, False):
            absence_sources.append(registry)
    
    has_presence = len(presence_sources) > 0
    has_absence = len(absence_sources) > 0
    
    is_valid = has_presence and has_absence
    
    evidence = {
        "presence_source": presence_sources if presence_sources else None,
        "absence_source": absence_sources if absence_sources else None,
        "shadow_reasons": signals.get("shadow_reasons", [])
    }
    
    return is_valid, evidence


def validate_sor_conflict_evidence(signals: Dict[str, Any]) -> tuple[bool, Dict[str, Any]]:
    """
    Validate SoR Conflict evidence gate (fail closed).
    
    Requirements:
    - Must have CONCRETE evidence: conflict_types with actual field info
    - Requires at least one of: conflicting_sots populated OR field_diffs populated
    - Rule trigger alone is NOT sufficient
    - Parked reason alone is NOT sufficient
    - Never emit placeholder/inferred values
    """
    conflict_types = signals.get("conflict_types", [])
    rules_triggered = signals.get("rules_triggered", [])
    parked_reason = signals.get("parked_reason", "")
    
    conflicting_sots = []
    field_diffs = []
    
    for conflict in conflict_types:
        if isinstance(conflict, dict):
            if conflict.get("sources"):
                conflicting_sots.extend(conflict["sources"])
            if conflict.get("field"):
                field_diffs.append(conflict["field"])
        elif isinstance(conflict, str):
            field_diffs.append(conflict)
    
    has_concrete_evidence = len(field_diffs) > 0 or len(conflicting_sots) > 0
    has_rule_trigger = any(r in ["SOR_CONFLICT", "ONT_SOR_CONFLICT"] for r in rules_triggered)
    has_parked_reason = parked_reason == "SoR Conflict"
    
    is_valid = has_concrete_evidence
    
    if not is_valid:
        return False, {}
    
    triggered_rules = [r for r in rules_triggered if r in ["SOR_CONFLICT", "ONT_SOR_CONFLICT"]]
    
    evidence = {
        "conflicting_sots": list(set(conflicting_sots)),
        "field_diffs": field_diffs,
        "rules_triggered": triggered_rules,
        "has_rule_trigger": has_rule_trigger,
        "parked_reason_match": has_parked_reason
    }
    
    if field_diffs:
        evidence["field_name"] = field_diffs[0]
    
    return True, evidence


def validate_schema_drift_evidence(signals: Dict[str, Any]) -> tuple[bool, Dict[str, Any]]:
    """
    Validate Schema Drift evidence gate (fail closed).
    
    Requirements:
    - Must have schema-related rule triggered
    - OR parked_reason is Schema Mismatch with supporting evidence
    - Never emit placeholder/inferred values
    """
    conflict_types = signals.get("conflict_types", [])
    rules_triggered = signals.get("rules_triggered", [])
    parked_reason = signals.get("parked_reason", "")
    
    schema_rules = ["SCHEMA_MISMATCH", "SCHEMA_OR_SHAPE_MISMATCH", "DATA_SCHEMA_DRIFT", "ONT_AMBIGUOUS_TYPE"]
    
    triggered_schema_rules = [r for r in rules_triggered if r in schema_rules]
    has_schema_rule = len(triggered_schema_rules) > 0
    has_parked_reason = parked_reason == "Schema Mismatch"
    
    if not has_schema_rule and not has_parked_reason:
        return False, {}
    
    evidence = {
        "schema_diff": conflict_types,
        "rules_triggered": triggered_schema_rules,
        "has_rule_trigger": has_schema_rule,
        "parked_reason_match": has_parked_reason
    }
    
    return True, evidence


def validate_data_conflict_evidence(signals: Dict[str, Any]) -> tuple[bool, Dict[str, Any]]:
    """
    Validate Data Conflict evidence gate.
    """
    conflict_types = signals.get("conflict_types", [])
    has_data_conflicts = signals.get("has_data_conflicts", False)
    
    evidence = {
        "conflict_types": conflict_types[:10] if conflict_types else []
    }
    
    is_valid = has_data_conflicts or len(conflict_types) > 0
    
    return is_valid, evidence


def assemble_observed_breaches(
    asset_data: Dict[str, Any],
    signals: Dict[str, Any],
    lens_coverage: Dict[str, bool]
) -> List[Dict[str, Any]]:
    """
    Assemble the observed_breaches[] array for an asset.
    
    Each breach includes:
    - breach_id: Stable string (e.g., "B-ONT-001")
    - is_breached: Boolean
    - severity_base: BLOCKER, NON_BLOCKING, or TAG
    - evidence: Minimal required fields
    - source: Which lens/fields triggered it
    """
    breaches = []
    
    parked_reason = asset_data.get("parked_reason")
    rules_triggered = signals.get("rules_triggered", [])
    
    enriched_signals = {**signals, "parked_reason": parked_reason}
    
    if parked_reason == "SoR Conflict" or any(r in ["SOR_CONFLICT", "ONT_SOR_CONFLICT"] for r in rules_triggered):
        is_valid, evidence = validate_sor_conflict_evidence(enriched_signals)
        if is_valid:
            breaches.append({
                "breach_id": "B-ONT-001",
                "name": BREACH_TAXONOMY["B-ONT-001"]["name"],
                "is_breached": True,
                "severity_base": SeverityBase.BLOCKER.value,
                "evidence": evidence,
                "source": "cmdb"
            })
    
    schema_rules = ["SCHEMA_MISMATCH", "SCHEMA_OR_SHAPE_MISMATCH", "DATA_SCHEMA_DRIFT", "ONT_AMBIGUOUS_TYPE"]
    if parked_reason == "Schema Mismatch" or any(r in schema_rules for r in rules_triggered):
        is_valid, evidence = validate_schema_drift_evidence(enriched_signals)
        if is_valid:
            breaches.append({
                "breach_id": "B-DATA-001",
                "name": BREACH_TAXONOMY["B-DATA-001"]["name"],
                "is_breached": True,
                "severity_base": SeverityBase.BLOCKER.value,
                "evidence": evidence,
                "source": "cmdb"
            })
    
    if parked_reason == "ID Collision" or "ID_COLLISION" in rules_triggered:
        breaches.append({
            "breach_id": "B-ID-001",
            "name": BREACH_TAXONOMY["B-ID-001"]["name"],
            "is_breached": True,
            "severity_base": SeverityBase.BLOCKER.value,
            "evidence": {"colliding_ids": [asset_data.get("farm_asset_id", "unknown")]},
            "source": "cmdb"
        })
    
    if parked_reason == "Missing ID" or "MISSING_PRIMARY_ID" in rules_triggered:
        breaches.append({
            "breach_id": "B-ID-002",
            "name": BREACH_TAXONOMY["B-ID-002"]["name"],
            "is_breached": True,
            "severity_base": SeverityBase.BLOCKER.value,
            "evidence": {"missing_id_type": "primary_id"},
            "source": "cmdb"
        })
    
    if asset_data.get("is_shadow_it"):
        asset_kind = asset_data.get("asset_kind", "").lower()
        tech_domain = asset_data.get("tech_domain", "").lower()
        
        is_never_shadow = asset_kind in NEVER_SHADOW_CATEGORIES or tech_domain in NEVER_SHADOW_CATEGORIES
        
        if not is_never_shadow:
            is_valid, evidence = validate_shadow_evidence(lens_coverage, signals)
            if is_valid:
                breaches.append({
                    "breach_id": "S-SHADOW-001",
                    "name": BREACH_TAXONOMY["S-SHADOW-001"]["name"],
                    "is_breached": True,
                    "severity_base": SeverityBase.NON_BLOCKING.value,
                    "evidence": evidence,
                    "source": "multi_lens"
                })
    
    owner = signals.get("owner")
    owner_email = signals.get("owner_email")
    owner_team = signals.get("owner_team")
    
    if not owner and not owner_email and not owner_team:
        missing_fields = []
        if not owner:
            missing_fields.append("owner")
        if not owner_email:
            missing_fields.append("owner_email")
        if not owner_team:
            missing_fields.append("owner_team")
        
        breaches.append({
            "breach_id": "S-GOV-001",
            "name": BREACH_TAXONOMY["S-GOV-001"]["name"],
            "is_breached": True,
            "severity_base": SeverityBase.NON_BLOCKING.value,
            "evidence": {"missing_fields": missing_fields},
            "source": "cmdb"
        })
    
    if signals.get("has_data_conflicts") or signals.get("conflict_types"):
        is_valid, evidence = validate_data_conflict_evidence(signals)
        if is_valid:
            breaches.append({
                "breach_id": "S-DATA-001",
                "name": BREACH_TAXONOMY["S-DATA-001"]["name"],
                "is_breached": True,
                "severity_base": SeverityBase.NON_BLOCKING.value,
                "evidence": evidence,
                "source": "cmdb"
            })
    
    prob_kind = signals.get("prob_kind", 1.0) or 1.0
    if prob_kind < 0.5:
        breaches.append({
            "breach_id": "T-CONF-001",
            "name": BREACH_TAXONOMY["T-CONF-001"]["name"],
            "is_breached": True,
            "severity_base": SeverityBase.TAG.value,
            "evidence": {"confidence_score": prob_kind},
            "source": "classifier"
        })
    
    return breaches


def get_breach_summary(breaches: List[Dict[str, Any]]) -> Dict[str, int]:
    """Get summary counts of breaches by severity."""
    summary = {
        "total": len(breaches),
        "blocker": 0,
        "non_blocking": 0,
        "tag": 0
    }
    
    for breach in breaches:
        severity = breach.get("severity_base", "")
        if severity == SeverityBase.BLOCKER.value:
            summary["blocker"] += 1
        elif severity == SeverityBase.NON_BLOCKING.value:
            summary["non_blocking"] += 1
        elif severity == SeverityBase.TAG.value:
            summary["tag"] += 1
    
    return summary
