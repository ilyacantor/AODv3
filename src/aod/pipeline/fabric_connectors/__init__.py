"""
Fabric Plane Connectors

Direct crawl connectors for fabric plane platforms.
These connectors query fabric plane APIs to get authoritative (Tier 1)
information about which assets/pipes flow through each plane.

Supported planes:
- Kong: API Gateway routes and upstreams
- Workato: iPaaS recipes and connections
- Snowflake: Data Warehouse tables and access patterns

Each connector implements the FabricPlaneConnector interface and produces
DirectCrawlResult records with Tier 1 confidence (0.95).
"""

from .base import (
    FabricPlaneConnector,
    DirectCrawlResult,
    CrawledAsset,
    CrawledPipe,
    ConnectorConfig,
    crawl_all_planes,
)
from .kong_connector import KongConnector
from .workato_connector import WorkatoConnector
from .snowflake_connector import SnowflakeConnector

__all__ = [
    "FabricPlaneConnector",
    "DirectCrawlResult",
    "CrawledAsset",
    "CrawledPipe",
    "ConnectorConfig",
    "crawl_all_planes",
    "KongConnector",
    "WorkatoConnector",
    "SnowflakeConnector",
]
