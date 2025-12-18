"""
Candidate Asset Key Extraction

Extracts canonical asset keys from ALL planes in a snapshot.
This ensures that any evidence containing a domain/hostname produces
a deterministic asset key for admission.

Key Invariants:
- Every hostname/domain in evidence produces a candidate key
- Keys are extracted from ALL planes (discovery, idp, cmdb, cloud, network, finance)
- Extraction is logged with counts by source for debugging
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from ..models.input_contracts import Snapshot
from .domain_normalization import (
    derive_canonical_asset_key,
    normalize_hostname,
    looks_like_domain,
)
from .aod_agent_reconcile import VENDOR_TO_DOMAIN

logger = logging.getLogger(__name__)


@dataclass
class CandidateKeyResult:
    """Result of candidate key extraction with provenance."""
    keys_from_discovery: set[str] = field(default_factory=set)
    keys_from_idp: set[str] = field(default_factory=set)
    keys_from_cmdb: set[str] = field(default_factory=set)
    keys_from_cloud: set[str] = field(default_factory=set)
    keys_from_network: set[str] = field(default_factory=set)
    keys_from_finance: set[str] = field(default_factory=set)
    
    finance_vendor_to_keys: dict[str, set[str]] = field(default_factory=dict)
    
    @property
    def all_keys(self) -> set[str]:
        """Get all candidate keys across all planes."""
        return (
            self.keys_from_discovery |
            self.keys_from_idp |
            self.keys_from_cmdb |
            self.keys_from_cloud |
            self.keys_from_network |
            self.keys_from_finance
        )
    
    def log_summary(self):
        """Log extraction summary for debugging."""
        logger.info(f"Candidate key extraction summary:")
        logger.info(f"  Discovery: {len(self.keys_from_discovery)} keys")
        logger.info(f"  IdP: {len(self.keys_from_idp)} keys")
        logger.info(f"  CMDB: {len(self.keys_from_cmdb)} keys")
        logger.info(f"  Cloud: {len(self.keys_from_cloud)} keys")
        logger.info(f"  Network: {len(self.keys_from_network)} keys")
        logger.info(f"  Finance: {len(self.keys_from_finance)} keys")
        logger.info(f"  TOTAL UNIQUE: {len(self.all_keys)} keys")


def _extract_key_from_domain_field(domain: Optional[str]) -> Optional[str]:
    """Extract canonical key from a domain field."""
    if not domain:
        return None
    return derive_canonical_asset_key(domain)


def _extract_key_from_uri(uri: Optional[str]) -> Optional[str]:
    """Extract canonical key from a URI field."""
    if not uri:
        return None
    hostname = normalize_hostname(uri)
    if hostname:
        return derive_canonical_asset_key(hostname)
    return None


def _extract_key_from_name(name: Optional[str]) -> Optional[str]:
    """Extract canonical key if name looks like a domain."""
    if not name:
        return None
    if looks_like_domain(name):
        return derive_canonical_asset_key(name)
    return None


def _extract_key_from_vendor(vendor: Optional[str]) -> Optional[str]:
    """Extract canonical key from vendor name using lookup."""
    if not vendor:
        return None
    vendor_key = vendor.lower().strip()
    if vendor_key in VENDOR_TO_DOMAIN:
        return VENDOR_TO_DOMAIN[vendor_key]
    return None


def extract_candidate_asset_keys(snapshot: Snapshot) -> CandidateKeyResult:
    """
    Extract all candidate asset keys from a snapshot.
    
    This function scans ALL planes and extracts canonical asset keys
    from any field that might contain a hostname/domain.
    
    Args:
        snapshot: The input snapshot
        
    Returns:
        CandidateKeyResult with keys organized by source plane
    """
    result = CandidateKeyResult()
    
    for obs in snapshot.planes.discovery.observations:
        key = _extract_key_from_domain_field(obs.domain)
        if key:
            result.keys_from_discovery.add(key)
            continue
        
        key = _extract_key_from_uri(obs.uri)
        if key:
            result.keys_from_discovery.add(key)
            continue
        
        key = _extract_key_from_uri(obs.hostname)
        if key:
            result.keys_from_discovery.add(key)
            continue
        
        key = _extract_key_from_name(obs.name)
        if key:
            result.keys_from_discovery.add(key)
            continue
    
    for obj in snapshot.planes.idp.objects:
        key = _extract_key_from_domain_field(obj.domain)
        if key:
            result.keys_from_idp.add(key)
        
        key = _extract_key_from_name(obj.name)
        if key:
            result.keys_from_idp.add(key)
    
    for ci in snapshot.planes.cmdb.cis:
        key = _extract_key_from_domain_field(ci.domain)
        if key:
            result.keys_from_cmdb.add(key)
        
        key = _extract_key_from_name(ci.name)
        if key:
            result.keys_from_cmdb.add(key)
        
        if ci.raw_data and isinstance(ci.raw_data, dict):
            for field_name in ['external_ref', 'url', 'endpoint', 'homepage']:
                url = ci.raw_data.get(field_name)
                if url:
                    key = _extract_key_from_uri(url)
                    if key:
                        result.keys_from_cmdb.add(key)
    
    for resource in snapshot.planes.cloud.resources:
        key = _extract_key_from_uri(resource.uri)
        if key:
            result.keys_from_cloud.add(key)
        
        key = _extract_key_from_name(resource.name)
        if key:
            result.keys_from_cloud.add(key)
    
    for dns in snapshot.planes.network.dns:
        key = _extract_key_from_domain_field(dns.domain)
        if key:
            result.keys_from_network.add(key)
    
    for proxy in snapshot.planes.network.proxy:
        key = _extract_key_from_domain_field(proxy.domain)
        if key:
            result.keys_from_network.add(key)
        
        key = _extract_key_from_uri(proxy.uri)
        if key:
            result.keys_from_network.add(key)
    
    for cert in snapshot.planes.network.certs:
        key = _extract_key_from_domain_field(cert.domain)
        if key:
            result.keys_from_network.add(key)
    
    for contract in snapshot.planes.finance.contracts:
        vendor_name = contract.vendor_name or ""
        
        key = _extract_key_from_vendor(vendor_name)
        if key:
            result.keys_from_finance.add(key)
            if vendor_name:
                vendor_lower = vendor_name.lower().strip()
                if vendor_lower not in result.finance_vendor_to_keys:
                    result.finance_vendor_to_keys[vendor_lower] = set()
                result.finance_vendor_to_keys[vendor_lower].add(key)
        
        if contract.product:
            key = _extract_key_from_vendor(contract.product)
            if key:
                result.keys_from_finance.add(key)
        
        if contract.raw_data and isinstance(contract.raw_data, dict):
            for field_name in ['url', 'domain', 'vendor_url', 'website']:
                url = contract.raw_data.get(field_name)
                if url:
                    key = _extract_key_from_uri(url)
                    if key:
                        result.keys_from_finance.add(key)
                        if vendor_name:
                            vendor_lower = vendor_name.lower().strip()
                            if vendor_lower not in result.finance_vendor_to_keys:
                                result.finance_vendor_to_keys[vendor_lower] = set()
                            result.finance_vendor_to_keys[vendor_lower].add(key)
    
    for txn in snapshot.planes.finance.transactions:
        vendor_name = txn.vendor_name or ""
        
        key = _extract_key_from_vendor(vendor_name)
        if key:
            result.keys_from_finance.add(key)
            if vendor_name:
                vendor_lower = vendor_name.lower().strip()
                if vendor_lower not in result.finance_vendor_to_keys:
                    result.finance_vendor_to_keys[vendor_lower] = set()
                result.finance_vendor_to_keys[vendor_lower].add(key)
        
        if txn.product:
            key = _extract_key_from_vendor(txn.product)
            if key:
                result.keys_from_finance.add(key)
    
    result.log_summary()
    
    return result
