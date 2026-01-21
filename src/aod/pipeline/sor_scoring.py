"""
System of Record (SOR) Scoring Engine

Identifies assets that are likely Systems of Record based on signals from:
- CMDB metadata (authoritative flags, data tier)
- Known SOR vendor patterns (Workday, Salesforce, SAP, etc.)
- Middleware topology (data exporter role)
- IdP coverage (SSO + SCIM indicates enterprise-wide)
- Finance signals (enterprise contracts)
- Discovery breadth (multi-source corroboration)

SOR is ORTHOGONAL to Shadow/Zombie/Governed classifications.
An asset can be: Governed+SOR, Shadow+SOR-candidate, Zombie+former-SOR.

Output: sor_likelihood (high/medium/low/none), sor_confidence (0-1), sor_evidence list
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Any

from ..models.output_contracts import Asset, LensCoverage
from ..core.policy import get_current_config

logger = logging.getLogger(__name__)


KNOWN_SOR_VENDORS = {
    "customer": [
        "salesforce.com", "hubspot.com", "dynamics.com", "dynamics365.com",
        "zoho.com", "pipedrive.com", "freshworks.com", "zendesk.com"
    ],
    "employee": [
        "workday.com", "adp.com", "bamboohr.com", "namely.com", 
        "paylocity.com", "paychex.com", "gusto.com", "rippling.com",
        "successfactors.com", "ultipro.com", "dayforce.com"
    ],
    "financial": [
        "netsuite.com", "quickbooks.com", "xero.com", "sage.com",
        "intacct.com", "freshbooks.com", "oracle.com", "sap.com"
    ],
    "product": [
        "sap.com", "oracle.com", "epicor.com", "infor.com",
        "dynamics.com", "netsuite.com"
    ],
    "identity": [
        "okta.com", "onelogin.com", "auth0.com", "ping.com",
        "duo.com", "azure.com", "google.com"
    ],
    "it_assets": [
        "servicenow.com", "jira.atlassian.com", "freshservice.com",
        "manageengine.com", "cherwell.com"
    ]
}


@dataclass
class SORSignal:
    """Individual SOR signal with weight and evidence"""
    name: str
    weight: int
    evidence: str
    domain: Optional[str] = None


@dataclass
class SORScoringResult:
    """Result of SOR scoring for an asset"""
    likelihood: str  # high, medium, low, none
    confidence: float  # 0.0 to 1.0
    evidence: list[str] = field(default_factory=list)
    domain: Optional[str] = None  # customer, employee, financial, etc.
    raw_score: int = 0
    max_possible_score: int = 0
    signals_matched: list[str] = field(default_factory=list)


def get_sor_policy_config() -> dict:
    """Get SOR scoring policy configuration with defaults, always returns dict"""
    config = get_current_config()
    
    defaults = {
        "enabled": True,
        "weights": {
            "cmdb_authoritative": 40,
            "known_sor_vendor": 30,
            "middleware_exporter": 25,
            "enterprise_sso_scim": 20,
            "enterprise_contract": 15,
            "multi_department": 15,
            "high_corroboration": 10,
            "edge_app_penalty": -20
        },
        "confidence_thresholds": {
            "high": 0.75,
            "medium": 0.50
        },
        "known_sor_vendors": KNOWN_SOR_VENDORS
    }
    
    if hasattr(config, 'sor_scoring') and config.sor_scoring:
        sor_config = config.sor_scoring
        return {
            "enabled": getattr(sor_config, 'enabled', defaults["enabled"]),
            "weights": getattr(sor_config, 'weights', defaults["weights"]),
            "confidence_thresholds": getattr(sor_config, 'confidence_thresholds', defaults["confidence_thresholds"]),
            "known_sor_vendors": getattr(sor_config, 'known_sor_vendors', defaults["known_sor_vendors"])
        }
    
    return defaults


def _check_cmdb_authoritative(
    asset: Asset,
    cmdb_record: Optional[Any] = None
) -> Optional[SORSignal]:
    """Check if CMDB marks this asset as authoritative/SOR"""
    
    if not asset.lens_coverage.cmdb:
        return None
    
    config = get_sor_policy_config()
    weights = config.get("weights", {})
    weight = weights.get("cmdb_authoritative", 40)
    
    authoritative_indicators = [
        "system_of_record", "authoritative", "master_data", 
        "golden_record", "data_tier_gold", "tier_1", "critical"
    ]
    
    if cmdb_record:
        ci_type = getattr(cmdb_record, 'ci_type', '') or ''
        lifecycle = getattr(cmdb_record, 'lifecycle', '') or ''
        description = getattr(cmdb_record, 'description', '') or ''
        tags = getattr(cmdb_record, 'tags', []) or []
        is_sor = getattr(cmdb_record, 'is_system_of_record', False)
        data_tier = getattr(cmdb_record, 'data_tier', '') or ''
        
        if is_sor:
            return SORSignal(
                name="cmdb_authoritative",
                weight=weight,
                evidence="CMDB indicates authoritative status: 'is_system_of_record=true'"
            )
        
        if data_tier.lower() in ['gold', 'tier_1', 'critical']:
            return SORSignal(
                name="cmdb_authoritative",
                weight=weight,
                evidence=f"CMDB indicates authoritative status: 'data_tier={data_tier}'"
            )
        
        combined = f"{ci_type} {lifecycle} {description} {' '.join(tags)}".lower()
        
        for indicator in authoritative_indicators:
            if indicator.replace('_', ' ') in combined or indicator in combined:
                return SORSignal(
                    name="cmdb_authoritative",
                    weight=weight,
                    evidence=f"CMDB indicates authoritative status: '{indicator}'"
                )
    
    return None


def _check_known_sor_vendor(asset: Asset) -> Optional[SORSignal]:
    """Check if asset matches known SOR vendor patterns"""
    
    domains = asset.identifiers.domains if asset.identifiers else []
    vendor = asset.vendor or ""
    name = asset.name.lower()
    
    config = get_sor_policy_config()
    known_vendors = config.get("known_sor_vendors", KNOWN_SOR_VENDORS)
    weights = config.get("weights", {})
    weight = weights.get("known_sor_vendor", 30)
    
    for data_domain, vendor_domains in known_vendors.items():
        for vendor_domain in vendor_domains:
            vendor_base = vendor_domain.replace('.com', '').replace('.io', '')
            
            for domain in domains:
                if vendor_domain in domain or vendor_base in domain:
                    return SORSignal(
                        name="known_sor_vendor",
                        weight=weight,
                        evidence=f"Matches known SOR vendor: {vendor_domain}",
                        domain=data_domain
                    )
            
            if vendor_base in vendor.lower() or vendor_base in name:
                return SORSignal(
                    name="known_sor_vendor",
                    weight=weight,
                    evidence=f"Vendor/name matches SOR pattern: {vendor_base}",
                    domain=data_domain
                )
    
    return None


def _check_middleware_exporter(
    asset: Asset,
    middleware_routes: Optional[list[dict]] = None
) -> Optional[SORSignal]:
    """Check if asset is a data source/exporter in middleware topology"""
    
    if not middleware_routes:
        return None
    
    config = get_sor_policy_config()
    weights = config.get("weights", {})
    weight = weights.get("middleware_exporter", 25)
    
    domains = asset.identifiers.domains if asset.identifiers else []
    asset_name = asset.name.lower()
    
    exporter_count = 0
    
    for route in middleware_routes:
        source = route.get("source", {})
        source_system = source.get("system", "").lower()
        source_url = source.get("url", "").lower()
        
        for domain in domains:
            if domain in source_url or domain.split('.')[0] in source_system:
                exporter_count += 1
                break
        
        if asset_name in source_system:
            exporter_count += 1
    
    if exporter_count > 0:
        return SORSignal(
            name="middleware_exporter",
            weight=weight,
            evidence=f"Data exporter in {exporter_count} middleware route(s)"
        )
    
    return None


def _check_enterprise_sso_scim(
    asset: Asset,
    idp_records: Optional[list[Any]] = None
) -> Optional[SORSignal]:
    """Check if asset has both SSO and SCIM (enterprise-wide indicator)"""
    
    if not asset.lens_coverage.idp:
        return None
    
    has_sso = False
    has_scim = False
    
    if idp_records:
        for record in idp_records:
            if hasattr(record, 'has_sso') and record.has_sso:
                has_sso = True
            if hasattr(record, 'has_scim') and record.has_scim:
                has_scim = True
    
    if not has_sso and asset.lens_match_debug and asset.lens_match_debug.idp:
        has_sso = True
    
    if not has_sso and hasattr(asset, 'activity_evidence'):
        has_sso = asset.activity_evidence.idp_governance_aligned
    
    config = get_sor_policy_config()
    weights = config.get("weights", {})
    full_weight = weights.get("enterprise_sso_scim", 20)
    
    if has_sso and has_scim:
        return SORSignal(
            name="enterprise_sso_scim",
            weight=full_weight,
            evidence="Both SSO and SCIM enabled (enterprise-wide deployment)"
        )
    elif has_sso:
        return SORSignal(
            name="enterprise_sso_scim",
            weight=full_weight // 2,
            evidence="SSO enabled (partial enterprise signal)"
        )
    
    return None


def _check_enterprise_contract(
    asset: Asset,
    finance_record: Optional[Any] = None
) -> Optional[SORSignal]:
    """Check for enterprise-level financial commitment"""
    
    if not asset.lens_coverage.finance:
        return None
    
    config = get_sor_policy_config()
    weights = config.get("weights", {})
    weight = weights.get("enterprise_contract", 15)
    
    if finance_record:
        annual_spend = getattr(finance_record, 'annual_spend', 0) or 0
        monthly_spend = getattr(finance_record, 'monthly_spend', 0) or 0
        contract_type = getattr(finance_record, 'contract_type', '') or ''
        
        effective_annual = annual_spend or (monthly_spend * 12)
        
        if effective_annual >= 50000 or 'enterprise' in contract_type.lower():
            return SORSignal(
                name="enterprise_contract",
                weight=weight,
                evidence=f"Enterprise contract: ${effective_annual:,.0f}/year"
            )
    
    return None


def _check_high_corroboration(asset: Asset) -> Optional[SORSignal]:
    """Check if asset has high cross-source corroboration"""
    
    config = get_sor_policy_config()
    weights = config.get("weights", {})
    weight = weights.get("high_corroboration", 10)
    
    source_count = 0
    
    if asset.lens_coverage:
        if asset.lens_coverage.idp:
            source_count += 1
        if asset.lens_coverage.cmdb:
            source_count += 1
        if asset.lens_coverage.cloud:
            source_count += 1
        if asset.lens_coverage.finance:
            source_count += 1
        if asset.lens_coverage.discovery:
            source_count += 1
    
    if source_count >= 4:
        return SORSignal(
            name="high_corroboration",
            weight=weight,
            evidence=f"Corroborated across {source_count} data sources"
        )
    
    return None


def _check_edge_app_penalty(asset: Asset) -> Optional[SORSignal]:
    """Check for edge app indicators that suggest NOT an SOR"""
    
    config = get_sor_policy_config()
    weights = config.get("weights", {})
    weight = weights.get("edge_app_penalty", -20)
    
    edge_indicators = []
    
    domains = asset.identifiers.domains if asset.identifiers else []
    for domain in domains:
        if any(tld in domain for tld in ['.io', '.app', '.dev', '.tools']):
            if not any(sor in domain for sor in ['salesforce', 'workday', 'oracle']):
                edge_indicators.append("niche TLD")
                break
    
    discovery_sources = getattr(asset, 'discovery_sources', []) or []
    if len(discovery_sources) == 1:
        edge_indicators.append("single discovery source")
    
    if edge_indicators:
        return SORSignal(
            name="edge_app_penalty",
            weight=weight,
            evidence=f"Edge app indicators: {', '.join(edge_indicators)}"
        )
    
    return None


def score_sor(
    asset: Asset,
    cmdb_record: Optional[Any] = None,
    finance_record: Optional[Any] = None,
    middleware_routes: Optional[list[dict]] = None,
    idp_records: Optional[list[Any]] = None
) -> SORScoringResult:
    """
    Score an asset for System of Record likelihood.
    
    Args:
        asset: The asset to score
        cmdb_record: Optional CMDB record for deeper inspection
        finance_record: Optional finance record for contract analysis
        middleware_routes: Optional middleware routes for topology analysis
        
    Returns:
        SORScoringResult with likelihood, confidence, and evidence
    """
    config = get_sor_policy_config()
    
    if not config.get("enabled", True):
        return SORScoringResult(
            likelihood="none",
            confidence=0.0,
            evidence=["SOR scoring disabled by policy"]
        )
    
    weights = config.get("weights", {})
    thresholds = config.get("confidence_thresholds", {"high": 0.75, "medium": 0.50})
    
    signals: list[SORSignal] = []
    
    signal = _check_cmdb_authoritative(asset, cmdb_record)
    if signal:
        signals.append(signal)
    
    signal = _check_known_sor_vendor(asset)
    if signal:
        signals.append(signal)
    
    signal = _check_middleware_exporter(asset, middleware_routes)
    if signal:
        signals.append(signal)
    
    signal = _check_enterprise_sso_scim(asset, idp_records)
    if signal:
        signals.append(signal)
    
    signal = _check_enterprise_contract(asset, finance_record)
    if signal:
        signals.append(signal)
    
    signal = _check_high_corroboration(asset)
    if signal:
        signals.append(signal)
    
    signal = _check_edge_app_penalty(asset)
    if signal:
        signals.append(signal)
    
    raw_score = sum(s.weight for s in signals)
    max_possible = sum(w for w in weights.values() if w > 0)
    
    if max_possible > 0:
        confidence = max(0.0, min(1.0, raw_score / max_possible))
    else:
        confidence = 0.0
    
    if confidence >= thresholds.get("high", 0.75):
        likelihood = "high"
    elif confidence >= thresholds.get("medium", 0.50):
        likelihood = "medium"
    elif confidence > 0:
        likelihood = "low"
    else:
        likelihood = "none"
    
    domains_detected = [s.domain for s in signals if s.domain]
    primary_domain = domains_detected[0] if domains_detected else None
    
    return SORScoringResult(
        likelihood=likelihood,
        confidence=round(confidence, 3),
        evidence=[s.evidence for s in signals],
        domain=primary_domain,
        raw_score=raw_score,
        max_possible_score=max_possible,
        signals_matched=[s.name for s in signals]
    )


def batch_score_sor(
    assets: list[Asset],
    middleware_routes: Optional[list[dict]] = None
) -> dict[str, SORScoringResult]:
    """
    Score multiple assets for SOR likelihood.
    
    Returns dict mapping asset_id -> SORScoringResult
    """
    results = {}
    
    for asset in assets:
        result = score_sor(
            asset=asset,
            middleware_routes=middleware_routes
        )
        results[str(asset.asset_id)] = result
    
    return results
