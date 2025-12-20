# KEY_NORMALIZATION_MISMATCH Root Cause - CORRECTED

## Actual Root Cause (User Correction)

### What I Got Wrong

In my initial review, I incorrectly stated:
- ❌ "Farm expects normalized keys (eTLD+1), not raw subdomain keys"
- ❌ "The vendor fallback overrides existing domain evidence"

### What's Actually Happening

✅ **Farm expects HOST-LEVEL keys** (full subdomains like `login498.edge.com`, `dropboxusercontent.io`)
✅ **Domain evidence is lost during entity correlation/merging**, NOT overridden

## The Real Bug

### Data Structure Mismatch

**CandidateEntity** has ONE domain field:
```python
# src/aod/pipeline/normalize_observations.py:12-27
@dataclass
class CandidateEntity:
    domain: Optional[str] = None  # ← SINGLE domain
```

**AssetIdentifiers** expects a LIST of domains:
```python
# src/aod/pipeline/admission.py:413-417
identifiers = AssetIdentifiers(
    domains=[entity.domain] if entity.domain else [],  # ← LIST
```

### The Bug Flow

1. **Discovery observation**: Contains `domain="dropboxusercontent.io"`
2. **Entity normalization**: Creates `CandidateEntity` with `domain="dropboxusercontent.io"`
3. **Entity correlation**: Matches CMDB/Finance record for "Dropbox" vendor
   - **BUG**: During merge, the correlation process may create a new entity or merge with a vendor-based entity
   - The original domain from the discovery observation gets lost
4. **Asset creation**: `entity.domain` is now `None` or different
5. **Result**: `asset.identifiers.domains = []` (empty!)
6. **Reconciliation**: `_extract_raw_domain()` finds no domains, falls back to vendor lookup → returns `dropbox.com`
7. **Farm**: Expects `dropboxusercontent.io` (from original observation) → **KEY_NORMALIZATION_MISMATCH**

### Where Domains Get Lost

Need to investigate correlation/merging code to find exactly where:
- Entities with domains get merged with vendor-matched entities without domains
- The domain field gets dropped or overwritten
- Multiple observations with different domains don't preserve all domain evidence

## Investigation Needed

1. How does entity correlation handle merging entities with different domains?
2. When CMDB/IDP matching occurs by NAME instead of DOMAIN, how is domain evidence preserved?
3. Should `CandidateEntity.domain` be a LIST instead of a single value?
4. Should correlation preserve ALL domains from ALL observations that contribute to an entity?

## Next Steps

1. Trace through a specific example (dropboxusercontent.io) to see exact merge behavior
2. Check if multiple observations for same entity but different subdomains are being collapsed
3. Determine if the fix is:
   - Change `CandidateEntity.domain` to `domains: list[str]`
   - Preserve domain evidence through correlation
   - Update admission to copy ALL domains from ALL observation IDs

## User's Key Insight

> "The vendor fallback isn't overriding existing domain evidence - the domain evidence was lost earlier in the pipeline."

This is the critical insight! The bug is in **entity merging/correlation**, not in **key extraction**.
