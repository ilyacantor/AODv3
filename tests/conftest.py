"""Shared test fixtures for AOD test suite"""

import os
import asyncio
import pytest
import pytest_asyncio
from pathlib import Path
from uuid import uuid4
from dotenv import load_dotenv

# Load .env before any AOD imports that read env vars
load_dotenv(Path(__file__).parent.parent / ".env")

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aod.db.database import Database, get_database_url


@pytest_asyncio.fixture
async def pg_db():
    """Database fixture using real PostgreSQL via DATABASE_URL/.env"""
    url = get_database_url()
    db = Database(url)
    await db.initialize()
    yield db
    await db.close()


@pytest_asyncio.fixture
async def pg_db_with_cleanup(pg_db):
    """
    Database fixture that tracks and cleans up test runs.

    Usage:
        async def test_something(pg_db_with_cleanup):
            db, track = pg_db_with_cleanup
            run_id = f"test_{uuid4()}"
            track(run_id)
            # ... test code using db and run_id ...
    """
    created_run_ids = []

    def track(run_id: str):
        created_run_ids.append(run_id)

    yield pg_db, track

    # Cleanup: delete test data in dependency order
    if created_run_ids:
        pool = await pg_db.get_pool()
        async with pool.acquire() as conn:
            for run_id in created_run_ids:
                for table in ("findings", "artifacts", "rejections", "observation_samples",
                              "ambiguous_matches", "assets", "runs"):
                    try:
                        await conn.execute(f"DELETE FROM {table} WHERE run_id = $1", run_id)
                    except Exception:
                        pass  # Table might not exist or column might not exist
