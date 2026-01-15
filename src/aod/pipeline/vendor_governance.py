"""
Vendor Governance Propagation

Stage 3: Farm-style vendor governance propagation.

Propagates governance signals (IdP, CMDB presence) across assets sharing the same vendor domain set.
Only seeds from AUTHORITATIVE matches that pass gates (lens_coverage.idp=True OR lens_coverage.cmdb=True).

Key Rules:
1. Seed a vendor as governed if any asset in that vendor's domain set has:
   - cmdb_present == True (gate-passed authoritative match), OR
   - idp_present == True (gate-passed authoritative match)
2. Propagate: For any asset whose registered domain maps to a seeded vendor, set vendor_governed=True
3. Governance becomes: is_governed = cmdb_present OR idp_present OR vendor_governed
4. Guardrails:
   - Vendor propagation does NOT add domains
   - Does NOT seed from heuristic "matched" (lens_status.MATCHED alone is insufficient)
   - Is fully traceable via vendor_governance_trace (vendor, seed_domain, seed_asset_id)

Example:
- outlook.com has IdP match (SSO enabled) -> lens_coverage.idp=True
- office.com/sharepoint.com map to same vendor "Microsoft" but no direct IdP match
- After propagation, office.com/sharepoint.com get vendor_governed=True
"""

from dataclasses import dataclass
from typing import Optional
import logging

from .correlate_entities import CorrelationResult, MatchStatus
from .normalize_observations import CandidateEntity
from .vendor_inference import (
    infer_vendor_from_domain, 
    DOMAIN_TO_VENDOR, 
    VENDOR_DOMAIN_SETS,
    extract_registered_domain
)
from ..models.output_contracts import Asset, VendorGovernanceTrace

logger = logging.getLogger(__name__)


@dataclass
class PropagatedGovernance:
    """Governance signals propagated from vendor siblings.

    Includes metadata fields so policy engine can evaluate strict requirements.
    """
    idp_present: bool = False
    cmdb_present: bool = False
    source_entity: Optional[str] = None
    propagation_reason: Optional[str] = None
    # IdP metadata (for policy engine strict requirements)
    has_sso: bool = False
    has_scim: bool = False
    idp_type: Optional[str] = None
    # CMDB metadata (for policy engine strict requirements)
    ci_type: Optional[str] = None
    lifecycle: Optional[str] = None


def get_effective_vendor(entity: CandidateEntity) -> Optional[str]:
    """Get vendor from entity or infer from domain."""
    if entity.vendor:
        return entity.vendor.lower().strip()
    
    if entity.domain:
        domain = entity.domain.lower().strip()
        if domain in DOMAIN_TO_VENDOR:
            return DOMAIN_TO_VENDOR[domain].lower()
        
        hypothesis = infer_vendor_from_domain(domain)
        if hypothesis:
            return hypothesis.value.lower()
    
    return None


def propagate_vendor_governance(
    correlations: list[CorrelationResult]
) -> dict[str, PropagatedGovernance]:
    """
    Propagate governance across entities sharing the same vendor.
    
    Returns dict mapping entity_id -> PropagatedGovernance
    """
    vendor_to_entities: dict[str, list[CorrelationResult]] = {}
    
    for corr in correlations:
        vendor = get_effective_vendor(corr.entity)
        if vendor:
            if vendor not in vendor_to_entities:
                vendor_to_entities[vendor] = []
            vendor_to_entities[vendor].append(corr)
    
    propagated: dict[str, PropagatedGovernance] = {}
    
    for vendor, vendor_correlations in vendor_to_entities.items():
        idp_source: Optional[CorrelationResult] = None
        cmdb_source: Optional[CorrelationResult] = None

        for corr in vendor_correlations:
            if corr.idp.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
                if idp_source is None:
                    idp_source = corr
            if corr.cmdb.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS):
                if cmdb_source is None:
                    cmdb_source = corr

        if idp_source or cmdb_source:
            for corr in vendor_correlations:
                has_direct_idp = corr.idp.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS)
                has_direct_cmdb = corr.cmdb.status in (MatchStatus.MATCHED, MatchStatus.AMBIGUOUS)

                needs_idp = not has_direct_idp and idp_source is not None
                needs_cmdb = not has_direct_cmdb and cmdb_source is not None

                if needs_idp or needs_cmdb:
                    reasons = []
                    source_name = None

                    # Jan 2026: Extract metadata from source records for policy engine
                    has_sso = False
                    has_scim = False
                    idp_type = None
                    ci_type = None
                    lifecycle = None

                    if needs_idp and idp_source and idp_source.idp.matched_records:
                        reasons.append(f"IdP from {idp_source.entity.original_name}")
                        source_name = idp_source.entity.original_name
                        # Extract IdP metadata from first matched record
                        idp_record = idp_source.idp.matched_records[0]
                        has_sso = getattr(idp_record, 'has_sso', False)
                        has_scim = getattr(idp_record, 'has_scim', False)
                        idp_type = getattr(idp_record, 'idp_type', None)

                    if needs_cmdb and cmdb_source and cmdb_source.cmdb.matched_records:
                        reasons.append(f"CMDB from {cmdb_source.entity.original_name}")
                        source_name = source_name or cmdb_source.entity.original_name
                        # Extract CMDB metadata from first matched record
                        cmdb_record = cmdb_source.cmdb.matched_records[0]
                        ci_type = getattr(cmdb_record, 'ci_type', None)
                        lifecycle = getattr(cmdb_record, 'lifecycle', None)

                    propagated[corr.entity.entity_id] = PropagatedGovernance(
                        idp_present=needs_idp or has_direct_idp,
                        cmdb_present=needs_cmdb or has_direct_cmdb,
                        source_entity=source_name,
                        propagation_reason=f"Vendor '{vendor}': " + ", ".join(reasons),
                        has_sso=has_sso,
                        has_scim=has_scim,
                        idp_type=idp_type,
                        ci_type=ci_type,
                        lifecycle=lifecycle
                    )
    
    return propagated


@dataclass
class VendorSeed:
    """Seed info for vendor governance propagation."""
    vendor: str
    seed_domain: str
    seed_asset_id: str
    source: str  # "idp" or "cmdb" or "both"


def propagate_vendor_governance_farm_style(
    assets: list[Asset],
    run_logger: Optional[logging.Logger] = None
) -> list[Asset]:
    """
    Stage 3: Farm-style vendor governance propagation.
    
    Propagates governance across assets sharing the same vendor domain set.
    Only seeds from AUTHORITATIVE matches that pass gates:
    - lens_coverage.idp=True (not just lens_status.MATCHED)
    - lens_coverage.cmdb=True (not just lens_status.MATCHED)
    
    Guardrails:
    - Does NOT add domains to assets
    - Does NOT seed from heuristic matches
    - Is fully traceable via vendor_governance_trace
    
    Args:
        assets: List of assets to process
        run_logger: Optional logger for propagation events
        
    Returns:
        List of assets with vendor_governed field updated where applicable
    """
    if not assets:
        return assets
    
    log = run_logger or logger
    
    # Step 1: Find governed vendors - seed only from authoritative gate-passed matches
    vendor_seeds: dict[str, VendorSeed] = {}
    
    for asset in assets:
        # Check for authoritative governance (lens_coverage, not lens_status)
        has_idp = asset.lens_coverage.idp if asset.lens_coverage else False
        has_cmdb = asset.lens_coverage.cmdb if asset.lens_coverage else False
        
        if not (has_idp or has_cmdb):
            continue
        
        # Check each domain in identifiers.domains for vendor mapping
        if not asset.identifiers or not asset.identifiers.domains:
            continue
        
        for domain in asset.identifiers.domains:
            if not domain:
                continue
            
            registered = extract_registered_domain(domain)
            if not registered:
                continue
            
            # Check if domain maps to a vendor
            vendor = DOMAIN_TO_VENDOR.get(registered.lower())
            if not vendor:
                continue
            
            vendor_key = vendor.lower().strip()
            
            # Record the seed (first one wins for each vendor)
            if vendor_key not in vendor_seeds:
                source = "both" if (has_idp and has_cmdb) else ("idp" if has_idp else "cmdb")
                vendor_seeds[vendor_key] = VendorSeed(
                    vendor=vendor,
                    seed_domain=registered,
                    seed_asset_id=str(asset.asset_id),
                    source=source
                )
                log.info("vendor_governance.seed", extra={
                    "vendor": vendor,
                    "seed_domain": registered,
                    "seed_asset_id": str(asset.asset_id),
                    "source": source
                })
    
    if not vendor_seeds:
        log.info("vendor_governance.no_seeds", extra={
            "asset_count": len(assets),
            "message": "No vendors seeded for governance propagation"
        })
        return assets
    
    # Step 2: Propagate governance to assets with matching vendor domains
    propagation_count = 0
    result_assets: list[Asset] = []
    
    for asset in assets:
        # Skip if already directly governed (no need to propagate)
        has_idp = asset.lens_coverage.idp if asset.lens_coverage else False
        has_cmdb = asset.lens_coverage.cmdb if asset.lens_coverage else False
        
        if has_idp or has_cmdb:
            result_assets.append(asset)
            continue
        
        # Check if any domain maps to a seeded vendor
        matching_seed: Optional[VendorSeed] = None
        matching_domain: Optional[str] = None
        
        if asset.identifiers and asset.identifiers.domains:
            for domain in asset.identifiers.domains:
                if not domain:
                    continue
                
                registered = extract_registered_domain(domain)
                if not registered:
                    continue
                
                vendor = DOMAIN_TO_VENDOR.get(registered.lower())
                if not vendor:
                    continue
                
                vendor_key = vendor.lower().strip()
                if vendor_key in vendor_seeds:
                    matching_seed = vendor_seeds[vendor_key]
                    matching_domain = registered
                    break
        
        if matching_seed:
            # Create updated asset with vendor_governed=True and trace info
            updated_coverage = asset.lens_coverage.model_copy() if asset.lens_coverage else None
            if updated_coverage:
                updated_coverage.vendor_governed = True
            
            trace = VendorGovernanceTrace(
                vendor=matching_seed.vendor,
                seed_domain=matching_seed.seed_domain,
                seed_asset_id=matching_seed.seed_asset_id
            )
            
            # Create new asset with propagated governance
            updated_asset = asset.model_copy(update={
                "lens_coverage": updated_coverage,
                "vendor_governance_trace": trace
            })
            
            result_assets.append(updated_asset)
            propagation_count += 1
            
            log.info("vendor_governance.propagate", extra={
                "asset_id": str(asset.asset_id),
                "asset_domain": matching_domain,
                "vendor": matching_seed.vendor,
                "seed_domain": matching_seed.seed_domain,
                "seed_asset_id": matching_seed.seed_asset_id
            })
        else:
            result_assets.append(asset)
    
    if propagation_count > 0:
        log.info("vendor_governance.summary", extra={
            "input_assets": len(assets),
            "vendors_seeded": len(vendor_seeds),
            "assets_propagated": propagation_count
        })
    
    return result_assets
