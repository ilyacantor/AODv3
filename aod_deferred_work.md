# Deferred work — aod

1. 2026-04-09 | https://claude.ai/chat/7aaa8044-1727-472d-9aaa-8e830c4da9e9 | src/aod/db/pool.py get_pool() | retry-forever loop when create_pool() raises. Pool never recovers — turns transient hiccup into permanent 500s until process restart. Severity: blocker. Blocking: AOD availability degrades silently after any pool init failure.

2. 2026-04-09 | https://claude.ai/chat/4457c1b3-e992-46ca-ac6e-1c6f737b0bbf | static/js/app.js:3342 | populateTenantsFromFarm dropdown displays UUID instead of entity_id. Same I2/I5 violation class as runs list/detail panel fix that landed. Severity: degraded. Blocking: UUID-in-UI consistency.
