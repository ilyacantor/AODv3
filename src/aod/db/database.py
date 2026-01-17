"""
PostgreSQL persistence layer for AOD using asyncpg.

This module has been refactored into a modular structure.
All imports are re-exported here for backwards compatibility.

New structure:
    db/
    ├── config.py            # get_database_url, get_active_db_source
    ├── core.py              # Database class, get_db, get_db_direct
    ├── schema.py            # initialize_schema
    ├── serializers.py       # Row deserialization helpers
    └── operations/
        ├── runs.py          # Run CRUD operations
        ├── assets.py        # Asset CRUD operations
        ├── artifacts.py     # Artifact CRUD operations
        ├── findings.py      # Finding CRUD operations
        ├── observations.py  # Observations, matches, rejections
        ├── llm_facts.py     # LLM fact operations
        └── triage.py        # Triage action operations

Original file preserved as: database_old.py
"""

# Re-export everything for backwards compatibility
from .config import (
    get_database_url,
    get_active_db_source,
)

from .serializers import (
    deserialize_asset_row,
    deserialize_artifact_row,
    deserialize_finding_row,
    deserialize_run_row,
    _deserialize_asset_row,
)

from .core import (
    Database,
    get_db,
    get_db_direct,
)

__all__ = [
    # Config
    "get_database_url",
    "get_active_db_source",
    # Serializers
    "deserialize_asset_row",
    "deserialize_artifact_row",
    "deserialize_finding_row",
    "deserialize_run_row",
    "_deserialize_asset_row",
    # Core
    "Database",
    "get_db",
    "get_db_direct",
]
