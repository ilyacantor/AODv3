"""
PolicyEngine - Pure Function Policy Evaluation.

This module contains the core logic for evaluating admission and classification
decisions. It is strictly a pure function with NO database dependencies or
side effects.
"""

from dataclasses import dataclass, field
from typing import Optional
from .schema import PolicyConfig


@dataclass
class PolicyDecision:
    """Result of policy evaluation."""
    admitted: bool
    classification: Optional[str] = None
    rejection_reason: Optional[str] = None
    admission_reason: Optional[str] = None
    reason_codes: list[str] = field(default_factory=list)


class PolicyEngine:
    """
    Pure function policy evaluation engine.
    
    No DB side effects - just decision logic based on configuration.
    
    Logic is applied in strict order:
    1. Kill List check (exclusions)
    2. Admission Gates (OR logic)
    3. Classification (mutually exclusive)
    """
    
    def __init__(self, config: PolicyConfig):
        self.config = config
        self._build_kill_list()
    
    def _build_kill_list(self):
        """Combine seed exclusions with mutable exclusions."""
        self.kill_list = set(self.config.exclusions)
        self.kill_list.update(self.config.corporate_root_domains)
        if not self.config.scope.include_infra:
            self.kill_list.update(self.config.infrastructure_domains)
    
    def evaluate(self, asset_data: dict) -> PolicyDecision:
        """
        Main entry point for policy evaluation.
        
        Args:
            asset_data: Dictionary containing:
                - domain: str
                - monthly_spend: float
                - in_idp: bool
                - in_cmdb: bool
                - in_cloud: bool
                - in_directory: bool (optional)
                - discovery_planes_count: int (distinct corroborating planes, NOT raw sources)
                - is_active: bool
                - has_sso: bool (optional)
                - has_scim: bool (optional)
                - is_service_principal: bool (optional)
                - ci_type: str (optional)
                - lifecycle: str (optional)
        
        Returns:
            PolicyDecision with admission status and classification
        """
        domain = (asset_data.get("domain") or "").lower().strip()
        reason_codes = []
        
        if self._is_killed(domain):
            return PolicyDecision(
                admitted=False,
                classification=None,
                rejection_reason=f"Domain in exclusion list: {domain}",
                admission_reason=None,
                reason_codes=["KILLED"]
            )
        
        gates_passed = []
        
        finance_pass, finance_codes = self._check_finance_gate(asset_data)
        if finance_pass:
            gates_passed.append("finance")
            reason_codes.extend(finance_codes)
        
        governance_pass, gov_codes = self._check_governance_gate(asset_data)
        if governance_pass:
            gates_passed.append("governance")
            reason_codes.extend(gov_codes)
        
        discovery_pass, disc_codes = self._check_discovery_gate(asset_data)
        if discovery_pass:
            gates_passed.append("discovery")
            reason_codes.extend(disc_codes)
        
        if not gates_passed:
            no_codes = self._compute_negative_codes(asset_data)
            return PolicyDecision(
                admitted=False,
                classification=None,
                rejection_reason="No admission criteria satisfied",
                admission_reason=None,
                reason_codes=no_codes
            )
        
        classification, class_codes = self._classify(asset_data)
        reason_codes.extend(class_codes)
        
        return PolicyDecision(
            admitted=True,
            classification=classification,
            rejection_reason=None,
            admission_reason=f"Passed gates: {', '.join(gates_passed)}",
            reason_codes=reason_codes
        )
    
    def _is_killed(self, domain: str) -> bool:
        """Check if domain is in the kill list."""
        if not domain:
            return False
        return domain.lower().strip() in self.kill_list
    
    def _check_finance_gate(self, data: dict) -> tuple[bool, list[str]]:
        """
        Finance Gate: spend >= minimum_spend threshold.
        """
        spend = data.get("monthly_spend", 0) or 0
        if spend >= self.config.admission.minimum_spend:
            return True, ["HAS_FINANCE", "SPEND_ABOVE_THRESHOLD"]
        return False, []
    
    def _check_governance_gate(self, data: dict) -> tuple[bool, list[str]]:
        """
        Governance Gate: IdP OR CMDB OR Cloud (with optional strictness).
        """
        codes = []
        
        in_idp = data.get("in_idp", False)
        if in_idp:
            if self.config.admission.require_sso_for_idp:
                has_sso = data.get("has_sso", False)
                has_scim = data.get("has_scim", False)
                is_sp = data.get("is_service_principal", False)
                if has_sso or has_scim or is_sp:
                    codes.append("HAS_IDP")
                    if has_sso:
                        codes.append("HAS_SSO")
                    if has_scim:
                        codes.append("HAS_SCIM")
                    if is_sp:
                        codes.append("IS_SERVICE_PRINCIPAL")
            else:
                codes.append("HAS_IDP")
        
        in_cmdb = data.get("in_cmdb", False)
        if in_cmdb:
            if self.config.admission.require_valid_ci_type:
                ci_type = (data.get("ci_type") or "").lower()
                lifecycle = (data.get("lifecycle") or "").lower()
                valid_ci = ci_type in {"app", "application", "service", "database", "infra", "infrastructure", "server", "system"}
                valid_lc = lifecycle in {"prod", "production", "staging", "stage", "live", "active"} if self.config.admission.require_valid_lifecycle else True
                if valid_ci and valid_lc:
                    codes.append("HAS_CMDB")
            else:
                codes.append("HAS_CMDB")
        
        in_cloud = data.get("in_cloud", False)
        if in_cloud:
            codes.append("HAS_CLOUD")
        
        if self.config.scope.treat_directory_as_idp:
            in_directory = data.get("in_directory", False)
            if in_directory:
                codes.append("HAS_DIRECTORY")
        
        passed = len(codes) > 0
        return passed, codes
    
    def _check_discovery_gate(self, data: dict) -> tuple[bool, list[str]]:
        """
        Discovery/Shadow Gate: plane_count >= noise_floor.
        
        CRITICAL: Count DISTINCT PLANES, not raw sources.
        - dns + proxy = 1 plane (network)
        - dns + edr = 2 planes (network, endpoint)
        
        Finance and CMDB do NOT count as discovery corroboration.
        Only: network, endpoint, idp, cloud, discovery
        """
        plane_count = data.get("discovery_planes_count", 0) or 0
        if plane_count >= self.config.admission.noise_floor:
            return True, ["HAS_DISCOVERY", f"PLANE_COUNT_{plane_count}"]
        return False, []
    
    def _classify(self, data: dict) -> tuple[str, list[str]]:
        """
        Classify admitted asset as shadow, zombie, or clean.
        
        Mutually exclusive:
        - SHADOW: Active + Ungoverned
        - ZOMBIE: Inactive + Governed  
        - CLEAN: Active + Governed
        """
        is_active = data.get("is_active", True)
        in_idp = data.get("in_idp", False)
        in_cmdb = data.get("in_cmdb", False)
        is_governed = in_idp or in_cmdb
        
        codes = []
        if is_active:
            codes.append("IS_ACTIVE")
        else:
            codes.append("IS_STALE")
        
        if is_governed:
            codes.append("IS_GOVERNED")
        else:
            codes.append("IS_UNGOVERNED")
        
        if is_active and not is_governed:
            return "shadow", codes + ["CLASSIFIED_SHADOW"]
        if not is_active and is_governed:
            return "zombie", codes + ["CLASSIFIED_ZOMBIE"]
        return "clean", codes + ["CLASSIFIED_CLEAN"]
    
    def _compute_negative_codes(self, data: dict) -> list[str]:
        """Compute reason codes for rejection."""
        codes = []
        
        if not data.get("in_idp"):
            codes.append("NO_IDP")
        if not data.get("in_cmdb"):
            codes.append("NO_CMDB")
        if not data.get("in_cloud"):
            codes.append("NO_CLOUD")
        
        spend = data.get("monthly_spend", 0) or 0
        if spend < self.config.admission.minimum_spend:
            codes.append("NO_FINANCE")
        
        plane_count = data.get("discovery_planes_count", 0) or 0
        if plane_count < self.config.admission.noise_floor:
            codes.append("DISCOVERY_PLANE_COUNT_LT_2")
        
        return codes
