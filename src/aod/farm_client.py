"""FarmClient - HTTP client for fetching snapshots from AOS Farm"""

import httpx
import logging
from typing import Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


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


class FarmClientError(Exception):
    """Error from Farm client operations"""
    def __init__(self, message: str, error_type: str = "FARM_ERROR"):
        super().__init__(message)
        self.error_type = error_type


class FarmClient:
    """HTTP client for fetching snapshots from AOS Farm"""
    
    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
    
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
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                
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
                
        except httpx.TimeoutException:
            logger.error("farm.list_snapshots.timeout", extra={"tenant_id": tenant_id, "base_url": self.base_url})
            return FarmListResult(
                success=False,
                error=f"Timeout connecting to Farm server at {self.base_url}",
                error_type="UPSTREAM_ERROR"
            )
        except httpx.ConnectError as e:
            logger.error("farm.list_snapshots.connection_error", extra={
                "tenant_id": tenant_id, "base_url": self.base_url, "error": str(e)
            })
            return FarmListResult(
                success=False,
                error=f"Failed to connect to Farm server at {self.base_url}: {str(e)}",
                error_type="UPSTREAM_ERROR"
            )
        except Exception as e:
            logger.exception("farm.list_snapshots.unexpected_error", extra={"tenant_id": tenant_id})
            return FarmListResult(
                success=False,
                error=f"Unexpected error fetching from Farm: {str(e)}",
                error_type="UPSTREAM_ERROR"
            )

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
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                
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
                
        except httpx.TimeoutException:
            logger.error("farm.fetch_snapshot.timeout", extra={
                "snapshot_id": snapshot_id, "base_url": self.base_url
            })
            return FarmFetchResult(
                success=False,
                error=f"Timeout connecting to Farm server at {self.base_url}",
                error_type="FARM_TIMEOUT"
            )
        except httpx.ConnectError as e:
            logger.error("farm.fetch_snapshot.connection_error", extra={
                "snapshot_id": snapshot_id, "base_url": self.base_url, "error": str(e)
            })
            return FarmFetchResult(
                success=False,
                error=f"Failed to connect to Farm server at {self.base_url}: {str(e)}",
                error_type="FARM_CONNECTION_ERROR"
            )
        except Exception as e:
            logger.exception("farm.fetch_snapshot.unexpected_error", extra={"snapshot_id": snapshot_id})
            return FarmFetchResult(
                success=False,
                error=f"Unexpected error fetching from Farm: {str(e)}",
                error_type="FARM_ERROR"
            )


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
