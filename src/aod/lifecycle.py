from typing import Tuple, Optional, List, Dict, Any


BLOCKING_RULES = {
    "ONT_SOR_CONFLICT": "SoR Conflict",
    "SOR_CONFLICT": "SoR Conflict",
    "SCHEMA_MISMATCH": "Schema Mismatch",
    "SCHEMA_OR_SHAPE_MISMATCH": "Schema Mismatch",
    "DATA_SCHEMA_DRIFT": "Schema Mismatch",
    "ID_COLLISION": "ID Collision",
    "MISSING_PRIMARY_ID": "Missing ID"
}

VENDOR_TAXONOMY = {
    "salesforce": {"tech_domain": "crm", "system_role": "SoR"},
    "hubspot": {"tech_domain": "crm", "system_role": "SoR"},
    "postgresql": {"tech_domain": "database", "system_role": "SoR"},
    "mysql": {"tech_domain": "database", "system_role": "SoR"},
    "mongodb": {"tech_domain": "database", "system_role": "SoR"},
    "redis": {"tech_domain": "cache", "system_role": "SoE"},
    "aws": {"tech_domain": "cloud", "system_role": "SoE"},
    "azure": {"tech_domain": "cloud", "system_role": "SoE"},
    "gcp": {"tech_domain": "cloud", "system_role": "SoE"},
    "kubernetes": {"tech_domain": "orchestration", "system_role": "SoE"},
    "docker": {"tech_domain": "container", "system_role": "SoE"},
    "slack": {"tech_domain": "collaboration", "system_role": "SoE"},
    "jira": {"tech_domain": "project_management", "system_role": "SoE"},
    "notion": {"tech_domain": "documentation", "system_role": "SoE"},
    "stripe": {"tech_domain": "payments", "system_role": "SoR"},
    "datadog": {"tech_domain": "observability", "system_role": "SoI"},
    "splunk": {"tech_domain": "observability", "system_role": "SoI"},
    "grafana": {"tech_domain": "observability", "system_role": "SoI"},
    "snowflake": {"tech_domain": "analytics", "system_role": "SoI"},
    "bigquery": {"tech_domain": "analytics", "system_role": "SoI"},
    "tableau": {"tech_domain": "bi", "system_role": "SoI"},
    ".net": {"tech_domain": "application", "system_role": "SoE"},
    "java": {"tech_domain": "application", "system_role": "SoE"},
    "python": {"tech_domain": "application", "system_role": "SoE"},
    "node": {"tech_domain": "application", "system_role": "SoE"},
}

TEAM_TO_DOMAIN = {
    "engineering": "operations",
    "data engineering": "operations",
    "devops": "operations",
    "platform": "operations",
    "security": "it_security",
    "it": "it_security",
    "sales": "gtm",
    "marketing": "gtm",
    "customer success": "gtm",
    "finance": "finance",
    "accounting": "finance",
    "hr": "hr",
    "people": "hr",
    "legal": "legal_risk",
    "compliance": "legal_risk",
    "product": "product_usage",
}


def route_lifecycle(signals: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    """
    Route an asset to the appropriate lifecycle state based on signals.
    
    V1 Full-Pull Model:
    - Assets are evaluated immediately upon ingestion
    - DISCOVERED state is not used in V1 (reserved for future incremental/streaming mode)
    - Blocking rules → PARKED with reason
    - No blocking rules → CATALOGED
    
    Future: In incremental mode, assets would first be DISCOVERED, then
    promoted to PARKED/CATALOGED after evaluation.
    """
    rules_triggered = signals.get("rules_triggered", [])
    parked_reason = signals.get("parked_reason")
    
    if parked_reason and parked_reason in BLOCKING_RULES:
        return "PARKED", BLOCKING_RULES[parked_reason]
    
    for rule in rules_triggered:
        if rule in BLOCKING_RULES:
            return "PARKED", BLOCKING_RULES[rule]
    
    return "CATALOGED", None


def derive_tech_domain(vendor: Optional[str], asset_kind: Optional[str]) -> str:
    if vendor:
        vendor_lower = vendor.lower()
        for key, info in VENDOR_TAXONOMY.items():
            if key in vendor_lower:
                return info["tech_domain"]
    
    kind_mapping = {
        "db": "database",
        "database": "database",
        "service": "application",
        "app": "application",
        "application": "application",
        "saas": "saas",
        "host": "infrastructure",
        "container": "container",
        "vm": "infrastructure",
    }
    
    if asset_kind:
        return kind_mapping.get(asset_kind.lower(), "unknown")
    
    return "unknown"


def derive_system_role(vendor: Optional[str]) -> str:
    if vendor:
        vendor_lower = vendor.lower()
        for key, info in VENDOR_TAXONOMY.items():
            if key in vendor_lower:
                return info["system_role"]
    return "unknown"


def derive_business_domain(owner_team: Optional[str], vendor: Optional[str]) -> str:
    if owner_team:
        team_lower = owner_team.lower()
        for key, domain in TEAM_TO_DOMAIN.items():
            if key in team_lower:
                return domain
    
    if vendor:
        vendor_lower = vendor.lower()
        if any(v in vendor_lower for v in ["stripe", "paypal", "quickbooks"]):
            return "finance"
        if any(v in vendor_lower for v in ["salesforce", "hubspot", "marketo"]):
            return "gtm"
        if any(v in vendor_lower for v in ["datadog", "splunk", "aws", "azure"]):
            return "operations"
    
    return "unknown"


def is_shadow_it(signals: Dict[str, Any]) -> bool:
    if signals.get("is_shadow_it"):
        return True
    
    if not signals.get("owner") and not signals.get("owner_email"):
        lens_coverage = signals.get("lens_coverage", {})
        if lens_coverage:
            core_lenses = ["idp", "cmdb", "billing"]
            has_core = any(lens_coverage.get(lens) for lens in core_lenses)
            if not has_core:
                return True
    
    return False


def derive_findings(asset: Dict[str, Any], signals: Dict[str, Any]) -> List[Dict[str, Any]]:
    findings = []
    
    if asset.get("is_shadow_it"):
        findings.append({
            "finding_type": "shadow_it",
            "rule_id": "SHADOW_DETECTED",
            "severity": "warn",
            "description": "Asset identified as Shadow IT - unauthorized or unmanaged application",
            "evidence": {"is_shadow_it": True, "reasons": signals.get("shadow_reasons", [])}
        })
    
    owner = signals.get("owner")
    owner_email = signals.get("owner_email")
    owner_team = signals.get("owner_team")
    vendor = signals.get("vendor", "")
    
    has_governance_gap = False
    governance_reasons = []
    
    if not owner and not owner_email and not owner_team:
        has_governance_gap = True
        governance_reasons.append("No ownership information")
    
    vendor_lower = (vendor or "").lower()
    is_known_vendor = any(v in vendor_lower for v in VENDOR_TAXONOMY.keys())
    if vendor and not is_known_vendor:
        has_governance_gap = True
        governance_reasons.append(f"Unmapped vendor: {vendor}")
    
    if has_governance_gap:
        findings.append({
            "finding_type": "governance_gap",
            "rule_id": "GOV_MISSING_INFO",
            "severity": "warn",
            "description": "Asset has governance gaps requiring attention",
            "evidence": {"reasons": governance_reasons}
        })
    
    if signals.get("has_data_conflicts") or signals.get("conflict_types"):
        findings.append({
            "finding_type": "data_conflicts",
            "rule_id": "DATA_CONFLICT_DETECTED",
            "severity": "warn",
            "description": "Data conflicts detected for this asset",
            "evidence": {"conflict_types": signals.get("conflict_types", [])}
        })
    
    anomaly_score = signals.get("anomaly_score", 0)
    if anomaly_score and anomaly_score >= 0.4:
        findings.append({
            "finding_type": "ops_risk",
            "rule_id": "OPS_ANOMALY_HIGH",
            "severity": "critical" if anomaly_score >= 0.7 else "warn",
            "description": f"Operational risk detected (anomaly score: {anomaly_score:.2f})",
            "evidence": {"anomaly_score": anomaly_score}
        })
    
    prob_kind = signals.get("prob_kind", 1.0)
    if prob_kind and prob_kind < 0.5:
        findings.append({
            "finding_type": "low_confidence",
            "rule_id": "LOW_CLASSIFICATION_CONFIDENCE",
            "severity": "info",
            "description": f"Low confidence in asset classification (prob_kind: {prob_kind:.2f})",
            "evidence": {"prob_kind": prob_kind}
        })
    
    return findings
