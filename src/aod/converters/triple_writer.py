"""
Write EAV triples to the DCL semantic_triples table via asyncpg.

Uses AOD's existing connection pool — no new connection pattern.
Batch inserts via executemany (asyncpg equivalent of psycopg2's execute_values).

The semantic_triples table is in the same Supabase Postgres database
that AOD already connects to. Connection parameters come from
SUPABASE_DB_URL / DATABASE_URL.
"""

import json
import logging
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

# Column order matching DCL's triple_store.py insert_triples
_COLUMNS = [
    "tenant_id", "entity_id", "concept", "property", "value",
    "period", "currency", "unit",
    "source_system", "source_table", "source_field",
    "pipe_id", "run_id", "source_run_tag",
    "confidence_score", "confidence_tier",
    "canonical_id", "resolution_method", "resolution_confidence",
]

_INSERT_SQL = (
    "INSERT INTO semantic_triples ("
    + ", ".join(_COLUMNS)
    + ") VALUES ("
    + ", ".join(f"${i + 1}" for i in range(len(_COLUMNS)))
    + ")"
)


def _triple_to_row(triple: dict) -> tuple:
    """Convert a triple dict to a tuple matching _COLUMNS order.

    The value field is JSON-serialized to match DCL's schema (JSONB column).
    """
    row = []
    for col in _COLUMNS:
        val = triple.get(col)
        if col == "value":
            val = json.dumps(val)
        row.append(val)
    return tuple(row)


async def write_triples_to_pg(
    triples: list[dict],
    pool: asyncpg.Pool,
) -> int:
    """Batch-insert triples into semantic_triples.

    Args:
        triples: List of triple dicts (19-column schema).
        pool: asyncpg connection pool (from AOD's Database.get_pool()).

    Returns:
        Number of triples inserted.

    Raises:
        RuntimeError: If the database connection or insert fails.
            Error includes full context (table, row count, detail).
    """
    if not triples:
        return 0

    rows = [_triple_to_row(t) for t in triples]

    try:
        async with pool.acquire() as conn:
            await conn.executemany(_INSERT_SQL, rows)
    except asyncpg.PostgresError as e:
        raise RuntimeError(
            f"Triple write to semantic_triples failed: {e}. "
            f"Attempted to insert {len(rows)} triples. "
            f"Check SUPABASE_DB_URL and Supabase connectivity. "
            f"Table: semantic_triples, columns: {_COLUMNS}"
        ) from e

    return len(rows)
