# AOD Policy Engine Refactoring Plan

> **What this document covers:** A future roadmap for replacing hardcoded business rules with a configuration-driven policy engine. It identifies where thresholds are currently hardcoded (finance threshold, zombie window, etc.), proposes a new PolicyConfig schema, and outlines a phased migration using the strangler pattern. This is a planning document for future work, not current implementation.

---

## Executive Summary

This document outlines the plan to refactor AOD from hardcoded business rules to a **Configuration-Driven Policy Engine**. AOD will become the System of Record, exposing a `PolicyConfig` that Farm consumes for aligned reconciliation.

---

## 1. Current State Analysis

### 1.1 Where Hardcoded Rules Live

| Rule | Current Location | Hardcoded Value |
|------|------------------|-----------------|
| Finance threshold | `findings_engine.py:11,426` | `$200/mo` or `$2,000/yr` |
| Discovery noise floor | `aod_agent_reconcile.py:283` | `>= 2` sources |
| Zombie window | `derived_classifications.py`, `aod_agent_reconcile.py` | `90` days (passed as param) |
| Corporate root domains | `admission.py:23-78` | `CORPORATE_ROOT_DOMAINS` set |
| Infrastructure domains | `decision_trace.py:32-42`, `constants.py` | `INFRASTRUCTURE_DOMAINS` set |
| Valid CI types | `admission.py:18` | `VALID_CI_TYPES` set |
| Valid lifecycles | `admission.py:19` | `VALID_LIFECYCLES` set |
| Cloud resource types | `admission.py:89-97` | `VALID_CLOUD_RESOURCE_TYPES` set |

### 1.2 Current Logic Flow

```
admission.py
├── is_corporate_root_domain() → Hardcoded CORPORATE_ROOT_DOMAINS
├── check_idp_admission() → Hardcoded SSO/SCIM/service_principal logic
├── check_cmdb_admission() → Hardcoded VALID_CI_TYPES, VALID_LIFECYCLES
├── check_cloud_admission() → Hardcoded VALID_CLOUD_RESOURCE_TYPES
├── check_finance_admission() → Currently no spend threshold (!)
└── check_discovery_admission() → Hardcoded source count threshold

derived_classifications.py
├── classify_shadow() → Uses activity_window_days param (90 default)
└── classify_zombie() → Uses activity_window_days param (90 default)

findings_engine.py
├── generate_finance_gap_finding() → Hardcoded $200 threshold
└── generate_identity_gap_finding() → Hardcoded multi-plane requirements
```

---

## 2. Target Architecture

### 2.1 PolicyConfig Schema

```python
# src/aod/core/policy/schema.py

from dataclasses import dataclass, field
from typing import Optional

@dataclass
class AdmissionConfig:
    minimum_spend: float = 200.0          # Finance gate threshold ($/month)
    noise_floor: int = 2                  # Minimum discovery sources
    zombie_window_days: int = 90          # Inactivity threshold
    require_sso_for_idp: bool = True      # IdP gate: require SSO/SCIM/SP
    require_valid_ci_type: bool = True    # CMDB gate: require app/service/etc
    require_valid_lifecycle: bool = True  # CMDB gate: require prod/staging

@dataclass
class ScopeConfig:
    include_infra: bool = False           # Include infrastructure domains
    treat_directory_as_idp: bool = False  # Startup maturity mode

@dataclass 
class PolicyConfig:
    admission: AdmissionConfig = field(default_factory=AdmissionConfig)
    scope: ScopeConfig = field(default_factory=ScopeConfig)
    exclusions: list[str] = field(default_factory=list)  # Mutable kill list
    
    # Read-only seed lists (for reference, not mutation)
    _corporate_root_domains: set[str] = field(default_factory=set)
    _infrastructure_domains: set[str] = field(default_factory=set)
```

### 2.2 PolicyEngine Interface

```python
# src/aod/core/policy/engine.py

from dataclasses import dataclass
from typing import Optional
from .schema import PolicyConfig

@dataclass
class PolicyDecision:
    admitted: bool
    classification: Optional[str]  # "shadow" | "zombie" | "clean" | None
    rejection_reason: Optional[str]
    admission_reason: Optional[str]
    reason_codes: list[str]

class PolicyEngine:
    """
    Pure function policy evaluation.
    No DB side effects - just decision logic.
    """
    
    def __init__(self, config: PolicyConfig):
        self.config = config
        self._build_kill_list()
    
    def _build_kill_list(self):
        """Combine seed exclusions with mutable exclusions."""
        self.kill_list = set(self.config.exclusions)
        self.kill_list.update(self.config._corporate_root_domains)
        if not self.config.scope.include_infra:
            self.kill_list.update(self.config._infrastructure_domains)
    
    def evaluate(self, asset_data: dict) -> PolicyDecision:
        """
        Main entry point. Applies logic in strict order:
        1. Kill List check
        2. Admission Gates (OR logic)
        3. Classification (mutually exclusive)
        """
        domain = asset_data.get("domain", "").lower()
        
        # 1. Kill List
        if self._is_killed(domain):
            return PolicyDecision(
                admitted=False,
                classification=None,
                rejection_reason=f"Domain in exclusion list: {domain}",
                admission_reason=None,
                reason_codes=["KILLED"]
            )
        
        # 2. Admission Gates
        gates_passed = []
        
        if self._check_finance_gate(asset_data):
            gates_passed.append("finance")
        if self._check_governance_gate(asset_data):
            gates_passed.append("governance")
        if self._check_shadow_gate(asset_data):
            gates_passed.append("discovery")
        
        if not gates_passed:
            return PolicyDecision(
                admitted=False,
                classification=None,
                rejection_reason="No admission criteria satisfied",
                admission_reason=None,
                reason_codes=["NO_GATES_PASSED"]
            )
        
        # 3. Classification
        classification = self._classify(asset_data)
        
        return PolicyDecision(
            admitted=True,
            classification=classification,
            rejection_reason=None,
            admission_reason=f"Passed gates: {', '.join(gates_passed)}",
            reason_codes=self._compute_reason_codes(asset_data, classification)
        )
    
    def _is_killed(self, domain: str) -> bool:
        return domain in self.kill_list
    
    def _check_finance_gate(self, data: dict) -> bool:
        spend = data.get("monthly_spend", 0)
        return spend >= self.config.admission.minimum_spend
    
    def _check_governance_gate(self, data: dict) -> bool:
        if data.get("in_idp"):
            return True
        if data.get("in_cmdb"):
            return True
        if data.get("in_cloud"):
            return True
        if self.config.scope.treat_directory_as_idp and data.get("in_directory"):
            return True
        return False
    
    def _check_shadow_gate(self, data: dict) -> bool:
        source_count = data.get("discovery_sources_count", 0)
        return source_count >= self.config.admission.noise_floor
    
    def _classify(self, data: dict) -> str:
        is_active = data.get("is_active", False)
        is_governed = data.get("in_idp") or data.get("in_cmdb")
        
        if is_active and not is_governed:
            return "shadow"
        if not is_active and is_governed:
            return "zombie"
        return "clean"
```

---

## 3. API Exposure

### 3.1 New Endpoint

```python
# src/aod/api/routes/policy.py

from fastapi import APIRouter
from ...core.policy.schema import PolicyConfig
from ...core.policy.loader import get_current_config

router = APIRouter(prefix="/api/v1/policy", tags=["policy"])

@router.get("/config")
async def get_policy_config() -> dict:
    """
    Expose current policy configuration.
    Farm fetches this before simulation to align rules.
    """
    config = get_current_config()
    return {
        "admission": {
            "minimum_spend": config.admission.minimum_spend,
            "noise_floor": config.admission.noise_floor,
            "zombie_window_days": config.admission.zombie_window_days,
        },
        "scope": {
            "include_infra": config.scope.include_infra,
            "treat_directory_as_idp": config.scope.treat_directory_as_idp,
        },
        "exclusions": config.exclusions,
        "seed_exclusions": {
            "corporate_root_domains": list(config._corporate_root_domains),
            "infrastructure_domains": list(config._infrastructure_domains),
        }
    }
```

### 3.2 Hot Reload Support

```python
# src/aod/core/policy/loader.py

import json
from pathlib import Path
from .schema import PolicyConfig, AdmissionConfig, ScopeConfig

_current_config: PolicyConfig | None = None

def load_config(path: str = "config/policy.json") -> PolicyConfig:
    """Load config from JSON file with defaults."""
    global _current_config
    
    config_path = Path(path)
    if config_path.exists():
        with open(config_path) as f:
            data = json.load(f)
        
        admission = AdmissionConfig(
            minimum_spend=data.get("admission", {}).get("minimum_spend", 200),
            noise_floor=data.get("admission", {}).get("noise_floor", 2),
            zombie_window_days=data.get("admission", {}).get("zombie_window_days", 90),
        )
        scope = ScopeConfig(
            include_infra=data.get("scope", {}).get("include_infra", False),
            treat_directory_as_idp=data.get("scope", {}).get("treat_directory_as_idp", False),
        )
        exclusions = data.get("exclusions", [])
    else:
        admission = AdmissionConfig()
        scope = ScopeConfig()
        exclusions = []
    
    # Load seed lists from constants
    from ..constants import CORPORATE_ROOT_DOMAINS, INFRASTRUCTURE_DOMAINS
    
    _current_config = PolicyConfig(
        admission=admission,
        scope=scope,
        exclusions=exclusions,
        _corporate_root_domains=CORPORATE_ROOT_DOMAINS,
        _infrastructure_domains=INFRASTRUCTURE_DOMAINS,
    )
    
    return _current_config

def get_current_config() -> PolicyConfig:
    global _current_config
    if _current_config is None:
        return load_config()
    return _current_config

def reload_config():
    """Hot reload - call when config file changes."""
    return load_config()
```

---

## 4. Strangler Pattern Refactoring

### 4.1 Phase 1: Create PolicyEngine (No Integration)

1. Create `src/aod/core/policy/` directory
2. Implement `schema.py`, `engine.py`, `loader.py`
3. Add `GET /api/v1/policy/config` endpoint
4. Write unit tests for PolicyEngine

### 4.2 Phase 2: Parallel Execution

Keep existing logic but add PolicyEngine evaluation alongside:

```python
# In pipeline_executor.py

from ..core.policy.engine import PolicyEngine
from ..core.policy.loader import get_current_config

# Existing admission call
admission_result = apply_admission_criteria(...)

# NEW: PolicyEngine evaluation (shadow mode)
policy_engine = PolicyEngine(get_current_config())
policy_decision = policy_engine.evaluate({
    "domain": candidate.domain,
    "monthly_spend": correlation.finance.monthly_spend,
    "in_idp": correlation.idp.status == MatchStatus.MATCHED,
    "in_cmdb": correlation.cmdb.status == MatchStatus.MATCHED,
    "in_cloud": correlation.cloud.status == MatchStatus.MATCHED,
    "discovery_sources_count": len(candidate.observation_ids),
    "is_active": True,  # Compute from activity evidence
})

# Log discrepancies for validation
if admission_result.admitted != policy_decision.admitted:
    logger.warning("Policy engine mismatch", extra={...})
```

### 4.3 Phase 3: Cutover

Once validated, replace existing functions with PolicyEngine calls:

| Old Function | New Call |
|--------------|----------|
| `is_corporate_root_domain()` | `policy_engine._is_killed()` |
| `check_finance_admission()` | `policy_engine._check_finance_gate()` |
| `check_idp_admission()` | `policy_engine._check_governance_gate()` |
| `check_discovery_admission()` | `policy_engine._check_shadow_gate()` |
| `classify_shadow()` | `policy_engine._classify()` |

### 4.4 Phase 4: Cleanup

- Remove hardcoded constants from `admission.py`
- Migrate `CORPORATE_ROOT_DOMAINS` to `constants.py` as seed data
- Remove duplicate classification logic from `derived_classifications.py`

---

## 5. Kill List Handling

### 5.1 Three-Tier Exclusion

| Tier | Source | Mutability |
|------|--------|------------|
| **Seed: Corporate Root** | Code constant | Immutable |
| **Seed: Infrastructure** | Code constant | Toggle via `scope.include_infra` |
| **Customer Overrides** | `config.exclusions` | Mutable per-tenant |

### 5.2 Merge Logic

```python
def _build_kill_list(self):
    # Always include corporate roots
    kill = set(CORPORATE_ROOT_DOMAINS)
    
    # Include infra only if scope says to exclude
    if not self.config.scope.include_infra:
        kill.update(INFRASTRUCTURE_DOMAINS)
    
    # Add customer overrides
    kill.update(self.config.exclusions)
    
    self.kill_list = kill
```

---

## 6. File Structure

```
src/aod/
├── core/
│   └── policy/
│       ├── __init__.py
│       ├── schema.py      # PolicyConfig dataclasses
│       ├── engine.py      # PolicyEngine class
│       └── loader.py      # Config loading/hot-reload
├── api/
│   └── routes/
│       └── policy.py      # GET /api/v1/policy/config
├── constants.py           # CORPORATE_ROOT_DOMAINS, INFRASTRUCTURE_DOMAINS (moved)
└── pipeline/
    └── admission.py       # Refactored to use PolicyEngine
```

---

## 7. Deliverables Checklist

- [ ] Create `src/aod/core/policy/schema.py`
- [ ] Create `src/aod/core/policy/engine.py`
- [ ] Create `src/aod/core/policy/loader.py`
- [ ] Add `GET /api/v1/policy/config` endpoint
- [ ] Move seed lists to `src/aod/constants.py`
- [ ] Create `config/policy.json` with defaults
- [ ] Add parallel PolicyEngine evaluation in pipeline
- [ ] Validate no discrepancies for 100 runs
- [ ] Cutover admission logic to PolicyEngine
- [ ] Update replit.md with new architecture

---

## 8. Farm Alignment

Once AOD exposes `GET /api/v1/policy/config`, Farm should:

1. **Fetch config before simulation**:
   ```python
   config = await fetch("https://aod.example.com/api/v1/policy/config")
   ```

2. **Use thresholds in generators**:
   ```python
   def generate_shadow():
       # Generate noise_floor + 1 sources to ensure admission
       sources = config["admission"]["noise_floor"] + 1
       return create_asset(sources=sources)
   ```

3. **Grade reconciliation against active config**:
   - If `minimum_spend = 500`, a $200 rejection is **correct**
   - Scorecard should say "AOD correctly rejected per policy"
