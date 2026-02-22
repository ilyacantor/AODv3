"""
MiddlewareScanner - Detects enterprise middleware routes (MuleSoft, Workato, etc.)

Phase 4: The Autonomous Handshake
AOD finds the route -> POSTs config to DCL -> DCL starts ingesting.
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

FARM_URL = os.environ.get(
    "FARM_URL_PROD",
    os.environ.get("FARM_URL", "https://farmv2.onrender.com")
)


@dataclass
class MiddlewareRoute:
    """Detected middleware integration route."""
    platform: str
    detected_url: str
    related_asset: str
    confidence: float
    stream_type: str = "ndjson"
    

class MiddlewareScanner:
    """
    Scans for enterprise middleware integration points.
    
    In production, this would analyze:
    - Network traffic patterns
    - API gateway logs
    - Known middleware domain patterns
    - OAuth/API key configurations
    
    For Phase 4, returns mock detections against Farm's synthetic stream.
    """
    
    KNOWN_MIDDLEWARE_PLATFORMS = {
        "mulesoft": {
            "domains": ["mulesoft.com", "anypoint.mulesoft.com"],
            "stream_patterns": ["/api/stream/", "/integration/sync/"]
        },
        "workato": {
            "domains": ["workato.com", "workato.io"],
            "stream_patterns": ["/api/recipes/", "/webhooks/"]
        },
        "zapier": {
            "domains": ["zapier.com", "hooks.zapier.com"],
            "stream_patterns": ["/hooks/", "/api/v2/"]
        },
        "boomi": {
            "domains": ["boomi.com", "platform.boomi.com"],
            "stream_patterns": ["/ws/", "/api/"]
        }
    }
    
    def __init__(self, farm_url: Optional[str] = None):
        self.farm_url = (farm_url or FARM_URL).rstrip("/")
    
    def scan(self, target_platform: str = "mulesoft") -> MiddlewareRoute:
        """
        Scan for middleware routes.
        
        Args:
            target_platform: The middleware platform to scan for
            
        Returns:
            MiddlewareRoute with detected configuration
        """
        logger.info(f"middleware_scanner.scan", extra={
            "platform": target_platform,
            "farm_url": self.farm_url
        })
        
        if target_platform == "mulesoft":
            return MiddlewareRoute(
                platform="mulesoft",
                detected_url=f"{self.farm_url}/api/stream/synthetic/mulesoft",
                related_asset="salesforce_crm",
                confidence=0.98,
                stream_type="ndjson"
            )
        elif target_platform == "workato":
            return MiddlewareRoute(
                platform="workato",
                detected_url=f"{self.farm_url}/api/stream/synthetic/workato",
                related_asset="netsuite_erp",
                confidence=0.95,
                stream_type="ndjson"
            )
        else:
            return MiddlewareRoute(
                platform=target_platform,
                detected_url=f"{self.farm_url}/api/stream/synthetic/{target_platform}",
                related_asset="unknown",
                confidence=0.5,
                stream_type="ndjson"
            )
    
    def scan_all(self) -> list[MiddlewareRoute]:
        """
        Scan for all known middleware platforms.
        
        Returns:
            List of detected MiddlewareRoutes
        """
        routes = []
        
        routes.append(MiddlewareRoute(
            platform="mulesoft",
            detected_url=f"{self.farm_url}/api/stream/synthetic/mulesoft",
            related_asset="salesforce_crm",
            confidence=0.98,
            stream_type="ndjson"
        ))
        
        routes.append(MiddlewareRoute(
            platform="workato",
            detected_url=f"{self.farm_url}/api/stream/synthetic/workato",
            related_asset="netsuite_erp",
            confidence=0.85,
            stream_type="ndjson"
        ))
        
        logger.info(f"middleware_scanner.scan_all", extra={
            "routes_found": len(routes)
        })
        
        return routes
    
    def to_targeting_package(self, route: MiddlewareRoute, chaos_mode: bool = True) -> dict:
        """
        Convert a MiddlewareRoute to a DCL Targeting Package.
        
        Args:
            route: The detected middleware route
            chaos_mode: Whether to enable chaos testing
            
        Returns:
            Dict formatted for DCL's /api/ingest/provision endpoint
        """
        target_url = route.detected_url
        if chaos_mode and "?" not in target_url:
            target_url += "?chaos=true"
        elif chaos_mode:
            target_url += "&chaos=true"
        
        return {
            "connector_id": f"{route.platform[:4]}_auto_{hash(route.detected_url) % 1000:03d}",
            "source_type": f"{route.platform}_stream",
            "target_url": target_url,
            "policy": {
                "repair_enabled": True,
                "circuit_breaker_threshold": 5,
                "backoff_seconds": 60
            },
            "meta": {
                "detected_by": "aod_middleware_scanner",
                "related_asset": route.related_asset,
                "confidence": route.confidence,
                "stream_type": route.stream_type
            }
        }
