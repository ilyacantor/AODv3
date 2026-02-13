"""FarmClient - HTTP client for fetching snapshots from AOS Farm"""

import httpx
import logging
import os
from typing import Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# HTTP client configuration (environment-configurable)
FARM_TIMEOUT = float(os.getenv("FARM_TIMEOUT", "25.0"))
FARM_MAX_RETRIES = int(os.getenv("FARM_RETRIES", "3"))
FARM_PROBE_TIMEOUT = float(os.getenv("FARM_PROBE_TIMEOUT", "1.0"))  # Fast probe for startup

# Retryable HTTP status codes:
# - 408: Request Timeout
# - 429: Too Many Requests (rate limited)
# - 502: Bad Gateway
# - 503: Service Unavailable
# - 504: Gateway Timeout
RETRYABLE_STATUS_CODES = {408, 429, 502, 503, 504}


@dataclass
class FarmFetchResult:
    """Result of fetching a snapshot from Farm"""
    success: bool
    data: dict[str, Any] | None = None
    error: str = ""
    error_type: str = ""


@dataclass
class FarmListResult:
    """Result of listing snapshots from Farm"""
    success: bool
    snapshots: list[dict[str, Any]] | None = None
    error: str = ""
    error_type: str = ""


@dataclass
class FarmFabricResult:
    """Result of fabric-related operations from Farm"""
    success: bool
    data: dict[str, Any] | list[dict[str, Any]] | None = None
    error: str = ""
    error_type: str = ""


class FarmClientError(Exception):
    """Error from Farm client operations"""
    def __init__(self, message: str, error_type: str = "FARM_ERROR"):
        super().__init__(message)
        self.error_type = error_type


class FarmClient:
    """HTTP client for fetching snapshots from AOS Farm"""

    def __init__(self, base_url: str, timeout: float = FARM_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def probe(self) -> bool:
        """
        Fast health probe - is Farm reachable right now?

        Uses FARM_PROBE_TIMEOUT (default 1s) to avoid blocking startup.
        No retries. If Farm doesn't respond in 1s, it's asleep.

        Returns True if Farm responds with any 2xx status.
        """
        url = f"{self.base_url}/api/snapshots?tenant_id=&limit=1"
        try:
            async with httpx.AsyncClient(timeout=FARM_PROBE_TIMEOUT) as client:
                response = await client.get(url)
                is_up = response.status_code < 400
                logger.info("farm.probe", extra={
                    "status": response.status_code, "up": is_up
                })
                return is_up
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError):
            logger.info("farm.probe.down", extra={"timeout": FARM_PROBE_TIMEOUT})
            return False
        except Exception:
            return False

    async def _make_request_with_retry(self, url: str, context: str = "request") -> tuple[httpx.Response | None, str | None]:
        """
        Make HTTP request with configurable retries on transient failures.

        Retries on: 408, 429, 502, 503, 504 status codes and network errors.
        Retry count controlled by FARM_RETRIES env var (default: 3 attempts).

        Returns:
            Tuple of (response, error_message). If error_message is set, response is None.
        """
        last_error = None
        max_attempts = FARM_MAX_RETRIES

        for attempt in range(max_attempts):
            is_last_attempt = (attempt == max_attempts - 1)

            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(url)

                    # Check for retryable status codes
                    if response.status_code in RETRYABLE_STATUS_CODES:
                        # Check if response is HTML (Replit "app not running" page)
                        content_type = response.headers.get("content-type", "")
                        if "html" in content_type.lower() or response.text.strip().startswith("<!"):
                            last_error = "FARM_WAKING_OR_DOWN"
                            if not is_last_attempt:
                                logger.info(f"farm.{context}.retry", extra={"url": url, "status": response.status_code, "attempt": attempt + 1})
                                continue
                            break

                        last_error = f"HTTP {response.status_code}"
                        if not is_last_attempt:
                            logger.info(f"farm.{context}.retry", extra={"url": url, "status": response.status_code, "attempt": attempt + 1})
                            continue
                        break

                    return response, None

            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
                last_error = "FARM_WAKING_OR_DOWN"
                logger.warning(f"farm.{context}.network_error", extra={
                    "url": url, "attempt": attempt + 1, "max_attempts": max_attempts, "error": str(e)
                })
                if not is_last_attempt:
                    continue

            except Exception as e:
                last_error = str(e)
                logger.exception(f"farm.{context}.unexpected_error", extra={"url": url})
                break

        return None, last_error
    
    async def list_snapshots(self, tenant_id: str, limit: int = 20, size: str | None = None) -> FarmListResult:
        """
        List available snapshots from Farm for a tenant.
        
        Args:
            tenant_id: The tenant ID to list snapshots for
            limit: Maximum number of snapshots to return (default 20)
            size: Optional size filter (small, medium, large)
            
        Returns:
            FarmListResult with success status and snapshots list or error
        """
        url = f"{self.base_url}/api/snapshots?tenant_id={tenant_id}&limit={limit}"
        if size:
            url += f"&size={size}"
        
        logger.info("farm.list_snapshots.start", extra={"tenant_id": tenant_id, "limit": limit, "size": size})
        
        response, error = await self._make_request_with_retry(url, "list_snapshots")
        
        if error:
            return FarmListResult(
                success=False,
                error=error,
                error_type="FARM_WAKING_OR_DOWN"
            )
        
        assert response is not None
        
        if response.status_code >= 400:
            logger.warning("farm.list_snapshots.http_error", extra={
                "tenant_id": tenant_id, "status_code": response.status_code
            })
            return FarmListResult(
                success=False,
                error=f"Farm server returned HTTP {response.status_code}: {response.text[:200]}",
                error_type="UPSTREAM_ERROR"
            )
        
        content_type = response.headers.get("content-type", "")
        if "json" not in content_type.lower():
            # Check for HTML response (Replit proxy page)
            if "html" in content_type.lower() or response.text.strip().startswith("<!"):
                return FarmListResult(
                    success=False,
                    error="FARM_WAKING_OR_DOWN",
                    error_type="FARM_WAKING_OR_DOWN"
                )
            logger.warning("farm.list_snapshots.invalid_content_type", extra={
                "tenant_id": tenant_id, "content_type": content_type
            })
            return FarmListResult(
                success=False,
                error=f"Farm server returned non-JSON content-type: {content_type}",
                error_type="UPSTREAM_ERROR"
            )
        
        try:
            data = response.json()
        except Exception as e:
            logger.error("farm.list_snapshots.json_parse_error", extra={
                "tenant_id": tenant_id, "error": str(e)
            })
            return FarmListResult(
                success=False,
                error=f"Farm server returned invalid JSON: {str(e)}",
                error_type="UPSTREAM_ERROR"
            )
        
        if isinstance(data, list):
            result = FarmListResult(success=True, snapshots=data)
        elif isinstance(data, dict) and "snapshots" in data:
            result = FarmListResult(success=True, snapshots=data["snapshots"])
        else:
            result = FarmListResult(success=True, snapshots=[data] if isinstance(data, dict) else [])
        
        logger.info("farm.list_snapshots.success", extra={
            "tenant_id": tenant_id, "snapshot_count": len(result.snapshots or [])
        })
        return result

    async def fetch_snapshot(self, snapshot_id: str) -> FarmFetchResult:
        """
        Fetch a snapshot from Farm.
        
        Validates:
        - HTTP status code (must be 2xx)
        - Content-Type includes JSON
        - Body is non-empty JSON
        
        Args:
            snapshot_id: The snapshot ID to fetch
            
        Returns:
            FarmFetchResult with success status and data or error
        """
        url = f"{self.base_url}/api/snapshots/{snapshot_id}"
        
        logger.info("farm.fetch_snapshot.start", extra={"snapshot_id": snapshot_id})
        
        response, error = await self._make_request_with_retry(url, "fetch_snapshot")
        
        if error:
            return FarmFetchResult(
                success=False,
                error=error,
                error_type="FARM_WAKING_OR_DOWN"
            )
        
        assert response is not None
        
        if response.status_code == 404:
            logger.warning("farm.fetch_snapshot.not_found", extra={"snapshot_id": snapshot_id})
            return FarmFetchResult(
                success=False,
                error=f"Snapshot '{snapshot_id}' not found on Farm server (HTTP 404)",
                error_type="FARM_SNAPSHOT_NOT_FOUND"
            )
        
        if response.status_code >= 400:
            logger.warning("farm.fetch_snapshot.http_error", extra={
                "snapshot_id": snapshot_id, "status_code": response.status_code
            })
            return FarmFetchResult(
                success=False,
                error=f"Farm server returned HTTP {response.status_code}: {response.text[:200]}",
                error_type="FARM_HTTP_ERROR"
            )
        
        content_type = response.headers.get("content-type", "")
        if "json" not in content_type.lower():
            # Check for HTML response (Replit proxy page)
            if "html" in content_type.lower() or response.text.strip().startswith("<!"):
                return FarmFetchResult(
                    success=False,
                    error="FARM_WAKING_OR_DOWN",
                    error_type="FARM_WAKING_OR_DOWN"
                )
            logger.warning("farm.fetch_snapshot.invalid_content_type", extra={
                "snapshot_id": snapshot_id, "content_type": content_type
            })
            return FarmFetchResult(
                success=False,
                error=f"Farm server returned non-JSON content-type: {content_type}. Expected application/json.",
                error_type="FARM_INVALID_CONTENT_TYPE"
            )
        
        body = response.text.strip()
        if not body:
            logger.warning("farm.fetch_snapshot.empty_response", extra={"snapshot_id": snapshot_id})
            return FarmFetchResult(
                success=False,
                error="Farm server returned empty response body",
                error_type="FARM_EMPTY_RESPONSE"
            )
        
        try:
            data = response.json()
        except Exception as e:
            logger.error("farm.fetch_snapshot.json_parse_error", extra={
                "snapshot_id": snapshot_id, "error": str(e)
            })
            return FarmFetchResult(
                success=False,
                error=f"Farm server returned invalid JSON: {str(e)}",
                error_type="FARM_INVALID_JSON"
            )
        
        if not isinstance(data, dict):
            logger.warning("farm.fetch_snapshot.invalid_json_type", extra={
                "snapshot_id": snapshot_id, "type": type(data).__name__
            })
            return FarmFetchResult(
                success=False,
                error=f"Farm server returned non-object JSON (got {type(data).__name__})",
                error_type="FARM_INVALID_JSON"
            )
        
        tenant_id = data.get("meta", {}).get("tenant_id", "unknown")
        logger.info("farm.fetch_snapshot.success", extra={
            "snapshot_id": snapshot_id, "tenant_id": tenant_id
        })
        return FarmFetchResult(success=True, data=data)

    # =========================================================================
    # Fabric API Methods - Industry-Weighted Vendor Selection
    # =========================================================================

    async def list_industries(self) -> FarmFabricResult:
        """
        List all available industry verticals from Farm.

        GET /api/fabric/industries

        Returns 9 industry verticals:
        - finance: Banks/insurance with SOX, PCI-DSS focus
        - healthcare: Hospitals/pharma with HIPAA focus
        - manufacturing: Industrial with edge computing
        - logistics: Supply chain and fleet management
        - tech_saas: Cloud-native startups
        - retail: E-commerce omnichannel
        - media: Streaming/gaming high throughput
        - government: FedRAMP/FISMA sovereign cloud
        - energy: Utilities with NERC-CIP focus
        """
        url = f"{self.base_url}/api/fabric/industries"

        logger.info("farm.list_industries.start")

        response, error = await self._make_request_with_retry(url, "list_industries")

        if error:
            return FarmFabricResult(
                success=False,
                error=error,
                error_type="FARM_WAKING_OR_DOWN"
            )

        assert response is not None

        if response.status_code >= 400:
            logger.warning("farm.list_industries.http_error", extra={
                "status_code": response.status_code
            })
            return FarmFabricResult(
                success=False,
                error=f"Farm returned HTTP {response.status_code}: {response.text[:200]}",
                error_type="UPSTREAM_ERROR"
            )

        try:
            data = response.json()
        except Exception as e:
            return FarmFabricResult(
                success=False,
                error=f"Invalid JSON response: {str(e)}",
                error_type="UPSTREAM_ERROR"
            )

        logger.info("farm.list_industries.success", extra={
            "industry_count": len(data) if isinstance(data, list) else len(data.get("industries", []))
        })
        return FarmFabricResult(success=True, data=data)

    async def get_industry_weights(self, industry: str) -> FarmFabricResult:
        """
        Get vendor selection weights for a specific industry.

        GET /api/fabric/weights/{industry}

        Args:
            industry: Industry ID (e.g., 'finance', 'healthcare')

        Returns:
            Vendor probabilities per fabric plane for the industry.
            Example: Finance favors MuleSoft (55%), Apigee (50%), Confluent (45%)
        """
        url = f"{self.base_url}/api/fabric/weights/{industry}"

        logger.info("farm.get_industry_weights.start", extra={"industry": industry})

        response, error = await self._make_request_with_retry(url, "get_industry_weights")

        if error:
            return FarmFabricResult(
                success=False,
                error=error,
                error_type="FARM_WAKING_OR_DOWN"
            )

        assert response is not None

        if response.status_code == 404:
            return FarmFabricResult(
                success=False,
                error=f"Industry '{industry}' not found",
                error_type="INDUSTRY_NOT_FOUND"
            )

        if response.status_code >= 400:
            logger.warning("farm.get_industry_weights.http_error", extra={
                "industry": industry, "status_code": response.status_code
            })
            return FarmFabricResult(
                success=False,
                error=f"Farm returned HTTP {response.status_code}: {response.text[:200]}",
                error_type="UPSTREAM_ERROR"
            )

        try:
            data = response.json()
        except Exception as e:
            return FarmFabricResult(
                success=False,
                error=f"Invalid JSON response: {str(e)}",
                error_type="UPSTREAM_ERROR"
            )

        logger.info("farm.get_industry_weights.success", extra={"industry": industry})
        return FarmFabricResult(success=True, data=data)

    async def get_weights_matrix(self) -> FarmFabricResult:
        """
        Get the complete weights matrix across all industries and planes.

        GET /api/fabric/weights-matrix

        Returns:
            Complete matrix showing vendor weights for each industry/plane combination.
            Useful for visualizing industry preferences across the entire fabric.
        """
        url = f"{self.base_url}/api/fabric/weights-matrix"

        logger.info("farm.get_weights_matrix.start")

        response, error = await self._make_request_with_retry(url, "get_weights_matrix")

        if error:
            return FarmFabricResult(
                success=False,
                error=error,
                error_type="FARM_WAKING_OR_DOWN"
            )

        assert response is not None

        if response.status_code >= 400:
            logger.warning("farm.get_weights_matrix.http_error", extra={
                "status_code": response.status_code
            })
            return FarmFabricResult(
                success=False,
                error=f"Farm returned HTTP {response.status_code}: {response.text[:200]}",
                error_type="UPSTREAM_ERROR"
            )

        try:
            data = response.json()
        except Exception as e:
            return FarmFabricResult(
                success=False,
                error=f"Invalid JSON response: {str(e)}",
                error_type="UPSTREAM_ERROR"
            )

        logger.info("farm.get_weights_matrix.success")
        return FarmFabricResult(success=True, data=data)

    async def generate_fabric(
        self,
        industry: str,
        seed: int | None = None,
        scale: str = "medium"
    ) -> FarmFabricResult:
        """
        Generate a fabric configuration using industry-weighted vendor selection.

        POST /api/fabric/generate

        Determinism: Same seed + industry always produces identical fabric config,
        enabling reproducible testing across environments.

        Args:
            industry: Industry ID (e.g., 'finance', 'healthcare')
            seed: Optional seed for deterministic generation
            scale: Enterprise scale: 'small', 'medium', 'large'

        Returns:
            Generated fabric configuration with selected vendors per plane.
        """
        url = f"{self.base_url}/api/fabric/generate"

        payload = {
            "industry": industry,
            "scale": scale
        }
        if seed is not None:
            payload["seed"] = seed

        logger.info("farm.generate_fabric.start", extra={
            "industry": industry, "seed": seed, "scale": scale
        })

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
            logger.warning("farm.generate_fabric.network_error", extra={
                "industry": industry, "error": str(e)
            })
            return FarmFabricResult(
                success=False,
                error="FARM_WAKING_OR_DOWN",
                error_type="FARM_WAKING_OR_DOWN"
            )
        except Exception as e:
            logger.exception("farm.generate_fabric.unexpected_error")
            return FarmFabricResult(
                success=False,
                error=str(e),
                error_type="UNEXPECTED_ERROR"
            )

        if response.status_code == 404:
            return FarmFabricResult(
                success=False,
                error=f"Industry '{industry}' not found",
                error_type="INDUSTRY_NOT_FOUND"
            )

        if response.status_code >= 400:
            logger.warning("farm.generate_fabric.http_error", extra={
                "industry": industry, "status_code": response.status_code
            })
            return FarmFabricResult(
                success=False,
                error=f"Farm returned HTTP {response.status_code}: {response.text[:200]}",
                error_type="UPSTREAM_ERROR"
            )

        try:
            data = response.json()
        except Exception as e:
            return FarmFabricResult(
                success=False,
                error=f"Invalid JSON response: {str(e)}",
                error_type="UPSTREAM_ERROR"
            )

        logger.info("farm.generate_fabric.success", extra={
            "industry": industry,
            "seed": data.get("seed"),
            "vendors_selected": len(data.get("fabric_config", []))
        })
        return FarmFabricResult(success=True, data=data)


def validate_schema_version(data: dict[str, Any]) -> tuple[bool, str]:
    """
    Validate that snapshot has correct schema_version.
    
    Requires meta.schema_version == "farm.v1"
    
    Args:
        data: Snapshot data
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    meta = data.get("meta")
    if not meta:
        return False, "Missing 'meta' field in snapshot"
    
    if not isinstance(meta, dict):
        return False, "'meta' field must be an object"
    
    schema_version = meta.get("schema_version")
    if not schema_version:
        return False, "Missing 'meta.schema_version' field in snapshot"
    
    if schema_version != "farm.v1":
        return False, f"Invalid schema_version: '{schema_version}'. Expected 'farm.v1'"
    
    return True, ""
