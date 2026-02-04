"""
CMDB Plane Evidence Collector

Extracts fabric plane signals from CMDB dependency and relationship records.

What it reveals: Explicitly documented integration relationships and asset
classifications. CMDB data quality varies wildly across organizations, but
when present, declared relationships are strong evidence.

CMDB Signal Examples:
- Dependency record: "App X depends on MuleSoft" → iPaaS plane routing (0.80)
- Config item type = "integration platform" for Workato → Fabric plane existence (0.90)
- Relationship: "Service A integrated with Service B via Kong" → API Gateway pipe (0.85)
- Asset tagged as "middleware" or "integration" → Potential plane or pipe (0.60)

THE RISK: Stale CMDB data. Finance might show no MuleSoft contract, but CMDB
still says "integrated via MuleSoft" — a contradiction that is itself a
valuable finding.

AOD action: Extract all CMDB dependency/relationship records that reference
known fabric plane vendors. Cross-reference against Finance plane to validate
currency. Flag contradictions.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Tuple, List

from ...models.input_contracts import Planes, CMDBConfigItem
from ...models.output_contracts import (
    FabricPlaneType,
    EvidenceSourcePlane,
)
from .base import EvidenceCollector, EvidenceCollectionResult, CONFIDENCE_SCORES

logger = logging.getLogger(__name__)


# CI types that indicate fabric plane infrastructure
FABRIC_PLANE_CI_TYPES: Dict[str, Tuple[FabricPlaneType, float]] = {
    # iPaaS
    "integration platform": (FabricPlaneType.IPAAS, 0.90),
    "integration service": (FabricPlaneType.IPAAS, 0.85),
    "ipaas": (FabricPlaneType.IPAAS, 0.95),
    "middleware": (FabricPlaneType.IPAAS, 0.70),
    "etl": (FabricPlaneType.IPAAS, 0.75),
    "data integration": (FabricPlaneType.IPAAS, 0.80),

    # API Gateway
    "api gateway": (FabricPlaneType.API_GATEWAY, 0.95),
    "api management": (FabricPlaneType.API_GATEWAY, 0.90),
    "api proxy": (FabricPlaneType.API_GATEWAY, 0.85),

    # Event Bus
    "message queue": (FabricPlaneType.EVENT_BUS, 0.85),
    "message broker": (FabricPlaneType.EVENT_BUS, 0.90),
    "event bus": (FabricPlaneType.EVENT_BUS, 0.95),
    "streaming platform": (FabricPlaneType.EVENT_BUS, 0.85),
    "event streaming": (FabricPlaneType.EVENT_BUS, 0.90),

    # Data Warehouse
    "data warehouse": (FabricPlaneType.DATA_WAREHOUSE, 0.95),
    "data lake": (FabricPlaneType.DATA_WAREHOUSE, 0.85),
    "analytics platform": (FabricPlaneType.DATA_WAREHOUSE, 0.80),
    "bi platform": (FabricPlaneType.DATA_WAREHOUSE, 0.75),
}

# Vendor names in CMDB that indicate fabric planes
FABRIC_PLANE_VENDORS: Dict[str, Tuple[FabricPlaneType, str, float]] = {
    "mulesoft": (FabricPlaneType.IPAAS, "mulesoft", 0.90),
    "workato": (FabricPlaneType.IPAAS, "workato", 0.90),
    "boomi": (FabricPlaneType.IPAAS, "boomi", 0.90),
    "tray.io": (FabricPlaneType.IPAAS, "tray", 0.90),
    "zapier": (FabricPlaneType.IPAAS, "zapier", 0.85),
    "celigo": (FabricPlaneType.IPAAS, "celigo", 0.90),
    "fivetran": (FabricPlaneType.IPAAS, "fivetran", 0.90),
    "airbyte": (FabricPlaneType.IPAAS, "airbyte", 0.85),

    "kong": (FabricPlaneType.API_GATEWAY, "kong", 0.90),
    "apigee": (FabricPlaneType.API_GATEWAY, "apigee", 0.90),

    "kafka": (FabricPlaneType.EVENT_BUS, "kafka", 0.90),
    "confluent": (FabricPlaneType.EVENT_BUS, "confluent", 0.90),
    "eventbridge": (FabricPlaneType.EVENT_BUS, "eventbridge", 0.90),

    "snowflake": (FabricPlaneType.DATA_WAREHOUSE, "snowflake", 0.90),
    "bigquery": (FabricPlaneType.DATA_WAREHOUSE, "bigquery", 0.90),
    "redshift": (FabricPlaneType.DATA_WAREHOUSE, "redshift", 0.90),
    "databricks": (FabricPlaneType.DATA_WAREHOUSE, "databricks", 0.90),
}

# Mapping from integrates_via field values to FabricPlaneType
INTEGRATES_VIA_MAPPING: Dict[str, FabricPlaneType] = {
    "ipaas": FabricPlaneType.IPAAS,
    "api_gateway": FabricPlaneType.API_GATEWAY,
    "event_bus": FabricPlaneType.EVENT_BUS,
    "data_warehouse": FabricPlaneType.DATA_WAREHOUSE,
    # Alternative spellings
    "apigateway": FabricPlaneType.API_GATEWAY,
    "eventbus": FabricPlaneType.EVENT_BUS,
    "datawarehouse": FabricPlaneType.DATA_WAREHOUSE,
    "warehouse": FabricPlaneType.DATA_WAREHOUSE,
    "gateway": FabricPlaneType.API_GATEWAY,
}

# Dependency relationship keywords that indicate fabric plane routing
DEPENDENCY_KEYWORDS: Dict[str, Tuple[FabricPlaneType, float]] = {
    "integrated via": (None, 0.85),  # plane type determined by target
    "depends on": (None, 0.80),
    "connects through": (None, 0.85),
    "routes through": (None, 0.90),
    "syncs with": (FabricPlaneType.IPAAS, 0.75),
    "replicates to": (FabricPlaneType.DATA_WAREHOUSE, 0.80),
    "streams to": (FabricPlaneType.EVENT_BUS, 0.80),
    "publishes to": (FabricPlaneType.EVENT_BUS, 0.85),
    "subscribes to": (FabricPlaneType.EVENT_BUS, 0.85),
}


class CMDBEvidenceCollector(EvidenceCollector):
    """
    Collects fabric plane evidence from CMDB configuration items.

    Extracts explicit dependency records and relationship metadata.
    Flags potential stale CMDB data for cross-reference validation.
    """

    @property
    def source_plane(self) -> EvidenceSourcePlane:
        return EvidenceSourcePlane.CMDB

    def collect(
        self,
        planes: Planes,
        snapshot_timestamp: datetime,
        result: EvidenceCollectionResult
    ) -> None:
        """Extract fabric plane evidence from CMDB CIs."""
        cis = planes.cmdb.cis
        if not cis:
            logger.debug("cmdb_evidence.no_cis")
            return

        for ci in cis:
            # Check if CI is a fabric plane itself
            self._check_ci_is_plane(ci, snapshot_timestamp, result)

            # Check for dependency relationships in raw_data
            self._check_dependencies(ci, snapshot_timestamp, result)

            # Check for explicit integrates_via field (Tier 2 evidence)
            self._check_integrates_via(ci, snapshot_timestamp, result)

    def _check_ci_is_plane(
        self,
        ci: CMDBConfigItem,
        timestamp: datetime,
        result: EvidenceCollectionResult
    ) -> None:
        """Check if CI is a fabric plane infrastructure item."""
        ci_type = ci.ci_type.lower()
        vendor = (ci.vendor or "").lower()
        name = ci.name.lower()

        # Check CI type
        for type_pattern, (plane_type, confidence) in FABRIC_PLANE_CI_TYPES.items():
            if type_pattern in ci_type:
                # Try to determine vendor
                plane_vendor = self._extract_vendor(ci)

                self._emit_plane_ci_evidence(
                    ci=ci,
                    plane_type=plane_type,
                    plane_vendor=plane_vendor,
                    confidence=confidence,
                    timestamp=timestamp,
                    signal_type="ci_type_match",
                    result=result
                )
                return

        # Check vendor
        for vendor_pattern, (plane_type, plane_vendor, confidence) in FABRIC_PLANE_VENDORS.items():
            if vendor_pattern in vendor or vendor_pattern in name:
                self._emit_plane_ci_evidence(
                    ci=ci,
                    plane_type=plane_type,
                    plane_vendor=plane_vendor,
                    confidence=confidence,
                    timestamp=timestamp,
                    signal_type="vendor_match",
                    result=result
                )
                return

    def _check_dependencies(
        self,
        ci: CMDBConfigItem,
        timestamp: datetime,
        result: EvidenceCollectionResult
    ) -> None:
        """Check CI raw_data for dependency relationships."""
        if not ci.raw_data:
            return

        # Look for common CMDB dependency fields
        dependencies = (
            ci.raw_data.get("dependencies", []) or
            ci.raw_data.get("depends_on", []) or
            ci.raw_data.get("relationships", []) or
            []
        )

        if isinstance(dependencies, str):
            dependencies = [dependencies]

        for dep in dependencies:
            if isinstance(dep, dict):
                dep_name = dep.get("name", "") or dep.get("target", "") or ""
                dep_type = dep.get("type", "") or dep.get("relationship", "") or ""
            else:
                dep_name = str(dep)
                dep_type = ""

            self._process_dependency(ci, dep_name, dep_type, timestamp, result)

        # Also check description/notes for integration mentions
        description = str(ci.raw_data.get("description", "") or ci.raw_data.get("notes", ""))
        self._check_description_for_planes(ci, description, timestamp, result)

    def _check_integrates_via(
        self,
        ci: CMDBConfigItem,
        timestamp: datetime,
        result: EvidenceCollectionResult
    ) -> None:
        """
        Check CI for explicit integrates_via field (Tier 2 evidence).

        When CMDB has integrates_via set, this is authoritative documentation
        that the asset routes through a specific fabric plane type. Combined
        with fabric_vendor, we can identify the exact plane instance.
        """
        integrates_via = getattr(ci, 'integrates_via', None)
        if not integrates_via:
            return

        integrates_via_lower = integrates_via.lower().strip()

        # Map integrates_via value to FabricPlaneType
        plane_type = INTEGRATES_VIA_MAPPING.get(integrates_via_lower)
        if not plane_type:
            logger.debug("cmdb_evidence.unknown_integrates_via", extra={
                "ci_name": ci.name,
                "integrates_via": integrates_via
            })
            return

        # Get fabric_vendor if available
        fabric_vendor = getattr(ci, 'fabric_vendor', None)
        if fabric_vendor:
            fabric_vendor = fabric_vendor.lower().strip()

        # Tier 2 confidence = 0.75 (documented but not directly crawled)
        confidence = 0.75

        evidence = self._create_evidence(
            signal_type="cmdb_integrates_via",
            signal_detail=f"CMDB declares '{ci.name}' integrates via {plane_type.value}"
                         f"{' (' + fabric_vendor + ')' if fabric_vendor else ''}",
            confidence=confidence,
            timestamp=timestamp,
            fabric_plane_type=plane_type,
            fabric_plane_vendor=fabric_vendor,
            raw_data={
                "ci_id": ci.ci_id,
                "ci_name": ci.name,
                "integrates_via": integrates_via,
                "fabric_vendor": fabric_vendor,
                "domain": ci.domain
            }
        )

        # Asset key is the CI's domain or name
        asset_key = ci.domain or ci.name
        result.add_evidence(asset_key, evidence)

        # Register plane if vendor identified
        if fabric_vendor:
            plane = self._create_fabric_plane(
                plane_type=plane_type,
                vendor=fabric_vendor,
                display_name=f"{fabric_vendor.title()} ({plane_type.value})",
                domain=None,
                confidence=confidence
            )
            result.add_detected_plane(plane, is_shadow=False)

        logger.info("cmdb_evidence.integrates_via_detected", extra={
            "ci_name": ci.name,
            "ci_domain": ci.domain,
            "integrates_via": integrates_via,
            "fabric_vendor": fabric_vendor,
            "plane_type": plane_type.value,
            "confidence": confidence
        })

    def _process_dependency(
        self,
        ci: CMDBConfigItem,
        dep_name: str,
        dep_type: str,
        timestamp: datetime,
        result: EvidenceCollectionResult
    ) -> None:
        """Process a single dependency record for fabric plane signals."""
        dep_name_lower = dep_name.lower()
        dep_type_lower = dep_type.lower()

        # Check if dependency target is a fabric plane vendor
        for vendor_pattern, (plane_type, plane_vendor, confidence) in FABRIC_PLANE_VENDORS.items():
            if vendor_pattern in dep_name_lower:
                self._emit_dependency_evidence(
                    ci=ci,
                    dependency_name=dep_name,
                    dependency_type=dep_type,
                    plane_type=plane_type,
                    plane_vendor=plane_vendor,
                    confidence=confidence * 0.9,  # Slightly reduce for dependency
                    timestamp=timestamp,
                    result=result
                )
                return

        # Check relationship type keywords
        combined = f"{dep_type_lower} {dep_name_lower}"
        for keyword, (plane_type, confidence) in DEPENDENCY_KEYWORDS.items():
            if keyword in combined:
                # Try to infer plane type from dependency name if not specified
                inferred_plane_type = plane_type
                inferred_vendor = None

                if not inferred_plane_type:
                    for vendor_pattern, (pt, pv, _) in FABRIC_PLANE_VENDORS.items():
                        if vendor_pattern in dep_name_lower:
                            inferred_plane_type = pt
                            inferred_vendor = pv
                            break

                if inferred_plane_type:
                    self._emit_dependency_evidence(
                        ci=ci,
                        dependency_name=dep_name,
                        dependency_type=dep_type,
                        plane_type=inferred_plane_type,
                        plane_vendor=inferred_vendor,
                        confidence=confidence,
                        timestamp=timestamp,
                        result=result
                    )
                return

    def _check_description_for_planes(
        self,
        ci: CMDBConfigItem,
        description: str,
        timestamp: datetime,
        result: EvidenceCollectionResult
    ) -> None:
        """Check CI description for fabric plane mentions."""
        if not description or len(description) < 10:
            return

        description_lower = description.lower()

        for vendor_pattern, (plane_type, plane_vendor, confidence) in FABRIC_PLANE_VENDORS.items():
            if vendor_pattern in description_lower:
                # Lower confidence for description mentions (less authoritative)
                self._emit_plane_ci_evidence(
                    ci=ci,
                    plane_type=plane_type,
                    plane_vendor=plane_vendor,
                    confidence=confidence * 0.7,
                    timestamp=timestamp,
                    signal_type="description_mention",
                    result=result
                )

    def _extract_vendor(self, ci: CMDBConfigItem) -> Optional[str]:
        """Extract fabric plane vendor from CI data."""
        vendor = (ci.vendor or "").lower()
        name = ci.name.lower()

        for vendor_pattern, (_, plane_vendor, _) in FABRIC_PLANE_VENDORS.items():
            if vendor_pattern in vendor or vendor_pattern in name:
                return plane_vendor

        return None

    def _emit_plane_ci_evidence(
        self,
        ci: CMDBConfigItem,
        plane_type: FabricPlaneType,
        plane_vendor: Optional[str],
        confidence: float,
        timestamp: datetime,
        signal_type: str,
        result: EvidenceCollectionResult
    ) -> None:
        """Emit evidence that a CI is fabric plane infrastructure."""
        evidence = self._create_evidence(
            signal_type=f"cmdb_{signal_type}",
            signal_detail=f"CMDB CI '{ci.name}' (type: {ci.ci_type}) "
                         f"is {plane_type.value} infrastructure"
                         f"{' (' + plane_vendor + ')' if plane_vendor else ''}",
            confidence=confidence,
            timestamp=timestamp,
            fabric_plane_type=plane_type,
            fabric_plane_vendor=plane_vendor,
            raw_data={
                "ci_id": ci.ci_id,
                "ci_name": ci.name,
                "ci_type": ci.ci_type,
                "vendor": ci.vendor,
                "lifecycle": ci.lifecycle
            }
        )

        # Asset key is the CI itself
        asset_key = ci.domain or ci.name
        result.add_evidence(asset_key, evidence)

        # Register plane if vendor identified
        if plane_vendor:
            plane = self._create_fabric_plane(
                plane_type=plane_type,
                vendor=plane_vendor,
                display_name=ci.name,
                domain=ci.domain,
                confidence=confidence
            )
            result.add_detected_plane(plane, is_shadow=False)

        logger.info("cmdb_evidence.plane_ci_detected", extra={
            "ci_name": ci.name,
            "ci_type": ci.ci_type,
            "plane_type": plane_type.value,
            "plane_vendor": plane_vendor,
            "confidence": confidence
        })

    def _emit_dependency_evidence(
        self,
        ci: CMDBConfigItem,
        dependency_name: str,
        dependency_type: str,
        plane_type: FabricPlaneType,
        plane_vendor: Optional[str],
        confidence: float,
        timestamp: datetime,
        result: EvidenceCollectionResult
    ) -> None:
        """Emit evidence for a CI dependency on fabric plane."""
        evidence = self._create_evidence(
            signal_type="cmdb_dependency",
            signal_detail=f"CMDB dependency: '{ci.name}' → '{dependency_name}' "
                         f"({dependency_type or 'unspecified'}) indicates "
                         f"{plane_type.value} routing",
            confidence=confidence,
            timestamp=timestamp,
            fabric_plane_type=plane_type,
            fabric_plane_vendor=plane_vendor,
            raw_data={
                "source_ci_id": ci.ci_id,
                "source_ci_name": ci.name,
                "dependency_name": dependency_name,
                "dependency_type": dependency_type
            }
        )

        # Asset key is the source CI (what routes through the plane)
        asset_key = ci.domain or ci.name
        result.add_evidence(asset_key, evidence)

        logger.debug("cmdb_evidence.dependency_detected", extra={
            "ci_name": ci.name,
            "dependency": dependency_name,
            "plane_type": plane_type.value,
            "confidence": confidence
        })
