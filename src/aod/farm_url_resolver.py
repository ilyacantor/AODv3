"""Farm URL resolver with automatic fallback from dev to prod."""

import os
import logging
from dataclasses import dataclass
from typing import Literal

import httpx

logger = logging.getLogger(__name__)

FARM_URL_DEV_DEFAULT = None
FARM_URL_PROD_DEFAULT = "https://autonomos.farm"

FarmMode = Literal["dev", "prod", "auto"]


@dataclass
class FarmUrlConfig:
    """Configuration for Farm URL resolution."""
    dev_url: str | None
    prod_url: str
    mode: FarmMode
    
    @classmethod
    def from_env(cls) -> "FarmUrlConfig":
        mode_raw = os.environ.get("FARM_URL_MODE", "auto").lower()
        if mode_raw not in ("dev", "prod", "auto"):
            mode_raw = "auto"
        
        return cls(
            dev_url=os.environ.get("FARM_URL_DEV", FARM_URL_DEV_DEFAULT),
            prod_url=os.environ.get("FARM_URL_PROD", FARM_URL_PROD_DEFAULT),
            mode=mode_raw,  # type: ignore
        )


@dataclass
class FarmFetchResponse:
    """Result of a Farm fetch with fallback."""
    ok: bool
    data: dict | list | None = None
    error: str | None = None
    mode: str = "auto"
    attempted: list[str] | None = None
    used_url: str | None = None
    warning: str | None = None


_config: FarmUrlConfig | None = None
_logged_startup = False


def get_farm_config() -> FarmUrlConfig:
    """Get or create Farm URL configuration."""
    global _config, _logged_startup
    if _config is None:
        _config = FarmUrlConfig.from_env()
        if not _logged_startup:
            logger.info(
                "farm_url_resolver.startup",
                extra={
                    "mode": _config.mode,
                    "dev_url": _config.dev_url or "(not set)",
                    "prod_url": _config.prod_url,
                }
            )
            _logged_startup = True
    return _config


def _is_farm_down_response(response: httpx.Response) -> tuple[bool, str]:
    """Check if response indicates Farm is down."""
    if response.status_code >= 500:
        return True, f"HTTP {response.status_code}"
    
    content_type = response.headers.get("content-type", "")
    if "text/html" in content_type.lower():
        return True, "HTML response (expected JSON)"
    
    try:
        body = response.text
        if "The app is currently not running" in body:
            return True, "Replit app not running"
    except Exception:
        pass
    
    return False, ""


async def fetch_from_farm(
    path: str,
    timeout: float = 30.0,
) -> FarmFetchResponse:
    """
    Fetch from Farm with automatic fallback based on FARM_URL_MODE.
    
    Args:
        path: API path (e.g., "/api/snapshots?tenant_id=X")
        timeout: Request timeout in seconds
        
    Returns:
        FarmFetchResponse with data or error info
    """
    config = get_farm_config()
    attempted = []
    
    urls_to_try = []
    if config.mode == "dev":
        if config.dev_url:
            urls_to_try = [("dev", config.dev_url)]
        else:
            return FarmFetchResponse(
                ok=False,
                error="FARM_URL_DEV not configured",
                mode=config.mode,
                attempted=["dev"],
            )
    elif config.mode == "prod":
        urls_to_try = [("prod", config.prod_url)]
    else:  # auto
        if config.dev_url:
            urls_to_try = [("dev", config.dev_url), ("prod", config.prod_url)]
        else:
            urls_to_try = [("prod", config.prod_url)]
    
    last_error = ""
    warning = None
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        for label, base_url in urls_to_try:
            attempted.append(label)
            url = f"{base_url.rstrip('/')}{path}"
            
            try:
                response = await client.get(url)
                
                is_down, down_reason = _is_farm_down_response(response)
                if is_down:
                    last_error = f"{label}: {down_reason}"
                    logger.warning(
                        "farm_url_resolver.upstream_down",
                        extra={"label": label, "reason": down_reason, "url": url}
                    )
                    if config.mode == "auto" and label == "dev":
                        warning = "Farm dev is not running - using prod Farm"
                        continue
                    continue
                
                if response.status_code >= 400:
                    last_error = f"{label}: HTTP {response.status_code}"
                    continue
                
                try:
                    data = response.json()
                    return FarmFetchResponse(
                        ok=True,
                        data=data,
                        mode=config.mode,
                        attempted=attempted,
                        used_url=label,
                        warning=warning,
                    )
                except Exception as e:
                    last_error = f"{label}: Invalid JSON - {e}"
                    continue
                    
            except httpx.TimeoutException:
                last_error = f"{label}: Timeout"
                logger.warning("farm_url_resolver.timeout", extra={"label": label, "url": url})
                if config.mode == "auto" and label == "dev":
                    warning = "Farm dev is not running - using prod Farm"
                continue
            except httpx.RequestError as e:
                last_error = f"{label}: Network error - {e}"
                logger.warning("farm_url_resolver.network_error", extra={"label": label, "error": str(e)})
                if config.mode == "auto" and label == "dev":
                    warning = "Farm dev is not running - using prod Farm"
                continue
    
    return FarmFetchResponse(
        ok=False,
        error="FARM_UNAVAILABLE",
        mode=config.mode,
        attempted=attempted,
        warning=f"All Farm endpoints failed: {last_error}",
    )


def reset_config():
    """Reset config (for testing)."""
    global _config, _logged_startup
    _config = None
    _logged_startup = False
