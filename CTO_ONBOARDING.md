# CTO Onboarding: AOD Discover

**Last Updated:** January 5, 2026  
**Status:** NEEDS ARCHITECTURAL FIX  
**Current Accuracy:** 83% (regression from 96.4%)

---

## Executive Summary

AOD Discover is the discovery module of AutonomOS. It processes enterprise evidence through a 7-stage pipeline to create an Asset Catalog with explainable findings for Shadow IT and Zombie asset detection.

**Current State:** The system is functional but has a critical architectural issue causing 26 zombie assets to be missed. A recent "Domain Primacy" refactor attempt failed catastrophically and was rolled back.

---

## The Core Problem: KEY_NORMALIZATION_MISMATCH

### What It Is
Farm (upstream system) expects assets to be keyed by **domain** (e.g., `rapidbox.net`), but AOD historically keyed assets by **display name** (e.g., `RapidBox`). This mismatch causes reconciliation failures, particularly for zombie detection.

### Why It Matters
- **Zombies Missed:** 26/56 zombies not detected (46% miss rate)
- **Farm Can't Match:** When Farm queries for `rapidbox.net`, AOD returns nothing because asset is named `RapidBox`

### Failed Fix Attempt: "Domain Primacy" (Jan 2026)
An attempt to fix this by enforcing "Domain > Name" hierarchy caused:
- 550/1163 candidates rejected (47% - "Domain Guillotine" too aggressive)
- Database constraint violations (duplicate UUIDs when entities collapsed to same domain)
- Accuracy regression from 96.4% → 83%

**Root Causes of Failure:**
1. Domain Guillotine rejected entities without domains (many zombies lack domains)
2. No collision handling when multiple entities resolved to same domain
3. Entity ID changed mid-pipeline, breaking downstream lookups
4. Batch insert deduplication was missing

---

## Architecture Overview

### 7-Stage Pipeline

```
1. VALIDATION    → Parse snapshot, validate structure
2. NORMALIZATION → Clean observation names, extract domains
3. INDEXING      → Build lookup indexes for IdP, CMDB, Cloud, Finance
4. CORRELATION   → Match entities to governance plane records
5. ADMISSION     → Apply admission criteria, create assets
6. ARTIFACTS     → Handle non-asset artifacts (browsers, etc.)
7. FINDINGS      → Generate Shadow/Zombie/Gap findings
```

### Key Files

| File | Purpose |
|------|---------|
| `src/aod/pipeline/pipeline_executor.py` | Main pipeline orchestration |
| `src/aod/pipeline/correlate_entities.py` | Entity-to-plane correlation |
| `src/aod/pipeline/admission.py` | Admission criteria & asset creation |
| `src/aod/pipeline/derived_classifications.py` | Shadow/Zombie classification |
| `src/aod/pipeline/aod_agent_reconcile.py` | Farm reconciliation adapter |
| `src/aod/db/database.py` | PostgreSQL persistence |

### Classification Logic

```python
# Governance Policy
is_governed = has_idp OR has_cmdb

# Shadow Asset
is_shadow = NOT is_governed AND activity_status == RECENT

# Zombie Asset  
is_zombie = is_governed AND activity_status == STALE AND has_ongoing_finance

# Parked Asset
is_parked = NOT is_governed AND activity_status == STALE
```

### Activity Calculation
Activity is determined by the MOST RECENT of:
1. Discovery observation timestamps
2. IdP `last_login_at` timestamps (cross-IdP aggregation applies)

**Cross-IdP Aggregation:** Assets matched to IdP records inherit activity from sibling records with the same vendor name. Example: `maxflow.ai` inherits recent activity from `maxflow.org` if they share the IdP name "Maxflow".

---

## Known Issues (Priority Order)

### P0: Zombie Detection Gap (26/56 missed)
- **Symptom:** Farm expects 56 zombies, AOD finds 30
- **Root Cause:** Asset keys don't match Farm's domain-based expectations
- **Constraint:** Any fix must NOT break the 56/57 shadow accuracy

### P1: Entity Identity Instability
- **Symptom:** Entities changing ID mid-pipeline breaks lookups
- **Root Cause:** `entity.entity_id` is mutated during correlation
- **Constraint:** Entity ID must remain stable from normalization through persistence

### P2: Fan-In Collision Handling
- **Symptom:** Multiple entities resolving to same domain cause UUID collisions
- **Root Cause:** No merge strategy for colliding entities
- **Constraint:** Must merge evidence/findings, not just drop duplicates

---

## Lessons Learned (From Failed Refactors)

### DO NOT:
1. **Change entity_id mid-pipeline** — breaks `correlation_by_entity_id` lookup
2. **Reject entities without domains** — kills zombies (they often lack domains)
3. **Mutate identity before persistence** — creates cascade of broken references
4. **Skip batch insert deduplication** — causes database constraint violations
5. **Deploy without regression tests** — no way to catch accuracy drops

### DO:
1. **Keep entity_id stable** — assign once during normalization, never change
2. **Apply identity transformation at persistence** — last step, with collision handling
3. **Deduplicate all batch inserts** — obs_samples, ambiguous_matches, rejections
4. **Test zombie/shadow counts** — before and after any change
5. **Use fallbacks** — if domain recovery fails, fall back to original_name

---

## Proposed Architecture Fix

### "Late Binding" Approach
Instead of changing entity identity during pipeline, apply domain-based naming only at the final persistence step:

1. **Pipeline runs with stable entity_id** (based on original_name)
2. **At persistence:** If canonical_domain exists, use it as asset.name
3. **If collision:** Merge entities that resolve to same domain (combine evidence)
4. **If no domain:** Use original_name (no guillotine)
5. **Always preserve:** original_name in identifiers.hostnames

### Key Invariants
- Entity ID is immutable after normalization
- Asset name can be domain OR name (with clear precedence)
- Collisions are merged, not dropped
- All batch inserts are deduplicated

---

## Testing & Validation

### Reconciliation Assessment
Run discovery → Run reconciliation → Check assessment report

```bash
# Via API
POST /api/discovery/run
GET /api/reconciliation/assess/{run_id}
```

### Key Metrics to Watch
| Metric | Target | Current |
|--------|--------|---------|
| Shadow Accuracy | 100% | 98.2% (56/57) |
| Zombie Accuracy | 100% | 53.6% (30/56) |
| Combined Accuracy | 95%+ | 83% |
| Rejection Rate | <10% | 47% (with failed fix) |

---

## External Dependencies

- **Farm:** Upstream snapshot provider and reconciliation source of truth
- **PostgreSQL:** Asset catalog persistence
- **FastAPI:** REST API framework
- **Pydantic v2:** Data validation

---

## Quick Start

```bash
# Start server
cd /home/runner/workspace
PYTHONPATH=/home/runner/workspace/src python -m uvicorn src.main:app --host 0.0.0.0 --port 5000 --reload

# Run discovery
curl -X POST http://localhost:5000/api/discovery/run \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "HelixLogic-9GC6", "snapshot_id": "..."}'

# Check reconciliation
curl http://localhost:5000/api/reconciliation/assess/{run_id}
```

---

## Contact & Resources

- **Farm API:** External service for snapshot ingestion
- **Assessment Reports:** Generated in `attached_assets/` directory
- **Demolition Manifest:** See `attached_assets/Pasted-This-Demolition-Manifest-*` for failed fix analysis
