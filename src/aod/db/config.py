"""Database configuration utilities."""

import os


def get_database_url() -> str:
    """
    Get database URL with single selection rule:
    1. Use SUPABASE_DB_URL if set
    2. Else use DATABASE_URL
    3. If neither is set, fail fast with clear error

    No SQLite fallback or other defaults are allowed.
    """
    db_url = os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")

    if not db_url:
        raise RuntimeError(
            "No database configured. Set SUPABASE_DB_URL or DATABASE_URL environment variable. "
            "No SQLite fallback or other defaults are allowed."
        )

    return db_url


def get_active_db_source() -> str:
    """Return which env var is providing the database URL."""
    if os.environ.get("SUPABASE_DB_URL"):
        return "SUPABASE_DB_URL"
    elif os.environ.get("DATABASE_URL"):
        return "DATABASE_URL"
    else:
        return "NONE"
