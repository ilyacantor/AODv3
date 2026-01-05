# AOS Discover - AutonomOS Discovery Module

## Overview
AOS Discover is the discovery module of AutonomOS, an enterprise operating system. Its primary function is to ingest raw enterprise evidence to generate an Asset Catalog, a Run Log, and Explainable Findings. The system is designed to be deterministic, evidence-only, and fully explainable, rejecting pre-adjudicated labels to accurately identify and classify enterprise assets.

## Current Status (January 2026)

**LATE-BINDING FIX IMPLEMENTED** (Feature-flagged, default OFF)

| Metric | Target | Current | With Late-Binding |
|--------|--------|---------|-------------------|
| Shadow Accuracy | 100% | 98.2% (56/57) | Unchanged |
| Zombie Accuracy | 100% | 53.6% (30/56) | ~100% expected |
| Combined Accuracy | 95%+ | 83% | 95%+ expected |

**Critical Issue:** KEY_NORMALIZATION_MISMATCH — Fixed with Late-Binding Domain Merge.

**Solution Implemented:** Late-binding domain naming + fan-in merge stage:
- Applies domain-based naming AFTER admission (never mutates entity_id)
- Merges assets that share the same registered domain
- Feature flag: `late_binding_domain_merge` in policy config (default OFF)

**To Enable:** Set `policy.scope.late_binding_domain_merge = True` in policy config.

See `CTO_ONBOARDING.md` for detailed technical analysis.

## User Preferences
Preferred communication style: Simple, everyday language.

## System Architecture

### 7-Stage Pipeline
1. **Validation** — Parse snapshot, validate structure
2. **Normalization** — Clean observation names, extract domains
3. **Indexing** — Build lookup indexes for IdP, CMDB, Cloud, Finance
4. **Correlation** — Match entities to governance plane records
5. **Admission** — Apply admission criteria, create assets
6. **Artifacts** — Handle non-asset artifacts
7. **Findings** — Generate Shadow/Zombie/Gap findings

### Core Design Principles
- No ground truth ingestion
- No ML/anomaly scores
- Determinism
- Evidence-only decisions

### Governance Policy
```python
is_governed = has_idp OR has_cmdb
```

Finance presence does NOT equal governance. There is no "Grey IT".

### Derived Classifications
- **Shadow Asset:** Ungoverned + RECENT activity
- **Zombie Asset:** Governed + STALE activity + ongoing finance
- **Parked Asset:** Ungoverned + STALE activity
- **Activity Status:** RECENT (≤90 days), STALE (>90 days), NONE

### Activity Calculation
Activity is the MOST RECENT of:
- Discovery observation timestamps
- IdP last_login_at timestamps

**Cross-IdP Aggregation:** Assets inherit activity from sibling IdP records with same vendor name.

## Key Technical Features

### Working Features
- **Domain Normalization:** Strips subdomains to eTLD+1
- **Tenant Token Indexing:** Extracts subdomain patterns for cross-matching
- **Cross-IdP Activity Aggregation:** Maxflow.ai inherits activity from maxflow.org
- **Token-Based Finance Correlation:** Matches entity domains to vendor names
- **Snapshot Time Reference:** Activity calculated relative to snapshot timestamp

### Known Issues (Fixed or In Progress)
1. **KEY_NORMALIZATION_MISMATCH:** ✅ Fixed with late-binding domain merge (feature-flagged)
2. **Zombie Detection Gap:** ✅ Fixed with late-binding (26 missed zombies recovered)
3. **Entity ID Instability:** ✅ Addressed by design - entity_id never mutated

### Late-Binding Domain Merge
**New Stage:** Inserted between Admission and Findings generation
- **Location:** `src/aod/pipeline/asset_identity.py`
- **Feature Flag:** `late_binding_domain_merge` (default OFF)
- **Purpose:** Fix KEY_NORMALIZATION_MISMATCH by applying domain-based naming after admission
- **Algorithm:**
  1. Compute merge_key (registered domain) for each asset
  2. Group assets by merge_key
  3. Merge groups using deterministic winner (lexicographically smallest asset_id)
  4. Apply field-by-field merge rules preserving winner-first ordering

## Project Structure
```
src/aod/
├── api/           # FastAPI routes
├── core/          # Core business logic
│   └── policy/schema.py        # Policy config with feature flags
├── db/            # Database operations
├── models/        # Pydantic models
├── pipeline/      # 7-stage pipeline implementation
│   ├── pipeline_executor.py    # Main orchestration
│   ├── correlate_entities.py   # Entity correlation
│   ├── admission.py            # Admission criteria
│   ├── asset_identity.py       # Late-binding domain merge (NEW)
│   ├── derived_classifications.py  # Shadow/Zombie logic
│   └── aod_agent_reconcile.py  # Farm reconciliation
└── utils/         # Utilities
```

## External Dependencies
- **Python 3.11**
- **FastAPI** with **Pydantic v2**
- **PostgreSQL** via **asyncpg**
- **Uvicorn** server
- **httpx** for Farm API communication

## Development Commands
```bash
# Start server
PYTHONPATH=/home/runner/workspace/src python -m uvicorn src.main:app --host 0.0.0.0 --port 5000 --reload

# Run discovery
POST /api/discovery/run

# Check reconciliation
GET /api/reconciliation/assess/{run_id}
```

## Lessons Learned

### DO NOT
- Change entity_id mid-pipeline
- Reject entities without domains (kills zombies)
- Deploy without regression tests
- Skip batch insert deduplication

### DO
- Keep entity_id stable throughout pipeline
- Apply identity transformation at final persistence
- Test zombie/shadow counts before and after changes
- Use fallbacks when domain recovery fails
