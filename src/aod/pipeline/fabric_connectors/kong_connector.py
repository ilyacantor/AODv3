"""
Kong Admin API Connector

Crawls Kong API Gateway to discover routes, services, and upstreams.
This is Tier 1 evidence - authoritative data from the gateway itself.

What Kong reveals:
- Routes: Which paths/hosts are exposed through the gateway
- Services: What upstream services those routes point to
- Upstreams: Load-balanced targets for services
- Plugins: Auth, rate limiting, transformations applied to routes

From this we can build:
- Pipes: Route → Service → Upstream target relationships
- Assets: The services/upstreams exposed through Kong
- Traffic metadata: Request counts, latency (if available)
"""

import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse

from ...models.output_contracts import (
    FabricPlaneType,
    ConnectivityModality,
)
from .base import (
    FabricPlaneConnector,
    ConnectorConfig,
    DirectCrawlResult,
    CrawledAsset,
    CrawledPipe,
    ConnectorStatus,
    TIER_1_CONFIDENCE,
)

logger = logging.getLogger(__name__)


class KongConnector(FabricPlaneConnector):
    """
    Kong Admin API connector for API Gateway fabric plane crawl.

    Queries Kong Admin API to discover:
    - Routes (path/host mappings)
    - Services (upstream backends)
    - Upstreams (load-balanced targets)

    Kong Admin API reference: https://docs.konghq.com/gateway/latest/admin-api/
    """

    @property
    def plane_type(self) -> FabricPlaneType:
        return FabricPlaneType.API_GATEWAY

    @property
    def vendor(self) -> str:
        return "kong"

    def _validate_config(self) -> None:
        """Validate Kong connector config."""
        if not self.config.base_url:
            raise ValueError("Kong connector requires base_url (Admin API endpoint)")

        # API key is optional (Kong can run without auth in some configs)
        # but recommended in production
        if not self.config.api_key:
            logger.warning("kong_connector.no_api_key",
                         extra={"instance": self.config.instance_name})

    def test_connection(self) -> bool:
        """Test connection to Kong Admin API."""
        try:
            response = self._make_request("GET", "/")
            return response is not None and "version" in response
        except Exception as e:
            logger.error("kong_connector.connection_test_failed", extra={
                "instance": self.config.instance_name,
                "error": str(e)
            })
            return False

    def crawl(self) -> DirectCrawlResult:
        """
        Execute Kong Admin API crawl.

        Crawls in order:
        1. Services (upstream backends)
        2. Routes (path/host mappings that point to services)
        3. Upstreams (load-balanced targets)

        Builds pipes from Route → Service → Upstream relationships.
        """
        self._log_crawl_start()
        result = self._create_result()

        try:
            # Crawl services first (routes reference them)
            services = self._crawl_services(result)

            # Crawl routes (the entry points to the gateway)
            routes = self._crawl_routes(result, services)

            # Crawl upstreams (load-balanced backends)
            upstreams = self._crawl_upstreams(result)

            # Build pipes from route→service→upstream relationships
            self._build_pipes(result, routes, services, upstreams)

            result.status = ConnectorStatus.SUCCESS
            result.crawl_completed_at = datetime.utcnow()

        except Exception as e:
            result.status = ConnectorStatus.FAILED
            result.error_message = str(e)
            logger.error("kong_connector.crawl_failed", extra={
                "instance": self.config.instance_name,
                "error": str(e)
            })

        self._log_crawl_complete(result)
        return result

    def _make_request(
        self,
        method: str,
        path: str,
        params: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Make a request to Kong Admin API.

        In production, this would use httpx or requests.
        For now, returns simulated data for testing.
        """
        # Build headers
        headers = {"Accept": "application/json"}
        if self.config.api_key:
            headers["Kong-Admin-Token"] = self.config.api_key

        # TODO: Replace with actual HTTP client
        # For now, this is a stub that logs the request
        logger.debug("kong_connector.request", extra={
            "method": method,
            "path": path,
            "base_url": self.config.base_url
        })

        # Return None - actual implementation would make HTTP request
        # The connector is designed to be integration-ready
        return None

    def _paginate(
        self,
        path: str,
        key: str = "data"
    ) -> List[Dict[str, Any]]:
        """
        Paginate through Kong Admin API results.

        Kong uses offset-based pagination with 'next' links.
        """
        all_items = []
        offset = None

        while True:
            params = {"size": self.config.page_size}
            if offset:
                params["offset"] = offset

            response = self._make_request("GET", path, params)
            if not response:
                break

            items = response.get(key, [])
            all_items.extend(items)

            # Check for next page
            offset = response.get("offset")
            if not offset:
                break

        return all_items

    def _crawl_services(
        self,
        result: DirectCrawlResult
    ) -> Dict[str, Dict[str, Any]]:
        """Crawl Kong services (upstream backends)."""
        services_by_id: Dict[str, Dict[str, Any]] = {}

        services = self._paginate("/services")
        for service in services:
            service_id = service.get("id")
            service_name = service.get("name", service_id)

            if not self._should_include(service_name):
                result.items_filtered += 1
                continue

            # Extract upstream target info
            host = service.get("host", "")
            port = service.get("port", 80)
            path = service.get("path", "/")
            protocol = service.get("protocol", "http")

            # Build target URL
            target_url = f"{protocol}://{host}:{port}{path}"

            # Create crawled asset for the service
            asset = CrawledAsset(
                asset_id=service_id,
                asset_name=service_name,
                asset_type="kong_service",
                domain=host,
                uri=target_url,
                created_at=self._parse_timestamp(service.get("created_at")),
                updated_at=self._parse_timestamp(service.get("updated_at")),
                raw_data=service
            )
            result.assets.append(asset)
            result.total_items_crawled += 1

            # Create Tier 1 evidence for service discovery
            result.add_evidence(
                signal_type="kong_service",
                signal_detail=f"Kong service '{service_name}' routes to {host}:{port}",
                asset_key=host,
                raw_data={
                    "service_id": service_id,
                    "service_name": service_name,
                    "target_host": host,
                    "target_port": port,
                    "protocol": protocol
                }
            )

            services_by_id[service_id] = service

        logger.info("kong_connector.services_crawled", extra={
            "instance": self.config.instance_name,
            "count": len(services_by_id)
        })

        return services_by_id

    def _crawl_routes(
        self,
        result: DirectCrawlResult,
        services: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Crawl Kong routes (entry points)."""
        all_routes = []

        routes = self._paginate("/routes")
        for route in routes:
            route_id = route.get("id")
            route_name = route.get("name", route_id)

            if not self._should_include(route_name):
                result.items_filtered += 1
                continue

            # Get route paths and hosts
            paths = route.get("paths", [])
            hosts = route.get("hosts", [])
            methods = route.get("methods", ["*"])

            # Get associated service
            service_ref = route.get("service", {})
            service_id = service_ref.get("id") if isinstance(service_ref, dict) else service_ref

            # Build route identifiers
            route_hosts = ", ".join(hosts) if hosts else "*"
            route_paths = ", ".join(paths) if paths else "/"

            # Create crawled asset for the route
            primary_host = hosts[0] if hosts else None
            primary_path = paths[0] if paths else "/"

            asset = CrawledAsset(
                asset_id=route_id,
                asset_name=route_name,
                asset_type="kong_route",
                domain=primary_host,
                uri=f"{primary_host or '*'}{primary_path}",
                created_at=self._parse_timestamp(route.get("created_at")),
                updated_at=self._parse_timestamp(route.get("updated_at")),
                raw_data=route
            )
            result.assets.append(asset)
            result.total_items_crawled += 1

            # Create Tier 1 evidence for route discovery
            result.add_evidence(
                signal_type="kong_route",
                signal_detail=f"Kong route '{route_name}' exposes {route_hosts}{route_paths}",
                asset_key=primary_host or route_name,
                raw_data={
                    "route_id": route_id,
                    "route_name": route_name,
                    "hosts": hosts,
                    "paths": paths,
                    "methods": methods,
                    "service_id": service_id
                }
            )

            all_routes.append({
                **route,
                "_service_id": service_id
            })

        logger.info("kong_connector.routes_crawled", extra={
            "instance": self.config.instance_name,
            "count": len(all_routes)
        })

        return all_routes

    def _crawl_upstreams(
        self,
        result: DirectCrawlResult
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Crawl Kong upstreams and their targets."""
        upstreams_by_name: Dict[str, List[Dict[str, Any]]] = {}

        upstreams = self._paginate("/upstreams")
        for upstream in upstreams:
            upstream_id = upstream.get("id")
            upstream_name = upstream.get("name", upstream_id)

            if not self._should_include(upstream_name):
                result.items_filtered += 1
                continue

            # Get targets for this upstream
            targets = self._paginate(f"/upstreams/{upstream_id}/targets")
            target_list = []

            for target in targets:
                target_addr = target.get("target", "")
                weight = target.get("weight", 100)

                target_list.append({
                    "target": target_addr,
                    "weight": weight,
                    "health": target.get("health", "unknown")
                })

                # Create asset for each target
                target_host = target_addr.split(":")[0] if ":" in target_addr else target_addr
                asset = CrawledAsset(
                    asset_id=f"{upstream_id}_{target_addr}",
                    asset_name=f"{upstream_name}/{target_addr}",
                    asset_type="kong_upstream_target",
                    domain=target_host,
                    uri=target_addr,
                    raw_data=target
                )
                result.assets.append(asset)
                result.total_items_crawled += 1

            upstreams_by_name[upstream_name] = target_list

            # Evidence for upstream discovery
            if target_list:
                result.add_evidence(
                    signal_type="kong_upstream",
                    signal_detail=f"Kong upstream '{upstream_name}' has {len(target_list)} targets",
                    asset_key=upstream_name,
                    raw_data={
                        "upstream_id": upstream_id,
                        "upstream_name": upstream_name,
                        "targets": target_list
                    }
                )

        logger.info("kong_connector.upstreams_crawled", extra={
            "instance": self.config.instance_name,
            "count": len(upstreams_by_name)
        })

        return upstreams_by_name

    def _build_pipes(
        self,
        result: DirectCrawlResult,
        routes: List[Dict[str, Any]],
        services: Dict[str, Dict[str, Any]],
        upstreams: Dict[str, List[Dict[str, Any]]]
    ) -> None:
        """Build pipes from route→service→upstream relationships."""
        for route in routes:
            route_id = route.get("id")
            route_name = route.get("name", route_id)
            service_id = route.get("_service_id")

            # Get the associated service
            service = services.get(service_id, {})
            if not service:
                continue

            service_name = service.get("name", service_id)
            target_host = service.get("host", "")

            # Determine source (who calls the route)
            hosts = route.get("hosts", [])
            paths = route.get("paths", [])
            source_identifier = hosts[0] if hosts else (paths[0] if paths else route_name)

            # Check if target is an upstream (load-balanced)
            targets = upstreams.get(target_host, [])

            if targets:
                # Multiple targets through upstream
                for target_info in targets:
                    target_addr = target_info.get("target", "")
                    pipe = CrawledPipe(
                        pipe_id=f"kong_{route_id}_{target_addr}",
                        pipe_name=f"{route_name} → {target_addr}",
                        source_identifier=source_identifier,
                        target_identifier=target_addr,
                        modality=ConnectivityModality.API,
                        is_active=target_info.get("health") != "unhealthy",
                        source_domain=source_identifier if "." in source_identifier else None,
                        target_domain=target_addr.split(":")[0] if target_addr else None,
                        raw_data={
                            "route_id": route_id,
                            "route_name": route_name,
                            "service_id": service_id,
                            "service_name": service_name,
                            "upstream": target_host,
                            "target": target_addr,
                            "weight": target_info.get("weight", 100)
                        }
                    )
                    result.pipes.append(pipe)
            else:
                # Direct service target (no upstream)
                pipe = CrawledPipe(
                    pipe_id=f"kong_{route_id}_{service_id}",
                    pipe_name=f"{route_name} → {service_name}",
                    source_identifier=source_identifier,
                    target_identifier=target_host,
                    modality=ConnectivityModality.API,
                    is_active=True,
                    source_domain=source_identifier if "." in source_identifier else None,
                    target_domain=target_host,
                    raw_data={
                        "route_id": route_id,
                        "route_name": route_name,
                        "service_id": service_id,
                        "service_name": service_name,
                        "target_host": target_host,
                        "target_port": service.get("port", 80)
                    }
                )
                result.pipes.append(pipe)

        logger.info("kong_connector.pipes_built", extra={
            "instance": self.config.instance_name,
            "count": len(result.pipes)
        })

    def _parse_timestamp(self, ts: Optional[int]) -> Optional[datetime]:
        """Parse Kong Unix timestamp (seconds)."""
        if ts:
            try:
                return datetime.utcfromtimestamp(ts)
            except (ValueError, OSError) as e:
                logger.debug("Failed to parse Unix timestamp %r: %s", ts, e)
        return None
