# Deferred work — aod

1. 2026-04-09 | https://claude.ai/chat/7aaa8044-1727-472d-9aaa-8e830c4da9e9 | src/aod/db/pool.py get_pool() | retry-forever loop when create_pool() raises. Pool never recovers — turns transient hiccup into permanent 500s until process restart. Severity: blocker. Blocking: AOD availability degrades silently after any pool init failure.

2. 2026-04-09 | https://claude.ai/chat/4457c1b3-e992-46ca-ac6e-1c6f737b0bbf | static/js/app.js:3342 | populateTenantsFromFarm dropdown displays UUID instead of entity_id. Same I2/I5 violation class as runs list/detail panel fix that landed. Severity: degraded. Blocking: UUID-in-UI consistency.

3. 2026-05-16 | ws-1 b5 cleanup | aod repo-wide (6 remaining files) | After Block 5 scrub of demo-critical src/aod/models/output_contracts.py (Pydantic Field example), 6 files retain banned literals in categories (c/d): tests/mai/test_status_endpoint.py + tests/test_pipeline_identity.py (test fixtures using meridian/cascadia tenant tags — exempted by hook tests/* rule), CLAUDE.md + AOS_MASTER_RACI_v8_6.csv + convergence_{blueprint,transition}_master.md (policy/spec). | severity: cosmetic | blocking: nothing
