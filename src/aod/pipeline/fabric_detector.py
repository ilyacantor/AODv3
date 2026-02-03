"""
Fabric Plane Detector - Identify Control Planes (Motherships) from observations.

STRATEGIC PRIORITY: Find the Control Planes FIRST.
Finding 500 APIs is useless if they're all managed by one MuleSoft instance.

The 4 Fabric Planes:
1. IPAAS: (Workato, MuleSoft) -> Control plane for integration flows
2. API_GATEWAY: (Kong, Apigee) -> Direct managed API access
3. EVENT_BUS: (Kafka, EventBridge) -> Streaming backbone
4. DATA_WAREHOUSE: (Snowflake, BigQuery) -> Source of Truth storage

AAM connects ONLY to Fabric Planes (not individual apps) unless in Preset 6 (Scrappy) mode.
"""

import logging
from typing import Optional

from ..models.output_contracts import (
    Asset, FabricPlane, FabricPlaneType, FabricPlaneTag
)

logger = logging.getLogger(__name__)

FABRIC_VENDORS: dict[FabricPlaneType, dict[str, list[str]]] = {
    FabricPlaneType.IPAAS: {
        "mulesoft": ["mulesoft.com", "anypoint.mulesoft.com", "cloudhub.io"],
        "workato": ["workato.com"],
        "boomi": ["boomi.com", "boomi.dell.com"],
        "tray": ["tray.io"],
        "zapier": ["zapier.com"],
        "make": ["make.com", "integromat.com"],
        "snaplogic": ["snaplogic.com"],
        "celigo": ["celigo.com"],
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


def _match_vendor(
    domains: list[str],
    vendor_str: str,
    plane_type: FabricPlaneType,
    vendors: dict[str, list[str]]
) -> tuple[Optional[str], Optional[str]]:
    """
    Check if domains or vendor string match a fabric plane vendor.
    
    Returns (vendor_name, matched_domain) or (None, None)
    """
    for vendor_name, vendor_domains in vendors.items():
        for domain in domains:
            domain_lower = domain.lower()
            for vd in vendor_domains:
                if vd in domain_lower or domain_lower.endswith(vd):
                    return vendor_name, domain
        
        if vendor_name.replace("_", "") in vendor_str or vendor_name in vendor_str:
            return vendor_name, None
    
    return None, None


def detect_fabric_planes(
    assets: list[Asset]
) -> tuple[list[FabricPlane], dict[str, FabricPlaneTag]]:
    """
    Detect Fabric Control Planes from discovered assets.
    
    Strategic priority: Identify the motherships that aggregate data.
    Individual app connections only happen in Preset 6 (Scrappy) mode.
    
    Returns:
        - List of detected FabricPlane objects (the motherships)
        - Dict mapping asset_id -> FabricPlaneTag for plane controllers
    """
    detected_planes: dict[str, FabricPlane] = {}
    asset_plane_tags: dict[str, FabricPlaneTag] = {}
    
    for asset in assets:
        domains = asset.identifiers.domains if asset.identifiers else []
        vendor_lower = (asset.vendor or "").lower()
        name_lower = (asset.name or "").lower()
        combined_str = f"{vendor_lower} {name_lower}"
        
        for plane_type, vendors in FABRIC_VENDORS.items():
            vendor_name, matched_domain = _match_vendor(
                domains, combined_str, plane_type, vendors
            )
            
            if vendor_name:
                plane_id = f"{plane_type.value}:{vendor_name}"
                
                if plane_id not in detected_planes:
                    detected_planes[plane_id] = FabricPlane(
                        plane_id=plane_id,
                        plane_type=plane_type,
                        vendor=vendor_name,
                        display_name=asset.name,
                        domain=matched_domain or (domains[0] if domains else None),
                        managed_asset_count=0,
                        evidence_refs=asset.evidence_refs[:5] if asset.evidence_refs else [],
                        confidence=0.85
                    )
                
                asset_plane_tags[str(asset.asset_id)] = FabricPlaneTag(
                    plane_type=plane_type,
                    controller_vendor=vendor_name,
                    controller_domain=matched_domain,
                    evidence=[f"Identified as {plane_type.value} control plane"],
                    confidence=0.9
                )
                
                logger.info("fabric_detector.plane_found", extra={
                    "asset_name": asset.name,
                    "plane_type": plane_type.value,
                    "vendor": vendor_name,
                    "domain": matched_domain
                })
                break
    
    for plane in detected_planes.values():
        plane.managed_asset_count = sum(
            1 for tag in asset_plane_tags.values()
            if tag.controller_vendor == plane.vendor
        )
    
    logger.info("fabric_detector.complete", extra={
        "planes_detected": len(detected_planes),
        "assets_tagged": len(asset_plane_tags)
    })
    
    return list(detected_planes.values()), asset_plane_tags


def _infer_downstream_fabric_tags(
    assets: list[Asset],
    detected_planes: list[FabricPlane]
) -> dict[str, FabricPlaneTag]:
    """
    Infer which fabric plane manages non-plane assets.
    
    Heuristic: If a fabric plane is detected, assume all assets of compatible
    type flow through that plane.
    
    Categories mapped to fabric planes:
    - CRM, ERP, Finance, HRIS → iPaaS (integration flows)
    - API, Gateway → API Gateway
    - Data, Analytics, BI → Data Warehouse
    - Messaging, Stream → Event Bus
    """
    downstream_tags: dict[str, FabricPlaneTag] = {}
    
    # Build map of available planes by type
    planes_by_type: dict[FabricPlaneType, FabricPlane] = {}
    for plane in detected_planes:
        if plane.plane_type not in planes_by_type:
            planes_by_type[plane.plane_type] = plane
    
    # Map asset categories to fabric plane types
    category_to_plane: dict[str, FabricPlaneType] = {
        "crm": FabricPlaneType.IPAAS,
        "erp": FabricPlaneType.IPAAS,
        "finance": FabricPlaneType.IPAAS,
        "hcm": FabricPlaneType.IPAAS,
        "hris": FabricPlaneType.IPAAS,
        "itsm": FabricPlaneType.IPAAS,
        "marketing": FabricPlaneType.IPAAS,
        "sales": FabricPlaneType.IPAAS,
        
        "api": FabricPlaneType.API_GATEWAY,
        "gateway": FabricPlaneType.API_GATEWAY,
        "rest": FabricPlaneType.API_GATEWAY,
        "graphql": FabricPlaneType.API_GATEWAY,
        
        "data": FabricPlaneType.DATA_WAREHOUSE,
        "analytics": FabricPlaneType.DATA_WAREHOUSE,
        "bi": FabricPlaneType.DATA_WAREHOUSE,
        "reporting": FabricPlaneType.DATA_WAREHOUSE,
        "warehouse": FabricPlaneType.DATA_WAREHOUSE,
        
        "messaging": FabricPlaneType.EVENT_BUS,
        "stream": FabricPlaneType.EVENT_BUS,
        "queue": FabricPlaneType.EVENT_BUS,
        "events": FabricPlaneType.EVENT_BUS,
    }
    
    for asset in assets:
        # Skip fabric planes themselves (already tagged)
        asset_id = str(asset.asset_id)
        if asset.fabric_plane_tag:
            continue
        
        # Infer category from vendor/name
        vendor_lower = (asset.vendor or "").lower()
        name_lower = (asset.name or "").lower()
        combined = f"{vendor_lower} {name_lower}"
        
        inferred_category = None
        for category_key in category_to_plane.keys():
            if category_key in combined:
                inferred_category = category_key
                break
        
        # Default: if no category match, assume iPaaS (most common)
        if not inferred_category and planes_by_type.get(FabricPlaneType.IPAAS):
            inferred_category = "crm"  # Force iPaaS for unknown
        
        if inferred_category:
            plane_type = category_to_plane[inferred_category]
            plane = planes_by_type.get(plane_type)
            
            if plane:
                downstream_tags[asset_id] = FabricPlaneTag(
                    plane_type=plane.plane_type,
                    controller_vendor=plane.vendor,
                    controller_domain=plane.domain,
                    evidence=[f"Inferred {inferred_category} asset routes through {plane.vendor}"],
                    confidence=0.7
                )
                
                logger.debug("fabric_detector.downstream_tagged", extra={
                    "asset": asset.name,
                    "category": inferred_category,
                    "plane_vendor": plane.vendor,
                    "plane_type": plane.plane_type.value
                })
    
    logger.info("fabric_detector.downstream_inference", extra={
        "assets_tagged": len(downstream_tags),
        "planes_available": len(planes_by_type)
    })
    
    return downstream_tags


def apply_fabric_plane_tags(
    assets: list[Asset],
    asset_plane_tags: dict[str, FabricPlaneTag]
) -> list[Asset]:
    """
    Apply fabric plane tags to assets.
    
    NEW: Also infers tags for downstream assets based on detected planes.
    """
    # First pass: tag fabric planes themselves
    detected_planes: list[FabricPlane] = []
    for asset in assets:
        asset_id = str(asset.asset_id)
        if asset_id in asset_plane_tags:
            asset.fabric_plane_tag = asset_plane_tags[asset_id]
            # Build list of detected planes for inference
            tag = asset_plane_tags[asset_id]
            plane_id = f"{tag.plane_type.value}:{tag.controller_vendor}"
            if not any(p.plane_id == plane_id for p in detected_planes):
                detected_planes.append(FabricPlane(
                    plane_id=plane_id,
                    plane_type=tag.plane_type,
                    vendor=tag.controller_vendor,
                    display_name=asset.name,
                    domain=tag.controller_domain,
                    managed_asset_count=0,
                    confidence=tag.confidence
                ))
    
    # Second pass: infer downstream tags
    downstream_tags = _infer_downstream_fabric_tags(assets, detected_planes)
    
    for asset in assets:
        asset_id = str(asset.asset_id)
        if asset_id in downstream_tags and not asset.fabric_plane_tag:
            asset.fabric_plane_tag = downstream_tags[asset_id]
    
    return assets
