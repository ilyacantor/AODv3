"""AOD Fresh - AutonomOS Discover Main Application"""

from dotenv import load_dotenv
load_dotenv()

import os
import logging
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from aod.api.routes import router
from aod.db.database import get_db_direct, close_db

logger = logging.getLogger(__name__)


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

# Include API router
app.include_router(router)

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

    # Release DB pool connections so the Supabase pooler reclaims the client
    # slots immediately instead of leaving orphaned sessions that accumulate
    # against the per-tenant cap across restarts/reloads.
    await close_db()
    logger.info("shutdown.db_pool_closed")


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
