"""AOD Fresh - AutonomOS Discover Main Application"""

from fastapi import FastAPI, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from aod.api.routes import router
from aod.db.database import get_db_direct

app = FastAPI(
    title="AOD Fresh",
    description="AutonomOS Discover - Enterprise Asset Discovery Module",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

STATIC_DIR = Path(__file__).parent.parent / "static"
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.on_event("startup")
async def startup():
    """Initialize database on startup"""
    await get_db_direct()


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


@app.get("/", response_class=HTMLResponse)
async def serve_ui(response: Response):
    """Serve the AOD Console UI"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    index_path = TEMPLATES_DIR / "index.html"
    if index_path.exists():
        with open(index_path, "r") as f:
            content = f.read()
        return HTMLResponse(content=content, status_code=200)
    return HTMLResponse(content="<h1>AOD Fresh</h1><p>UI not found</p>", status_code=200)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
