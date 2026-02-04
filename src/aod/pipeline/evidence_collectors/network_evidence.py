"""
Network Plane Evidence Collector

Extracts fabric plane signals from network traffic patterns (DNS, proxy, certs).

What it reveals: Actual traffic patterns showing which assets communicate
through which planes. This is the most direct evidence of fabric belonging
because it observes what's actually happening, regardless of configuration.

Network Signal Examples:
- Traffic from `app-x` → `kong-proxy.internal:8443` → App routes through API Gateway (0.90)
- DNS resolution for `hooks.workato.com` by `marketing-tool` → iPaaS connection (0.85)
- TCP connections to `kafka-broker-1:9092` → Event Bus usage (0.90)
- HTTPS to `account.snowflakecomputing.com` → Data Warehouse routing (0.85)
- Traffic to `hooks.zapier.com` from unknown → Shadow iPaaS plane detected (0.80)

Challenge: Volume. Network records include health checks, CDN traffic, SaaS UI access.
AOD needs heuristics to filter:
- Include: Traffic to known fabric plane endpoints, sustained/recurring patterns,
  high data volume connections, integration-specific ports (9092 Kafka, 8443 Kong admin)
- Exclude: Browser-based SaaS access (short sessions, low volume),
  health check / monitoring pings, CDN and static asset traffic
"""

import logging
import re
from datetime import datetime
from typing import Optional, Dict, List, Tuple

from ...models.input_contracts import Planes, ProxyLog, DNSRecord, Certificate
from ...models.output_contracts import (
    FabricPlaneType,
    EvidenceSourcePlane,
    EvidenceLeadType,
)
from .base import EvidenceCollector, EvidenceCollectionResult, CONFIDENCE_SCORES

logger = logging.getLogger(__name__)


# Known fabric plane endpoint patterns (hostname/domain patterns)
FABRIC_ENDPOINT_PATTERNS: Dict[str, Tuple[FabricPlaneType, str, float]] = {
    # iPaaS
    "workato.com": (FabricPlaneType.IPAAS, "workato", 0.85),
    "hooks.workato.com": (FabricPlaneType.IPAAS, "workato", 0.90),
    "anypoint.mulesoft.com": (FabricPlaneType.IPAAS, "mulesoft", 0.85),
    "cloudhub.io": (FabricPlaneType.IPAAS, "mulesoft", 0.85),
    "mulesoft.com": (FabricPlaneType.IPAAS, "mulesoft", 0.80),
    "boomi.com": (FabricPlaneType.IPAAS, "boomi", 0.85),
    "hooks.zapier.com": (FabricPlaneType.IPAAS, "zapier", 0.85),
    "zapier.com": (FabricPlaneType.IPAAS, "zapier", 0.75),
    "tray.io": (FabricPlaneType.IPAAS, "tray", 0.85),
    "celigo.com": (FabricPlaneType.IPAAS, "celigo", 0.85),
    "integromat.com": (FabricPlaneType.IPAAS, "make", 0.85),
    "make.com": (FabricPlaneType.IPAAS, "make", 0.85),
    "fivetran.com": (FabricPlaneType.IPAAS, "fivetran", 0.85),
    "airbyte.io": (FabricPlaneType.IPAAS, "airbyte", 0.85),

    # API Gateway
    "konghq.com": (FabricPlaneType.API_GATEWAY, "kong", 0.80),
    "kong-proxy": (FabricPlaneType.API_GATEWAY, "kong", 0.90),
    "apigee.com": (FabricPlaneType.API_GATEWAY, "apigee", 0.80),
    "apigee.googleapis.com": (FabricPlaneType.API_GATEWAY, "apigee", 0.90),
    "execute-api.amazonaws.com": (FabricPlaneType.API_GATEWAY, "aws_api_gateway", 0.90),
    "apigateway.amazonaws.com": (FabricPlaneType.API_GATEWAY, "aws_api_gateway", 0.85),
    "azure-api.net": (FabricPlaneType.API_GATEWAY, "azure_api_mgmt", 0.90),

    # Event Bus
    "confluent.io": (FabricPlaneType.EVENT_BUS, "confluent", 0.80),
    "confluent.cloud": (FabricPlaneType.EVENT_BUS, "confluent", 0.90),
    "kafka": (FabricPlaneType.EVENT_BUS, "kafka", 0.85),  # internal hostname pattern
    "events.amazonaws.com": (FabricPlaneType.EVENT_BUS, "eventbridge", 0.90),
    "eventbridge.amazonaws.com": (FabricPlaneType.EVENT_BUS, "eventbridge", 0.85),
    "servicebus.windows.net": (FabricPlaneType.EVENT_BUS, "eventhubs", 0.90),
    "pubsub.googleapis.com": (FabricPlaneType.EVENT_BUS, "pubsub", 0.90),
    "kinesis.amazonaws.com": (FabricPlaneType.EVENT_BUS, "kinesis", 0.85),

    # Data Warehouse
    "snowflakecomputing.com": (FabricPlaneType.DATA_WAREHOUSE, "snowflake", 0.90),
    "snowflake.com": (FabricPlaneType.DATA_WAREHOUSE, "snowflake", 0.80),
    "bigquery.googleapis.com": (FabricPlaneType.DATA_WAREHOUSE, "bigquery", 0.90),
    "cloud.google.com/bigquery": (FabricPlaneType.DATA_WAREHOUSE, "bigquery", 0.85),
    "redshift.amazonaws.com": (FabricPlaneType.DATA_WAREHOUSE, "redshift", 0.90),
    "databricks.com": (FabricPlaneType.DATA_WAREHOUSE, "databricks", 0.85),
    "databricks.net": (FabricPlaneType.DATA_WAREHOUSE, "databricks", 0.85),
    "azuredatabricks.net": (FabricPlaneType.DATA_WAREHOUSE, "databricks", 0.90),
    "sql.azuresynapse.net": (FabricPlaneType.DATA_WAREHOUSE, "synapse", 0.90),
}

# Integration-specific ports that indicate fabric plane traffic
FABRIC_PORTS: Dict[int, Tuple[FabricPlaneType, str, float]] = {
    9092: (FabricPlaneType.EVENT_BUS, "kafka", 0.90),      # Kafka broker
    9093: (FabricPlaneType.EVENT_BUS, "kafka", 0.90),      # Kafka SSL
    8443: (FabricPlaneType.API_GATEWAY, "kong", 0.85),     # Kong admin API
    8001: (FabricPlaneType.API_GATEWAY, "kong", 0.80),     # Kong admin HTTP
    8000: (FabricPlaneType.API_GATEWAY, "kong", 0.75),     # Kong proxy
}

# Exclude patterns (health checks, CDN, monitoring)
EXCLUDE_PATTERNS = [
    r"healthcheck",
    r"health-check",
    r"/health$",
    r"/ping$",
    r"cdn\.",
    r"cloudfront\.net",
    r"akamai\.",
    r"fastly\.",
    r"cloudflare\.",
    r"static\.",
    r"assets\.",
    r"\.css$",
    r"\.js$",
    r"\.png$",
    r"\.jpg$",
    r"\.svg$",
    r"\.woff",
    r"google-analytics\.com",
    r"analytics\.",
    r"tracking\.",
    r"telemetry\.",
]

# Minimum bytes threshold for integration traffic (filter out small requests)
MIN_BYTES_THRESHOLD = 1000  # 1KB


class NetworkEvidenceCollector(EvidenceCollector):
    """
    Collects fabric plane evidence from network traffic patterns.

    Cross-references network flow records against known fabric plane infrastructure
    (identified in Cloud scan and from vendor hostname patterns).
    """

    @property
    def source_plane(self) -> EvidenceSourcePlane:
        return EvidenceSourcePlane.NETWORK

    def collect(
        self,
        planes: Planes,
        snapshot_timestamp: datetime,
        result: EvidenceCollectionResult
    ) -> None:
        """Extract fabric plane evidence from network traffic."""
        network = planes.network

        # Process proxy logs (HTTP/HTTPS traffic)
        for proxy_log in network.proxy:
            self._process_proxy_log(proxy_log, snapshot_timestamp, result)

        # Process DNS records (resolution to fabric plane endpoints)
        for dns_record in network.dns:
            self._process_dns_record(dns_record, snapshot_timestamp, result)

        # Process certificates (TLS connections to fabric planes)
        for cert in network.certs:
            self._process_certificate(cert, snapshot_timestamp, result)

    def _process_proxy_log(
        self,
        log: ProxyLog,
        timestamp: datetime,
        result: EvidenceCollectionResult
    ) -> None:
        """Process proxy log for fabric plane traffic."""
        domain = log.domain.lower() if log.domain else ""
        uri = (log.uri or "").lower()

        # Skip excluded patterns (health checks, CDN, static assets)
        combined = f"{domain}{uri}"
        for pattern in EXCLUDE_PATTERNS:
            if re.search(pattern, combined, re.IGNORECASE):
                return

        # Skip low-volume traffic (likely browser access, not integration)
        # Only filter if bytes_transferred is available (> 0 means it was provided)
        if log.bytes_transferred > 0 and log.bytes_transferred < MIN_BYTES_THRESHOLD:
            return

        # Check for fabric plane endpoint match
        match = self._match_fabric_endpoint(domain, uri)
        if match:
            plane_type, vendor, confidence = match
            self._emit_traffic_evidence(
                source_identifier=log.user or log.log_id,
                destination=domain,
                plane_type=plane_type,
                vendor=vendor,
                confidence=confidence,
                timestamp=log.timestamp or timestamp,
                signal_type="proxy_traffic",
                extra_data={
                    "uri": log.uri,
                    "bytes": log.bytes_transferred,
                    "user": log.user
                },
                result=result
            )

    def _process_dns_record(
        self,
        dns: DNSRecord,
        timestamp: datetime,
        result: EvidenceCollectionResult
    ) -> None:
        """Process DNS record for fabric plane resolution."""
        domain = dns.domain.lower()

        # Check for fabric plane endpoint match
        match = self._match_fabric_endpoint(domain, "")
        if match:
            plane_type, vendor, confidence = match
            # DNS is slightly less confident than actual traffic
            confidence = min(confidence, 0.80)

            self._emit_traffic_evidence(
                source_identifier=dns.record_id,
                destination=domain,
                plane_type=plane_type,
                vendor=vendor,
                confidence=confidence,
                timestamp=dns.timestamp or timestamp,
                signal_type="dns_resolution",
                extra_data={
                    "record_type": dns.record_type,
                    "value": dns.value
                },
                result=result
            )

    def _process_certificate(
        self,
        cert: Certificate,
        timestamp: datetime,
        result: EvidenceCollectionResult
    ) -> None:
        """Process certificate for fabric plane TLS connections."""
        domain = cert.domain.lower()

        # Check for fabric plane endpoint match
        match = self._match_fabric_endpoint(domain, "")
        if match:
            plane_type, vendor, confidence = match
            # Cert is moderate confidence (indicates capability, not active use)
            confidence = min(confidence, 0.75)

            self._emit_traffic_evidence(
                source_identifier=cert.cert_id,
                destination=domain,
                plane_type=plane_type,
                vendor=vendor,
                confidence=confidence,
                timestamp=timestamp,
                signal_type="tls_certificate",
                extra_data={
                    "issuer": cert.issuer,
                    "expires_at": cert.expires_at.isoformat() if cert.expires_at else None
                },
                result=result
            )

    def _match_fabric_endpoint(
        self,
        domain: str,
        uri: str
    ) -> Optional[Tuple[FabricPlaneType, str, float]]:
        """Match domain/URI against known fabric plane endpoints."""
        combined = f"{domain} {uri}"

        for pattern, match_data in FABRIC_ENDPOINT_PATTERNS.items():
            if pattern in combined:
                return match_data

        return None

    def _emit_traffic_evidence(
        self,
        source_identifier: str,
        destination: str,
        plane_type: FabricPlaneType,
        vendor: str,
        confidence: float,
        timestamp: datetime,
        signal_type: str,
        extra_data: dict,
        result: EvidenceCollectionResult
    ) -> None:
        """Emit evidence for fabric plane traffic."""
        evidence = self._create_evidence(
            signal_type=f"network_{signal_type}",
            signal_detail=f"Traffic to {destination} indicates {plane_type.value} plane ({vendor})",
            confidence=confidence,
            timestamp=timestamp,
            fabric_plane_type=plane_type,
            fabric_plane_vendor=vendor,
            raw_data={
                "destination": destination,
                "source": source_identifier,
                **extra_data
            }
        )

        # Asset key is the source of the traffic (what's connecting TO the plane)
        asset_key = source_identifier
        result.add_evidence(asset_key, evidence)

        # Generate EvidenceLead for AAM validation (RACI Sprint)
        lead = self._create_evidence_lead(
            asset_id=source_identifier,
            asset_name=source_identifier,
            asset_domain=destination,
            suggested_plane_type=plane_type,
            suggested_plane_product=vendor,
            evidence_type=EvidenceLeadType.NETWORK_FLOW,
            evidence_detail=f"Network traffic from {source_identifier} to {destination} suggests routing via {vendor} {plane_type.value}",
            confidence=confidence,
            raw_data={
                "destination": destination,
                "source": source_identifier,
                "signal_type": signal_type,
                **extra_data
            }
        )
        result.add_evidence_lead(lead)

        # Also register the fabric plane if confident enough
        if confidence >= 0.80:
            plane = self._create_fabric_plane(
                plane_type=plane_type,
                vendor=vendor,
                display_name=f"{vendor} ({destination})",
                domain=destination,
                confidence=confidence
            )
            result.add_detected_plane(plane, is_shadow=False)

        logger.debug("network_evidence.traffic_detected", extra={
            "source": source_identifier,
            "destination": destination,
            "plane_type": plane_type.value,
            "vendor": vendor,
            "confidence": confidence,
            "signal_type": signal_type
        })
