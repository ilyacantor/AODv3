"""
Maestra status endpoint tests for AOD.

Tests per session1_module_status.md spec and HARNESS_RULES.md.

Tests call GET /api/maestra/status?tenant_id=<id> against the live FastAPI app.
No mocks. No test-only endpoints. No hardcoded expected counts.
"""

import time

import pytest
from httpx import AsyncClient, ASGITransport

import sys
sys.path.insert(0, "src")

from main import app


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Disable API key auth and reset DB singleton between tests.

    The DB pool is bound to an event loop. pytest-asyncio creates a new loop
    per test function, so we must reset the singleton to avoid
    'Future attached to a different loop' errors.
    """
    monkeypatch.delenv("AOD_API_KEY", raising=False)

    yield

    # Reset DB singleton so next test gets a fresh pool on its own event loop
    import aod.db.database_old as db_mod
    if db_mod._db_instance is not None:
        # Pool close needs an event loop — but we're in sync teardown.
        # Setting to None is safe: the pool will be GC'd and the next test
        # will create a fresh one on its own loop.
        db_mod._db_instance = None


# Required fields per the session spec
REQUIRED_TOP_LEVEL_FIELDS = {
    "module", "tenant_id", "discovery_phase", "systems_discovered",
    "shadows_detected", "governance_items", "fabric_availability",
    "last_run_at", "healthy",
}

VALID_DISCOVERY_PHASES = {"pending", "running", "complete"}

FABRIC_AVAILABILITY_FIELDS = {"identity", "collaboration", "operations", "data"}


# --------------------------------------------------------------------------
# 1. Schema validation with a tenant that may or may not have data
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_status_returns_200():
    """GET /api/maestra/status returns HTTP 200."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/maestra/status", params={"tenant_id": "meridian"})
    assert resp.status_code == 200, (
        f"Expected 200, got {resp.status_code}: {resp.text}"
    )


@pytest.mark.asyncio
async def test_status_returns_valid_json():
    """Response is valid JSON."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/maestra/status", params={"tenant_id": "meridian"})
    data = resp.json()
    assert isinstance(data, dict), f"Expected JSON object, got {type(data)}"


@pytest.mark.asyncio
async def test_status_has_all_required_fields():
    """Response contains all required top-level fields per spec."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/maestra/status", params={"tenant_id": "meridian"})
    data = resp.json()
    missing = REQUIRED_TOP_LEVEL_FIELDS - set(data.keys())
    assert not missing, (
        f"Missing required fields: {missing}. "
        f"User would see an incomplete Maestra status response."
    )


@pytest.mark.asyncio
async def test_status_module_field_is_aod():
    """module field must be 'aod'."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/maestra/status", params={"tenant_id": "meridian"})
    data = resp.json()
    assert data["module"] == "aod", (
        f"Expected module='aod', got module='{data.get('module')}'. "
        f"Maestra would misidentify this module."
    )


@pytest.mark.asyncio
async def test_status_healthy_is_boolean():
    """healthy field must be a boolean."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/maestra/status", params={"tenant_id": "meridian"})
    data = resp.json()
    assert isinstance(data["healthy"], bool), (
        f"Expected healthy to be bool, got {type(data['healthy']).__name__}={data['healthy']}. "
        f"Maestra needs a boolean to make orchestration decisions."
    )


@pytest.mark.asyncio
async def test_status_tenant_id_matches_request():
    """tenant_id in response matches the requested tenant_id."""
    test_tenant = "meridian"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/maestra/status", params={"tenant_id": test_tenant})
    data = resp.json()
    assert data["tenant_id"] == test_tenant, (
        f"Expected tenant_id='{test_tenant}', got '{data.get('tenant_id')}'. "
        f"Maestra would associate this status with the wrong tenant."
    )


@pytest.mark.asyncio
async def test_status_response_time_under_500ms():
    """Response time must be < 500ms (warm — excludes cold DB pool creation)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Warmup: establish DB pool (cold start is infrastructure, not endpoint latency)
        await client.get("/api/maestra/status", params={"tenant_id": "meridian"})
        # Measure warm response
        start = time.monotonic()
        resp = await client.get("/api/maestra/status", params={"tenant_id": "meridian"})
        elapsed_ms = (time.monotonic() - start) * 1000
    assert resp.status_code == 200
    assert elapsed_ms < 500, (
        f"Response took {elapsed_ms:.0f}ms, must be < 500ms. "
        f"Maestra status checks must be fast for orchestration loops."
    )


# --------------------------------------------------------------------------
# 2. Discovery phase validation
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_status_discovery_phase_is_valid():
    """discovery_phase must be one of: pending, running, complete."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/maestra/status", params={"tenant_id": "meridian"})
    data = resp.json()
    phase = data["discovery_phase"]
    assert phase in VALID_DISCOVERY_PHASES, (
        f"discovery_phase='{phase}' not in {VALID_DISCOVERY_PHASES}. "
        f"Maestra can't interpret this phase value."
    )


# --------------------------------------------------------------------------
# 3. Nested structure validation
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_status_systems_discovered_structure():
    """systems_discovered must have count (int) and list (list)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/maestra/status", params={"tenant_id": "meridian"})
    data = resp.json()
    sd = data["systems_discovered"]
    assert "count" in sd and "list" in sd, (
        f"systems_discovered missing count/list: {sd}"
    )
    assert isinstance(sd["count"], int), f"count must be int, got {type(sd['count'])}"
    assert isinstance(sd["list"], list), f"list must be list, got {type(sd['list'])}"
    assert sd["count"] == len(sd["list"]), (
        f"count ({sd['count']}) != len(list) ({len(sd['list'])}). Data inconsistency."
    )


@pytest.mark.asyncio
async def test_status_shadows_detected_structure():
    """shadows_detected must have count (int) and list (list)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/maestra/status", params={"tenant_id": "meridian"})
    data = resp.json()
    sh = data["shadows_detected"]
    assert "count" in sh and "list" in sh, (
        f"shadows_detected missing count/list: {sh}"
    )
    assert isinstance(sh["count"], int), f"count must be int, got {type(sh['count'])}"
    assert isinstance(sh["list"], list), f"list must be list, got {type(sh['list'])}"
    assert sh["count"] == len(sh["list"]), (
        f"count ({sh['count']}) != len(list) ({len(sh['list'])}). Data inconsistency."
    )


@pytest.mark.asyncio
async def test_status_governance_items_structure():
    """governance_items must have count (int) and items (list)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/maestra/status", params={"tenant_id": "meridian"})
    data = resp.json()
    gi = data["governance_items"]
    assert "count" in gi and "items" in gi, (
        f"governance_items missing count/items: {gi}"
    )
    assert isinstance(gi["count"], int), f"count must be int, got {type(gi['count'])}"
    assert isinstance(gi["items"], list), f"items must be list, got {type(gi['items'])}"
    assert gi["count"] == len(gi["items"]), (
        f"count ({gi['count']}) != len(items) ({len(gi['items'])}). Data inconsistency."
    )


@pytest.mark.asyncio
async def test_status_fabric_availability_structure():
    """fabric_availability must have identity, collaboration, operations, data — all boolean."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/maestra/status", params={"tenant_id": "meridian"})
    data = resp.json()
    fa = data["fabric_availability"]
    missing = FABRIC_AVAILABILITY_FIELDS - set(fa.keys())
    assert not missing, (
        f"fabric_availability missing fields: {missing}"
    )
    for field in FABRIC_AVAILABILITY_FIELDS:
        assert isinstance(fa[field], bool), (
            f"fabric_availability.{field} must be bool, got {type(fa[field]).__name__}={fa[field]}"
        )


# --------------------------------------------------------------------------
# 4. Tenant isolation / missing tenant
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_status_unknown_tenant_returns_pending():
    """Unknown tenant returns valid response with discovery_phase=pending."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/maestra/status",
            params={"tenant_id": "nonexistent_tenant_xyz_999"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["discovery_phase"] == "pending", (
        f"Unknown tenant should have discovery_phase='pending', got '{data['discovery_phase']}'"
    )
    assert data["systems_discovered"]["count"] == 0
    assert data["shadows_detected"]["count"] == 0
    assert data["governance_items"]["count"] == 0
    assert data["last_run_at"] is None


@pytest.mark.asyncio
async def test_status_requires_tenant_id():
    """Missing tenant_id query parameter returns 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/maestra/status")
    assert resp.status_code == 422, (
        f"Expected 422 for missing tenant_id, got {resp.status_code}: {resp.text}"
    )


# --------------------------------------------------------------------------
# 5. Idempotency — same result on repeated calls (CLAUDE.md B14)
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_status_idempotent():
    """Two consecutive calls return identical results (no non-determinism)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp1 = await client.get("/api/maestra/status", params={"tenant_id": "meridian"})
        resp2 = await client.get("/api/maestra/status", params={"tenant_id": "meridian"})
    assert resp1.json() == resp2.json(), (
        "Two consecutive calls returned different results — non-deterministic endpoint. "
        "CLAUDE.md B14 requires identical results on repeated runs."
    )
