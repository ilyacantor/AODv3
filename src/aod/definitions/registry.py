"""
Farm Definitions Registry - Cached Vendor & Domain Definitions.

Syncs authoritative vendor/domain lists from Farm's GET /api/fabric/definitions
endpoint and caches them in memory. AOD never stores its own vendor lists.

Cache Strategy:
- On startup: Sync from Farm (blocking)
- Background: Periodic refresh every 5 minutes
- Fallback: Use embedded defaults if Farm unreachable (logged as warning)

The fallback defaults are INTENTIONALLY minimal - just enough to not crash.
Production should always sync from Farm.
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class FabricPlaneTypeStr(str, Enum):
    """Fabric plane types as strings for definitions."""
    IPAAS = "ipaas"
    API_GATEWAY = "api_gateway"
    EVENT_BUS = "event_bus"
    DATA_WAREHOUSE = "data_warehouse"


@dataclass
class VendorEntry:
    """A vendor in the authoritative registry."""
    vendor_name: str
    domains: List[str]
    fabric_plane: Optional[str] = None
    sor_category: Optional[str] = None  # customer, employee, financial, etc.
    is_infrastructure: bool = False
    updated_at: Optional[datetime] = None


@dataclass
class SaaSRoutingEntry:
    """Known enterprise SaaS app routing through fabric planes."""
    app_name: str
    fabric_plane: str
    default_vendor: str


@dataclass
class FabricVendorPatterns:
    """Domain patterns for a fabric plane vendor."""
    vendor_name: str
    domains: List[str]


@dataclass
class FarmDefinitions:
    """
    Authoritative definitions from Farm.

    This is the single source of truth for:
    - Fabric vendor domain patterns
    - Known enterprise SaaS routing
    - SOR vendor patterns
    - Infrastructure domain exclusions
    """
    # Fabric vendor patterns: plane_type -> vendor_name -> domains
    fabric_vendors: Dict[str, Dict[str, List[str]]] = field(default_factory=dict)

    # Known enterprise SaaS routing: app_name -> (plane_type, default_vendor)
    saas_routing: Dict[str, Tuple[str, str]] = field(default_factory=dict)

    # SOR vendor patterns: category -> domains
    sor_vendors: Dict[str, List[str]] = field(default_factory=dict)

    # Infrastructure domains to exclude
    infrastructure_domains: List[str] = field(default_factory=list)

    # Category to plane inference (Tier 3)
    category_to_plane: Dict[str, str] = field(default_factory=dict)

    # Confidence thresholds
    confidence_tiers: Dict[str, float] = field(default_factory=dict)

    # Metadata
    synced_at: Optional[datetime] = None
    farm_version: Optional[str] = None

    def get_fabric_vendor_domains(self, plane_type: str, vendor: str) -> List[str]:
        """Get domain patterns for a fabric vendor."""
        return self.fabric_vendors.get(plane_type, {}).get(vendor, [])

    def get_saas_routing(self, app_name: str) -> Optional[Tuple[str, str]]:
        """Get routing for a known SaaS app: (plane_type, vendor)."""
        app_lower = app_name.lower()
        for name, routing in self.saas_routing.items():
            if name in app_lower:
                return routing
        return None

    def get_sor_domains(self, category: str) -> List[str]:
        """Get domain patterns for an SOR category."""
        return self.sor_vendors.get(category, [])

    def is_infrastructure_domain(self, domain: str) -> bool:
        """Check if domain is infrastructure (should be excluded)."""
        domain_lower = domain.lower()
        return any(d.lower() in domain_lower for d in self.infrastructure_domains)

    def get_plane_for_category(self, category: str) -> Optional[str]:
        """Get inferred fabric plane for a category (Tier 3)."""
        return self.category_to_plane.get(category.lower())


# Global cache
_definitions_cache: Optional[FarmDefinitions] = None
_cache_expiry: Optional[datetime] = None
_CACHE_TTL_SECONDS = int(os.getenv("FARM_DEFINITIONS_TTL", "300"))  # 5 min default


def _get_fallback_definitions() -> FarmDefinitions:
    """
    Minimal fallback definitions when Farm is unreachable.

    WARNING: These are intentionally sparse.
    Production should always sync from Farm.
    """
    logger.warning("definitions.using_fallback",
                   extra={"reason": "Farm unreachable, using embedded fallback"})

    return FarmDefinitions(
        fabric_vendors={
            "ipaas": {
                "mulesoft": ["mulesoft.com", "anypoint.mulesoft.com", "cloudhub.io"],
                "workato": ["workato.com"],
                "boomi": ["boomi.com"],
            },
            "api_gateway": {
                "kong": ["kong.com", "konghq.com"],
                "apigee": ["apigee.com", "apigee.googleapis.com"],
            },
            "event_bus": {
                "confluent": ["confluent.io", "confluent.cloud"],
                "eventbridge": ["events.amazonaws.com"],
            },
            "data_warehouse": {
                "snowflake": ["snowflake.com", "snowflakecomputing.com"],
                "bigquery": ["bigquery.googleapis.com"],
            },
        },
        saas_routing={
            "salesforce": ("ipaas", "workato"),
            "workday": ("ipaas", "workato"),
            "netsuite": ("ipaas", "workato"),
            "servicenow": ("ipaas", "workato"),
            "slack": ("api_gateway", "kong"),
            "github": ("api_gateway", "kong"),
        },
        sor_vendors={
            "customer": ["salesforce.com", "hubspot.com", "dynamics.com"],
            "employee": ["workday.com", "adp.com", "bamboohr.com"],
            "financial": ["netsuite.com", "quickbooks.com", "xero.com"],
            "identity": ["okta.com", "onelogin.com", "auth0.com"],
        },
        infrastructure_domains=[
            "github.com", "gitlab.com", "docker.com", "kubernetes.io",
            "aws.amazon.com", "azure.microsoft.com", "cloud.google.com",
        ],
        category_to_plane={
            "crm": "ipaas",
            "erp": "ipaas",
            "finance": "ipaas",
            "hcm": "ipaas",
            "api": "api_gateway",
            "data": "data_warehouse",
            "analytics": "data_warehouse",
            "messaging": "event_bus",
        },
        confidence_tiers={
            "tier_1_direct": 0.95,
            "tier_2_multi_source": 0.85,
            "tier_2_single_source": 0.75,
            "tier_2_lower": 0.70,
            "tier_3_inferred": 0.35,
        },
        synced_at=datetime.utcnow(),
        farm_version="fallback_v1",
    )


async def _fetch_from_farm() -> Optional[FarmDefinitions]:
    """
    Fetch definitions from Farm's GET /api/fabric/definitions endpoint.

    Returns None if Farm is unreachable.
    """
    try:
        from ..farm_client import FarmClient

        farm_url = os.getenv("FARM_URL", "")
        if not farm_url:
            logger.warning("definitions.no_farm_url",
                          extra={"detail": "FARM_URL not set, using fallback"})
            return None

        client = FarmClient(farm_url)

        # Try to fetch definitions endpoint
        # For now, use the existing fabric endpoints to build definitions
        result = await client.get_weights_matrix()

        if not result.success:
            logger.warning("definitions.farm_fetch_failed",
                          extra={"error": result.error})
            return None

        # Parse Farm response into FarmDefinitions
        # The actual Farm endpoint structure may differ
        data = result.data or {}

        return _parse_farm_response(data)

    except Exception as e:
        logger.exception("definitions.fetch_error", extra={"error": str(e)})
        return None


def _parse_farm_response(data: dict) -> FarmDefinitions:
    """Parse Farm API response into FarmDefinitions."""
    # Extract fabric vendors from weights matrix
    fabric_vendors = {}
    saas_routing = {}

    # Parse vendor_domains if present
    vendor_domains = data.get("vendor_domains", {})
    for plane_type, vendors in vendor_domains.items():
        fabric_vendors[plane_type] = vendors

    # Parse saas_routing if present
    saas_data = data.get("saas_routing", {})
    for app_name, routing in saas_data.items():
        if isinstance(routing, dict):
            plane = routing.get("plane", "ipaas")
            vendor = routing.get("vendor", "unknown")
            saas_routing[app_name] = (plane, vendor)
        elif isinstance(routing, (list, tuple)) and len(routing) >= 2:
            saas_routing[app_name] = (routing[0], routing[1])

    # Parse SOR vendors
    sor_vendors = data.get("sor_vendors", {})

    # Parse infrastructure domains
    infra_domains = data.get("infrastructure_domains", [])

    # Parse category mappings
    category_to_plane = data.get("category_to_plane", {})

    # Parse confidence tiers
    confidence_tiers = data.get("confidence_tiers", {
        "tier_1_direct": 0.95,
        "tier_2_multi_source": 0.85,
        "tier_2_single_source": 0.75,
        "tier_2_lower": 0.70,
        "tier_3_inferred": 0.35,
    })

    return FarmDefinitions(
        fabric_vendors=fabric_vendors,
        saas_routing=saas_routing,
        sor_vendors=sor_vendors,
        infrastructure_domains=infra_domains,
        category_to_plane=category_to_plane,
        confidence_tiers=confidence_tiers,
        synced_at=datetime.utcnow(),
        farm_version=data.get("version", "unknown"),
    )


def get_definitions() -> FarmDefinitions:
    """
    Get cached definitions, using fallback if needed.

    This is a synchronous accessor for cached definitions.
    Call sync_from_farm() to refresh the cache.
    """
    global _definitions_cache

    if _definitions_cache is None:
        _definitions_cache = _get_fallback_definitions()

    return _definitions_cache


async def sync_from_farm() -> FarmDefinitions:
    """
    Sync definitions from Farm.

    Updates the global cache and returns the new definitions.
    Falls back to embedded defaults if Farm is unreachable.
    """
    global _definitions_cache, _cache_expiry

    definitions = await _fetch_from_farm()

    if definitions is None:
        definitions = _get_fallback_definitions()

    _definitions_cache = definitions
    _cache_expiry = datetime.utcnow() + timedelta(seconds=_CACHE_TTL_SECONDS)

    logger.info("definitions.synced", extra={
        "farm_version": definitions.farm_version,
        "fabric_vendors_count": sum(len(v) for v in definitions.fabric_vendors.values()),
        "saas_routing_count": len(definitions.saas_routing),
        "sor_vendors_count": sum(len(v) for v in definitions.sor_vendors.values()),
    })

    return definitions


def clear_cache() -> None:
    """Clear the definitions cache (for testing)."""
    global _definitions_cache, _cache_expiry
    _definitions_cache = None
    _cache_expiry = None


def is_cache_stale() -> bool:
    """Check if cache needs refresh."""
    global _cache_expiry
    if _cache_expiry is None:
        return True
    return datetime.utcnow() > _cache_expiry
