from fastapi import FastAPI, Request, HTTPException, Query
from typing import Optional
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from contextlib import asynccontextmanager

from src.aod.db import init_db, close_db
from src.aod.models import IngestRequest
from src.aod.ingest_service import ingest_full_pull, reset_all_data
from src.aod.dashboard_service import (
    get_dashboard_data, get_assets_by_lifecycle, get_assets_by_parked_reason,
    get_assets_by_finding_type, get_shadow_it_assets, get_asset_detail, get_ingest_runs,
    get_assets_by_inventory, get_shadow_it_by_field, get_farm_bucket_counts, get_validation_metrics,
    filter_assets_by_inventory
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()


app = FastAPI(title="AOD Discover v3", version="1.0.0", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "AOD Discover v3"}


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    data = await get_dashboard_data()
    return templates.TemplateResponse("dashboard.html", {"request": request, "data": data})


@app.get("/triage", response_class=HTMLResponse)
async def triage(request: Request):
    data = await get_dashboard_data()
    return templates.TemplateResponse("triage.html", {"request": request, "data": data})


@app.get("/api/dashboard")
async def api_dashboard():
    return await get_dashboard_data()


@app.get("/api/assets/lifecycle/{state}")
async def api_assets_by_lifecycle(state: str):
    if state not in ["DISCOVERED", "PARKED", "CATALOGED"]:
        raise HTTPException(status_code=400, detail="Invalid lifecycle state")
    assets = await get_assets_by_lifecycle(state)
    return {"assets": assets, "count": len(assets)}


@app.get("/api/assets/parked/{reason}")
async def api_assets_by_parked_reason(reason: str):
    assets = await get_assets_by_parked_reason(reason)
    return {"assets": assets, "count": len(assets)}


@app.get("/api/assets/finding/{finding_type}")
async def api_assets_by_finding(finding_type: str):
    assets = await get_assets_by_finding_type(finding_type)
    return {"assets": assets, "count": len(assets)}


@app.get("/api/assets/shadow-it")
async def api_shadow_it_assets():
    assets = await get_shadow_it_assets()
    return {"assets": assets, "count": len(assets)}


@app.get("/api/assets/inventory")
async def api_filter_assets_inventory(
    field: str = Query(..., description="Field to filter by: vendor, asset_kind, tech_domain, business_domain"),
    key: Optional[str] = Query(None, description="Stable key for the filter value"),
    value: Optional[str] = Query(None, description="Display value (use key instead when possible)")
):
    """Filter assets by inventory field using query parameters.
    Preferred: Use 'key' parameter for stable URL-safe lookups.
    Always returns 200 with {assets: [], total: 0, filters: {...}}
    """
    result = await filter_assets_by_inventory(field, value=value, key=key)
    return result


@app.get("/api/assets/inventory/{field}/{value:path}")
async def api_assets_by_inventory(field: str, value: str):
    """DEPRECATED: Use /api/assets/inventory?field=...&key=... instead.
    This endpoint is kept for backward compatibility only."""
    assets = await get_assets_by_inventory(field, value)
    return {"assets": assets, "count": len(assets)}


@app.get("/api/assets/shadow-it/{field}/{value}")
async def api_shadow_it_by_field(field: str, value: str):
    assets = await get_shadow_it_by_field(field, value)
    return {"assets": assets, "count": len(assets)}


@app.get("/api/assets/{asset_id}")
async def api_asset_detail(asset_id: str):
    detail = await get_asset_detail(asset_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Asset not found")
    return detail


@app.get("/api/ingest/runs")
async def api_ingest_runs():
    runs = await get_ingest_runs()
    return {"runs": runs}


@app.post("/api/farm/ingest")
async def api_ingest(request: IngestRequest):
    result = await ingest_full_pull(request.archetype, request.scale)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Ingestion failed"))
    return result


@app.post("/api/reset")
async def api_reset():
    result = await reset_all_data()
    return result


@app.get("/catalogs", response_class=HTMLResponse)
async def catalogs(request: Request):
    runs = await get_ingest_runs()
    return templates.TemplateResponse("catalogs.html", {"request": request, "runs": runs})


@app.get("/validation", response_class=HTMLResponse)
async def validation(request: Request):
    bucket_counts = await get_farm_bucket_counts()
    metrics = await get_validation_metrics()
    return templates.TemplateResponse("validation.html", {
        "request": request,
        "bucket_counts": bucket_counts,
        "metrics": metrics
    })


@app.get("/api/validation/buckets")
async def api_validation_buckets():
    return await get_farm_bucket_counts()


@app.get("/api/validation/metrics")
async def api_validation_metrics():
    return await get_validation_metrics()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
