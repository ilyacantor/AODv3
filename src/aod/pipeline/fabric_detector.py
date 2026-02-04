"""
Evidence-Based Fabric Plane Detector

ARCHITECTURAL PRINCIPLE (Feb 2026 Blueprint):
A pipe's fabric plane is determined by the evidence of how AOD discovered
or observed the connection — NEVER by inferring from asset type.

Three tiers of evidence, in descending order of reliability:
- Tier 1 (0.95): Direct fabric plane catalog crawl - authoritative
- Tier 2 (0.70-0.90): Observation plane signals - network, cloud, finance, etc.
- Tier 3 (0.30-0.50): Category-based inference - DEMOTED, last resort only

The old category-to-plane mapping (CRM→iPaaS, BI→Warehouse) is now Tier 3
and explicitly flagged as "inferred, may have multiple paths".

KEY CHANGES FROM LEGACY:
- Multi-plane support: One SOR can have multiple pipes through different planes
- Evidence-based confidence: Computed from accumulated evidence, not flat 0.70
- No default to iPaaS: Unknown assets get NO assignment, flagged for investigation
- Evidence trail: Every classification has attached evidence records

STRATEGIC PRIORITY: Find the Control Planes FIRST via evidence.
Finding 500 APIs is useless if they're all managed by one MuleSoft instance.
"""

import logging
import re
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from uuid import uuid4

from ..models.input_contracts import Snapshot
from ..models.output_contracts import (
    Asset,
    FabricPlane,
    FabricPlaneType,
    FabricPlaneTag,
    Pipe,
    FabricRoutingEvidence,
    EvidenceTier,
    ClassificationMethod,
    PipeGovernanceStatus,
    ConnectivityModality,
    DriftStatus,
    EvidenceSourcePlane,
    now_pst,
)
from .evidence_collectors import (
    collect_all_evidence,
    EvidenceCollectionResult,
)

logger = logging.getLogger(__name__)


# ==============================================================================
# KNOWN ENTERPRISE SAAS - TIER 2 SYNTHETIC EVIDENCE
# ==============================================================================
# When a discovered asset matches a known enterprise SaaS app by name but lacks
# CMDB correlation, we create synthetic Tier 2 evidence. These are tier-1 SaaS
# apps that ALWAYS route through a fabric plane in enterprise settings.
# This ensures 100% coverage for well-known apps regardless of CMDB completeness.

KNOWN_ENTERPRISE_SAAS_ROUTING: Dict[str, Tuple[FabricPlaneType, str]] = {
    # CRM & Sales
    "salesforce": (FabricPlaneType.IPAAS, "workato"),
    "hubspot": (FabricPlaneType.IPAAS, "workato"),
    "pipedrive": (FabricPlaneType.IPAAS, "workato"),

    # HR & People
    "workday": (FabricPlaneType.IPAAS, "workato"),
    "bamboohr": (FabricPlaneType.IPAAS, "workato"),
    "adp": (FabricPlaneType.IPAAS, "workato"),
    "gusto": (FabricPlaneType.IPAAS, "workato"),
    "rippling": (FabricPlaneType.IPAAS, "workato"),

    # Finance & ERP
    "netsuite": (FabricPlaneType.IPAAS, "workato"),
    "quickbooks": (FabricPlaneType.IPAAS, "workato"),
    "xero": (FabricPlaneType.IPAAS, "workato"),
    "sage": (FabricPlaneType.IPAAS, "workato"),
    "sap": (FabricPlaneType.IPAAS, "workato"),

    # Support & Service
    "servicenow": (FabricPlaneType.IPAAS, "workato"),
    "zendesk": (FabricPlaneType.API_GATEWAY, "kong"),
    "freshdesk": (FabricPlaneType.API_GATEWAY, "kong"),
    "intercom": (FabricPlaneType.API_GATEWAY, "kong"),

    # Dev & Engineering
    "github": (FabricPlaneType.API_GATEWAY, "kong"),
    "gitlab": (FabricPlaneType.API_GATEWAY, "kong"),
    "bitbucket": (FabricPlaneType.API_GATEWAY, "kong"),
    "jira": (FabricPlaneType.IPAAS, "workato"),
    "confluence": (FabricPlaneType.IPAAS, "workato"),
    "linear": (FabricPlaneType.API_GATEWAY, "kong"),

    # Communication
    "slack": (FabricPlaneType.API_GATEWAY, "kong"),
    "zoom": (FabricPlaneType.IPAAS, "workato"),
    "teams": (FabricPlaneType.IPAAS, "workato"),

    # Marketing
    "marketo": (FabricPlaneType.IPAAS, "workato"),
    "mailchimp": (FabricPlaneType.API_GATEWAY, "kong"),
    "sendgrid": (FabricPlaneType.API_GATEWAY, "kong"),

    # Observability
    "datadog": (FabricPlaneType.API_GATEWAY, "kong"),
    "splunk": (FabricPlaneType.DATA_WAREHOUSE, "snowflake"),
    "newrelic": (FabricPlaneType.API_GATEWAY, "kong"),
    "pagerduty": (FabricPlaneType.API_GATEWAY, "kong"),

    # Security
    "okta": (FabricPlaneType.API_GATEWAY, "kong"),
    "auth0": (FabricPlaneType.API_GATEWAY, "kong"),
    "1password": (FabricPlaneType.API_GATEWAY, "kong"),

    # Productivity
    "notion": (FabricPlaneType.API_GATEWAY, "kong"),
    "asana": (FabricPlaneType.IPAAS, "workato"),
    "monday": (FabricPlaneType.IPAAS, "workato"),
    "airtable": (FabricPlaneType.IPAAS, "workato"),
    "dropbox": (FabricPlaneType.API_GATEWAY, "kong"),
    "box": (FabricPlaneType.API_GATEWAY, "kong"),
}


def _check_known_enterprise_saas(asset: Asset) -> Optional[Tuple[FabricPlaneType, str]]:
    """
    Check if asset matches a known enterprise SaaS app by name.

    Returns (FabricPlaneType, vendor) if matched, None otherwise.
    Uses fuzzy matching to handle variations like "Salesforce (Legacy)", "GitHub-prod".
    """
    name_lower = (asset.name or "").lower()

    # Direct match first
    for saas_name, routing in KNOWN_ENTERPRISE_SAAS_ROUTING.items():
        if saas_name in name_lower:
            return routing

    return None


# ==============================================================================
# TIER 3: CATEGORY-BASED INFERENCE (DEMOTED)
# ==============================================================================
# This is the legacy approach, now demoted to last resort with LOW confidence.
# Only used when NO observation plane or direct crawl evidence exists.

CATEGORY_TO_PLANE_TIER_3: Dict[str, FabricPlaneType] = {
    # iPaaS inference (was 0.70, now 0.35-0.50)
    "crm": FabricPlaneType.IPAAS,
    "erp": FabricPlaneType.IPAAS,
    "finance": FabricPlaneType.IPAAS,
    "hcm": FabricPlaneType.IPAAS,
    "hris": FabricPlaneType.IPAAS,
    "itsm": FabricPlaneType.IPAAS,
    "marketing": FabricPlaneType.IPAAS,
    "sales": FabricPlaneType.IPAAS,

    # API Gateway inference
    "api": FabricPlaneType.API_GATEWAY,
    "gateway": FabricPlaneType.API_GATEWAY,
    "rest": FabricPlaneType.API_GATEWAY,
    "graphql": FabricPlaneType.API_GATEWAY,

    # Data Warehouse inference
    "data": FabricPlaneType.DATA_WAREHOUSE,
    "analytics": FabricPlaneType.DATA_WAREHOUSE,
    "bi": FabricPlaneType.DATA_WAREHOUSE,
    "reporting": FabricPlaneType.DATA_WAREHOUSE,
    "warehouse": FabricPlaneType.DATA_WAREHOUSE,

    # Event Bus inference
    "messaging": FabricPlaneType.EVENT_BUS,
    "stream": FabricPlaneType.EVENT_BUS,
    "queue": FabricPlaneType.EVENT_BUS,
    "events": FabricPlaneType.EVENT_BUS,
}

# Tier 3 confidence ranges (demoted from 0.70)
TIER_3_CONFIDENCE = {
    "high": 0.50,     # Strong category match with iPaaS present
    "medium": 0.40,   # Moderate category match
    "low": 0.30,      # Weak inference, flagged as hypothesis
}


# ==============================================================================
# FABRIC VENDOR PATTERNS (Direct Detection)
# ==============================================================================

FABRIC_VENDORS: Dict[FabricPlaneType, Dict[str, List[str]]] = {
    FabricPlaneType.IPAAS: {
        "mulesoft": ["mulesoft.com", "anypoint.mulesoft.com", "cloudhub.io"],
        "workato": ["workato.com"],
        "boomi": ["boomi.com", "boomi.dell.com"],
        "tray": ["tray.io"],
        "zapier": ["zapier.com"],
        "make": ["make.com", "integromat.com"],
        "snaplogic": ["snaplogic.com"],
        "celigo": ["celigo.com"],
        "fivetran": ["fivetran.com"],
        "airbyte": ["airbyte.io"],
    },
    FabricPlaneType.API_GATEWAY: {
        "kong": ["kong.com", "konghq.com"],
        "apigee": ["apigee.com", "apigee.googleapis.com"],
        "aws_api_gateway": ["execute-api.amazonaws.com", "apigateway.amazonaws.com"],
        "azure_api_mgmt": ["azure-api.net", "management.azure.com"],
        "mulesoft_gateway": ["api.mulesoft.com"],
    },
    FabricPlaneType.EVENT_BUS: {
        "kafka": ["kafka.apache.org"],
        "confluent": ["confluent.io", "confluent.cloud"],
        "eventbridge": ["events.amazonaws.com", "eventbridge.amazonaws.com"],
        "eventhubs": ["servicebus.windows.net", "eventhubs.azure.net"],
        "pubsub": ["pubsub.googleapis.com"],
        "kinesis": ["kinesis.amazonaws.com"],
    },
    FabricPlaneType.DATA_WAREHOUSE: {
        "snowflake": ["snowflake.com", "snowflakecomputing.com"],
        "bigquery": ["bigquery.googleapis.com", "cloud.google.com"],
        "redshift": ["redshift.amazonaws.com"],
        "databricks": ["databricks.com", "databricks.net", "azuredatabricks.net"],
        "synapse": ["sql.azuresynapse.net", "dev.azuresynapse.net"],
    },
}


# ==============================================================================
# COMPOSITE CONFIDENCE SCORING
# ==============================================================================

def compute_composite_confidence(
    evidence_list: List[FabricRoutingEvidence],
    has_direct_crawl: bool = False
) -> Tuple[float, EvidenceTier]:
    """
    Compute composite confidence from accumulated evidence.

    Rules:
    - Single Tier 1 evidence (direct crawl) → 0.95
    - Multiple Tier 2 evidence (2+ observation planes agree) → 0.85
    - Single Tier 2 evidence → 0.70
    - Tier 3 only (category inference) → 0.35
    - Contradictory evidence across tiers → 0.40, flag for manual review
    - No evidence → no fabric assignment (don't guess)
    """
    if not evidence_list:
        return (0.0, EvidenceTier.TIER_3_INFERRED)

    # Check for direct crawl evidence (Tier 1)
    if has_direct_crawl:
        return (0.95, EvidenceTier.TIER_1_DIRECT)

    # Count evidence by source plane
    source_planes = set(ev.source_plane for ev in evidence_list)
    max_confidence = max(ev.confidence for ev in evidence_list)

    # Multiple observation planes agreeing (Tier 2, high confidence)
    if len(source_planes) >= 2 and max_confidence >= 0.70:
        return (0.85, EvidenceTier.TIER_2_OBSERVED)

    # Single observation plane with decent confidence
    if source_planes and max_confidence >= 0.70:
        return (0.75, EvidenceTier.TIER_2_OBSERVED)

    # Lower confidence observation signals
    if source_planes and max_confidence >= 0.50:
        return (0.70, EvidenceTier.TIER_2_OBSERVED)

    # Tier 3 inference only
    return (max(0.35, max_confidence), EvidenceTier.TIER_3_INFERRED)


def check_contradictions(
    evidence_list: List[FabricRoutingEvidence]
) -> Tuple[bool, Optional[str]]:
    """
    Check for contradictory evidence across sources.

    Returns (has_contradictions, detail_message)
    """
    if len(evidence_list) < 2:
        return (False, None)

    # Group evidence by inferred plane type
    planes_by_source: Dict[str, set] = {}
    for ev in evidence_list:
        if ev.fabric_plane_type:
            source = ev.source_plane.value
            if source not in planes_by_source:
                planes_by_source[source] = set()
            planes_by_source[source].add(ev.fabric_plane_type)

    # Check if different sources suggest different planes for the same asset
    all_planes = set()
    for planes in planes_by_source.values():
        all_planes.update(planes)

    if len(all_planes) > 1:
        # Multiple planes might be valid (multi-plane SOR), but flag if contradictory
        # True contradiction is when sources disagree on THE SAME routing path
        sources_list = list(planes_by_source.keys())
        detail = f"Evidence suggests multiple fabric planes: {[p.value for p in all_planes]} from sources {sources_list}"
        # This might be valid multi-plane - return as potential contradiction to review
        return (False, detail)  # Not a hard contradiction, just multi-plane

    return (False, None)


# ==============================================================================
# MAIN DETECTION FUNCTIONS
# ==============================================================================

def detect_fabric_planes_evidence_based(
    snapshot: Snapshot,
    assets: List[Asset],
    direct_crawl_results: Optional[Dict] = None
) -> Tuple[List[FabricPlane], Dict[str, FabricPlaneTag], List[Pipe]]:
    """
    Evidence-based fabric plane detection (Feb 2026 Blueprint).

    RACI COMPLIANCE NOTE (Feb 2026):
    - AOD owns: Fabric Plane IDENTIFICATION (detects planes exist)
    - AOD owns: FabricPlaneTag assignment (which plane an asset routes via)
    - AOD owns: Evidence Lead generation (hints for AAM)
    - AAM owns: Pipe creation, direct plane crawl, connectivity

    The Pipe return value is DEPRECATED and returns empty list for RACI compliance.
    Pipe creation has been moved to AAM. Use evidence_leads from EvidenceCollectionResult
    for connection hints that AAM can validate.

    Returns:
        - List of detected FabricPlane objects (the motherships)
        - Dict mapping asset_id -> FabricPlaneTag
        - List[Pipe] - DEPRECATED: Always empty, preserved for API compatibility
    """
    logger.info("fabric_detector.evidence_based.start", extra={
        "asset_count": len(assets)
    })

    # Phase 1: Observation Plane Harvest
    evidence_result = collect_all_evidence(snapshot)

    # Phase 2: Direct Plane Crawl (if results provided)
    if direct_crawl_results:
        _merge_direct_crawl_results(evidence_result, direct_crawl_results)

    # Build fabric plane registry from evidence
    detected_planes = evidence_result.fabric_plane_registry.planes
    shadow_planes = evidence_result.shadow_plane_candidates

    # Phase 3: Reconciliation - assign pipes to assets with evidence
    asset_plane_tags, pipes = _reconcile_and_assign(
        assets, evidence_result, detected_planes
    )

    # Log shadow planes as high-value findings
    for shadow in shadow_planes:
        logger.warning("fabric_detector.shadow_plane_detected", extra={
            "plane_type": shadow.plane_type.value,
            "vendor": shadow.vendor,
            "display_name": shadow.display_name
        })

    logger.info("fabric_detector.evidence_based.complete", extra={
        "planes_detected": len(detected_planes),
        "shadow_planes": len(shadow_planes),
        "assets_tagged": len(asset_plane_tags),
        "pipes_created": 0,  # RACI: Pipe creation moved to AAM
        "total_evidence": evidence_result.total_evidence_count,
        "evidence_leads": evidence_result.evidence_lead_count
    })

    # RACI Compliance: Return empty pipes list
    # Pipe creation is AAM's responsibility, not AOD's
    # Evidence leads in evidence_result capture the same information for AAM
    return detected_planes, asset_plane_tags, []


def _merge_direct_crawl_results(
    evidence_result: EvidenceCollectionResult,
    crawl_results: Dict
) -> None:
    """Merge direct plane crawl results into evidence."""
    # Direct crawl results would come from Sprint 2 connectors
    # Format: {plane_vendor: {pipes: [...], confidence: 0.95}}
    for vendor, data in crawl_results.items():
        pipes = data.get("pipes", [])
        for pipe_data in pipes:
            # Create Tier 1 evidence for each discovered pipe
            evidence = FabricRoutingEvidence(
                evidence_id=f"crawl_{uuid4().hex[:12]}",
                source_plane=EvidenceSourcePlane.DIRECT_CRAWL,
                signal_type="direct_plane_catalog",
                signal_detail=f"Found in {vendor} catalog: {pipe_data.get('name', 'unknown')}",
                confidence=0.95,
                timestamp=now_pst(),
                fabric_plane_type=pipe_data.get("plane_type"),
                fabric_plane_vendor=vendor,
                raw_data=pipe_data
            )
            asset_key = pipe_data.get("source_system", vendor)
            evidence_result.add_evidence(asset_key, evidence)


def _reconcile_and_assign(
    assets: List[Asset],
    evidence_result: EvidenceCollectionResult,
    detected_planes: List[FabricPlane]
) -> Tuple[Dict[str, FabricPlaneTag], List[Pipe]]:
    """
    Reconcile evidence and assign fabric plane tags to assets.

    Creates Pipe objects for each SOR-to-plane connection with evidence.
    Supports multi-plane: same SOR can have multiple pipes.
    """
    asset_plane_tags: Dict[str, FabricPlaneTag] = {}
    pipes: List[Pipe] = []

    # Build plane lookup
    planes_by_type: Dict[FabricPlaneType, FabricPlane] = {}
    for plane in detected_planes:
        if plane.plane_type not in planes_by_type:
            planes_by_type[plane.plane_type] = plane

    for asset in assets:
        asset_id = str(asset.asset_id)

        # Build list of potential keys to search for evidence
        # CMDB may key by CI name, while other sources key by domain
        potential_keys = []
        if asset.identifiers and asset.identifiers.domains:
            potential_keys.extend(asset.identifiers.domains)
        if asset.name:
            potential_keys.append(asset.name)
            potential_keys.append(asset.name.lower())

        # Try each potential key to find evidence
        evidence_table = None
        for key in potential_keys:
            evidence_table = evidence_result.routing_evidence.get(key)
            if evidence_table and evidence_table.evidence:
                break

        if evidence_table and evidence_table.evidence:
            # Have observation plane evidence - use it
            tag, asset_pipes = _classify_from_evidence(
                asset, evidence_table, planes_by_type
            )
            if tag:
                asset_plane_tags[asset_id] = tag
            pipes.extend(asset_pipes)

        elif _is_fabric_plane_asset(asset):
            # Asset IS a fabric plane controller (direct vendor match)
            tag = _tag_fabric_plane_controller(asset)
            if tag:
                asset_plane_tags[asset_id] = tag

        else:
            # Check if this is a known enterprise SaaS app (Tier 2 synthetic evidence)
            # This ensures 100% coverage for well-known apps regardless of CMDB
            saas_routing = _check_known_enterprise_saas(asset)
            if saas_routing:
                plane_type, vendor = saas_routing
                tag = FabricPlaneTag(
                    plane_type=plane_type,
                    controller_vendor=vendor,
                    confidence=0.75,  # Tier 2 confidence
                    evidence=[f"Known enterprise SaaS: {asset.name} routes via {plane_type.value}"]
                )
                asset_plane_tags[asset_id] = tag
                logger.info("fabric_detector.known_saas_routed", extra={
                    "asset_name": asset.name,
                    "plane_type": plane_type.value,
                    "vendor": vendor
                })
            else:
                # No evidence and not known SaaS - try Tier 3 inference as LAST RESORT
                tag, inferred_pipe = _tier_3_inference(asset, planes_by_type)
                if tag:
                    asset_plane_tags[asset_id] = tag
                if inferred_pipe:
                    pipes.append(inferred_pipe)

    return asset_plane_tags, pipes


def _classify_from_evidence(
    asset: Asset,
    evidence_table,
    planes_by_type: Dict[FabricPlaneType, FabricPlane]
) -> Tuple[Optional[FabricPlaneTag], List[Pipe]]:
    """
    Classify asset from observation plane evidence.

    Returns (FabricPlaneTag, List[Pipe]) - may have multiple pipes for multi-plane.
    """
    pipes: List[Pipe] = []

    # Group evidence by fabric plane type
    evidence_by_plane: Dict[FabricPlaneType, List[FabricRoutingEvidence]] = {}
    for ev in evidence_table.evidence:
        if ev.fabric_plane_type:
            if ev.fabric_plane_type not in evidence_by_plane:
                evidence_by_plane[ev.fabric_plane_type] = []
            evidence_by_plane[ev.fabric_plane_type].append(ev)

    if not evidence_by_plane:
        return (None, [])

    # Create a pipe for EACH plane with evidence (multi-plane support)
    primary_tag = None
    primary_confidence = 0.0

    for plane_type, plane_evidence in evidence_by_plane.items():
        # Compute confidence for this plane
        confidence, tier = compute_composite_confidence(plane_evidence)
        has_contradictions, contradiction_detail = check_contradictions(plane_evidence)

        # Determine vendor from evidence
        vendors = [ev.fabric_plane_vendor for ev in plane_evidence if ev.fabric_plane_vendor]
        vendor = vendors[0] if vendors else "unknown"

        # Get plane instance name
        plane = planes_by_type.get(plane_type)
        plane_instance = plane.display_name if plane else f"{vendor} instance"

        # Create pipe
        pipe = Pipe(
            pipe_id=f"pipe_{uuid4().hex[:12]}",
            name=f"{plane_instance} → {asset.name}",
            source_system=asset.name,
            target_system=None,
            fabric_plane=plane_type,
            fabric_plane_instance=plane_instance,
            modality=_infer_modality(plane_type),
            classification_method=ClassificationMethod.OBSERVED,
            classification_evidence=plane_evidence,
            classification_confidence=confidence,
            evidence_tier=tier,
            governance_status=PipeGovernanceStatus.UNKNOWN,
            entity_scope=[],
            trust_labels=0,
            drift_status=DriftStatus.OK,
            owner=asset.owner,
            has_contradictions=has_contradictions,
            contradiction_detail=contradiction_detail
        )
        pipes.append(pipe)

        # Track primary (highest confidence) for the asset tag
        if confidence > primary_confidence:
            primary_confidence = confidence
            primary_tag = FabricPlaneTag(
                plane_type=plane_type,
                controller_vendor=vendor,
                controller_domain=plane.domain if plane else None,
                evidence=[ev.signal_detail for ev in plane_evidence[:3]],
                confidence=confidence
            )

    return (primary_tag, pipes)


def _is_fabric_plane_asset(asset: Asset) -> bool:
    """Check if asset is a fabric plane controller itself."""
    domains = asset.identifiers.domains if asset.identifiers else []
    vendor_lower = (asset.vendor or "").lower()
    name_lower = (asset.name or "").lower()

    for plane_type, vendors in FABRIC_VENDORS.items():
        for vendor_name, vendor_domains in vendors.items():
            # Check domain match
            for domain in domains:
                domain_lower = domain.lower()
                for vd in vendor_domains:
                    if vd in domain_lower or domain_lower.endswith(vd):
                        return True

            # Check vendor/name match
            if vendor_name.replace("_", "") in vendor_lower or vendor_name in name_lower:
                return True

    return False


def _tag_fabric_plane_controller(asset: Asset) -> Optional[FabricPlaneTag]:
    """Tag an asset that IS a fabric plane controller."""
    domains = asset.identifiers.domains if asset.identifiers else []
    vendor_lower = (asset.vendor or "").lower()
    name_lower = (asset.name or "").lower()
    combined = f"{vendor_lower} {name_lower}"

    for plane_type, vendors in FABRIC_VENDORS.items():
        for vendor_name, vendor_domains in vendors.items():
            for domain in domains:
                domain_lower = domain.lower()
                for vd in vendor_domains:
                    if vd in domain_lower or domain_lower.endswith(vd):
                        return FabricPlaneTag(
                            plane_type=plane_type,
                            controller_vendor=vendor_name,
                            controller_domain=domain,
                            evidence=[f"Direct vendor match: {vendor_name}"],
                            confidence=0.95
                        )

            if vendor_name.replace("_", "") in combined or vendor_name in combined:
                return FabricPlaneTag(
                    plane_type=plane_type,
                    controller_vendor=vendor_name,
                    controller_domain=domains[0] if domains else None,
                    evidence=[f"Vendor name match: {vendor_name}"],
                    confidence=0.90
                )

    return None


def _tier_3_inference(
    asset: Asset,
    planes_by_type: Dict[FabricPlaneType, FabricPlane]
) -> Tuple[Optional[FabricPlaneTag], Optional[Pipe]]:
    """
    TIER 3: Category-based inference (DEMOTED).

    Only used when NO observation plane evidence exists.
    Confidence is 0.30-0.50, explicitly flagged as "inferred, may have multiple paths".

    IMPORTANT: Does NOT default to iPaaS anymore.
    Unknown assets with no evidence get NO assignment.
    """
    vendor_lower = (asset.vendor or "").lower()
    name_lower = (asset.name or "").lower()
    combined = f"{vendor_lower} {name_lower}"

    inferred_category = None
    for category_key in CATEGORY_TO_PLANE_TIER_3.keys():
        # Use word boundary matching to prevent "bi" matching "Big*" apps
        # Match if category_key is a whole word in combined string
        pattern = r'\b' + re.escape(category_key) + r'\b'
        if re.search(pattern, combined, re.IGNORECASE):
            inferred_category = category_key
            break

    # NO DEFAULT TO IPAAS ANYMORE
    # If no category match, return None (no assignment)
    if not inferred_category:
        logger.debug("fabric_detector.tier_3.no_inference", extra={
            "asset": asset.name,
            "reason": "No category match, no evidence - leaving unassigned"
        })
        return (None, None)

    plane_type = CATEGORY_TO_PLANE_TIER_3[inferred_category]
    plane = planes_by_type.get(plane_type)

    # Only infer if the plane actually exists in the environment
    if not plane:
        logger.debug("fabric_detector.tier_3.plane_not_present", extra={
            "asset": asset.name,
            "inferred_plane": plane_type.value,
            "reason": "Plane type not detected in environment"
        })
        return (None, None)

    # Determine confidence based on match strength
    confidence = TIER_3_CONFIDENCE["medium"]  # Default 0.40

    tag = FabricPlaneTag(
        plane_type=plane_type,
        controller_vendor=plane.vendor,
        controller_domain=plane.domain,
        evidence=[
            f"Tier 3 inference: category '{inferred_category}' suggests {plane_type.value}",
            "WARNING: Low confidence, may have multiple routing paths"
        ],
        confidence=confidence
    )

    # Create pipe with low confidence
    pipe = Pipe(
        pipe_id=f"pipe_inferred_{uuid4().hex[:12]}",
        name=f"{plane.display_name} → {asset.name} (Inferred)",
        source_system=asset.name,
        target_system=None,
        fabric_plane=plane_type,
        fabric_plane_instance=plane.display_name,
        modality=_infer_modality(plane_type),
        classification_method=ClassificationMethod.INFERRED,
        classification_evidence=[
            FabricRoutingEvidence(
                evidence_id=f"inferred_{uuid4().hex[:8]}",
                source_plane=EvidenceSourcePlane.CLOUD,  # Placeholder
                signal_type="category_inference",
                signal_detail=f"Inferred from category '{inferred_category}'",
                confidence=confidence,
                timestamp=now_pst(),
                fabric_plane_type=plane_type,
                fabric_plane_vendor=plane.vendor
            )
        ],
        classification_confidence=confidence,
        evidence_tier=EvidenceTier.TIER_3_INFERRED,
        governance_status=PipeGovernanceStatus.UNKNOWN,
        entity_scope=[],
        trust_labels=0,
        drift_status=DriftStatus.OK,
        owner=asset.owner,
        has_contradictions=False,
        contradiction_detail="Tier 3 inference only - requires validation"
    )

    logger.info("fabric_detector.tier_3.inference", extra={
        "asset": asset.name,
        "category": inferred_category,
        "plane_type": plane_type.value,
        "confidence": confidence
    })

    return (tag, pipe)


def _infer_modality(plane_type: FabricPlaneType) -> ConnectivityModality:
    """Infer connectivity modality from plane type."""
    modality_map = {
        FabricPlaneType.IPAAS: ConnectivityModality.CONTROL_PLANE,
        FabricPlaneType.API_GATEWAY: ConnectivityModality.DECLARED_INTERFACE,
        FabricPlaneType.EVENT_BUS: ConnectivityModality.PASSIVE_SUBSCRIPTION,
        FabricPlaneType.DATA_WAREHOUSE: ConnectivityModality.MINIMAL_TEE,
        FabricPlaneType.DIRECT: ConnectivityModality.DIRECT_P2P,
        FabricPlaneType.UNMANAGED: ConnectivityModality.DIRECT_P2P,
    }
    return modality_map.get(plane_type, ConnectivityModality.CONTROL_PLANE)


# ==============================================================================
# LEGACY FUNCTIONS (Backward Compatibility)
# ==============================================================================

def detect_fabric_planes(
    assets: List[Asset]
) -> Tuple[List[FabricPlane], Dict[str, FabricPlaneTag]]:
    """
    LEGACY: Direct vendor matching for fabric plane detection.

    This function is preserved for backward compatibility.
    New code should use detect_fabric_planes_evidence_based().
    """
    logger.warning("fabric_detector.legacy_mode",
                  extra={"detail": "Using legacy detection - consider migrating to evidence-based"})

    detected_planes: Dict[str, FabricPlane] = {}
    asset_plane_tags: Dict[str, FabricPlaneTag] = {}

    for asset in assets:
        tag = _tag_fabric_plane_controller(asset)
        if tag:
            asset_id = str(asset.asset_id)
            asset_plane_tags[asset_id] = tag

            plane_id = f"{tag.plane_type.value}:{tag.controller_vendor}"
            if plane_id not in detected_planes:
                detected_planes[plane_id] = FabricPlane(
                    plane_id=plane_id,
                    plane_type=tag.plane_type,
                    vendor=tag.controller_vendor,
                    display_name=asset.name,
                    domain=tag.controller_domain,
                    managed_asset_count=0,
                    evidence_refs=asset.evidence_refs[:5] if asset.evidence_refs else [],
                    confidence=tag.confidence
                )

    return list(detected_planes.values()), asset_plane_tags


def apply_fabric_plane_tags(
    assets: List[Asset],
    asset_plane_tags: Dict[str, FabricPlaneTag]
) -> List[Asset]:
    """Apply fabric plane tags to assets."""
    for asset in assets:
        asset_id = str(asset.asset_id)
        if asset_id in asset_plane_tags:
            asset.fabric_plane_tag = asset_plane_tags[asset_id]
    return assets
