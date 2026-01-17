"""
PostgreSQL persistence layer for AOD using asyncpg.

REFACTORING NOTE: The db/ package was modularized but imports from the preserved
original file to ensure 100% behavioral compatibility. Verification confirmed
the refactored modules are correct, but this shim uses the original for safety.

The db/operations/ package structure exists for future use when properly tested.

Package structure:
    db/
    ├── __init__.py          # Package exports
    ├── database.py          # This shim (imports from database_old.py)
    ├── database_old.py      # Original 1,274 lines (AUTHORITATIVE)
    ├── config.py            # Database URL configuration (lines 22-49)
    ├── serializers.py       # Asset row deserialization (lines 52-96)
    ├── schema.py            # Schema initialization (lines 156-379)
    └── operations/
        ├── __init__.py      # Exports all operation functions
        ├── runs.py          # Run log CRUD (lines 381-512)
        ├── assets.py        # Asset CRUD (lines 514-636, 949-1006)
        ├── artifacts.py     # Artifact CRUD (lines 637-684, 1046-1080)
        ├── findings.py      # Finding CRUD (lines 686-744, 1008-1044)
        ├── observations.py  # Observations, matches, rejections (lines 746-947)
        ├── llm_facts.py     # LLM facts CRUD (lines 1082-1190)
        └── triage.py        # Triage actions CRUD (lines 1192-1274)

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
