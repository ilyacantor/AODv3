"""
PolicyManifestBuilder - Export policy_master.json into versioned manifests.

This module provides a builder for creating versioned policy manifests
that can be consumed by downstream systems (AAM, Farm, etc.).

The manifest includes all governance rules needed for a DiscoveryScan session.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

POLICY_MASTER_PATH = Path("config/policy_master.json")


class PolicyManifestBuilder:
    """
    Builds versioned policy manifests from policy_master.json.
    
    The manifest is a snapshot of governance rules at a point in time,
    associated with a specific DiscoveryScan session (scan_session_id).
    """
    
    MANIFEST_VERSION = "1.0.0"
    
    def __init__(self, policy_master_path: Path = POLICY_MASTER_PATH):
        """
        Initialize the PolicyManifestBuilder.
        
        Args:
            policy_master_path: Path to the policy_master.json file
        """
        self.policy_master_path = policy_master_path
    
    def _load_policy_master(self) -> dict:
        """Load and return the raw policy_master.json content."""
        if not self.policy_master_path.exists():
            raise FileNotFoundError(f"Policy master file not found: {self.policy_master_path}")
        
        with open(self.policy_master_path) as f:
            return json.load(f)
    
    def _extract_value(self, setting: Any) -> Any:
        """Extract value from a setting dict or return as-is."""
        if isinstance(setting, dict) and "value" in setting:
            return setting["value"]
        return setting
    
    def _extract_section_values(self, section: dict) -> dict:
        """Extract all values from a section, ignoring description and metadata."""
        result = {}
        for key, value in section.items():
            if key == "description":
                continue
            if isinstance(value, dict):
                if "value" in value:
                    result[key] = value["value"]
                else:
                    result[key] = self._extract_section_values(value)
            else:
                result[key] = value
        return result
    
    def build_manifest(self, scan_session_id: Optional[str] = None) -> dict:
        """
        Build a versioned policy manifest for a DiscoveryScan session.
        
        Args:
            scan_session_id: Optional DiscoveryScan session ID to associate with manifest
        
        Returns:
            dict containing:
            - manifest_version: Version of the manifest format
            - policy_version: Version from policy_master.json
            - generated_at: ISO timestamp of when manifest was generated
            - scan_session_id: Associated DiscoveryScan session (if provided)
            - governance_rules: All governance rules extracted from policy_master
        """
        policy_master = self._load_policy_master()
        
        governance_rules = {
            "admission_gates": self._extract_section_values(
                policy_master.get("admission_gates", {})
            ),
            "idp_governance": self._extract_section_values(
                policy_master.get("idp_governance", {})
            ),
            "scope_toggles": self._extract_section_values(
                policy_master.get("scope_toggles", {})
            ),
            "infrastructure_domain_handling": self._extract_section_values(
                policy_master.get("infrastructure_domain_handling", {})
            ),
            "finance_thresholds": self._extract_section_values(
                policy_master.get("finance_thresholds", {})
            ),
            "activity_windows": self._extract_section_values(
                policy_master.get("activity_windows", {})
            ),
            "connection_policy": self._extract_section_values(
                policy_master.get("connection_policy", {})
            ),
        }
        
        manifest = {
            "manifest_version": self.MANIFEST_VERSION,
            "policy_version": policy_master.get("version", "unknown"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "scan_session_id": scan_session_id,
            "governance_rules": governance_rules,
        }
        
        logger.info("policy_manifest.built", extra={
            "manifest_version": manifest["manifest_version"],
            "policy_version": manifest["policy_version"],
            "scan_session_id": scan_session_id,
        })
        
        return manifest
    
    def build_manifest_with_metadata(self, scan_session_id: Optional[str] = None) -> dict:
        """
        Build a policy manifest that includes full metadata (types, descriptions, etc.).
        
        Useful for UI rendering where you need type hints, min/max values, and labels.
        
        Args:
            scan_session_id: Optional DiscoveryScan session ID to associate with manifest
        
        Returns:
            dict containing full policy_master.json with manifest wrapper
        """
        policy_master = self._load_policy_master()
        
        return {
            "manifest_version": self.MANIFEST_VERSION,
            "policy_version": policy_master.get("version", "unknown"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "scan_session_id": scan_session_id,
            "policy_master": policy_master,
        }
