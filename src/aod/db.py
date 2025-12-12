import asyncpg
from typing import Optional
from contextlib import asynccontextmanager
from src.aod.config import DATABASE_URL

_pool: Optional[asyncpg.Pool] = None


async def init_db():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    return _pool


async def close_db():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def get_pool() -> asyncpg.Pool:
    if _pool is None:
        await init_db()
    return _pool


@asynccontextmanager
async def get_connection():
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn


async def execute(query: str, *args):
    async with get_connection() as conn:
        return await conn.execute(query, *args)


async def fetch(query: str, *args):
    async with get_connection() as conn:
        return await conn.fetch(query, *args)


async def fetchrow(query: str, *args):
    async with get_connection() as conn:
        return await conn.fetchrow(query, *args)


async def fetchval(query: str, *args):
    async with get_connection() as conn:
        return await conn.fetchval(query, *args)
