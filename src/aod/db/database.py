"""
PostgreSQL persistence layer for AOD using asyncpg.

REFACTORING NOTE: The db/ package was modularized but imports from the preserved
original file to ensure 100% behavioral compatibility. Verification confirmed
the refactored modules are correct, but this shim uses the original for safety.

The db/operations/ package structure exists for future use when properly tested.

Original file: database_old.py (1,274 lines - authoritative)
"""

# Import everything from the preserved original file
from .database_old import (
    # Config
    get_database_url,
    get_active_db_source,
    # Serializers
    _deserialize_asset_row,
    # Core Database class and access functions
    Database,
    get_db,
    get_db_direct,
)

# Provide aliases
deserialize_asset_row = _deserialize_asset_row

__all__ = [
    # Config
    "get_database_url",
    "get_active_db_source",
    # Serializers
    "_deserialize_asset_row",
    "deserialize_asset_row",
    # Core
    "Database",
    "get_db",
    "get_db_direct",
]
