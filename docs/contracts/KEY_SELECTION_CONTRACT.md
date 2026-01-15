# Key Selection Contract v1.0

## Overview

This document defines the deterministic contract for canonical key generation in AOD.
Farm MUST implement identical logic to achieve reconciliation alignment.

## Contract Summary

| Question | AOD Answer |
|----------|------------|
| Which domain becomes canonical key? | `identifiers.domains[0]` after normalization |
| Domain priority order? | Discovery → CMDB primary → (others are reference only) |
| When do aliases collapse? | Only domains in `ALIAS_DOMAINS_TO_COLLAPSE` set |
| When do we exclude by policy? | Admission gates reject, key never generated |

---

## 1. Domain Priority Order

When building `identifiers.domains`, AOD uses this strict priority:

```
1. Discovery domain (highest priority)
   - Source: entity.domain from discovery observations
   - Provenance: "discovery"
   
2. CMDB primary domain (if not already in list)
   - Source: record.domain field (NOT external_ref URLs)
   - Condition: Authoritative match + gates passed (cmdb_admitted=True)
   - Provenance: "cmdb"
   
3. Reference domains (NOT in identifiers.domains)
   - Source: All other plane domains (external_ref URLs, etc.)
   - Location: identifiers.reference_domains (enrichment only)
```

**Result**: `domains[0]` is ALWAYS the discovery domain if present.

---

## 2. Canonical Key Computation

The canonical key is computed from `domains[0]`:

```python
def compute_canonical_key(domains: list[str], ...) -> CanonicalKeyResult:
    # Step 1: Get domains[0]
    raw_domain = domains[0].lower().strip()
    
    # Step 2: Extract eTLD+1 (registered domain)
    registered = extract_registered_domain(raw_domain)
    # Example: login.microsoftonline.com -> microsoftonline.com
    
    # Step 3: Collapse known aliases to vendor domain
    if registered in ALIAS_DOMAINS_TO_COLLAPSE:
        canonical = VENDOR_TO_DOMAIN[DOMAIN_TO_VENDOR[registered]]
        primary_key = canonical
    else:
        primary_key = registered
    
    return CanonicalKeyResult(primary_key=primary_key, ...)
```

---

## 3. Alias Collapse Rules

### 3.1 Domains That COLLAPSE to Vendor Domain

```python
ALIAS_DOMAINS_TO_COLLAPSE = {
    # Microsoft -> microsoft.com
    "microsoftonline.com",
    "microsoft365.com",
    "azure.com",
    "office365.com",
    "live.com",
    "onedrive.com",
    "powerbi.com",
    
    # Google -> google.com
    # (none currently - googleapis.com etc are NOT collapsed)
    
    # Zoom -> zoom.us
    "zoom.com",
    "zoom-video.com",
    "zoom-meetings.net",
    "zoomapp.io",
    
    # Atlassian -> atlassian.com
    "jira.com",
    "confluence.com",
    "opsgenie.com",
    
    # GitHub -> github.com
    "github.io",
    "githubusercontent.com",
    
    # AWS -> amazon.com
    "amazonaws.com",
    
    # Other vendor aliases
    "dropboxapi.com",
    "dropboxusercontent.io",
    "slackb2b.com",
    "boxcdn.net",
    "oktapreview.com",
    "sendgrid.net",
    "stripe.network",
    "zdassets.com",
    "hubspotusercontent.com",
    "splunkcloud.com",
    "docusign.net",
    "adobelogin.com",
    "snowflakecomputing.com",
}
```

### 3.2 Domains That DO NOT COLLAPSE (Standalone Keys)

These produce their own canonical keys despite belonging to a vendor family:

```python
# Infrastructure/service domains - Stage 4 Fix (Jan 2026)
STANDALONE_DOMAINS = {
    # Microsoft services (distinct SaaS endpoints)
    "outlook.com",      # Email service
    "office.com",       # Office suite
    "sharepoint.com",   # PaaS root (multi-tenant)
    
    # Google services
    "gstatic.com",      # Static assets/CDN
    "googleapis.com",   # API service
    "googleusercontent.com",  # PaaS root
    
    # AWS services
    "cloudfront.net",   # CDN service
    "awsstatic.com",    # Static assets
    
    # Other legitimate primary domains
    "atlassian.net",    # Jira Cloud (not an alias)
    "notion.so",        # Canonical domain
    "segment.io",       # Canonical domain
    "datadoghq.com",    # Canonical SaaS domain
}
```

### 3.3 Decision Tree

```
Given: registered_domain
├─ Is it in ALIAS_DOMAINS_TO_COLLAPSE?
│   ├─ YES: canonical_key = VENDOR_TO_DOMAIN[vendor]
│   └─ NO:  canonical_key = registered_domain (standalone)
```

---

## 4. Policy Exclusions

### 4.1 When Keys Are NOT Generated

An entity is rejected (no key generated) when:

1. **Infrastructure domain without governance**
   - Domain in `shared_infrastructure_domains` AND no IdP/CMDB match
   
2. **Vendor portal excluded by policy**
   - Domain in `vendor_root_portals` AND mode="exclude"
   
3. **Dev/build infrastructure excluded**
   - Domain in `dev_build_infrastructure` AND mode="exclude"
   
4. **Custom exclusion list**
   - Domain in `policy_master.json → custom_exclusions`

### 4.2 Representation in Expected Blocks

Rejected entities appear in **expected.rejected** (not expected.admitted):

```json
{
  "expected": {
    "admitted": ["slack.com", "zoom.us"],
    "rejected": [
      {
        "entity_key": "entity:cloudfront.net",
        "reason_code": "INFRASTRUCTURE_NO_GOVERNANCE",
        "reason_detail": "Infrastructure domain without IdP/CMDB match"
      }
    ]
  }
}
```

---

## 5. Multi-Domain Entity Examples

### Example 1: Discovery + CMDB Same Vendor

```
Discovery: login.microsoftonline.com
CMDB: azure.com (authoritative match)

identifiers.domains = ["microsoftonline.com", "azure.com"]
canonical_key = "microsoft.com" (both collapse to same vendor)
```

### Example 2: Discovery + CMDB Different

```
Discovery: slack.com
CMDB: slackb2b.com (authoritative match)

identifiers.domains = ["slack.com", "slackb2b.com"]
canonical_key = "slack.com" (discovery has priority, slackb2b.com collapses to slack.com anyway)
```

### Example 3: Standalone Infrastructure Domain

```
Discovery: app.outlook.com

identifiers.domains = ["outlook.com"]
canonical_key = "outlook.com" (NOT collapsed to microsoft.com)
```

### Example 4: No Discovery, CMDB Only

```
Discovery: (none - no domain in observations)
CMDB: zoom.us (authoritative match)

identifiers.domains = ["zoom.us"]
canonical_key = "zoom.us"
```

---

## 6. V2 Key Strategy (Preview)

V2 uses domain provenance priority instead of position:

```python
priority_order = ["discovery", "cmdb", "idp", "vendor_map", "inferred"]

def compute_canonical_key_v2(domains, domain_provenance, ...):
    # Find highest-priority domain based on provenance
    best_domain = min(domains, key=lambda d: priority_order.index(domain_provenance.get(d, "inferred")))
    return compute_key_from(best_domain)
```

**Key Difference**: V1 uses `domains[0]` position. V2 uses provenance source.
Both should produce same result if domain ordering is consistent.

---

## 7. Farm Alignment Checklist

Farm MUST implement:

- [ ] Same `ALIAS_DOMAINS_TO_COLLAPSE` set
- [ ] Same standalone domain exceptions (outlook.com, gstatic.com, etc.)
- [ ] Same domain priority order (discovery → cmdb → reference)
- [ ] Same eTLD+1 extraction (using public suffix list)
- [ ] Same vendor-to-domain mapping for alias collapse

---

## 8. Reconciliation Diagnostics

When keys don't match, check:

1. **Different domain sources**: AOD using discovery, Farm using CMDB?
2. **Alias collapse mismatch**: One system collapses, other doesn't?
3. **eTLD+1 extraction bug**: Different PSL versions or extraction logic?
4. **Missing domain in observations**: Farm indexed domain AOD didn't see?

Use `KEY_NORMALIZATION_MISMATCH` log entries to diagnose.
