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


def apply_fabric_plane_tags(
    assets: list[Asset],
    asset_plane_tags: dict[str, FabricPlaneTag]
) -> list[Asset]:
    """
    Apply fabric plane tags to assets.
    """
    for asset in assets:
        asset_id = str(asset.asset_id)
        if asset_id in asset_plane_tags:
            asset.fabric_plane_tag = asset_plane_tags[asset_id]
    
    return assets
