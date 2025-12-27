#!/usr/bin/env python3
"""
Migration Script: Merge Duplicate Assets

This script scans the database for duplicate assets created by the "split brain"
problem (e.g., "Airtable" from Finance vs "airtable.com" from Discovery) and
merges them into a single record.

The domain entity is always the survivor - it absorbs all evidence from name-only entities.

Usage:
    python scripts/merge_duplicate_assets.py [--dry-run] [--run-id RUN_ID]

Options:
    --dry-run   Show what would be merged without making changes
    --run-id    Process only assets from a specific run (default: all runs)
"""

import asyncio
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.aod.utils.normalization import get_normalization_token
from src.aod.db.database import get_db_pool


async def find_duplicate_assets(pool, run_id: str = None):
    """Find assets that may be duplicates based on normalization token."""
    query = """
        SELECT asset_id, name, vendor, run_id,
               COALESCE(domains, '[]'::jsonb) as domains,
               COALESCE(evidence_refs, '[]'::jsonb) as evidence_refs,
               provisioning_status
        FROM assets
    """
    if run_id:
        query += " WHERE run_id = $1"
    query += " ORDER BY run_id, name"
    
    async with pool.acquire() as conn:
        if run_id:
            rows = await conn.fetch(query, run_id)
        else:
            rows = await conn.fetch(query)
    
    assets_by_run: dict[str, list] = {}
    for row in rows:
        r = row['run_id']
        if r not in assets_by_run:
            assets_by_run[r] = []
        assets_by_run[r].append(dict(row))
    
    duplicates = []
    for r_id, assets in assets_by_run.items():
        token_groups: dict[str, list] = {}
        for asset in assets:
            name = asset.get('name') or ''
            vendor = asset.get('vendor') or ''
            domains = asset.get('domains') or []
            
            if domains and isinstance(domains, list) and len(domains) > 0:
                token = get_normalization_token(domains[0])
            else:
                token = get_normalization_token(name) or get_normalization_token(vendor)
            
            if token and len(token) >= 3:
                if token not in token_groups:
                    token_groups[token] = []
                token_groups[token].append(asset)
        
        for token, group in token_groups.items():
            if len(group) > 1:
                domain_assets = [a for a in group if a.get('domains') and len(a['domains']) > 0]
                name_only_assets = [a for a in group if not a.get('domains') or len(a['domains']) == 0]
                
                if domain_assets and name_only_assets:
                    survivor = domain_assets[0]
                    to_merge = name_only_assets
                    duplicates.append({
                        'run_id': r_id,
                        'token': token,
                        'survivor': survivor,
                        'to_merge': to_merge
                    })
    
    return duplicates


async def merge_assets(pool, survivor: dict, to_merge: list, dry_run: bool = True):
    """Merge name-only assets into the domain survivor."""
    survivor_id = survivor['asset_id']
    survivor_refs = survivor.get('evidence_refs') or []
    if isinstance(survivor_refs, str):
        import json
        survivor_refs = json.loads(survivor_refs)
    
    merged_refs = set(survivor_refs)
    merged_asset_ids = []
    
    for asset in to_merge:
        asset_refs = asset.get('evidence_refs') or []
        if isinstance(asset_refs, str):
            import json
            asset_refs = json.loads(asset_refs)
        merged_refs.update(asset_refs)
        merged_asset_ids.append(asset['asset_id'])
    
    merged_refs_list = list(merged_refs)
    
    if dry_run:
        print(f"  [DRY-RUN] Would merge {len(to_merge)} assets into '{survivor.get('name')}'")
        print(f"            Evidence refs: {len(survivor_refs)} -> {len(merged_refs_list)}")
        for a in to_merge:
            print(f"            - Delete: {a.get('name')} ({a['asset_id'][:8]}...)")
        return True
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            import json
            await conn.execute("""
                UPDATE assets 
                SET evidence_refs = $1::jsonb
                WHERE asset_id = $2
            """, json.dumps(merged_refs_list), survivor_id)
            
            for asset_id in merged_asset_ids:
                await conn.execute("""
                    UPDATE findings SET asset_id = $1 WHERE asset_id = $2
                """, survivor_id, asset_id)
                
                await conn.execute("""
                    DELETE FROM assets WHERE asset_id = $1
                """, asset_id)
    
    print(f"  [MERGED] {len(to_merge)} assets into '{survivor.get('name')}'")
    return True


async def main():
    parser = argparse.ArgumentParser(description='Merge duplicate assets')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be merged without making changes')
    parser.add_argument('--run-id', type=str, help='Process only assets from a specific run')
    args = parser.parse_args()
    
    print("=" * 60)
    print("AOD Asset Deduplication Migration")
    print("=" * 60)
    if args.dry_run:
        print("MODE: DRY RUN (no changes will be made)")
    else:
        print("MODE: LIVE (changes will be applied)")
    print()
    
    pool = await get_db_pool()
    if not pool:
        print("ERROR: Could not connect to database")
        return 1
    
    try:
        duplicates = await find_duplicate_assets(pool, args.run_id)
        
        if not duplicates:
            print("No duplicate assets found. Database is clean!")
            return 0
        
        print(f"Found {len(duplicates)} duplicate groups to merge:\n")
        
        for i, dup in enumerate(duplicates, 1):
            print(f"[{i}] Token: '{dup['token']}' (Run: {dup['run_id'][:16]}...)")
            print(f"    Survivor: {dup['survivor'].get('name')} -> {dup['survivor'].get('domains', [])}")
            await merge_assets(pool, dup['survivor'], dup['to_merge'], dry_run=args.dry_run)
            print()
        
        if args.dry_run:
            print("\nTo apply these changes, run without --dry-run")
        else:
            print(f"\nSuccessfully merged {len(duplicates)} duplicate groups")
        
        return 0
        
    finally:
        await pool.close()


if __name__ == '__main__':
    exit(asyncio.run(main()))
