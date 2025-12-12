from typing import Dict, Any, List, Optional
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


async def get_findings_summary() -> Dict[str, Dict[str, int]]:
    rows = await fetch("""
        SELECT f.finding_type, 
               COUNT(DISTINCT f.asset_id) as asset_count, 
               COUNT(*) as finding_count
        FROM findings f
        JOIN assets a ON f.asset_id = a.id
        WHERE f.status = 'open'
        GROUP BY f.finding_type
    """)
    
    summary = {
        "shadow_it": {"assets": 0, "findings": 0},
        "governance_gap": {"assets": 0, "findings": 0},
        "data_conflicts": {"assets": 0, "findings": 0},
        "ops_risk": {"assets": 0, "findings": 0},
        "low_confidence": {"assets": 0, "findings": 0}
    }
    
    for row in rows:
        finding_type = row["finding_type"]
        if finding_type in summary:
            summary[finding_type] = {
                "assets": row["asset_count"],
                "findings": row["finding_count"]
            }
    
    return summary


async def get_unique_assets_with_findings() -> int:
    """Count unique assets that have at least one open finding OR are shadow IT."""
    row = await fetchrow("""
        SELECT COUNT(DISTINCT asset_id) as unique_count
        FROM (
            SELECT f.asset_id FROM findings f
            JOIN assets a ON f.asset_id = a.id
            WHERE f.status = 'open'
            UNION
            SELECT id as asset_id FROM assets WHERE is_shadow_it = true
        ) combined
    """)
    return row["unique_count"] if row else 0


async def get_shadow_it_count() -> Dict[str, Any]:
    """Get shadow IT counts across all lifecycle states."""
    total = await fetchval("SELECT COUNT(*) FROM assets WHERE is_shadow_it = true")
    by_lifecycle = await fetch("""
        SELECT lifecycle_state, COUNT(*) as count 
        FROM assets WHERE is_shadow_it = true 
        GROUP BY lifecycle_state
    """)
    return {
        "total": total or 0,
        "by_lifecycle": {row["lifecycle_state"]: row["count"] for row in by_lifecycle}
    }


def generate_stable_key(value: str) -> str:
    """Generate a stable URL-safe key from a display value."""
    import re
    import hashlib
    key = value.lower().strip()
    key = re.sub(r'[^a-z0-9]+', '_', key)
    key = key.strip('_')
    if not key or len(key) < 2:
        key = hashlib.md5(value.encode()).hexdigest()[:8]
    return key


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
    
    return [
        {
            "label": row["label"] or "Unknown", 
            "key": generate_stable_key(row["label"] or "Unknown"),
            "count": row["count"]
        } 
        for row in rows
    ]


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
    
    return [
        {
            "label": row["label"] or "Unknown",
            "key": generate_stable_key(row["label"] or "Unknown"),
            "count": row["count"]
        }
        for row in rows
    ]


async def get_dashboard_data() -> Dict[str, Any]:
    lifecycle = await get_lifecycle_counts()
    blocking = await get_blocking_summary()
    findings = await get_findings_summary()
    shadow_it_count = await get_shadow_it_count()
    unique_assets_with_findings = await get_unique_assets_with_findings()
    
    return {
        "lifecycle": lifecycle,
        "blocking": blocking,
        "findings": findings,
        "shadow_it_count": shadow_it_count,
        "unique_assets_with_findings": unique_assets_with_findings,
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
        "total_assets": lifecycle["DISCOVERED"]
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


async def get_asset_detail(asset_id: str) -> Optional[Dict[str, Any]]:
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
    
    results = []
    for row in rows:
        r = dict(row)
        if r.get('id'):
            r['id'] = str(r['id'])
        if r.get('started_at'):
            r['started_at'] = r['started_at'].isoformat()
        if r.get('finished_at'):
            r['finished_at'] = r['finished_at'].isoformat()
        results.append(r)
    return results


async def get_assets_by_inventory(field: str, value: str) -> List[Dict[str, Any]]:
    """Get assets filtered by an inventory field (vendor, asset_kind, tech_domain, business_domain).
    DEPRECATED: Use filter_assets_by_inventory with query params instead."""
    valid_fields = ["vendor", "asset_kind", "tech_domain", "business_domain"]
    if field not in valid_fields:
        return []
    
    rows = await fetch(f"""
        SELECT id, name, vendor, asset_kind, environment, lifecycle_state, 
               parked_reason, is_shadow_it, owner, owner_team, tech_domain, business_domain
        FROM assets
        WHERE {field} = $1 AND lifecycle_state = 'CATALOGED'
        ORDER BY updated_at DESC
    """, value)
    
    return [dict(row) for row in rows]


async def filter_assets_by_inventory(
    field: str, 
    value: Optional[str] = None,
    key: Optional[str] = None
) -> Dict[str, Any]:
    """Filter assets by inventory field using either display value or stable key.
    Always returns 200 with consistent shape: {assets: [], total: 0, filters: {...}}
    """
    valid_fields = ["vendor", "asset_kind", "tech_domain", "business_domain"]
    if field not in valid_fields:
        return {"assets": [], "total": 0, "filters": {"field": field, "error": "invalid_field"}}
    
    if key:
        rows = await fetch(f"""
            SELECT id, name, vendor, asset_kind, environment, lifecycle_state, 
                   parked_reason, is_shadow_it, owner, owner_team, tech_domain, business_domain
            FROM assets
            WHERE lifecycle_state = 'CATALOGED'
            ORDER BY updated_at DESC
        """)
        matching = []
        for row in rows:
            field_value = row[field]
            if field_value and generate_stable_key(field_value) == key:
                matching.append(dict(row))
        return {
            "assets": matching, 
            "total": len(matching), 
            "filters": {"field": field, "key": key}
        }
    elif value:
        rows = await fetch(f"""
            SELECT id, name, vendor, asset_kind, environment, lifecycle_state, 
                   parked_reason, is_shadow_it, owner, owner_team, tech_domain, business_domain
            FROM assets
            WHERE {field} = $1 AND lifecycle_state = 'CATALOGED'
            ORDER BY updated_at DESC
        """, value)
        return {
            "assets": [dict(row) for row in rows], 
            "total": len(rows), 
            "filters": {"field": field, "value": value}
        }
    else:
        return {"assets": [], "total": 0, "filters": {"field": field, "error": "no_filter"}}


async def get_shadow_it_by_field(field: str, value: str) -> List[Dict[str, Any]]:
    """Get shadow IT assets filtered by tech_domain or business_domain."""
    valid_fields = ["tech_domain", "business_domain"]
    if field not in valid_fields:
        return []
    
    rows = await fetch(f"""
        SELECT id, name, vendor, asset_kind, environment, lifecycle_state, 
               parked_reason, is_shadow_it, owner, owner_team, tech_domain, business_domain
        FROM assets
        WHERE is_shadow_it = true AND {field} = $1
        ORDER BY updated_at DESC
    """, value)
    
    return [dict(row) for row in rows]


async def get_farm_bucket_counts() -> Dict[str, int]:
    """Get counts for Farm's mutually exclusive bucket classification."""
    rows = await fetch("""
        SELECT farm_bucket, COUNT(*) as count
        FROM assets
        WHERE farm_bucket IS NOT NULL
        GROUP BY farm_bucket
    """)
    
    counts = {
        "clean": 0,
        "non_blocking": 0,
        "blocking": 0,
        "shadow": 0
    }
    
    for row in rows:
        bucket = row["farm_bucket"]
        if bucket in counts:
            counts[bucket] = row["count"]
    
    return counts


async def get_validation_metrics() -> Dict[str, Any]:
    """Get validation metrics for precision/recall calculations (placeholder for future)."""
    bucket_counts = await get_farm_bucket_counts()
    total = sum(bucket_counts.values())
    
    return {
        "bucket_counts": bucket_counts,
        "total_classified": total,
        "precision": None,
        "recall": None,
        "f1_score": None
    }
