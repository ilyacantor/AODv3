"""
Preset Inference Engine - Determine Enterprise Integration Preset Pattern.

Enterprise Presets determine AAM's connection strategy:
- PRESET_6_SCRAPPY: Direct app connections (no fabric planes)
- PRESET_8_IPAAS: >50% assets via iPaaS (MuleSoft/Workato)
- PRESET_9_EVENT_DRIVEN: Kafka is primary integration bus
- PRESET_10_API_GATEWAY: API Gateway-centric (Kong/Apigee)
- PRESET_11_WAREHOUSE: Snowflake holds canonical data tables

AAM switches logic based on the detected preset.
"""

import logging
from typing import Optional

from ..models.output_contracts import (
    Asset, FabricPlane, FabricPlaneType, EnterprisePreset, PresetContext
)

logger = logging.getLogger(__name__)

PRESET_THRESHOLDS = {
    "ipaas_dominance": 0.50,       # >50% assets via iPaaS
    "warehouse_canonical": 0.30,   # >30% + canonical tables
    "event_bus_primary": 0.25,     # >25% via event bus
    "api_gateway_centric": 0.30,   # >30% via API gateway
    "scrappy_threshold": 0.10,     # <10% fabric = scrappy
}


def infer_preset(
    assets: list[Asset],
    fabric_planes: list[FabricPlane]
) -> PresetContext:
    """
    Infer Enterprise Preset pattern from Fabric Plane density.
    
    This determines how AAM should connect:
    - Scrappy orgs: Connect directly to apps
    - Mature orgs: Connect through fabric planes only
    
    Args:
        assets: All discovered assets
        fabric_planes: Detected fabric control planes
        
    Returns:
        PresetContext with preset classification and evidence
    """
    total_assets = max(len(assets), 1)
    
    plane_type_counts: dict[FabricPlaneType, int] = {pt: 0 for pt in FabricPlaneType}
    for asset in assets:
        if asset.fabric_plane_tag:
            plane_type_counts[asset.fabric_plane_tag.plane_type] += 1
    
    density_scores = {
        pt.value: round(count / total_assets, 3)
        for pt, count in plane_type_counts.items()
    }
    
    primary_vendor: Optional[str] = None
    primary_count = 0
    for plane in fabric_planes:
        if plane.managed_asset_count > primary_count:
            primary_count = plane.managed_asset_count
            primary_vendor = plane.vendor
    
    ipaas_density = density_scores.get("ipaas", 0)
    warehouse_density = density_scores.get("warehouse", 0)
    event_bus_density = density_scores.get("event_bus", 0)
    gateway_density = density_scores.get("api_gateway", 0)
    
    total_fabric_density = ipaas_density + warehouse_density + event_bus_density + gateway_density
    
    evidence: list[str] = []
    
    if total_fabric_density < PRESET_THRESHOLDS["scrappy_threshold"]:
        evidence.append(f"Total fabric density {total_fabric_density:.1%} < 10% threshold")
        return PresetContext(
            preset=EnterprisePreset.PRESET_6_SCRAPPY,
            confidence=0.8,
            rationale="Scrappy mode: No dominant fabric planes, direct app connections",
            density_scores=density_scores,
            primary_plane=None,
            evidence=evidence
        )
    
    if ipaas_density >= PRESET_THRESHOLDS["ipaas_dominance"]:
        evidence.append(f"iPaaS density {ipaas_density:.1%} >= 50% threshold")
        return PresetContext(
            preset=EnterprisePreset.PRESET_8_IPAAS,
            confidence=min(0.95, ipaas_density + 0.2),
            rationale=f"iPaaS-centric: {ipaas_density:.1%} of assets behind {primary_vendor or 'iPaaS'}",
            density_scores=density_scores,
            primary_plane=primary_vendor,
            evidence=evidence
        )
    
    if gateway_density >= PRESET_THRESHOLDS["api_gateway_centric"]:
        evidence.append(f"API Gateway density {gateway_density:.1%} >= 30% threshold")
        return PresetContext(
            preset=EnterprisePreset.PRESET_10_API_GATEWAY,
            confidence=min(0.9, gateway_density + 0.25),
            rationale=f"API Gateway-centric: {primary_vendor or 'gateway'} manages API access",
            density_scores=density_scores,
            primary_plane=primary_vendor,
            evidence=evidence
        )
    
    if warehouse_density >= PRESET_THRESHOLDS["warehouse_canonical"]:
        evidence.append(f"Warehouse density {warehouse_density:.1%} >= 30% threshold")
        return PresetContext(
            preset=EnterprisePreset.PRESET_11_WAREHOUSE,
            confidence=min(0.9, warehouse_density + 0.3),
            rationale=f"Warehouse-centric: {primary_vendor or 'warehouse'} holds canonical data",
            density_scores=density_scores,
            primary_plane=primary_vendor,
            evidence=evidence
        )
    
    if event_bus_density >= PRESET_THRESHOLDS["event_bus_primary"]:
        evidence.append(f"Event bus density {event_bus_density:.1%} >= 25% threshold")
        return PresetContext(
            preset=EnterprisePreset.PRESET_9_EVENT_DRIVEN,
            confidence=min(0.85, event_bus_density + 0.3),
            rationale=f"Event-driven: {primary_vendor or 'event bus'} is primary integration",
            density_scores=density_scores,
            primary_plane=primary_vendor,
            evidence=evidence
        )
    
    if total_fabric_density >= 0.2:
        evidence.append(f"Mixed fabric plane usage: {total_fabric_density:.1%} total")
        return PresetContext(
            preset=EnterprisePreset.PRESET_HYBRID,
            confidence=0.7,
            rationale="Hybrid integration pattern with multiple fabric planes",
            density_scores=density_scores,
            primary_plane=primary_vendor,
            evidence=evidence
        )
    
    return PresetContext(
        preset=EnterprisePreset.PRESET_UNKNOWN,
        confidence=0.4,
        rationale="Insufficient fabric plane presence to determine preset",
        density_scores=density_scores,
        primary_plane=None,
        evidence=["Fabric plane density below classification thresholds"]
    )


def get_connection_via_string(asset: Asset) -> Optional[str]:
    """
    Generate the connected_via_plane string for an asset.
    
    Returns None if asset should connect directly (Scrappy mode).
    """
    if not asset.fabric_plane_tag:
        return None
    
    vendor = asset.fabric_plane_tag.controller_vendor
    plane_type = asset.fabric_plane_tag.plane_type
    
    vendor_display = vendor.replace("_", " ").title()
    
    plane_type_names = {
        FabricPlaneType.IPAAS: "iPaaS",
        FabricPlaneType.API_GATEWAY: "API Gateway",
        FabricPlaneType.EVENT_BUS: "Event Bus",
        FabricPlaneType.DATA_WAREHOUSE: "Warehouse",
    }
    
    plane_name = plane_type_names.get(plane_type, "")
    
    if plane_name:
        return f"Connect via {vendor_display} ({plane_name})"
    return f"Connect via {vendor_display}"
