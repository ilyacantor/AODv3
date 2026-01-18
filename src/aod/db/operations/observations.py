"""Observation, ambiguous match, and rejection operations for database."""

import json
from datetime import datetime
from typing import Optional

import asyncpg


class ObservationOperations:
    """Operations for observation samples, ambiguous matches, and rejections."""

    def __init__(self, get_pool):
        self._get_pool = get_pool

    # Observation samples

    async def create_observation_sample(
        self,
        sample_id: str,
        run_id: str,
        name: str,
        domain: Optional[str],
        source: str,
        category: Optional[str],
        raw_preview: str,
        created_at: datetime
    ) -> None:
        """Create an observation sample record."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO observation_samples (id, run_id, name, domain, source, category, raw_preview, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                sample_id, run_id, name, domain, source, category, raw_preview, created_at.isoformat()
            )

    async def get_observation_samples_by_run(self, run_id: str, limit: int = 100, offset: int = 0) -> tuple[list[dict], int]:
        """Get observation samples for a run with pagination."""
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            count_row = await conn.fetchrow(
                "SELECT COUNT(*) as total FROM observation_samples WHERE run_id = $1",
                run_id
            )
            total = count_row["total"] if count_row else 0

            rows = await conn.fetch(
                "SELECT * FROM observation_samples WHERE run_id = $1 ORDER BY name LIMIT $2 OFFSET $3",
                run_id, limit, offset
            )

        items = [
            {
                "id": row["id"],
                "name": row["name"],
                "domain": row["domain"],
                "source": row["source"],
                "category": row["category"],
                "raw_preview": row["raw_preview"],
                "created_at": row["created_at"]
            }
            for row in rows
        ]
        return items, total

    async def create_observation_samples_batch(self, samples: list[tuple]) -> None:
        """Batch insert observation samples."""
        if not samples:
            return
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO observation_samples (id, run_id, name, domain, source, category, raw_preview, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                samples
            )

    # Ambiguous matches

    async def create_ambiguous_match(
        self,
        match_id: str,
        run_id: str,
        entity_key: str,
        entity_name: str,
        plane: str,
        candidate_ids: list[str],
        candidate_names: list[str],
        match_keys: list[str],
        created_at: datetime
    ) -> None:
        """Create an ambiguous match record."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO ambiguous_matches (id, run_id, entity_key, entity_name, plane, candidate_ids, candidate_names, match_keys, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                match_id, run_id, entity_key, entity_name, plane,
                json.dumps(candidate_ids), json.dumps(candidate_names), json.dumps(match_keys),
                created_at.isoformat()
            )

    async def get_ambiguous_matches_by_run(self, run_id: str, limit: int = 100, offset: int = 0) -> tuple[list[dict], int]:
        """Get ambiguous matches for a run with pagination."""
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            count_row = await conn.fetchrow(
                "SELECT COUNT(*) as total FROM ambiguous_matches WHERE run_id = $1",
                run_id
            )
            total = count_row["total"] if count_row else 0

            rows = await conn.fetch(
                "SELECT * FROM ambiguous_matches WHERE run_id = $1 ORDER BY entity_name LIMIT $2 OFFSET $3",
                run_id, limit, offset
            )

        items = [
            {
                "id": row["id"],
                "entity_key": row["entity_key"],
                "entity_name": row["entity_name"],
                "plane": row["plane"],
                "candidate_ids": json.loads(row["candidate_ids"]),
                "candidate_names": json.loads(row["candidate_names"]),
                "match_keys": json.loads(row["match_keys"]),
                "created_at": row["created_at"]
            }
            for row in rows
        ]
        return items, total

    async def create_ambiguous_matches_batch(self, matches: list[tuple]) -> None:
        """Batch insert ambiguous matches."""
        if not matches:
            return
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO ambiguous_matches (id, run_id, entity_key, entity_name, plane, candidate_ids, candidate_names, match_keys, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                matches
            )

    # Rejections

    async def create_rejection(
        self,
        rejection_id: str,
        run_id: str,
        entity_key: str,
        entity_name: str,
        reason_code: str,
        reason_detail: str,
        evidence_summary: dict,
        created_at: datetime
    ) -> None:
        """Create a rejection record."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO rejections (id, run_id, entity_key, entity_name, reason_code, reason_detail, evidence_summary, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                rejection_id, run_id, entity_key, entity_name, reason_code, reason_detail,
                json.dumps(evidence_summary), created_at.isoformat()
            )

    async def get_rejections_by_run(self, run_id: str, limit: int = 100, offset: int = 0) -> tuple[list[dict], int]:
        """Get rejections for a run with pagination."""
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            count_row = await conn.fetchrow(
                "SELECT COUNT(*) as total FROM rejections WHERE run_id = $1",
                run_id
            )
            total = count_row["total"] if count_row else 0

            rows = await conn.fetch(
                "SELECT * FROM rejections WHERE run_id = $1 ORDER BY entity_name LIMIT $2 OFFSET $3",
                run_id, limit, offset
            )

        items = [
            {
                "id": row["id"],
                "entity_key": row["entity_key"],
                "entity_name": row["entity_name"],
                "reason_code": row["reason_code"],
                "reason_detail": row["reason_detail"],
                "evidence_summary": json.loads(row["evidence_summary"]),
                "created_at": row["created_at"]
            }
            for row in rows
        ]
        return items, total

    async def create_rejections_batch(self, rejections: list[tuple]) -> None:
        """Batch insert rejections."""
        if not rejections:
            return
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO rejections (id, run_id, entity_key, entity_name, reason_code, reason_detail, evidence_summary, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                rejections
            )
