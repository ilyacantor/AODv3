from typing import Dict, Any, List
from src.aod.db import fetch, fetchrow, fetchval


async def get_lifecycle_counts() -> Dict[str, int]:
    """
    Get lifecycle counts. DISCOVERED = total assets (all states combined).
    In V1 full-pull mode, assets go directly to PARKED or CATALOGED.
    """
    rows = await fetch("""
        SELECT lifecycle_state, COUNT(*) as count
        FROM assets
        GROUP BY lifecycle_state
    """)
    
    counts = {"PARKED": 0, "CATALOGED": 0}
    total = 0
    for row in rows:
        state = row["lifecycle_state"]
        count = row["count"]
        if state in counts:
            counts[state] = count
        total += count
    
    counts["DISCOVERED"] = total
    
    return counts


async def get_blocking_summary() -> Dict[str, int]:
    rows = await fetch("""
        SELECT parked_reason, COUNT(*) as count
        FROM assets
        WHERE lifecycle_state = 'PARKED' AND parked_reason IS NOT NULL
        GROUP BY parked_reason
    """)
    
    summary = {
        "SoR Conflict": 0,
        "Schema Mismatch": 0,
        "ID Collision": 0,
        "Missing ID": 0
    }
    
    for row in rows:
        reason = row["parked_reason"]
        if reason in summary:
            summary[reason] = row["count"]
    
    return summary


async def get_findings_summary() -> Dict[str, int]:
    rows = await fetch("""
        SELECT f.finding_type, COUNT(DISTINCT f.asset_id) as count
        FROM findings f
        JOIN assets a ON f.asset_id = a.id
        WHERE a.lifecycle_state = 'CATALOGED' AND f.status = 'open'
        GROUP BY f.finding_type
    """)
    
    summary = {
        "shadow_it": 0,
        "governance_gap": 0,
        "data_conflicts": 0,
        "ops_risk": 0,
        "low_confidence": 0
    }
    
    for row in rows:
        finding_type = row["finding_type"]
        if finding_type in summary:
            summary[finding_type] = row["count"]
    
    return summary


async def get_inventory_by_field(field: str) -> List[Dict[str, Any]]:
    valid_fields = ["vendor", "asset_kind", "tech_domain", "business_domain"]
    if field not in valid_fields:
        return []
    
    rows = await fetch(f"""
        SELECT {field} as label, COUNT(*) as count
        FROM assets
        WHERE lifecycle_state = 'CATALOGED' AND {field} IS NOT NULL AND {field} != ''
        GROUP BY {field}
        ORDER BY count DESC
        LIMIT 10
    """)
    
    return [{"label": row["label"] or "Unknown", "count": row["count"]} for row in rows]


async def get_shadow_it_breakdown(field: str) -> List[Dict[str, Any]]:
    valid_fields = ["tech_domain", "business_domain"]
    if field not in valid_fields:
        return []
    
    rows = await fetch(f"""
        SELECT {field} as label, COUNT(*) as count
        FROM assets
        WHERE is_shadow_it = true AND {field} IS NOT NULL AND {field} != ''
        GROUP BY {field}
        ORDER BY count DESC
        LIMIT 10
    """)
    
    return [{"label": row["label"] or "Unknown", "count": row["count"]} for row in rows]


async def get_dashboard_data() -> Dict[str, Any]:
    lifecycle = await get_lifecycle_counts()
    blocking = await get_blocking_summary()
    findings = await get_findings_summary()
    
    return {
        "lifecycle": lifecycle,
        "blocking": blocking,
        "findings": findings,
        "inventory": {
            "by_vendor": await get_inventory_by_field("vendor"),
            "by_kind": await get_inventory_by_field("asset_kind"),
            "by_tech_domain": await get_inventory_by_field("tech_domain"),
            "by_business_domain": await get_inventory_by_field("business_domain")
        },
        "shadow_it": {
            "by_tech_domain": await get_shadow_it_breakdown("tech_domain"),
            "by_business_domain": await get_shadow_it_breakdown("business_domain")
        },
        "total_assets": lifecycle["DISCOVERED"] + lifecycle["PARKED"] + lifecycle["CATALOGED"]
    }


async def get_assets_by_lifecycle(state: str) -> List[Dict[str, Any]]:
    rows = await fetch("""
        SELECT id, name, vendor, asset_kind, environment, lifecycle_state, 
               parked_reason, is_shadow_it, owner, owner_team
        FROM assets
        WHERE lifecycle_state = $1
        ORDER BY updated_at DESC
    """, state)
    
    return [dict(row) for row in rows]


async def get_assets_by_parked_reason(reason: str) -> List[Dict[str, Any]]:
    rows = await fetch("""
        SELECT id, name, vendor, asset_kind, environment, lifecycle_state, 
               parked_reason, is_shadow_it, owner, owner_team
        FROM assets
        WHERE lifecycle_state = 'PARKED' AND parked_reason = $1
        ORDER BY updated_at DESC
    """, reason)
    
    return [dict(row) for row in rows]


async def get_assets_by_finding_type(finding_type: str) -> List[Dict[str, Any]]:
    rows = await fetch("""
        SELECT DISTINCT a.id, a.name, a.vendor, a.asset_kind, a.environment, 
               a.lifecycle_state, a.parked_reason, a.is_shadow_it, a.owner, a.owner_team,
               a.updated_at
        FROM assets a
        JOIN findings f ON f.asset_id = a.id
        WHERE f.finding_type = $1 AND f.status = 'open' AND a.lifecycle_state = 'CATALOGED'
        ORDER BY a.updated_at DESC
    """, finding_type)
    
    return [dict(row) for row in rows]


async def get_shadow_it_assets() -> List[Dict[str, Any]]:
    rows = await fetch("""
        SELECT id, name, vendor, asset_kind, environment, lifecycle_state, 
               parked_reason, is_shadow_it, owner, owner_team, tech_domain, business_domain
        FROM assets
        WHERE is_shadow_it = true
        ORDER BY updated_at DESC
    """)
    
    return [dict(row) for row in rows]


async def get_asset_detail(asset_id: str) -> Dict[str, Any]:
    asset = await fetchrow("""
        SELECT * FROM assets WHERE id = $1
    """, asset_id)
    
    if not asset:
        return None
    
    findings = await fetch("""
        SELECT * FROM findings WHERE asset_id = $1 ORDER BY severity, created_at DESC
    """, asset_id)
    
    return {
        "asset": dict(asset),
        "findings": [dict(f) for f in findings]
    }


async def get_ingest_runs() -> List[Dict[str, Any]]:
    rows = await fetch("""
        SELECT * FROM ingest_runs
        ORDER BY started_at DESC
        LIMIT 20
    """)
    
    return [dict(row) for row in rows]
