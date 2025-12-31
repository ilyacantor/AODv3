"""Trace correlation for a specific entity to debug why CMDB matching fails."""
import sys
import os
sys.path.insert(0, '/home/runner/workspace/src')

import asyncio
import httpx
from aod.pipeline.build_plane_indexes import build_cmdb_index, build_idp_index
from aod.pipeline.farm_adapter import normalize_farm_snapshot
from aod.models.input_contracts import Snapshot

AOD_URL = "http://localhost:5000"
TARGET_DOMAINS = ["easycloud.cloud", "smartsync.org", "rapidbox.net"]

async def main():
    print(f"Using AOD_URL: {AOD_URL}")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        all_snapshots_resp = await client.get(f"{AOD_URL}/api/farm/all-snapshots")
        snapshots = all_snapshots_resp.json()
        
        if not snapshots:
            print("No snapshots found")
            return
        
        snapshot_id = snapshots[0]["snapshot_id"]
        print(f"Using snapshot: {snapshot_id}\n")
        
        farm_url_resp = await client.get(f"{AOD_URL}/api/farm/url")
        farm_url = farm_url_resp.json().get("farm_url", "").rstrip("/")
        print(f"Farm URL: {farm_url}")
        
        full_snapshot_resp = await client.get(f"{farm_url}/api/snapshots/{snapshot_id}")
        if full_snapshot_resp.status_code != 200:
            print(f"Failed to fetch snapshot: {full_snapshot_resp.status_code}")
            print(f"Response: {full_snapshot_resp.text[:500]}")
            return
        
        raw_data = full_snapshot_resp.json()
        print(f"\nRaw snapshot keys: {raw_data.keys()}")
        
        normalized_data = normalize_farm_snapshot(raw_data, snapshot_id=snapshot_id)
        snapshot = Snapshot.model_validate(normalized_data)
        
        print(f"\n=== SNAPSHOT PLANES ===")
        print(f"Discovery observations: {len(snapshot.planes.discovery.observations)}")
        print(f"CMDB CIs: {len(snapshot.planes.cmdb.cis)}")
        print(f"IdP objects: {len(snapshot.planes.idp.objects)}")
        print(f"Cloud resources: {len(snapshot.planes.cloud.resources)}")
        
        print(f"\n=== RAW CMDB RECORDS (looking for target domains) ===")
        found_count = 0
        for ci in snapshot.planes.cmdb.cis:
            ci_domain = ci.domain
            raw_domain = ci.raw_data.get('domain') if ci.raw_data else None
            raw_external_ref = ci.raw_data.get('external_ref') if ci.raw_data else None
            
            for target in TARGET_DOMAINS:
                base_name = target.split('.')[0]
                match_found = False
                
                if (ci_domain and target in ci_domain):
                    match_found = True
                elif (raw_domain and target in raw_domain):
                    match_found = True  
                elif (raw_external_ref and target in raw_external_ref):
                    match_found = True
                elif (ci.name and base_name.lower() in ci.name.lower()):
                    match_found = True
                
                if match_found:
                    found_count += 1
                    print(f"\n[{found_count}] CMDB record for '{target}':")
                    print(f"  ci_id: {ci.ci_id}")
                    print(f"  name: {ci.name}")
                    print(f"  domain (attr): {repr(ci.domain)}")
                    print(f"  vendor: {ci.vendor}")
                    print(f"  raw_data keys: {list(ci.raw_data.keys()) if ci.raw_data else None}")
                    print(f"  raw_data: {ci.raw_data}")
                    break
        
        if found_count == 0:
            print("No CMDB records found matching target domains!")
            print("\nFirst 5 CMDB records (sample):")
            for i, ci in enumerate(snapshot.planes.cmdb.cis[:5]):
                print(f"  [{i+1}] name={ci.name}, domain={repr(ci.domain)}, raw_data={ci.raw_data}")
        
        print(f"\n=== BUILDING INDEXES ===")
        cmdb_index = build_cmdb_index(snapshot.planes.cmdb)
        idp_index = build_idp_index(snapshot.planes.idp)
        
        print(f"CMDB by_name_words keys (sample): {list(cmdb_index.by_name_words.keys())[:20]}")
        print(f"CMDB by_domain keys (sample): {list(cmdb_index.by_domain.keys())[:20]}")
        
        print(f"\n=== CHECKING by_name_words INDEX ===")
        for target in TARGET_DOMAINS:
            base_name = target.split('.')[0].lower()
            cmdb_matches = cmdb_index.by_name_words.get(base_name, [])
            idp_matches = idp_index.by_name_words.get(base_name, [])
            
            print(f"\n'{base_name}' in by_name_words:")
            print(f"  CMDB: {cmdb_matches}")
            print(f"  IdP: {idp_matches}")
            
            if cmdb_matches:
                for cid in cmdb_matches:
                    record = cmdb_index.records.get(cid)
                    if record:
                        print(f"    -> CMDB record: name={record.name}, domain={repr(record.domain)}")
            if idp_matches:
                for iid in idp_matches:
                    record = idp_index.records.get(iid)
                    if record:
                        print(f"    -> IdP record: name={record.name}, domain={repr(record.domain)}")
        
        print(f"\n=== CHECKING by_domain INDEX ===")
        for target in TARGET_DOMAINS:
            cmdb_matches = cmdb_index.by_domain.get(target, [])
            idp_matches = idp_index.by_domain.get(target, [])
            
            print(f"\n'{target}' in by_domain:")
            print(f"  CMDB: {cmdb_matches}")
            print(f"  IdP: {idp_matches}")

if __name__ == "__main__":
    asyncio.run(main())
