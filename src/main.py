"""AOD Fresh - AutonomOS Discover Main Application"""

from dotenv import load_dotenv
load_dotenv()

import asyncio
import logging
import os
import socket
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from aod.api.routes import router
from aod.db.database import get_db_direct

logger = logging.getLogger(__name__)


# =============================================================================
# Boot-time downstream validation
# =============================================================================
# AOD calls Farm and AAM directly. Required env vars, no dev-host fallback —
# a missing URL would silently route every workflow to a bogus host. Surface
# the misconfig at module load so Render marks the deploy failed instead of
# degrading silently when the first request comes in.

FARM_URL = os.environ.get("FARM_URL", "").rstrip("/")
if not FARM_URL:
    raise RuntimeError(
        "FARM_URL environment variable is required. AOD discovery, "
        "reconciliation, and runs all call Farm — a missing URL would "
        "silently break every workflow."
    )

AAM_URL = os.environ.get("AAM_URL", "").rstrip("/")
if not AAM_URL:
    raise RuntimeError(
        "AAM_URL environment variable is required. AOD handoff to AAM "
        "for connector provisioning needs an explicit AAM URL."
    )


async def _probe_one(client: httpx.AsyncClient, name: str, base_url: str, health_path: str) -> str | None:
    """Probe a single downstream — DNS resolve + GET /health. Returns error string or None."""
    parsed = urlparse(base_url)
    host = parsed.hostname
    if not host:
        return f"{name}: cannot parse hostname from {base_url}"
    try:
        await asyncio.get_running_loop().run_in_executor(None, socket.gethostbyname, host)
    except socket.gaierror as exc:
        return f"{name}: DNS resolution failed for {host}: {exc}"
    try:
        resp = await client.get(f"{base_url}{health_path}")
    except httpx.ConnectError as exc:
        return f"{name}: connection refused at {base_url}{health_path}: {exc}"
    except httpx.TimeoutException:
        return f"{name}: timeout reaching {base_url}{health_path} after 2s"
    if resp.status_code != 200:
        return f"{name}: HTTP {resp.status_code} from {base_url}{health_path}"
    return None


async def _probe_downstreams() -> None:
    """Boot-time validation of every downstream AOD depends on."""
    targets: list[tuple[str, str, str]] = [
        ("Farm", FARM_URL, "/health"),
        ("AAM", AAM_URL, "/health"),
    ]
    async with httpx.AsyncClient(timeout=2.0) as client:
        results = await asyncio.gather(
            *[_probe_one(client, name, url, path) for name, url, path in targets]
        )
    failures = [r for r in results if r]
    if failures:
        raise RuntimeError(
            "AOD cannot start — downstream probes failed:\n  " + "\n  ".join(failures)
        )
    logger.info("AOD downstream probes succeeded for %d services", len(targets))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info("AOD starting up")
    await _probe_downstreams()
    await asyncio.wait_for(get_db_direct(), timeout=15)
    logger.info("startup.db_ready")

    yield

    from aod.api.deps import get_farm_client
    farm_client = get_farm_client()
    if farm_client:
        await farm_client.close()
        logger.info("shutdown.farm_client_closed")


# =============================================================================
# APPLICATION SETUP
# =============================================================================

app = FastAPI(
    title="AOD Fresh",
    description="AutonomOS Discover - Enterprise Asset Discovery Module",
    version="1.0.0",
    lifespan=lifespan,
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
