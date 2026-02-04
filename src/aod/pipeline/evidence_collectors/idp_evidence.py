"""
IdP Plane Evidence Collector

Extracts fabric plane signals from Identity Provider OAuth grants and
authentication relationships.

What it reveals: Which assets have authentication/authorization relationships
with fabric plane platforms.

IdP Signal Examples:
- OAuth grant from App → Workato → App is connected via iPaaS (0.75)
- SAML assertion for Kong admin portal → User manages API Gateway (0.60, admin not a pipe)
- OAuth client ID in API Gateway matching known app → App routes through gateway (0.80)
- Service account credentials for Snowflake from ETL tool → ETL routes through warehouse (0.75)

LIMITATION: IdP data shows authentication relationships, not data flow.
An OAuth grant from Salesforce to Workato means Workato CAN access Salesforce —
not that it currently DOES. Useful as corroborating evidence, not primary.

AOD action: Cross-reference IdP OAuth grants and service account bindings
against known fabric plane platforms. Use as Tier 2 evidence when combined
with other signals.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Tuple

from ...models.input_contracts import Planes, IdPObject
from ...models.output_contracts import (
    FabricPlaneType,
    EvidenceSourcePlane,
)
from .base import EvidenceCollector, EvidenceCollectionResult, CONFIDENCE_SCORES

logger = logging.getLogger(__name__)


# IdP app names/domains that indicate fabric plane platforms
FABRIC_PLANE_IDP_PATTERNS: Dict[str, Tuple[FabricPlaneType, str, float]] = {
    # iPaaS platforms
    "workato": (FabricPlaneType.IPAAS, "workato", 0.75),
    "mulesoft": (FabricPlaneType.IPAAS, "mulesoft", 0.75),
    "anypoint": (FabricPlaneType.IPAAS, "mulesoft", 0.75),
    "boomi": (FabricPlaneType.IPAAS, "boomi", 0.75),
    "tray.io": (FabricPlaneType.IPAAS, "tray", 0.75),
    "zapier": (FabricPlaneType.IPAAS, "zapier", 0.70),  # Often individual use
    "celigo": (FabricPlaneType.IPAAS, "celigo", 0.75),
    "snaplogic": (FabricPlaneType.IPAAS, "snaplogic", 0.75),
    "fivetran": (FabricPlaneType.IPAAS, "fivetran", 0.75),
    "airbyte": (FabricPlaneType.IPAAS, "airbyte", 0.70),

    # API Gateway platforms
    "kong": (FabricPlaneType.API_GATEWAY, "kong", 0.75),
    "konnect": (FabricPlaneType.API_GATEWAY, "kong", 0.75),  # Kong Konnect
    "apigee": (FabricPlaneType.API_GATEWAY, "apigee", 0.75),

    # Event Bus platforms
    "confluent": (FabricPlaneType.EVENT_BUS, "confluent", 0.75),
    "kafka": (FabricPlaneType.EVENT_BUS, "kafka", 0.70),

    # Data Warehouse platforms
    "snowflake": (FabricPlaneType.DATA_WAREHOUSE, "snowflake", 0.75),
    "bigquery": (FabricPlaneType.DATA_WAREHOUSE, "bigquery", 0.75),
    "databricks": (FabricPlaneType.DATA_WAREHOUSE, "databricks", 0.75),
    "redshift": (FabricPlaneType.DATA_WAREHOUSE, "redshift", 0.70),
}

# IdP types that indicate service-to-service authentication (higher confidence)
SERVICE_ACCOUNT_TYPES = ["service_principal", "service_account", "machine", "api_client", "oauth_client"]

# IdP types that indicate admin access (lower confidence - user access, not integration)
ADMIN_ACCESS_TYPES = ["user", "admin", "operator"]


class IdPEvidenceCollector(EvidenceCollector):
    """
    Collects fabric plane evidence from IdP OAuth grants and authentication.

    Cross-references IdP records against known fabric plane platforms.
    Distinguishes service-to-service auth (integration) from user auth (admin).
    """

    @property
    def source_plane(self) -> EvidenceSourcePlane:
        return EvidenceSourcePlane.IDP

    def collect(
        self,
        planes: Planes,
        snapshot_timestamp: datetime,
        result: EvidenceCollectionResult
    ) -> None:
        """Extract fabric plane evidence from IdP records."""
        idp_objects = planes.idp.objects
        if not idp_objects:
            logger.debug("idp_evidence.no_objects")
            return

        for idp_obj in idp_objects:
            self._process_idp_object(idp_obj, snapshot_timestamp, result)

    def _process_idp_object(
        self,
        idp_obj: IdPObject,
        timestamp: datetime,
        result: EvidenceCollectionResult
    ) -> None:
        """Process a single IdP object for fabric plane signals."""
        name_lower = idp_obj.name.lower()
        domain_lower = (idp_obj.domain or "").lower()
        idp_type = idp_obj.idp_type.lower()

        # Check if this IdP object IS a fabric plane platform
        match = self._match_fabric_plane(name_lower, domain_lower)
        if match:
            plane_type, plane_vendor, base_confidence = match

            # Adjust confidence based on IdP type
            confidence = self._adjust_confidence(base_confidence, idp_type, idp_obj)

            self._emit_idp_evidence(
                idp_obj=idp_obj,
                plane_type=plane_type,
                plane_vendor=plane_vendor,
                confidence=confidence,
                timestamp=idp_obj.last_login_at or timestamp,
                is_service_auth=idp_type in SERVICE_ACCOUNT_TYPES,
                result=result
            )
            return

        # Check raw_data for OAuth grants TO fabric planes
        if idp_obj.raw_data:
            self._check_oauth_grants(idp_obj, timestamp, result)

    def _match_fabric_plane(
        self,
        name: str,
        domain: str
    ) -> Optional[Tuple[FabricPlaneType, str, float]]:
        """Match IdP name/domain against fabric plane patterns."""
        combined = f"{name} {domain}"

        for pattern, match_data in FABRIC_PLANE_IDP_PATTERNS.items():
            if pattern in combined:
                return match_data

        return None

    def _adjust_confidence(
        self,
        base_confidence: float,
        idp_type: str,
        idp_obj: IdPObject
    ) -> float:
        """Adjust confidence based on IdP object characteristics."""
        confidence = base_confidence

        # Service accounts/principals are stronger evidence of integration
        if idp_type in SERVICE_ACCOUNT_TYPES:
            confidence = min(confidence + 0.10, 0.90)

        # Admin/user access is weaker evidence (just means they have access)
        if idp_type in ADMIN_ACCESS_TYPES:
            confidence = max(confidence - 0.15, 0.50)

        # SCIM enabled suggests automated provisioning (stronger integration)
        if idp_obj.has_scim:
            confidence = min(confidence + 0.05, 0.90)

        # Recent login is better evidence than stale record
        if idp_obj.last_login_at:
            # If login was recent (within 30 days), slight boost
            days_since = (datetime.now(idp_obj.last_login_at.tzinfo) - idp_obj.last_login_at).days
            if days_since <= 30:
                confidence = min(confidence + 0.05, 0.90)
            elif days_since > 180:
                # Stale login reduces confidence
                confidence = max(confidence - 0.10, 0.50)

        return confidence

    def _check_oauth_grants(
        self,
        idp_obj: IdPObject,
        timestamp: datetime,
        result: EvidenceCollectionResult
    ) -> None:
        """Check IdP raw_data for OAuth grants to fabric planes."""
        raw_data = idp_obj.raw_data
        if not raw_data:
            return

        # Look for common OAuth grant fields
        grants = (
            raw_data.get("oauth_grants", []) or
            raw_data.get("connected_apps", []) or
            raw_data.get("api_permissions", []) or
            []
        )

        if isinstance(grants, str):
            grants = [grants]

        for grant in grants:
            if isinstance(grant, dict):
                grant_target = (
                    grant.get("app_name", "") or
                    grant.get("target", "") or
                    grant.get("resource", "") or
                    ""
                )
                grant_scope = grant.get("scope", "") or grant.get("permissions", "")
            else:
                grant_target = str(grant)
                grant_scope = ""

            # Check if grant target is a fabric plane
            match = self._match_fabric_plane(grant_target.lower(), "")
            if match:
                plane_type, plane_vendor, confidence = match

                # OAuth grants are corroborating evidence
                confidence = confidence * 0.9

                self._emit_grant_evidence(
                    source_idp=idp_obj,
                    target_name=grant_target,
                    scope=grant_scope,
                    plane_type=plane_type,
                    plane_vendor=plane_vendor,
                    confidence=confidence,
                    timestamp=timestamp,
                    result=result
                )

    def _emit_idp_evidence(
        self,
        idp_obj: IdPObject,
        plane_type: FabricPlaneType,
        plane_vendor: str,
        confidence: float,
        timestamp: datetime,
        is_service_auth: bool,
        result: EvidenceCollectionResult
    ) -> None:
        """Emit evidence for IdP object as fabric plane platform."""
        auth_type = "service authentication" if is_service_auth else "user access"

        evidence = self._create_evidence(
            signal_type=f"idp_{'service_auth' if is_service_auth else 'user_access'}",
            signal_detail=f"IdP record '{idp_obj.name}' ({auth_type}) "
                         f"indicates {plane_type.value} platform "
                         f"({plane_vendor})",
            confidence=confidence,
            timestamp=timestamp,
            fabric_plane_type=plane_type,
            fabric_plane_vendor=plane_vendor,
            raw_data={
                "idp_id": idp_obj.idp_id,
                "idp_name": idp_obj.name,
                "idp_type": idp_obj.idp_type,
                "has_sso": idp_obj.has_sso,
                "has_scim": idp_obj.has_scim,
                "domain": idp_obj.domain
            }
        )

        # Asset key is the fabric plane platform
        asset_key = idp_obj.domain or idp_obj.name
        result.add_evidence(asset_key, evidence)

        # Register fabric plane
        plane = self._create_fabric_plane(
            plane_type=plane_type,
            vendor=plane_vendor,
            display_name=idp_obj.name,
            domain=idp_obj.domain,
            confidence=confidence
        )
        result.add_detected_plane(plane, is_shadow=False)

        logger.info("idp_evidence.fabric_platform_detected", extra={
            "idp_name": idp_obj.name,
            "idp_type": idp_obj.idp_type,
            "plane_type": plane_type.value,
            "plane_vendor": plane_vendor,
            "confidence": confidence,
            "is_service_auth": is_service_auth
        })

    def _emit_grant_evidence(
        self,
        source_idp: IdPObject,
        target_name: str,
        scope: str,
        plane_type: FabricPlaneType,
        plane_vendor: str,
        confidence: float,
        timestamp: datetime,
        result: EvidenceCollectionResult
    ) -> None:
        """Emit evidence for OAuth grant to fabric plane."""
        evidence = self._create_evidence(
            signal_type="idp_oauth_grant",
            signal_detail=f"OAuth grant from '{source_idp.name}' to '{target_name}' "
                         f"indicates {plane_type.value} connection",
            confidence=confidence,
            timestamp=timestamp,
            fabric_plane_type=plane_type,
            fabric_plane_vendor=plane_vendor,
            raw_data={
                "source_idp_id": source_idp.idp_id,
                "source_idp_name": source_idp.name,
                "target": target_name,
                "scope": scope
            }
        )

        # Asset key is the SOURCE (what has the grant TO the fabric plane)
        asset_key = source_idp.domain or source_idp.name
        result.add_evidence(asset_key, evidence)

        logger.debug("idp_evidence.oauth_grant_detected", extra={
            "source": source_idp.name,
            "target": target_name,
            "plane_type": plane_type.value,
            "confidence": confidence
        })
