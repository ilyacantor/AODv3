"""
Negative tests: AOD rejects requests that use the wrong auth header.

The security contract: AOD requires X-API-Key header when AOD_API_KEY is set.
Farm (and any other caller) MUST send X-API-Key, not Authorization: Bearer
or X-Shared-Secret. This test proves the wrong headers are rejected.
"""

import os
import pytest
from httpx import AsyncClient, ASGITransport

import sys
sys.path.insert(0, "src")

from main import app

VALID_KEY = "test-api-key-for-auth-verification"
PROTECTED_ENDPOINT = "/api/health"


@pytest.fixture(autouse=True)
def set_api_key(monkeypatch):
    """Enable auth by setting AOD_API_KEY for all tests in this module."""
    monkeypatch.setenv("AOD_API_KEY", VALID_KEY)


@pytest.mark.asyncio
async def test_correct_header_accepted():
    """X-API-Key with valid key → 200."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(PROTECTED_ENDPOINT, headers={"X-API-Key": VALID_KEY})
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"


@pytest.mark.asyncio
async def test_wrong_header_authorization_bearer_rejected():
    """Authorization: Bearer <key> → 401. This was Farm's old (broken) pattern."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            PROTECTED_ENDPOINT,
            headers={"Authorization": f"Bearer {VALID_KEY}"},
        )
    assert resp.status_code == 401, (
        f"Authorization: Bearer must be rejected, got {resp.status_code}: {resp.text}"
    )


@pytest.mark.asyncio
async def test_wrong_header_x_shared_secret_rejected():
    """X-Shared-Secret: <key> → 401. This was Farm's other old (broken) pattern."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            PROTECTED_ENDPOINT,
            headers={"X-Shared-Secret": VALID_KEY},
        )
    assert resp.status_code == 401, (
        f"X-Shared-Secret must be rejected, got {resp.status_code}: {resp.text}"
    )


@pytest.mark.asyncio
async def test_no_header_rejected():
    """No auth header at all → 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(PROTECTED_ENDPOINT)
    assert resp.status_code == 401, (
        f"Missing header must be rejected, got {resp.status_code}: {resp.text}"
    )


@pytest.mark.asyncio
async def test_wrong_key_value_rejected():
    """X-API-Key with wrong value → 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            PROTECTED_ENDPOINT,
            headers={"X-API-Key": "wrong-key-value"},
        )
    assert resp.status_code == 401, (
        f"Wrong key value must be rejected, got {resp.status_code}: {resp.text}"
    )
