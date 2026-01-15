# Key Selection Contract v2.0

## Overview

This document defines the **minimal, deterministic, alignable** contract for canonical key generation.
Both Farm and AOD MUST implement identical logic to achieve reconciliation alignment.

---

## Contract Summary

| Step | Rule |
|------|------|
| 1. Build candidate set | `observed_registered_domains = {eTLD+1(domain) for domain in discovery_observations}` |
| 2. Apply policy exclusions | Remove domains in `BANNED_DOMAINS` → if empty, emit as rejected |
| 3. Apply alias collapse | Only for domains in `ALIAS_DOMAINS_TO_COLLAPSE` |
| 4. Select canonical key | **Lexicographic sort** on registered domain, pick first |

---

## 1. Build Observed Registered Domains

```python
def build_observed_domains(discovery_observations: list[Observation]) -> set[str]:
    """Extract eTLD+1 domains from discovery observations ONLY."""
    domains = set()
    for obs in discovery_observations:
        if obs.domain:
            registered = extract_registered_domain(obs.domain)  # eTLD+1
            if registered:
                domains.add(registered)
    return domains
```

**Source**: Discovery observations only. NOT from CMDB, IdP, or other planes.

---

## 2. Apply Policy Exclusions

```python
def apply_policy_exclusions(domains: set[str], banned_domains: set[str]) -> set[str]:
    """Remove banned domains. If empty, entity is REJECTED."""
    remaining = domains - banned_domains
    if not remaining:
        return None  # Emit as rejected, no key generated
    return remaining
```

**Rule**: If all observed domains are banned, the entity is **rejected** (not silently dropped).

---

## 3. Apply Alias Collapse

```python
def apply_alias_collapse(domains: set[str]) -> set[str]:
    """Collapse known aliases to canonical vendor domain."""
    result = set()
    for domain in domains:
        if domain in ALIAS_DOMAINS_TO_COLLAPSE:
            canonical = VENDOR_TO_DOMAIN[DOMAIN_TO_VENDOR[domain]]
            result.add(canonical)
        else:
            result.add(domain)
    return result
```

**Rule**: Only domains explicitly in `ALIAS_DOMAINS_TO_COLLAPSE` are collapsed.

---

## 4. Select Canonical Key (Deterministic Tie-Breaker)

```python
def select_canonical_key(domains: set[str]) -> str:
    """Select canonical key via deterministic lexicographic sort."""
    if not domains:
        raise ValueError("No domains available for key selection")
    
    # Sort lexicographically, pick first
    sorted_domains = sorted(domains)
    return sorted_domains[0]
```

**Rule**: Lexicographic sort ensures identical key selection regardless of ingestion order.

---

## 5. Full Algorithm

```python
def compute_canonical_key_v2(discovery_observations: list[Observation]) -> str | None:
    # Step 1: Build observed domains from discovery only
    observed = build_observed_domains(discovery_observations)
    
    # Step 2: Apply policy exclusions
    after_exclusions = apply_policy_exclusions(observed, BANNED_DOMAINS)
    if after_exclusions is None:
        return None  # Entity rejected
    
    # Step 3: Apply alias collapse
    after_collapse = apply_alias_collapse(after_exclusions)
    
    # Step 4: Deterministic selection
    canonical_key = select_canonical_key(after_collapse)
    
    return canonical_key
```

---

## CMDB / IdP Domains

**Rule**: CMDB and IdP domains are stored as **reference/enrichment only**.

They do NOT participate in canonical key selection unless:
- Explicitly promoted by policy (e.g., `enable_cmdb_domain_promotion: true`)
- AND the entity has NO discovery domains

```python
# Reference domains stored separately
asset.identifiers.reference_domains = cmdb_domains + idp_domains

# Only used for keying if discovery domains are empty AND policy allows
if not observed_domains and policy.enable_cmdb_domain_promotion:
    observed_domains = extract_cmdb_primary_domain(correlation)
```

---

## What is NOT Allowed

To prevent repeat regressions:

| Forbidden Pattern | Reason |
|-------------------|--------|
| Using CMDB `external_ref` extracted domains for keying | Stage 1 fix - external_ref URLs are often vendor portals |
| Adding correlation-extracted domains to `identifiers.domains` | Pollutes identity with non-discovery domains |
| Choosing key based on list position (`domains[0]`) | Ingestion-order-dependent, non-deterministic |
| "First observation wins" | Same problem as list position |
| Rolling up to vendor roots unless in `ALIAS_DOMAINS_TO_COLLAPSE` | Loses granularity for infrastructure domains |

---

## Alias Collapse List

Only these domains collapse to their vendor root:

```python
ALIAS_DOMAINS_TO_COLLAPSE = {
    # Microsoft -> microsoft.com
    "microsoftonline.com", "microsoft365.com", "azure.com",
    "office365.com", "live.com", "onedrive.com", "powerbi.com",
    
    # Zoom -> zoom.us
    "zoom.com", "zoom-video.com", "zoom-meetings.net", "zoomapp.io",
    
    # Atlassian -> atlassian.com
    "jira.com", "confluence.com", "opsgenie.com",
    
    # GitHub -> github.com
    "github.io", "githubusercontent.com",
    
    # AWS -> amazon.com
    "amazonaws.com",
    
    # Other vendor aliases
    "dropboxapi.com", "dropboxusercontent.io", "slackb2b.com",
    "boxcdn.net", "oktapreview.com", "sendgrid.net", "stripe.network",
    "zdassets.com", "hubspotusercontent.com", "splunkcloud.com",
    "docusign.net", "adobelogin.com", "snowflakecomputing.com",
}
```

**Standalone domains** (NOT in collapse list, keep their own key):
- `outlook.com`, `office.com`, `sharepoint.com` (Microsoft services)
- `gstatic.com`, `googleapis.com`, `googleusercontent.com` (Google services)
- `cloudfront.net`, `awsstatic.com` (AWS CDN/static)
- `atlassian.net`, `notion.so`, `segment.io`, `datadoghq.com` (canonical SaaS)

---

## Alignment Checklist

Farm and AOD MUST verify:

- [ ] Both use the same `extract_registered_domain()` implementation (same PSL behavior)
- [ ] Both enforce `BANNED_DOMAINS` during key selection (reject, don't silently drop)
- [ ] Both apply the same `ALIAS_DOMAINS_TO_COLLAPSE` set
- [ ] Both use the same deterministic tie-breaker (lexicographic sort)
- [ ] Neither uses CMDB URL domains for key selection
- [ ] Neither uses list order (`domains[0]`) for key selection
- [ ] Both use discovery observations as the source for key candidates

---

## Examples

### Example 1: Single Domain
```
Discovery: app.slack.com
observed_registered_domains = {"slack.com"}
→ canonical_key = "slack.com"
```

### Example 2: Multiple Domains (Lexicographic)
```
Discovery: [zoom.us, app.webex.com, teams.microsoft.com]
observed_registered_domains = {"zoom.us", "webex.com", "microsoft.com"}
after_collapse = {"zoom.us", "webex.com", "microsoft.com"}
sorted = ["microsoft.com", "webex.com", "zoom.us"]
→ canonical_key = "microsoft.com" (lexicographically first)
```

### Example 3: Alias Collapse
```
Discovery: login.microsoftonline.com
observed_registered_domains = {"microsoftonline.com"}
after_collapse = {"microsoft.com"}
→ canonical_key = "microsoft.com"
```

### Example 4: Standalone Infrastructure
```
Discovery: mail.outlook.com
observed_registered_domains = {"outlook.com"}
after_collapse = {"outlook.com"}  # NOT collapsed to microsoft.com
→ canonical_key = "outlook.com"
```

### Example 5: Policy Rejection
```
Discovery: cdn.cloudflare.com
observed_registered_domains = {"cloudflare.com"}
BANNED_DOMAINS = {"cloudflare.com", ...}
after_exclusions = {} (empty)
→ REJECTED (no key generated)
```
