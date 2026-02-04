"""
Finance Plane Evidence Collector

Extracts fabric plane signals from financial/contract records.

What it reveals: Which fabric planes EXIST (paid for) and who owns them.
Finance data reveals the organizational fabric plane map.

Finance Signal Examples:
- Enterprise contract for Workato/MuleSoft/Tray.io → iPaaS plane exists (0.95)
- Confluent Cloud subscription → Event Bus plane exists (0.95)
- Snowflake / BigQuery billing → Data Warehouse plane exists (0.95)
- Kong Enterprise / Apigee subscription → API Gateway plane exists (0.95)
- Department-level Zapier subscription → Shadow iPaaS plane detected (0.85)
- Usage-based invoices with volume data → Scale of integration through plane

CRITICAL INSIGHT: Finance data reveals SHADOW FABRIC PLANES.
A marketing team paying for their own Zapier Pro account is a fabric plane
that IT doesn't know about. This is a high-value finding.

Finance does NOT tell you which specific assets route through which planes.
It only confirms plane existence and ownership at an organizational level.

AOD action: Use Finance data to build the "expected fabric plane inventory".
- Any plane found in Cloud/Network but not Finance = potential shadow plane
- Any plane in Finance but not Cloud/Network = possible decommissioned/underused
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Tuple, List

from ...models.input_contracts import Planes, Contract, Transaction, Vendor
from ...models.output_contracts import (
    FabricPlaneType,
    EvidenceSourcePlane,
)
from .base import EvidenceCollector, EvidenceCollectionResult, CONFIDENCE_SCORES

logger = logging.getLogger(__name__)


# Vendor names that indicate fabric plane subscriptions
FABRIC_PLANE_VENDORS: Dict[str, Tuple[FabricPlaneType, str, float]] = {
    # iPaaS vendors
    "workato": (FabricPlaneType.IPAAS, "workato", 0.95),
    "mulesoft": (FabricPlaneType.IPAAS, "mulesoft", 0.95),
    "boomi": (FabricPlaneType.IPAAS, "boomi", 0.95),
    "dell boomi": (FabricPlaneType.IPAAS, "boomi", 0.95),
    "tray.io": (FabricPlaneType.IPAAS, "tray", 0.95),
    "tray": (FabricPlaneType.IPAAS, "tray", 0.90),
    "zapier": (FabricPlaneType.IPAAS, "zapier", 0.90),  # Often shadow
    "make.com": (FabricPlaneType.IPAAS, "make", 0.90),
    "integromat": (FabricPlaneType.IPAAS, "make", 0.90),
    "snaplogic": (FabricPlaneType.IPAAS, "snaplogic", 0.95),
    "celigo": (FabricPlaneType.IPAAS, "celigo", 0.95),
    "fivetran": (FabricPlaneType.IPAAS, "fivetran", 0.95),
    "airbyte": (FabricPlaneType.IPAAS, "airbyte", 0.90),

    # API Gateway vendors
    "kong": (FabricPlaneType.API_GATEWAY, "kong", 0.95),
    "kong inc": (FabricPlaneType.API_GATEWAY, "kong", 0.95),
    "apigee": (FabricPlaneType.API_GATEWAY, "apigee", 0.95),
    "google apigee": (FabricPlaneType.API_GATEWAY, "apigee", 0.95),
    "aws api gateway": (FabricPlaneType.API_GATEWAY, "aws_api_gateway", 0.95),
    "azure api management": (FabricPlaneType.API_GATEWAY, "azure_api_mgmt", 0.95),

    # Event Bus vendors
    "confluent": (FabricPlaneType.EVENT_BUS, "confluent", 0.95),
    "confluent cloud": (FabricPlaneType.EVENT_BUS, "confluent", 0.95),
    "apache kafka": (FabricPlaneType.EVENT_BUS, "kafka", 0.85),
    "amazon msk": (FabricPlaneType.EVENT_BUS, "confluent", 0.95),
    "aws eventbridge": (FabricPlaneType.EVENT_BUS, "eventbridge", 0.95),
    "azure event hubs": (FabricPlaneType.EVENT_BUS, "eventhubs", 0.95),
    "google pub/sub": (FabricPlaneType.EVENT_BUS, "pubsub", 0.95),
    "amazon kinesis": (FabricPlaneType.EVENT_BUS, "kinesis", 0.95),

    # Data Warehouse vendors
    "snowflake": (FabricPlaneType.DATA_WAREHOUSE, "snowflake", 0.95),
    "snowflake inc": (FabricPlaneType.DATA_WAREHOUSE, "snowflake", 0.95),
    "google bigquery": (FabricPlaneType.DATA_WAREHOUSE, "bigquery", 0.95),
    "bigquery": (FabricPlaneType.DATA_WAREHOUSE, "bigquery", 0.95),
    "amazon redshift": (FabricPlaneType.DATA_WAREHOUSE, "redshift", 0.95),
    "redshift": (FabricPlaneType.DATA_WAREHOUSE, "redshift", 0.90),
    "databricks": (FabricPlaneType.DATA_WAREHOUSE, "databricks", 0.95),
    "azure synapse": (FabricPlaneType.DATA_WAREHOUSE, "synapse", 0.95),
}

# Product names that indicate fabric plane subscriptions
FABRIC_PLANE_PRODUCTS: Dict[str, Tuple[FabricPlaneType, str, float]] = {
    # iPaaS products
    "workato enterprise": (FabricPlaneType.IPAAS, "workato", 0.95),
    "anypoint platform": (FabricPlaneType.IPAAS, "mulesoft", 0.95),
    "cloudhub": (FabricPlaneType.IPAAS, "mulesoft", 0.95),
    "boomi atomsphere": (FabricPlaneType.IPAAS, "boomi", 0.95),
    "zapier pro": (FabricPlaneType.IPAAS, "zapier", 0.85),  # Often shadow
    "zapier team": (FabricPlaneType.IPAAS, "zapier", 0.85),
    "zapier business": (FabricPlaneType.IPAAS, "zapier", 0.90),

    # API Gateway products
    "kong enterprise": (FabricPlaneType.API_GATEWAY, "kong", 0.95),
    "kong gateway": (FabricPlaneType.API_GATEWAY, "kong", 0.95),
    "apigee edge": (FabricPlaneType.API_GATEWAY, "apigee", 0.95),
    "apigee x": (FabricPlaneType.API_GATEWAY, "apigee", 0.95),

    # Event Bus products
    "confluent cloud": (FabricPlaneType.EVENT_BUS, "confluent", 0.95),
    "confluent platform": (FabricPlaneType.EVENT_BUS, "confluent", 0.95),
    "managed kafka": (FabricPlaneType.EVENT_BUS, "confluent", 0.90),

    # Data Warehouse products
    "snowflake compute": (FabricPlaneType.DATA_WAREHOUSE, "snowflake", 0.95),
    "snowflake storage": (FabricPlaneType.DATA_WAREHOUSE, "snowflake", 0.95),
    "bigquery compute": (FabricPlaneType.DATA_WAREHOUSE, "bigquery", 0.95),
}

# Shadow plane indicators (department-level subscriptions, non-IT cost centers)
SHADOW_PLANE_INDICATORS = [
    "marketing",
    "sales",
    "hr",
    "finance",  # ironically, finance dept using shadow tools
    "operations",
    "dept",
    "team",
]


class FinanceEvidenceCollector(EvidenceCollector):
    """
    Collects fabric plane evidence from financial records.

    Builds the "expected fabric plane inventory" from contracts and transactions.
    Identifies shadow fabric planes from department-level subscriptions.
    """

    @property
    def source_plane(self) -> EvidenceSourcePlane:
        return EvidenceSourcePlane.FINANCE

    def collect(
        self,
        planes: Planes,
        snapshot_timestamp: datetime,
        result: EvidenceCollectionResult
    ) -> None:
        """Extract fabric plane evidence from finance records."""
        finance = planes.finance

        # Track detected planes for shadow analysis
        detected_planes: Dict[str, bool] = {}  # plane_id -> is_enterprise

        # Process vendors
        for vendor in finance.vendors:
            plane_info = self._check_vendor(vendor, snapshot_timestamp, result)
            if plane_info:
                plane_id, is_enterprise = plane_info
                detected_planes[plane_id] = is_enterprise

        # Process contracts
        for contract in finance.contracts:
            plane_info = self._check_contract(contract, snapshot_timestamp, result)
            if plane_info:
                plane_id, is_enterprise = plane_info
                # Contracts are more authoritative than vendors
                detected_planes[plane_id] = detected_planes.get(plane_id, False) or is_enterprise

        # Process transactions
        for transaction in finance.transactions:
            plane_info = self._check_transaction(transaction, snapshot_timestamp, result)
            if plane_info:
                plane_id, is_enterprise = plane_info
                detected_planes[plane_id] = detected_planes.get(plane_id, False) or is_enterprise

    def _check_vendor(
        self,
        vendor: Vendor,
        timestamp: datetime,
        result: EvidenceCollectionResult
    ) -> Optional[Tuple[str, bool]]:
        """Check vendor for fabric plane subscription."""
        vendor_name = vendor.name.lower()

        match = self._match_vendor_name(vendor_name)
        if match:
            plane_type, plane_vendor, confidence = match
            is_enterprise = self._is_enterprise_subscription(vendor.raw_data)

            self._emit_finance_evidence(
                identifier=vendor.vendor_id,
                vendor_name=vendor.name,
                product_name=None,
                plane_type=plane_type,
                plane_vendor=plane_vendor,
                confidence=confidence,
                timestamp=timestamp,
                is_shadow=not is_enterprise,
                extra_data={"products": vendor.products},
                result=result
            )

            return (f"{plane_type.value}:{plane_vendor}", is_enterprise)

        # Also check product names
        for product in vendor.products:
            match = self._match_product_name(product.lower())
            if match:
                plane_type, plane_vendor, confidence = match
                is_enterprise = self._is_enterprise_subscription(vendor.raw_data)

                self._emit_finance_evidence(
                    identifier=vendor.vendor_id,
                    vendor_name=vendor.name,
                    product_name=product,
                    plane_type=plane_type,
                    plane_vendor=plane_vendor,
                    confidence=confidence,
                    timestamp=timestamp,
                    is_shadow=not is_enterprise,
                    extra_data={},
                    result=result
                )

                return (f"{plane_type.value}:{plane_vendor}", is_enterprise)

        return None

    def _check_contract(
        self,
        contract: Contract,
        timestamp: datetime,
        result: EvidenceCollectionResult
    ) -> Optional[Tuple[str, bool]]:
        """Check contract for fabric plane subscription."""
        vendor_name = (contract.vendor_name or "").lower()
        product_name = (contract.product or "").lower()

        # Check vendor name
        match = self._match_vendor_name(vendor_name) or self._match_product_name(product_name)
        if match:
            plane_type, plane_vendor, confidence = match
            is_enterprise = contract.is_recurring and contract.amount > 1000  # >$1K recurring = enterprise

            self._emit_finance_evidence(
                identifier=contract.contract_id,
                vendor_name=contract.vendor_name or "",
                product_name=contract.product,
                plane_type=plane_type,
                plane_vendor=plane_vendor,
                confidence=confidence,
                timestamp=contract.start_date or timestamp,
                is_shadow=not is_enterprise,
                extra_data={
                    "amount": contract.amount,
                    "currency": contract.currency,
                    "is_recurring": contract.is_recurring,
                    "end_date": contract.end_date.isoformat() if contract.end_date else None
                },
                result=result
            )

            return (f"{plane_type.value}:{plane_vendor}", is_enterprise)

        return None

    def _check_transaction(
        self,
        transaction: Transaction,
        timestamp: datetime,
        result: EvidenceCollectionResult
    ) -> Optional[Tuple[str, bool]]:
        """Check transaction for fabric plane subscription."""
        vendor_name = (transaction.vendor_name or "").lower()
        product_name = (transaction.product or "").lower()
        memo = (transaction.memo or "").lower()

        # Check all text fields
        combined = f"{vendor_name} {product_name} {memo}"

        for vendor_key, match_data in FABRIC_PLANE_VENDORS.items():
            if vendor_key in combined:
                plane_type, plane_vendor, confidence = match_data
                is_enterprise = transaction.is_recurring and transaction.amount > 100

                # Detect shadow indicators
                is_shadow = self._detect_shadow_indicators(combined, transaction.raw_data)

                self._emit_finance_evidence(
                    identifier=transaction.transaction_id,
                    vendor_name=transaction.vendor_name or "",
                    product_name=transaction.product,
                    plane_type=plane_type,
                    plane_vendor=plane_vendor,
                    confidence=confidence * 0.9,  # Transactions slightly less confident
                    timestamp=transaction.date or timestamp,
                    is_shadow=is_shadow or not is_enterprise,
                    extra_data={
                        "amount": transaction.amount,
                        "currency": transaction.currency,
                        "memo": transaction.memo
                    },
                    result=result
                )

                return (f"{plane_type.value}:{plane_vendor}", is_enterprise and not is_shadow)

        return None

    def _match_vendor_name(
        self,
        vendor_name: str
    ) -> Optional[Tuple[FabricPlaneType, str, float]]:
        """Match vendor name against known fabric plane vendors."""
        for pattern, match_data in FABRIC_PLANE_VENDORS.items():
            if pattern in vendor_name:
                return match_data
        return None

    def _match_product_name(
        self,
        product_name: str
    ) -> Optional[Tuple[FabricPlaneType, str, float]]:
        """Match product name against known fabric plane products."""
        for pattern, match_data in FABRIC_PLANE_PRODUCTS.items():
            if pattern in product_name:
                return match_data
        return None

    def _is_enterprise_subscription(
        self,
        raw_data: Optional[dict]
    ) -> bool:
        """Determine if subscription is enterprise-level (IT managed)."""
        if not raw_data:
            return True  # Assume enterprise if no data

        # Check for cost center indicators
        cost_center = str(raw_data.get("cost_center", "")).lower()
        owner = str(raw_data.get("owner", "")).lower()
        department = str(raw_data.get("department", "")).lower()

        combined = f"{cost_center} {owner} {department}"

        # If owned by IT or no department specified, assume enterprise
        if "it" in combined or "technology" in combined or "engineering" in combined:
            return True

        # Check for shadow indicators
        for indicator in SHADOW_PLANE_INDICATORS:
            if indicator in combined:
                return False

        return True

    def _detect_shadow_indicators(
        self,
        text: str,
        raw_data: Optional[dict]
    ) -> bool:
        """Detect if this is likely a shadow plane subscription."""
        # Check text for shadow indicators
        for indicator in SHADOW_PLANE_INDICATORS:
            if indicator in text:
                return True

        # Check raw_data
        if raw_data:
            cost_center = str(raw_data.get("cost_center", "")).lower()
            department = str(raw_data.get("department", "")).lower()

            for indicator in SHADOW_PLANE_INDICATORS:
                if indicator in cost_center or indicator in department:
                    return True

        return False

    def _emit_finance_evidence(
        self,
        identifier: str,
        vendor_name: str,
        product_name: Optional[str],
        plane_type: FabricPlaneType,
        plane_vendor: str,
        confidence: float,
        timestamp: datetime,
        is_shadow: bool,
        extra_data: dict,
        result: EvidenceCollectionResult
    ) -> None:
        """Emit evidence for fabric plane subscription."""
        evidence = self._create_evidence(
            signal_type="finance_subscription",
            signal_detail=f"{'Shadow ' if is_shadow else ''}Subscription to {vendor_name}"
                         f"{' (' + product_name + ')' if product_name else ''} "
                         f"indicates {plane_type.value} plane exists",
            confidence=confidence,
            timestamp=timestamp,
            fabric_plane_type=plane_type,
            fabric_plane_vendor=plane_vendor,
            raw_data={
                "vendor": vendor_name,
                "product": product_name,
                "is_shadow": is_shadow,
                **extra_data
            }
        )

        # Asset key is the fabric plane itself (we're confirming its existence)
        asset_key = f"{plane_type.value}:{plane_vendor}"
        result.add_evidence(asset_key, evidence)

        # Register the fabric plane
        plane = self._create_fabric_plane(
            plane_type=plane_type,
            vendor=plane_vendor,
            display_name=f"{vendor_name}{' (Shadow)' if is_shadow else ''}",
            domain=None,
            confidence=confidence
        )
        result.add_detected_plane(plane, is_shadow=is_shadow)

        if is_shadow:
            logger.warning("finance_evidence.shadow_plane_detected", extra={
                "vendor": vendor_name,
                "product": product_name,
                "plane_type": plane_type.value,
                "plane_vendor": plane_vendor
            })
        else:
            logger.info("finance_evidence.plane_subscription", extra={
                "vendor": vendor_name,
                "product": product_name,
                "plane_type": plane_type.value,
                "plane_vendor": plane_vendor,
                "confidence": confidence
            })
