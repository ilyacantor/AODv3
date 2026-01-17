"""Database operations package.

Extracted from database_old.py (1,274 lines) for modular organization.
The main database.py shim imports from database_old.py for safety.
These modules are available for future use when properly tested.

Structure:
    operations/
    ├── __init__.py      # This file - exports all functions
    ├── runs.py          # Run log CRUD (lines 381-512)
    ├── assets.py        # Asset CRUD (lines 514-636, 949-1006)
    ├── artifacts.py     # Artifact CRUD (lines 637-684, 1046-1080)
    ├── findings.py      # Finding CRUD (lines 686-744, 1008-1044)
    ├── observations.py  # Observations, ambiguous matches, rejections (lines 746-947)
    ├── llm_facts.py     # LLM facts CRUD (lines 1082-1190)
    └── triage.py        # Triage actions CRUD (lines 1192-1274)
"""

from .runs import (
    create_run,
    update_run,
    get_run,
    get_all_runs,
    delete_all_runs,
)

from .assets import (
    create_asset,
    get_assets_by_run,
    get_asset_by_id,
    update_asset_owner,
    update_asset_provisioning_status,
    create_assets_batch,
)

from .artifacts import (
    create_artifact,
    get_artifacts_by_run,
    create_artifacts_batch,
)

from .findings import (
    create_finding,
    get_findings_by_run,
    create_findings_batch,
)

from .observations import (
    create_observation_sample,
    create_ambiguous_match,
    create_rejection,
    get_observation_samples_by_run,
    get_ambiguous_matches_by_run,
    get_rejections_by_run,
    create_observation_samples_batch,
    create_ambiguous_matches_batch,
    create_rejections_batch,
)

from .llm_facts import (
    get_llm_fact,
    upsert_llm_fact,
    get_llm_facts_batch,
)

from .triage import (
    save_triage_action,
    get_triage_actions_by_run,
    delete_triage_action,
)

__all__ = [
    # Runs
    "create_run",
    "update_run",
    "get_run",
    "get_all_runs",
    "delete_all_runs",
    # Assets
    "create_asset",
    "get_assets_by_run",
    "get_asset_by_id",
    "update_asset_owner",
    "update_asset_provisioning_status",
    "create_assets_batch",
    # Artifacts
    "create_artifact",
    "get_artifacts_by_run",
    "create_artifacts_batch",
    # Findings
    "create_finding",
    "get_findings_by_run",
    "create_findings_batch",
    # Observations
    "create_observation_sample",
    "create_ambiguous_match",
    "create_rejection",
    "get_observation_samples_by_run",
    "get_ambiguous_matches_by_run",
    "get_rejections_by_run",
    "create_observation_samples_batch",
    "create_ambiguous_matches_batch",
    "create_rejections_batch",
    # LLM Facts
    "get_llm_fact",
    "upsert_llm_fact",
    "get_llm_facts_batch",
    # Triage
    "save_triage_action",
    "get_triage_actions_by_run",
    "delete_triage_action",
]
