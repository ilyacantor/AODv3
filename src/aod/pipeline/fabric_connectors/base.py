"""
Base Fabric Plane Connector Interface

Defines the contract for all fabric plane connectors.
Each connector queries a specific fabric plane's API to extract authoritative
information about which assets/pipes flow through that plane.

This is Phase 2 of the evidence pipeline - direct crawl produces Tier 1 evidence.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

from ...models.output_contracts import (
    FabricPlaneType,
    FabricRoutingEvidence,
    EvidenceSourcePlane,
    EvidenceTier,
    ConnectivityModality,
    now_pst,
)

logger = logging.getLogger(__name__)


# Tier 1 confidence for direct crawl (authoritative)
TIER_1_CONFIDENCE = 0.95


class ConnectorStatus(str, Enum):
    """Status of a connector crawl attempt."""
    SUCCESS = "success"
    PARTIAL = "partial"  # Some data retrieved but errors occurred
    FAILED = "failed"
    NOT_CONFIGURED = "not_configured"
    AUTH_ERROR = "auth_error"
    TIMEOUT = "timeout"


@dataclass
class ConnectorConfig:
    """
    Configuration for a fabric plane connector.

    Each connector may require different auth mechanisms:
    - API key
    - OAuth tokens
    - Service account credentials
    - Connection strings
    """
    plane_type: FabricPlaneType
    vendor: str
    instance_name: str  # e.g., "prod-kong", "workato-enterprise"

    # Connection details
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    oauth_token: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    connection_string: Optional[str] = None

    # Connector behavior
    timeout_seconds: int = 30
    max_retries: int = 3
    page_size: int = 100

    # Filtering
    include_patterns: List[str] = field(default_factory=list)  # Only crawl matching
    exclude_patterns: List[str] = field(default_factory=list)  # Skip matching

    # Additional vendor-specific config
    extra_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CrawledAsset:
    """
    An asset discovered by direct fabric plane crawl.

    This is an authoritative record from the plane itself,
    so it has Tier 1 confidence.
    """
    asset_id: str  # ID within the fabric plane
    asset_name: str  # Display name
    asset_type: str  # Route, Recipe, Table, etc.

    # Identification for matching to existing assets
    domain: Optional[str] = None  # e.g., api.example.com
    uri: Optional[str] = None  # Full URI if available

    # Metadata
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    owner: Optional[str] = None

    # Raw data from the plane API
    raw_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CrawledPipe:
    """
    A pipe (data flow) discovered by direct fabric plane crawl.

    This represents the actual routing through the plane:
    - Source → Fabric Plane → Target

    Tier 1 confidence because it comes directly from the plane.
    """
    pipe_id: str  # Unique ID for this pipe
    pipe_name: str  # Display name

    # Connection details
    source_identifier: str  # What connects TO this plane (upstream)
    target_identifier: Optional[str] = None  # Where the plane routes TO (downstream)

    # Modality
    modality: ConnectivityModality = ConnectivityModality.API

    # Status
    is_active: bool = True
    last_activity: Optional[datetime] = None

    # Traffic metadata (if available)
    request_count: Optional[int] = None
    byte_count: Optional[int] = None
    error_rate: Optional[float] = None

    # Matching hints
    source_domain: Optional[str] = None
    target_domain: Optional[str] = None

    # Raw data from the plane API
    raw_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DirectCrawlResult:
    """
    Result of a direct fabric plane crawl.

    Contains all assets and pipes discovered from the plane,
    plus evidence records suitable for the reconciliation engine.
    """
    # Connector info
    plane_type: FabricPlaneType
    vendor: str
    instance_name: str

    # Crawl status
    status: ConnectorStatus
    crawl_started_at: datetime = field(default_factory=now_pst)
    crawl_completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    # Discovered data
    assets: List[CrawledAsset] = field(default_factory=list)
    pipes: List[CrawledPipe] = field(default_factory=list)

    # Pre-built evidence records (Tier 1)
    evidence: List[FabricRoutingEvidence] = field(default_factory=list)

    # Statistics
    total_items_crawled: int = 0
    items_filtered: int = 0  # Excluded by patterns
    items_errored: int = 0

    def add_evidence(
        self,
        signal_type: str,
        signal_detail: str,
        asset_key: str,
        raw_data: Optional[dict] = None
    ) -> FabricRoutingEvidence:
        """Helper to create Tier 1 evidence from crawl data."""
        evidence = FabricRoutingEvidence(
            evidence_id=f"dc_{self.vendor}_{len(self.evidence)}",
            source_plane=EvidenceSourcePlane.DIRECT_CRAWL,
            signal_type=signal_type,
            signal_detail=signal_detail,
            confidence=TIER_1_CONFIDENCE,
            timestamp=self.crawl_started_at,
            fabric_plane_type=self.plane_type,
            fabric_plane_vendor=self.vendor,
            raw_data=raw_data or {}
        )
        self.evidence.append(evidence)
        return evidence


class FabricPlaneConnector(ABC):
    """
    Abstract base class for fabric plane connectors.

    Each connector implements the crawl() method to query
    a specific fabric plane and extract authoritative data.

    Connectors should:
    1. Handle pagination for large datasets
    2. Apply include/exclude filters from config
    3. Build CrawledAsset and CrawledPipe records
    4. Generate Tier 1 evidence for each discovered item
    5. Handle errors gracefully with partial results
    """

    def __init__(self, config: ConnectorConfig):
        self.config = config
        self._validate_config()

    @property
    @abstractmethod
    def plane_type(self) -> FabricPlaneType:
        """Which fabric plane this connector handles."""
        pass

    @property
    @abstractmethod
    def vendor(self) -> str:
        """Vendor name (kong, workato, snowflake, etc.)."""
        pass

    @abstractmethod
    def _validate_config(self) -> None:
        """
        Validate that required config is present.
        Raise ValueError if config is invalid.
        """
        pass

    @abstractmethod
    def crawl(self) -> DirectCrawlResult:
        """
        Execute the fabric plane crawl.

        Should:
        1. Connect to the fabric plane API
        2. Paginate through all relevant data
        3. Filter based on include/exclude patterns
        4. Build CrawledAsset and CrawledPipe records
        5. Generate Tier 1 evidence
        6. Return DirectCrawlResult

        Returns:
            DirectCrawlResult with all discovered data
        """
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test the connection to the fabric plane.

        Returns:
            True if connection successful, False otherwise
        """
        pass

    def _matches_include(self, identifier: str) -> bool:
        """Check if identifier matches include patterns (or no patterns set)."""
        if not self.config.include_patterns:
            return True

        import re
        for pattern in self.config.include_patterns:
            if re.search(pattern, identifier, re.IGNORECASE):
                return True
        return False

    def _matches_exclude(self, identifier: str) -> bool:
        """Check if identifier matches exclude patterns."""
        if not self.config.exclude_patterns:
            return False

        import re
        for pattern in self.config.exclude_patterns:
            if re.search(pattern, identifier, re.IGNORECASE):
                return True
        return False

    def _should_include(self, identifier: str) -> bool:
        """Check if identifier should be included based on patterns."""
        if self._matches_exclude(identifier):
            return False
        return self._matches_include(identifier)

    def _create_result(self, status: ConnectorStatus = ConnectorStatus.SUCCESS) -> DirectCrawlResult:
        """Helper to create a DirectCrawlResult with connector info."""
        return DirectCrawlResult(
            plane_type=self.plane_type,
            vendor=self.vendor,
            instance_name=self.config.instance_name,
            status=status,
            crawl_started_at=now_pst()
        )

    def _log_crawl_start(self) -> None:
        """Log the start of a crawl."""
        logger.info("fabric_connector.crawl_start", extra={
            "plane_type": self.plane_type.value,
            "vendor": self.vendor,
            "instance": self.config.instance_name
        })

    def _log_crawl_complete(self, result: DirectCrawlResult) -> None:
        """Log the completion of a crawl."""
        logger.info("fabric_connector.crawl_complete", extra={
            "plane_type": self.plane_type.value,
            "vendor": self.vendor,
            "instance": self.config.instance_name,
            "status": result.status.value,
            "assets_found": len(result.assets),
            "pipes_found": len(result.pipes),
            "evidence_count": len(result.evidence)
        })


def crawl_all_planes(
    configs: List[ConnectorConfig]
) -> Dict[str, DirectCrawlResult]:
    """
    Execute crawls for all configured fabric plane connectors.

    This is the Phase 2 entry point - run after Phase 1 evidence collection.

    Args:
        configs: List of connector configurations

    Returns:
        Dict mapping instance_name to DirectCrawlResult
    """
    results: Dict[str, DirectCrawlResult] = {}

    # Import connectors here to avoid circular imports
    from .kong_connector import KongConnector
    from .workato_connector import WorkatoConnector
    from .snowflake_connector import SnowflakeConnector

    # Map vendor to connector class
    CONNECTOR_CLASSES = {
        "kong": KongConnector,
        "workato": WorkatoConnector,
        "snowflake": SnowflakeConnector,
    }

    for config in configs:
        connector_class = CONNECTOR_CLASSES.get(config.vendor.lower())
        if not connector_class:
            logger.warning("fabric_connector.unknown_vendor", extra={
                "vendor": config.vendor,
                "instance": config.instance_name
            })
            continue

        try:
            connector = connector_class(config)
            result = connector.crawl()
            results[config.instance_name] = result

        except Exception as e:
            logger.error("fabric_connector.crawl_error", extra={
                "vendor": config.vendor,
                "instance": config.instance_name,
                "error": str(e)
            })
            # Create a failed result
            result = DirectCrawlResult(
                plane_type=config.plane_type,
                vendor=config.vendor,
                instance_name=config.instance_name,
                status=ConnectorStatus.FAILED,
                error_message=str(e)
            )
            results[config.instance_name] = result

    logger.info("fabric_connector.all_crawls_complete", extra={
        "total_configs": len(configs),
        "successful": sum(1 for r in results.values() if r.status == ConnectorStatus.SUCCESS),
        "failed": sum(1 for r in results.values() if r.status == ConnectorStatus.FAILED)
    })

    return results
