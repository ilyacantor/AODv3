"""FarmClient - HTTP client for fetching snapshots from AOS Farm"""

import httpx
from typing import Any
from dataclasses import dataclass


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
    
    async def list_snapshots(self, tenant_id: str, limit: int = 20) -> FarmListResult:
        """
        List available snapshots from Farm for a tenant.
        
        Args:
            tenant_id: The tenant ID to list snapshots for
            limit: Maximum number of snapshots to return (default 20)
            
        Returns:
            FarmListResult with success status and snapshots list or error
        """
        url = f"{self.base_url}/api/snapshots?tenant_id={tenant_id}&limit={limit}"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                
                if response.status_code >= 400:
                    return FarmListResult(
                        success=False,
                        error=f"Farm server returned HTTP {response.status_code}: {response.text[:200]}",
                        error_type="UPSTREAM_ERROR"
                    )
                
                content_type = response.headers.get("content-type", "")
                if "json" not in content_type.lower():
                    return FarmListResult(
                        success=False,
                        error=f"Farm server returned non-JSON content-type: {content_type}",
                        error_type="UPSTREAM_ERROR"
                    )
                
                try:
                    data = response.json()
                except Exception as e:
                    return FarmListResult(
                        success=False,
                        error=f"Farm server returned invalid JSON: {str(e)}",
                        error_type="UPSTREAM_ERROR"
                    )
                
                if isinstance(data, list):
                    return FarmListResult(success=True, snapshots=data)
                elif isinstance(data, dict) and "snapshots" in data:
                    return FarmListResult(success=True, snapshots=data["snapshots"])
                else:
                    return FarmListResult(success=True, snapshots=[data] if isinstance(data, dict) else [])
                
        except httpx.TimeoutException:
            return FarmListResult(
                success=False,
                error=f"Timeout connecting to Farm server at {self.base_url}",
                error_type="UPSTREAM_ERROR"
            )
        except httpx.ConnectError as e:
            return FarmListResult(
                success=False,
                error=f"Failed to connect to Farm server at {self.base_url}: {str(e)}",
                error_type="UPSTREAM_ERROR"
            )
        except Exception as e:
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
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                
                if response.status_code == 404:
                    return FarmFetchResult(
                        success=False,
                        error=f"Snapshot '{snapshot_id}' not found on Farm server (HTTP 404)",
                        error_type="FARM_SNAPSHOT_NOT_FOUND"
                    )
                
                if response.status_code >= 400:
                    return FarmFetchResult(
                        success=False,
                        error=f"Farm server returned HTTP {response.status_code}: {response.text[:200]}",
                        error_type="FARM_HTTP_ERROR"
                    )
                
                content_type = response.headers.get("content-type", "")
                if "json" not in content_type.lower():
                    return FarmFetchResult(
                        success=False,
                        error=f"Farm server returned non-JSON content-type: {content_type}. Expected application/json.",
                        error_type="FARM_INVALID_CONTENT_TYPE"
                    )
                
                body = response.text.strip()
                if not body:
                    return FarmFetchResult(
                        success=False,
                        error="Farm server returned empty response body",
                        error_type="FARM_EMPTY_RESPONSE"
                    )
                
                try:
                    data = response.json()
                except Exception as e:
                    return FarmFetchResult(
                        success=False,
                        error=f"Farm server returned invalid JSON: {str(e)}",
                        error_type="FARM_INVALID_JSON"
                    )
                
                if not isinstance(data, dict):
                    return FarmFetchResult(
                        success=False,
                        error=f"Farm server returned non-object JSON (got {type(data).__name__})",
                        error_type="FARM_INVALID_JSON"
                    )
                
                return FarmFetchResult(success=True, data=data)
                
        except httpx.TimeoutException:
            return FarmFetchResult(
                success=False,
                error=f"Timeout connecting to Farm server at {self.base_url}",
                error_type="FARM_TIMEOUT"
            )
        except httpx.ConnectError as e:
            return FarmFetchResult(
                success=False,
                error=f"Failed to connect to Farm server at {self.base_url}: {str(e)}",
                error_type="FARM_CONNECTION_ERROR"
            )
        except Exception as e:
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
