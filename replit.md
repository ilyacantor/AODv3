# AOS Discover - AutonomOS Discovery Module

## Overview
AOS Discover is the discovery module of AutonomOS, an enterprise operating system. Its primary function is to ingest raw enterprise evidence to generate an Asset Catalog, a Run Log, and Explainable Findings. The system is designed to be deterministic, evidence-only, and fully explainable, rejecting pre-adjudicated labels to accurately identify and classify enterprise assets.

## Current Status (January 2026)

**NEEDS ARCHITECTURAL FIX**

| Metric | Target | Current |
|--------|--------|---------|
| Shadow Accuracy | 100% | 98.2% (56/57) |
| Zombie Accuracy | 100% | 53.6% (30/56) |
| Combined Accuracy | 95%+ | 83% |

**Critical Issue:** KEY_NORMALIZATION_MISMATCH — Farm expects domain-based asset keys, AOD uses name-based keys. This causes zombie detection failures.

**Failed Fix (Jan 2026):** "Domain Primacy" refactor was rolled back after causing 47% rejection rate and accuracy regression from 96.4% → 83%.

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

### Known Issues
1. **KEY_NORMALIZATION_MISMATCH:** Asset keys don't match Farm's domain-based expectations
2. **Zombie Detection Gap:** 26/56 zombies missed due to key mismatch
3. **Entity ID Instability:** Changing entity_id mid-pipeline breaks lookups

## Project Structure
```
src/aod/
├── api/           # FastAPI routes
├── core/          # Core business logic
├── db/            # Database operations
├── models/        # Pydantic models
├── pipeline/      # 7-stage pipeline implementation
│   ├── pipeline_executor.py    # Main orchestration
│   ├── correlate_entities.py   # Entity correlation
│   ├── admission.py            # Admission criteria
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
