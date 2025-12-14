"""
Derived Classifications Module

Computes Shadow and Zombie classifications from evidence AFTER the main pipeline.
These are computed on-read, not stored as flags.

Shadow Asset = admitted asset with:
  - finance evidence OR cloud presence OR discovery observations
  - AND no IdP match (no SSO / SCIM / service principal)
  - AND no CMDB match

Zombie Asset = admitted asset with:
  - CMDB or IdP presence
  - AND no discovery observations or activity evidence
"""

from dataclasses import dataclass
from typing import Optional
from ..models.output_contracts import Asset, LensStatus


@dataclass
class ClassificationResult:
    """Result of a derived classification check"""
    is_classified: bool
    classification_type: str
    reason: str
    evidence_summary: list[str]


@dataclass
class DerivedClassificationSummary:
    """Summary of derived classifications for a run"""
    shadow_count: int
    zombie_count: int
    indeterminate_count: int
    shadow_assets: list[dict]
    zombie_assets: list[dict]


def classify_shadow(asset: Asset) -> ClassificationResult:
    """
    Determine if an asset is a Shadow Asset.
    
    Shadow = has evidence of existence (finance, cloud, or observations)
             but is NOT in identity systems and NOT in CMDB
    
    Interpretation: "We know this software is used, but it's not being
    managed through official channels."
    """
    has_idp = asset.lens_status.idp == LensStatus.MATCHED
    has_cmdb = asset.lens_status.cmdb == LensStatus.MATCHED
    has_finance = asset.lens_coverage.finance
    has_cloud = asset.lens_coverage.cloud
    has_discovery = len(asset.evidence_refs) > 0
    
    if has_idp or has_cmdb:
        return ClassificationResult(
            is_classified=False,
            classification_type="shadow",
            reason="Asset has IdP or CMDB presence - not shadow",
            evidence_summary=[]
        )
    
    presence_sources = []
    if has_finance:
        presence_sources.append("finance evidence (spending/contracts)")
    if has_cloud:
        presence_sources.append("cloud infrastructure")
    if has_discovery:
        presence_sources.append(f"discovery observations ({len(asset.evidence_refs)} refs)")
    
    if not presence_sources:
        return ClassificationResult(
            is_classified=False,
            classification_type="shadow",
            reason="No evidence of presence - indeterminate",
            evidence_summary=[]
        )
    
    gaps = []
    gaps.append("No IdP match (not in SSO/SCIM/identity systems)")
    gaps.append("No CMDB match (not in configuration management)")
    
    return ClassificationResult(
        is_classified=True,
        classification_type="shadow",
        reason=f"Shadow IT: Found via {', '.join(presence_sources)} but missing from official systems",
        evidence_summary=[
            f"Presence: {', '.join(presence_sources)}",
            f"Gaps: {'; '.join(gaps)}"
        ]
    )


def classify_zombie(asset: Asset) -> ClassificationResult:
    """
    Determine if an asset is a Zombie Asset.
    
    Zombie = exists in CMDB or IdP (official records)
             but has NO discovery observations or activity evidence
    
    Interpretation: "This is in our official systems but we have no
    evidence anyone is actually using it."
    """
    has_idp = asset.lens_status.idp == LensStatus.MATCHED
    has_cmdb = asset.lens_status.cmdb == LensStatus.MATCHED
    has_discovery = len(asset.evidence_refs) > 0
    has_finance = asset.lens_coverage.finance
    has_cloud = asset.lens_coverage.cloud
    
    if not (has_idp or has_cmdb):
        return ClassificationResult(
            is_classified=False,
            classification_type="zombie",
            reason="Asset not in CMDB or IdP - cannot be zombie",
            evidence_summary=[]
        )
    
    has_activity = has_discovery or has_finance or has_cloud
    
    if has_activity:
        activity_sources = []
        if has_discovery:
            activity_sources.append(f"discovery observations ({len(asset.evidence_refs)} refs)")
        if has_finance:
            activity_sources.append("finance activity")
        if has_cloud:
            activity_sources.append("cloud activity")
        
        return ClassificationResult(
            is_classified=False,
            classification_type="zombie",
            reason=f"Asset has activity evidence: {', '.join(activity_sources)}",
            evidence_summary=[]
        )
    
    official_presence = []
    if has_idp:
        official_presence.append("IdP/identity systems")
    if has_cmdb:
        official_presence.append("CMDB")
    
    return ClassificationResult(
        is_classified=True,
        classification_type="zombie",
        reason=f"Zombie: Exists in {', '.join(official_presence)} but no activity evidence",
        evidence_summary=[
            f"Official presence: {', '.join(official_presence)}",
            "No discovery observations",
            "No finance activity",
            "No cloud activity"
        ]
    )


def compute_derived_classifications(assets: list[Asset]) -> DerivedClassificationSummary:
    """
    Compute derived classifications for all assets.
    
    Returns summary with counts and detailed lists.
    """
    shadow_assets = []
    zombie_assets = []
    indeterminate_count = 0
    
    for asset in assets:
        shadow_result = classify_shadow(asset)
        zombie_result = classify_zombie(asset)
        
        if shadow_result.is_classified:
            shadow_assets.append({
                "asset_id": str(asset.asset_id),
                "name": asset.name,
                "vendor": asset.vendor,
                "asset_type": asset.asset_type.value,
                "environment": asset.environment.value,
                "classification": "shadow",
                "reason": shadow_result.reason,
                "evidence_summary": shadow_result.evidence_summary,
                "lens_status": {
                    "idp": asset.lens_status.idp.value,
                    "cmdb": asset.lens_status.cmdb.value,
                    "cloud": asset.lens_status.cloud.value,
                    "finance": asset.lens_status.finance.value
                },
                "lens_coverage": {
                    "idp": asset.lens_coverage.idp,
                    "cmdb": asset.lens_coverage.cmdb,
                    "cloud": asset.lens_coverage.cloud,
                    "finance": asset.lens_coverage.finance
                }
            })
        elif zombie_result.is_classified:
            zombie_assets.append({
                "asset_id": str(asset.asset_id),
                "name": asset.name,
                "vendor": asset.vendor,
                "asset_type": asset.asset_type.value,
                "environment": asset.environment.value,
                "classification": "zombie",
                "reason": zombie_result.reason,
                "evidence_summary": zombie_result.evidence_summary,
                "lens_status": {
                    "idp": asset.lens_status.idp.value,
                    "cmdb": asset.lens_status.cmdb.value,
                    "cloud": asset.lens_status.cloud.value,
                    "finance": asset.lens_status.finance.value
                },
                "lens_coverage": {
                    "idp": asset.lens_coverage.idp,
                    "cmdb": asset.lens_coverage.cmdb,
                    "cloud": asset.lens_coverage.cloud,
                    "finance": asset.lens_coverage.finance
                }
            })
        else:
            pass
    
    return DerivedClassificationSummary(
        shadow_count=len(shadow_assets),
        zombie_count=len(zombie_assets),
        indeterminate_count=indeterminate_count,
        shadow_assets=shadow_assets,
        zombie_assets=zombie_assets
    )
