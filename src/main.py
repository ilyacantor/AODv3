"""AOD Fresh - AutonomOS Discover Main Application"""

import os
import logging
from fastapi import FastAPI, Request, Response, Depends, HTTPException, Security
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pathlib import Path

from aod.api.routes import router
from aod.db.database import get_db_direct

logger = logging.getLogger(__name__)

# =============================================================================
# SECURITY: API Key Authentication
# =============================================================================
# When AOD_API_KEY is set, all /api/* endpoints require X-API-Key header.
# When not set (development), authentication is bypassed.
# =============================================================================

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(request: Request, api_key: str = Security(API_KEY_HEADER)):
    """
    Verify API key for protected endpoints.

    Behavior:
    - If AOD_API_KEY env var is NOT set: Allow all requests (dev mode)
    - If AOD_API_KEY env var IS set: Require matching X-API-Key header
    - Same-origin browser requests (Referer from served UI) are exempt
    """
    expected_key = os.environ.get("AOD_API_KEY")

    if not expected_key:
        # No key configured = dev mode, allow all
        return True

    # Allow same-origin requests from the served UI
    referer = request.headers.get("referer", "")
    host = request.headers.get("host", "")
    if referer and host and host in referer:
        return True

    if not api_key:
        logger.warning("api.auth.missing_key", extra={"path": "api"})
        raise HTTPException(
            status_code=401,
            detail="API key required. Provide X-API-Key header."
        )

    if api_key != expected_key:
        logger.warning("api.auth.invalid_key", extra={"path": "api"})
        raise HTTPException(
            status_code=401,
            detail="Invalid API key."
        )

    return True


# =============================================================================
# APPLICATION SETUP
# =============================================================================

app = FastAPI(
    title="AOD Fresh",
    description="AutonomOS Discover - Enterprise Asset Discovery Module",
    version="1.0.0"
)

# =============================================================================
# SECURITY: CORS Configuration
# =============================================================================
# In production, restrict to known origins. In development, allow all.
# =============================================================================

AOD_ENVIRONMENT = os.environ.get("AOD_ENVIRONMENT", "development")

if AOD_ENVIRONMENT == "production":
    # Production: Restrict to configured origins
    allowed_origins_str = os.environ.get("AOD_CORS_ORIGINS", "")
    if allowed_origins_str:
        allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",")]
    else:
        # Default to same-origin only (no CORS) if not configured
        allowed_origins = []
    logger.info("cors.production_mode", extra={"origins": allowed_origins})
else:
    # Development: Allow all origins
    allowed_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router with authentication dependency
app.include_router(router, dependencies=[Depends(verify_api_key)])

STATIC_DIR = Path(__file__).parent.parent / "static"
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
CONFIG_DIR = Path(__file__).parent.parent / "config"

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

if CONFIG_DIR.exists():
    app.mount("/config", StaticFiles(directory=str(CONFIG_DIR)), name="config")


@app.on_event("startup")
async def startup():
    """Initialize database on startup — non-blocking so health check passes"""
    import asyncio
    try:
        await asyncio.wait_for(get_db_direct(), timeout=15)
        logger.info("startup.db_ready")
    except asyncio.TimeoutError:
        logger.warning("startup.db_timeout — DB init timed out after 15s, will retry lazily on first request")
    except Exception as e:
        logger.warning("startup.db_error — %s — will retry lazily on first request", str(e))


@app.on_event("shutdown")
async def shutdown():
    """Cleanup resources on shutdown"""
    from aod.api.deps import get_farm_client

    # Close Farm HTTP client and cleanup connections
    farm_client = get_farm_client()
    if farm_client:
        await farm_client.close()
        logger.info("shutdown.farm_client_closed")


@app.get("/health")
async def health_check():
    """Health check endpoint for deployment"""
    return {"status": "ok"}


@app.get("/favicon.ico")
async def favicon():
    """Serve favicon"""
    favicon_path = STATIC_DIR / "favicon.png"
    if favicon_path.exists():
        return FileResponse(favicon_path, media_type="image/png")
    return Response(status_code=204)


@app.get("/static/overview/index.html", response_class=HTMLResponse)
async def serve_overview(response: Response):
    """Serve overview with no-cache headers to prevent stale content"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    overview_path = STATIC_DIR / "overview" / "index.html"
    if overview_path.exists():
        with open(overview_path, "r") as f:
            content = f.read()
        return HTMLResponse(content=content, status_code=200)
    return HTMLResponse(content="<h1>Overview not found</h1>", status_code=404)


@app.get("/switchboard")
async def redirect_to_switchboard():
    """Redirect to Policy Switchboard UI"""
    return RedirectResponse(url="/static/policy-switchboard.html")


@app.get("/", response_class=HTMLResponse)
async def serve_ui(response: Response):
    """Serve the AOD Console UI"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    index_path = TEMPLATES_DIR / "index.html"
    if index_path.exists():
        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content, status_code=200)
    return HTMLResponse(content="<h1>AOD Fresh</h1><p>UI not found</p>", status_code=200)


if __name__ == "__main__":
    import uvicorn
    # Use 2 workers for better concurrency (production uses same in render.yaml)
    uvicorn.run(app, host="0.0.0.0", port=5000, workers=2)
