"""
Convert AOD discovery output to EAV triples for the DCL triple store.

This module takes AOD's pipeline output (assets, findings, fabric planes)
and produces a list of triple dicts matching the semantic_triples schema.
Each property of each business object becomes one triple row.

Pure conversion logic — no DB calls, no I/O, no side effects.
"""

import logging
from typing import Any

from ..models.output_contracts import Asset, Finding, Confidence

logger = logging.getLogger(__name__)

# Governance status mapping: ProvisioningStatus → human-readable governance label
_GOVERNANCE_MAP = {
    "active": "governed",
    "review": "zombie",
    "quarantine": "shadow",
    "blocked": "blocked",
    "retired": "retired",
    "ignored": "ignored",
}

# Confidence enum → numeric score mapping
_CONFIDENCE_SCORES = {
    Confidence.HIGH: 0.9,
    Confidence.MED: 0.7,
    Confidence.LOW: 0.4,
}

# Confidence score → tier mapping
_TIER_THRESHOLDS = (
    (0.75, "high"),
    (0.50, "medium"),
    (0.0, "low"),
)


def _score_to_tier(score: float) -> str:
    """Convert a numeric confidence score to a tier label."""
    for threshold, tier in _TIER_THRESHOLDS:
        if score >= threshold:
            return tier
    return "low"


def _make_triple(
    entity_id: str,
    tenant_id: str,
    run_id: str,
    concept: str,
    prop: str,
    value: Any,
    source_field: str,
    confidence_score: float,
    confidence_tier: str,
    canonical_id: str,
    source_table: str,
) -> dict | None:
    """Build a single triple dict. Returns None if value is empty/None."""
    if value is None:
        return None
    str_value = str(value)
    if str_value == "":
        return None

    return {
        "tenant_id": tenant_id,
        "entity_id": entity_id,
        "concept": concept,
        "property": prop,
        "value": value,
        "period": None,
        "currency": None,
        "unit": None,
        "source_system": "AOD",
        "source_table": source_table,
        "source_field": source_field,
        "pipe_id": None,
        "run_id": run_id,
        "source_run_tag": None,
        "confidence_score": confidence_score,
        "confidence_tier": confidence_tier,
        "canonical_id": canonical_id,
        "resolution_method": None,
        "resolution_confidence": None,
    }


def _convert_asset(
    asset: Asset,
    entity_id: str,
    tenant_id: str,
    run_id: str,
) -> list[dict]:
    """Convert one asset to discovery.asset triples (up to 8 properties)."""
    canonical_id = str(asset.asset_id)

    # Confidence from SOR scoring if available, else medium default
    if asset.sor_tagging and asset.sor_tagging.confidence is not None:
        conf_score = asset.sor_tagging.confidence
    else:
        conf_score = 0.5
    conf_tier = _score_to_tier(conf_score)

    properties = {
        "vendor": asset.vendor,
        "category": asset.asset_type.value if asset.asset_type else None,
        "system_type": asset.asset_type.value if asset.asset_type else None,
        "name": asset.name,
        "connection_status": asset.provisioning_status.value if asset.provisioning_status else None,
        "in_cmdb": asset.lens_coverage.cmdb,
        "in_finance": asset.lens_coverage.finance,
        "in_idp": asset.lens_coverage.idp,
    }

    triples = []
    for prop_name, prop_value in properties.items():
        t = _make_triple(
            entity_id=entity_id,
            tenant_id=tenant_id,
            run_id=run_id,
            concept="discovery.asset",
            prop=prop_name,
            value=prop_value,
            source_field=prop_name,
            confidence_score=conf_score,
            confidence_tier=conf_tier,
            canonical_id=canonical_id,
            source_table="assets",
        )
        if t is not None:
            triples.append(t)

    return triples


def _convert_governance(
    asset: Asset,
    entity_id: str,
    tenant_id: str,
    run_id: str,
) -> list[dict]:
    """Convert one asset's governance classification to discovery.governance triples."""
    canonical_id = str(asset.asset_id)
    prov_status = asset.provisioning_status.value if asset.provisioning_status else "quarantine"
    governance_status = _GOVERNANCE_MAP.get(prov_status, prov_status)

    # Classification basis from admission_reason or status name
    classification_basis = asset.admission_reason if asset.admission_reason else prov_status

    # Governance is deterministic — always high confidence
    triples = []
    for prop_name, prop_value in [
        ("governance_status", governance_status),
        ("classification_basis", classification_basis),
    ]:
        t = _make_triple(
            entity_id=entity_id,
            tenant_id=tenant_id,
            run_id=run_id,
            concept="discovery.governance",
            prop=prop_name,
            value=prop_value,
            source_field=prop_name,
            confidence_score=0.95,
            confidence_tier="high",
            canonical_id=canonical_id,
            source_table="assets",
        )
        if t is not None:
            triples.append(t)

    return triples


def _convert_sor(
    asset: Asset,
    entity_id: str,
    tenant_id: str,
    run_id: str,
) -> list[dict]:
    """Convert one asset's SOR tagging to discovery.sor triples."""
    if not asset.sor_tagging:
        return []
    if asset.sor_tagging.likelihood == "none":
        return []

    canonical_id = str(asset.asset_id)
    sor = asset.sor_tagging
    conf_score = sor.confidence
    conf_tier = _score_to_tier(conf_score)

    properties = {
        "sor_score": sor.confidence,
        "sor_rank": sor.likelihood,
        "is_system_of_record": sor.likelihood == "high",
    }

    triples = []
    for prop_name, prop_value in properties.items():
        t = _make_triple(
            entity_id=entity_id,
            tenant_id=tenant_id,
            run_id=run_id,
            concept="discovery.sor",
            prop=prop_name,
            value=prop_value,
            source_field=prop_name,
            confidence_score=conf_score,
            confidence_tier=conf_tier,
            canonical_id=canonical_id,
            source_table="assets",
        )
        if t is not None:
            triples.append(t)

    return triples


def _convert_finding(
    finding: Finding,
    entity_id: str,
    tenant_id: str,
    run_id: str,
) -> list[dict]:
    """Convert one finding to discovery.finding triples."""
    canonical_id = str(finding.finding_id)
    conf_score = _CONFIDENCE_SCORES.get(finding.confidence, 0.7)
    conf_tier = _score_to_tier(conf_score)

    affected_asset = str(finding.asset_id) if finding.asset_id else "unknown"

    properties = {
        "finding_type": finding.finding_type.value,
        "severity": finding.severity.value,
        "affected_asset": affected_asset,
        "description": finding.explanation,
    }

    triples = []
    for prop_name, prop_value in properties.items():
        t = _make_triple(
            entity_id=entity_id,
            tenant_id=tenant_id,
            run_id=run_id,
            concept="discovery.finding",
            prop=prop_name,
            value=prop_value,
            source_field=prop_name,
            confidence_score=conf_score,
            confidence_tier=conf_tier,
            canonical_id=canonical_id,
            source_table="findings",
        )
        if t is not None:
            triples.append(t)

    return triples


def _convert_fabric_plane(
    plane: dict,
    entity_id: str,
    tenant_id: str,
    run_id: str,
) -> list[dict]:
    """Convert one fabric plane registry entry to discovery.fabric_plane triples."""
    plane_type = plane.get("plane_type")
    product = plane.get("product")
    canonical_id = f"{plane_type}_{product}" if plane_type and product else str(plane_type)

    # Confidence from the entry, or derive from detection evidence count
    conf_score = plane.get("confidence")
    if conf_score is None:
        evidence = plane.get("detection_evidence", [])
        conf_score = min(len(evidence) / 5.0, 1.0) if evidence else 0.5
    conf_tier = _score_to_tier(conf_score)

    # Instance is domain or endpoint
    instance = plane.get("domain") or plane.get("endpoint")

    properties = {
        "plane_type": plane_type,
        "vendor": product,
        "instance": instance,
        "is_shadow": plane.get("is_shadow"),
    }

    triples = []
    for prop_name, prop_value in properties.items():
        t = _make_triple(
            entity_id=entity_id,
            tenant_id=tenant_id,
            run_id=run_id,
            concept="discovery.fabric_plane",
            prop=prop_name,
            value=prop_value,
            source_field=prop_name,
            confidence_score=conf_score,
            confidence_tier=conf_tier,
            canonical_id=canonical_id,
            source_table="fabric_plane_registry",
        )
        if t is not None:
            triples.append(t)

    return triples


def convert_discovery_to_triples(
    assets: list[Asset],
    findings: list[Finding],
    fabric_plane_registry: list[dict],
    entity_id: str,
    tenant_id: str,
    run_id: str,
) -> list[dict]:
    """Convert AOD discovery output to EAV triples.

    Each property of each business object becomes one triple row.
    Skips properties with None or empty string values.

    Args:
        assets: Admitted assets from the pipeline.
        findings: Generated findings from the pipeline.
        fabric_plane_registry: Fabric plane registry entries (dicts from input_meta).
        entity_id: Business entity identifier (required, not hardcoded).
        tenant_id: Platform tenant identifier.
        run_id: Discovery scan run identifier.

    Returns:
        List of triple dicts matching the semantic_triples 19-column schema.
    """
    triples: list[dict] = []

    for asset in assets:
        triples.extend(_convert_asset(asset, entity_id, tenant_id, run_id))
        triples.extend(_convert_governance(asset, entity_id, tenant_id, run_id))
        triples.extend(_convert_sor(asset, entity_id, tenant_id, run_id))

    for finding in findings:
        triples.extend(_convert_finding(finding, entity_id, tenant_id, run_id))

    for plane in fabric_plane_registry:
        triples.extend(_convert_fabric_plane(plane, entity_id, tenant_id, run_id))

    logger.info(
        "triple_converter.converted",
        extra={
            "run_id": run_id,
            "entity_id": entity_id,
            "asset_count": len(assets),
            "finding_count": len(findings),
            "fabric_plane_count": len(fabric_plane_registry),
            "triple_count": len(triples),
        },
    )

    return triples
