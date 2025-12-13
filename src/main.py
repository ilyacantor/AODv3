"""AOD Fresh - AutonomOS Discover Main Application"""

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pathlib import Path

from aod.api.routes import router
from aod.db.database import get_db

app = FastAPI(
    title="AOD Fresh",
    description="AutonomOS Discover - Enterprise Asset Discovery Module",
    version="1.0.0"
)

app.include_router(router)

STATIC_DIR = Path(__file__).parent.parent / "static"
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.on_event("startup")
async def startup():
    """Initialize database on startup"""
    await get_db()


@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serve the AOD Console UI"""
    index_path = TEMPLATES_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path, media_type="text/html")
    return HTMLResponse(content="<h1>AOD Fresh</h1><p>UI not found</p>", status_code=200)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
