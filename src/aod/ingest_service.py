import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from src.aod.db import execute, fetch, fetchrow
from src.aod.farm_client import farm_client
from src.aod.lifecycle import (
    route_lifecycle, derive_tech_domain, derive_system_role,
    derive_business_domain, is_shadow_it, derive_findings
)


async def reset_all_data() -> Dict[str, Any]:
    """Reset all assets and findings but preserve catalog run history."""
    await execute("DELETE FROM findings")
    await execute("DELETE FROM assets")
    return {"success": True, "message": "All assets and findings have been reset. Catalog history preserved."}


async def create_ingest_run(tenant_id: str, archetype: str, scale: str) -> str:
    run_id = str(uuid.uuid4())
    await execute("""
        INSERT INTO ingest_runs (id, tenant_id, archetype, scale, status, started_at)
        VALUES ($1, $2, $3, $4, 'running', NOW())
    """, run_id, tenant_id, archetype, scale)
    return run_id


async def update_ingest_run(run_id: str, status: str, stats: Dict[str, Any], message: str = ""):
    await execute("""
        UPDATE ingest_runs 
        SET status = $1, finished_at = NOW(), 
            total_assets = $2, shadow_it_count = $3, parked_count = $4,
            cataloged_count = $5, company_name = $6,
            findings_shadow_it = $7, findings_governance = $8, 
            findings_data_conflicts = $9, findings_ops_risk = $10, 
            findings_low_confidence = $11,
            blocking_sor_conflict = $12, blocking_schema_mismatch = $13,
            blocking_id_collision = $14, blocking_missing_id = $15,
            message = $16
        WHERE id = $17
    """, status, 
        stats.get("total", 0), stats.get("shadow", 0), stats.get("parked", 0),
        stats.get("cataloged", 0), stats.get("company_name", ""),
        stats.get("findings_shadow_it", 0), stats.get("findings_governance", 0),
        stats.get("findings_data_conflicts", 0), stats.get("findings_ops_risk", 0),
        stats.get("findings_low_confidence", 0),
        stats.get("blocking_sor_conflict", 0), stats.get("blocking_schema_mismatch", 0),
        stats.get("blocking_id_collision", 0), stats.get("blocking_missing_id", 0),
        message, run_id)


def extract_lens_coverage(surfaces: Dict[str, Any], farm_asset_id: str) -> Dict[str, bool]:
    coverage = {}
    lens_names = ["idp", "cmdb", "billing", "edr", "browser", "network", "observability", "saas_api"]
    
    for lens in lens_names:
        lens_data = surfaces.get(lens, {})
        evidence = lens_data.get("evidence", [])
        coverage[lens] = any(
            e.get("signals", {}).get("farm_asset_id") == farm_asset_id 
            for e in evidence
        )
    
    return coverage


def build_asset_from_signals(tenant_id: str, signals: Dict[str, Any], entity_hint: str, 
                             vendor_hint: str, lens_coverage: Dict[str, bool]) -> Dict[str, Any]:
    farm_asset_id = signals.get("farm_asset_id", str(uuid.uuid4()))
    
    vendor = signals.get("vendor") or vendor_hint
    owner_team = signals.get("owner_team")
    asset_kind = signals.get("asset_kind", "unknown")
    
    lifecycle_state, parked_reason = route_lifecycle(signals)
    
    shadow_flag = is_shadow_it({**signals, "lens_coverage": lens_coverage})
    
    return {
        "tenant_id": tenant_id,
        "farm_asset_id": farm_asset_id,
        "name": signals.get("asset_name") or entity_hint or f"Asset-{farm_asset_id[:8]}",
        "asset_kind": asset_kind,
        "asset_type": signals.get("catalog_asset_type", asset_kind),
        "vendor": vendor,
        "environment": signals.get("environment", "unknown"),
        "business_domain": derive_business_domain(owner_team, vendor),
        "tech_domain": derive_tech_domain(vendor, asset_kind),
        "system_role": derive_system_role(vendor),
        "owner": signals.get("owner"),
        "owner_email": signals.get("owner_email"),
        "owner_team": owner_team,
        "lifecycle_state": lifecycle_state,
        "parked_reason": parked_reason,
        "is_shadow_it": shadow_flag,
        "has_data_conflicts": signals.get("has_data_conflicts", False),
        "lens_coverage": lens_coverage,
        "metadata": {
            "rules_triggered": signals.get("rules_triggered", []),
            "conflict_types": signals.get("conflict_types", []),
            "anomaly_score": signals.get("anomaly_score"),
            "prob_kind": signals.get("prob_kind"),
            "sources": signals.get("sources", [])
        }
    }


def derive_farm_bucket(signals: Dict[str, Any], parked_reason: Optional[str] = None) -> str:
    """Derive Farm's mutually exclusive bucket classification.
    
    Priority order (mutually exclusive):
    1. shadow - if is_shadow_it is true
    2. blocking - if parked_reason exists (blocking issues)
    3. non_blocking - if has findings (data conflicts, governance gaps, ops risk, low confidence)
    4. clean - no issues
    """
    if signals.get("is_shadow_it", False):
        return "shadow"
    
    if parked_reason:
        return "blocking"
    
    has_data_conflicts = signals.get("has_data_conflicts", False)
    has_governance_gap = not signals.get("owner") or not signals.get("owner_team")
    conflict_types = signals.get("conflict_types", [])
    rules_triggered = signals.get("rules_triggered", [])
    anomaly_score = signals.get("anomaly_score", 0) or 0
    prob_kind = signals.get("prob_kind", 1.0) or 1.0
    
    has_findings = (
        has_data_conflicts or
        has_governance_gap or
        len(conflict_types) > 0 or
        len(rules_triggered) > 0 or
        anomaly_score > 0.7 or
        prob_kind < 0.8
    )
    
    if has_findings:
        return "non_blocking"
    
    return "clean"


def build_asset_from_ground_truth(tenant_id: str, signals: Dict[str, Any], entity_hint: str, 
                                   vendor_hint: str, lens_coverage: Dict[str, bool]) -> Dict[str, Any]:
    """Build asset from ground truth data which has authoritative is_shadow_it flag."""
    farm_asset_id = signals.get("farm_asset_id", str(uuid.uuid4()))
    
    vendor = signals.get("vendor") or vendor_hint
    owner_team = signals.get("owner_team")
    asset_kind = signals.get("asset_kind", "unknown")
    
    lifecycle_state, parked_reason = route_lifecycle(signals)
    
    shadow_flag = signals.get("is_shadow_it", False)
    
    farm_bucket = derive_farm_bucket(signals, parked_reason)
    
    return {
        "tenant_id": tenant_id,
        "farm_asset_id": farm_asset_id,
        "name": signals.get("asset_name") or entity_hint or f"Asset-{farm_asset_id[:8]}",
        "asset_kind": asset_kind,
        "asset_type": signals.get("catalog_asset_type", asset_kind),
        "vendor": vendor,
        "environment": signals.get("environment", "unknown"),
        "business_domain": derive_business_domain(owner_team, vendor),
        "tech_domain": derive_tech_domain(vendor, asset_kind),
        "system_role": derive_system_role(vendor),
        "owner": signals.get("owner"),
        "owner_email": signals.get("owner_email"),
        "owner_team": owner_team,
        "lifecycle_state": lifecycle_state,
        "parked_reason": parked_reason,
        "is_shadow_it": shadow_flag,
        "has_data_conflicts": signals.get("has_data_conflicts", False),
        "lens_coverage": lens_coverage,
        "farm_bucket": farm_bucket,
        "metadata": {
            "rules_triggered": signals.get("rules_triggered", []),
            "conflict_types": signals.get("conflict_types", []),
            "anomaly_score": signals.get("anomaly_score"),
            "prob_kind": signals.get("prob_kind"),
            "shadow_reasons": signals.get("shadow_reasons", []),
            "sources": signals.get("sources", [])
        }
    }


async def upsert_asset(asset: Dict[str, Any]) -> str:
    import json
    
    existing = await fetchrow("""
        SELECT id FROM assets WHERE tenant_id = $1 AND farm_asset_id = $2
    """, asset["tenant_id"], asset["farm_asset_id"])
    
    if existing:
        asset_id = str(existing["id"])
        await execute("""
            UPDATE assets SET
                name = $1, asset_kind = $2, asset_type = $3, vendor = $4,
                environment = $5, business_domain = $6, tech_domain = $7,
                system_role = $8, owner = $9, owner_email = $10, owner_team = $11,
                lifecycle_state = $12, parked_reason = $13, is_shadow_it = $14,
                has_data_conflicts = $15, lens_coverage = $16, metadata = $17,
                farm_bucket = $18, updated_at = NOW()
            WHERE id = $19
        """, asset["name"], asset["asset_kind"], asset["asset_type"], asset["vendor"],
            asset["environment"], asset["business_domain"], asset["tech_domain"],
            asset["system_role"], asset["owner"], asset["owner_email"], asset["owner_team"],
            asset["lifecycle_state"], asset["parked_reason"], asset["is_shadow_it"],
            asset["has_data_conflicts"], json.dumps(asset["lens_coverage"]), 
            json.dumps(asset["metadata"]), asset.get("farm_bucket"), asset_id)
    else:
        asset_id = str(uuid.uuid4())
        await execute("""
            INSERT INTO assets (id, tenant_id, farm_asset_id, name, asset_kind, asset_type,
                vendor, environment, business_domain, tech_domain, system_role,
                owner, owner_email, owner_team, lifecycle_state, parked_reason,
                is_shadow_it, has_data_conflicts, lens_coverage, metadata, farm_bucket)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21)
        """, asset_id, asset["tenant_id"], asset["farm_asset_id"], asset["name"],
            asset["asset_kind"], asset["asset_type"], asset["vendor"], asset["environment"],
            asset["business_domain"], asset["tech_domain"], asset["system_role"],
            asset["owner"], asset["owner_email"], asset["owner_team"],
            asset["lifecycle_state"], asset["parked_reason"], asset["is_shadow_it"],
            asset["has_data_conflicts"], json.dumps(asset["lens_coverage"]), 
            json.dumps(asset["metadata"]), asset.get("farm_bucket"))
    
    return asset_id


async def save_findings(asset_id: str, findings: List[Dict[str, Any]]):
    import json
    
    await execute("DELETE FROM findings WHERE asset_id = $1", asset_id)
    
    for finding in findings:
        await execute("""
            INSERT INTO findings (id, asset_id, finding_type, rule_id, severity, status, description, evidence)
            VALUES ($1, $2, $3, $4, $5, 'open', $6, $7)
        """, str(uuid.uuid4()), asset_id, finding["finding_type"], finding.get("rule_id"),
            finding["severity"], finding["description"], json.dumps(finding.get("evidence", {})))


async def ingest_full_pull(archetype: str, scale: str) -> Dict[str, Any]:
    try:
        snapshot = await farm_client.create_enterprise(archetype, scale)
    except Exception as e:
        return {"success": False, "error": f"Failed to fetch from Farm: {str(e)}"}
    
    tenant_id = snapshot.get("tenant_id")
    if not tenant_id:
        return {"success": False, "error": "No tenant_id in Farm response"}
    
    run_id = await create_ingest_run(tenant_id, archetype, scale)
    
    try:
        ground_truth = await farm_client.get_ground_truth(tenant_id)
        expected_assets = ground_truth.get("ground_truth", {}).get("expected_assets", [])
        
        surfaces = snapshot.get("surfaces", {})
        
        cmdb_signals_map = {}
        cmdb_data = surfaces.get("cmdb", {})
        for record in cmdb_data.get("evidence", []):
            signals = record.get("signals", {})
            farm_asset_id = signals.get("farm_asset_id")
            if farm_asset_id:
                cmdb_signals_map[farm_asset_id] = {
                    "signals": signals,
                    "entity_hint": record.get("entity_hint", ""),
                    "vendor_hint": record.get("vendor_hint", "")
                }
        
        stats = {
            "total": 0, "shadow": 0, "parked": 0, "cataloged": 0,
            "company_name": snapshot.get("company_name", ""),
            "findings_shadow_it": 0, "findings_governance": 0,
            "findings_data_conflicts": 0, "findings_ops_risk": 0,
            "findings_low_confidence": 0,
            "blocking_sor_conflict": 0, "blocking_schema_mismatch": 0,
            "blocking_id_collision": 0, "blocking_missing_id": 0
        }
        
        for gt_asset in expected_assets:
            farm_asset_id = gt_asset.get("farm_asset_id")
            if not farm_asset_id:
                continue
            
            lens_coverage = extract_lens_coverage(surfaces, farm_asset_id)
            
            cmdb_info = cmdb_signals_map.get(farm_asset_id, {})
            cmdb_signals = cmdb_info.get("signals", {})
            
            signals = {
                "farm_asset_id": farm_asset_id,
                "asset_name": gt_asset.get("asset_name"),
                "asset_kind": gt_asset.get("asset_kind"),
                "catalog_asset_type": gt_asset.get("catalog_asset_type"),
                "vendor": gt_asset.get("vendor"),
                "environment": gt_asset.get("environment"),
                "owner": gt_asset.get("owner"),
                "owner_email": gt_asset.get("owner_email"),
                "owner_team": gt_asset.get("owner_team"),
                "is_shadow_it": gt_asset.get("is_shadow_it", False),
                "has_data_conflicts": cmdb_signals.get("has_data_conflicts", False) or gt_asset.get("has_data_conflicts", False),
                "conflict_types": cmdb_signals.get("conflict_types", []) or gt_asset.get("conflict_types", []),
                "rules_triggered": cmdb_signals.get("rules_triggered", []) or gt_asset.get("rules_triggered", []),
                "parked_reason": cmdb_signals.get("parked_reason") or gt_asset.get("parked_reason"),
                "anomaly_score": cmdb_signals.get("anomaly_score", 0),
                "prob_kind": cmdb_signals.get("prob_kind", 1.0),
                "shadow_reasons": gt_asset.get("shadow_reasons", []),
            }
            
            entity_hint = cmdb_info.get("entity_hint") or gt_asset.get("asset_name", "")
            vendor_hint = cmdb_info.get("vendor_hint") or gt_asset.get("vendor", "")
            
            asset_data = build_asset_from_ground_truth(
                tenant_id, signals, entity_hint, vendor_hint, lens_coverage
            )
            
            asset_id = await upsert_asset(asset_data)
            
            findings = derive_findings(asset_data, signals)
            await save_findings(asset_id, findings)
            
            stats["total"] += 1
            if asset_data["is_shadow_it"]:
                stats["shadow"] += 1
            if asset_data["lifecycle_state"] == "PARKED":
                stats["parked"] += 1
                pr = asset_data.get("parked_reason", "")
                if pr == "SoR Conflict":
                    stats["blocking_sor_conflict"] += 1
                elif pr == "Schema Mismatch":
                    stats["blocking_schema_mismatch"] += 1
                elif pr == "ID Collision":
                    stats["blocking_id_collision"] += 1
                elif pr == "Missing ID":
                    stats["blocking_missing_id"] += 1
            else:
                stats["cataloged"] += 1
            
            for f in findings:
                ft = f.get("finding_type", "")
                if ft == "shadow_it":
                    stats["findings_shadow_it"] += 1
                elif ft == "governance_gap":
                    stats["findings_governance"] += 1
                elif ft == "data_conflicts":
                    stats["findings_data_conflicts"] += 1
                elif ft == "ops_risk":
                    stats["findings_ops_risk"] += 1
                elif ft == "low_confidence":
                    stats["findings_low_confidence"] += 1
        
        await update_ingest_run(run_id, "success", stats)
        
        return {
            "success": True,
            "tenant_id": tenant_id,
            "run_id": run_id,
            "total_assets": stats["total"],
            "shadow_it_count": stats["shadow"],
            "parked_count": stats["parked"],
            "cataloged_count": stats["cataloged"],
            "company_name": stats["company_name"],
            "archetype": archetype,
            "scale": scale
        }
        
    except Exception as e:
        await update_ingest_run(run_id, "failed", {"company_name": ""}, str(e))
        return {"success": False, "error": str(e), "run_id": run_id}
