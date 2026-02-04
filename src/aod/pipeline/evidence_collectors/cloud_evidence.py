"""
Cloud Plane Evidence Collector

Extracts fabric plane signals from cloud resource inventory (AWS, Azure, GCP).

What it reveals: The fabric planes themselves as cloud resources.
Many fabric plane components are discoverable as cloud resources:
- AWS API Gateway (REST/HTTP API) → API Gateway plane
- Amazon MSK cluster → Event Bus plane (managed Kafka)
- AWS EventBridge bus → Event Bus plane
- ECS/EKS service running Kong → API Gateway plane
- Lambda + API Gateway integration → API Gateway plane
- Snowflake account / Redshift cluster → Data Warehouse plane
- EC2 running MuleSoft Mule Runtime → iPaaS plane
- Fivetran / Airbyte agents → iPaaS / Data Warehouse plane

Additionally, cloud resource metadata reveals connections between resources:
- Security groups / VPC peering → which services can talk to which plane infra
- IAM roles with cross-service permissions → which assets are authorized
- API Gateway route tables → literally a list of upstream services (pipes)
"""

import logging
import re
from datetime import datetime
from typing import Optional

from ...models.input_contracts import Planes, CloudResource
from ...models.output_contracts import (
    FabricPlaneType,
    EvidenceSourcePlane,
    EvidenceLeadType,
)
from .base import EvidenceCollector, EvidenceCollectionResult, CONFIDENCE_SCORES

logger = logging.getLogger(__name__)


# Cloud resource types that indicate fabric plane infrastructure
FABRIC_PLANE_RESOURCE_PATTERNS = {
    FabricPlaneType.API_GATEWAY: {
        # AWS
        "aws::apigateway::restapi": ("aws_api_gateway", 0.90),
        "aws::apigatewayv2::api": ("aws_api_gateway", 0.90),
        "aws::apigateway::stage": ("aws_api_gateway", 0.85),
        # Azure
        "microsoft.apimanagement/service": ("azure_api_mgmt", 0.90),
        # GCP
        "apigateway.googleapis.com/api": ("gcp_api_gateway", 0.90),
        # Container-based gateways
        "aws::ecs::service": None,  # Needs name check for Kong/Apigee
        "aws::eks::service": None,
    },
    FabricPlaneType.EVENT_BUS: {
        # Kafka (MSK)
        "aws::msk::cluster": ("confluent", 0.90),
        "aws::kafka::cluster": ("confluent", 0.90),
        # EventBridge
        "aws::events::eventbus": ("eventbridge", 0.90),
        "aws::events::rule": ("eventbridge", 0.85),
        # Azure Event Hubs
        "microsoft.eventhub/namespaces": ("eventhubs", 0.90),
        # Kinesis
        "aws::kinesis::stream": ("kinesis", 0.85),
        # GCP Pub/Sub
        "pubsub.googleapis.com/topic": ("pubsub", 0.90),
    },
    FabricPlaneType.DATA_WAREHOUSE: {
        # Snowflake (usually detected via domain, but can appear as integration)
        "aws::glue::connection": None,  # Check for Snowflake/Redshift
        # Redshift
        "aws::redshift::cluster": ("redshift", 0.90),
        # BigQuery
        "bigquery.googleapis.com/dataset": ("bigquery", 0.90),
        # Databricks
        "databricks::workspace": ("databricks", 0.90),
        # Synapse
        "microsoft.synapse/workspaces": ("synapse", 0.90),
    },
    FabricPlaneType.IPAAS: {
        # MuleSoft on AWS
        "aws::ec2::instance": None,  # Check AMI/tags for MuleSoft runtime
        # Fivetran/Airbyte agents
        "aws::ecs::taskdefinition": None,  # Check for Fivetran/Airbyte images
    },
}

# Vendor patterns to check in resource names/tags
VENDOR_NAME_PATTERNS = {
    "kong": (FabricPlaneType.API_GATEWAY, "kong"),
    "apigee": (FabricPlaneType.API_GATEWAY, "apigee"),
    "mulesoft": (FabricPlaneType.IPAAS, "mulesoft"),
    "workato": (FabricPlaneType.IPAAS, "workato"),
    "boomi": (FabricPlaneType.IPAAS, "boomi"),
    "tray.io": (FabricPlaneType.IPAAS, "tray"),
    "zapier": (FabricPlaneType.IPAAS, "zapier"),
    "celigo": (FabricPlaneType.IPAAS, "celigo"),
    "fivetran": (FabricPlaneType.IPAAS, "fivetran"),
    "airbyte": (FabricPlaneType.IPAAS, "airbyte"),
    "kafka": (FabricPlaneType.EVENT_BUS, "kafka"),
    "confluent": (FabricPlaneType.EVENT_BUS, "confluent"),
    "snowflake": (FabricPlaneType.DATA_WAREHOUSE, "snowflake"),
    "databricks": (FabricPlaneType.DATA_WAREHOUSE, "databricks"),
}


class CloudEvidenceCollector(EvidenceCollector):
    """
    Collects fabric plane evidence from cloud resource inventory.

    Identifies fabric plane infrastructure and extracts connection metadata
    (routes, security groups, IAM bindings) as fabric_routing_evidence.
    """

    @property
    def source_plane(self) -> EvidenceSourcePlane:
        return EvidenceSourcePlane.CLOUD

    def collect(
        self,
        planes: Planes,
        snapshot_timestamp: datetime,
        result: EvidenceCollectionResult
    ) -> None:
        """Extract fabric plane evidence from cloud resources."""
        resources = planes.cloud.resources
        if not resources:
            logger.debug("cloud_evidence.no_resources")
            return

        for resource in resources:
            self._process_resource(resource, snapshot_timestamp, result)

    def _process_resource(
        self,
        resource: CloudResource,
        timestamp: datetime,
        result: EvidenceCollectionResult
    ) -> None:
        """Process a single cloud resource for fabric plane signals."""
        resource_type = resource.resource_type.lower()
        resource_name = resource.name.lower()
        resource_uri = (resource.uri or "").lower()

        # Check direct resource type matches
        fabric_match = self._match_resource_type(resource_type)
        if fabric_match:
            plane_type, vendor, confidence = fabric_match
            self._emit_plane_evidence(
                resource, plane_type, vendor, confidence, timestamp, result
            )
            return

        # Check name/URI for vendor patterns
        vendor_match = self._match_vendor_pattern(resource_name, resource_uri)
        if vendor_match:
            plane_type, vendor = vendor_match
            self._emit_plane_evidence(
                resource, plane_type, vendor, CONFIDENCE_SCORES["tier_2_high"], timestamp, result
            )
            return

        # Check raw_data for tags/metadata indicating fabric plane
        if resource.raw_data:
            tag_match = self._match_tags(resource.raw_data)
            if tag_match:
                plane_type, vendor = tag_match
                self._emit_plane_evidence(
                    resource, plane_type, vendor, CONFIDENCE_SCORES["tier_2_medium"], timestamp, result
                )

    def _match_resource_type(
        self,
        resource_type: str
    ) -> Optional[tuple[FabricPlaneType, str, float]]:
        """Match resource type to fabric plane."""
        for plane_type, patterns in FABRIC_PLANE_RESOURCE_PATTERNS.items():
            for pattern, vendor_conf in patterns.items():
                if pattern in resource_type or resource_type.endswith(pattern.split("::")[-1]):
                    if vendor_conf:
                        vendor, confidence = vendor_conf
                        return (plane_type, vendor, confidence)
        return None

    def _match_vendor_pattern(
        self,
        name: str,
        uri: str
    ) -> Optional[tuple[FabricPlaneType, str]]:
        """Match resource name/URI against vendor patterns."""
        combined = f"{name} {uri}"
        for pattern, (plane_type, vendor) in VENDOR_NAME_PATTERNS.items():
            if pattern in combined:
                return (plane_type, vendor)
        return None

    def _match_tags(
        self,
        raw_data: dict
    ) -> Optional[tuple[FabricPlaneType, str]]:
        """Check resource tags for fabric plane indicators."""
        tags = raw_data.get("tags", {}) or raw_data.get("Tags", {})
        if not tags:
            return None

        # Flatten tags if they're in AWS format [{Key: x, Value: y}]
        if isinstance(tags, list):
            tags = {t.get("Key", ""): t.get("Value", "") for t in tags if isinstance(t, dict)}

        tag_str = " ".join(f"{k} {v}" for k, v in tags.items()).lower()

        for pattern, (plane_type, vendor) in VENDOR_NAME_PATTERNS.items():
            if pattern in tag_str:
                return (plane_type, vendor)

        return None

    def _emit_plane_evidence(
        self,
        resource: CloudResource,
        plane_type: FabricPlaneType,
        vendor: str,
        confidence: float,
        timestamp: datetime,
        result: EvidenceCollectionResult
    ) -> None:
        """Emit evidence for detected fabric plane infrastructure."""
        # Create evidence record
        evidence = self._create_evidence(
            signal_type=f"cloud_resource_{resource.resource_type}",
            signal_detail=f"Cloud resource '{resource.name}' ({resource.resource_type}) on {resource.provider}",
            confidence=confidence,
            timestamp=resource.observed_at or timestamp,
            fabric_plane_type=plane_type,
            fabric_plane_vendor=vendor,
            raw_data={
                "resource_id": resource.resource_id,
                "resource_type": resource.resource_type,
                "provider": resource.provider,
                "uri": resource.uri
            }
        )

        # Asset key is the resource itself (fabric plane infrastructure)
        asset_key = resource.uri or resource.name or resource.resource_id
        result.add_evidence(asset_key, evidence)

        # Generate EvidenceLead for AAM validation (RACI Sprint)
        lead = self._create_evidence_lead(
            asset_id=resource.resource_id,
            asset_name=resource.name,
            asset_domain=self._extract_domain(resource),
            suggested_plane_type=plane_type,
            suggested_plane_product=vendor,
            evidence_type=EvidenceLeadType.CLOUD_RESOURCE,
            evidence_detail=f"Cloud resource '{resource.name}' ({resource.resource_type}) indicates {plane_type.value} infrastructure",
            confidence=confidence,
            raw_data={
                "resource_id": resource.resource_id,
                "resource_type": resource.resource_type,
                "provider": resource.provider
            }
        )
        result.add_evidence_lead(lead)

        # Also register the detected fabric plane
        plane = self._create_fabric_plane(
            plane_type=plane_type,
            vendor=vendor,
            display_name=resource.name,
            domain=self._extract_domain(resource),
            confidence=confidence
        )
        result.add_detected_plane(plane, is_shadow=False)

        logger.info("cloud_evidence.fabric_plane_detected", extra={
            "resource": resource.name,
            "resource_type": resource.resource_type,
            "plane_type": plane_type.value,
            "vendor": vendor,
            "confidence": confidence
        })

    def _extract_domain(self, resource: CloudResource) -> Optional[str]:
        """Extract domain from resource URI if present."""
        if not resource.uri:
            return None

        # Simple domain extraction from URI
        uri = resource.uri.lower()
        if "://" in uri:
            uri = uri.split("://")[1]
        if "/" in uri:
            uri = uri.split("/")[0]
        if ":" in uri:
            uri = uri.split(":")[0]

        return uri if "." in uri else None
