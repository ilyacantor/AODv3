import sys
import logging
sys.path.insert(0, '/home/runner/workspace/src')

from aod.pipeline.admission import _extract_domain_from_correlation
from aod.pipeline.correlate_entities import PlaneMatch, CorrelationResult, MatchStatus
from aod.pipeline.normalize_observations import CandidateEntity
from aod.models.input_contracts import IdPObject, CMDBConfigItem

logging.basicConfig(level=logging.INFO)

print("--- STARTING ZOMBIE DIAGNOSTIC ---")

dummy_entity = CandidateEntity(
    entity_id="ent_1",
    canonical_name="rapidbox",
    original_name="RapidBox",
    domain=None,
    source="discovery"
)

evidence_variations = [
    ("Dict with top-level domain", {"name": "RapidBox SSO", "domain": "rapidbox.net", "id": "1"}, "idp"),
    
    ("IdPObject with domain", IdPObject(
        idp_id="idp_1", 
        name="RapidBox SSO", 
        domain="rapidbox.net"
    ), "idp"),
    
    ("IdPObject with domain=None, raw_data has registered_domain", IdPObject(
        idp_id="idp_2",
        name="RapidBox SSO", 
        domain=None,
        raw_data={"registered_domain": "rapidbox.net", "service_url": "https://rapidbox.net/login"}
    ), "idp"),
    
    ("IdPObject with domain=None, raw_data has external_ref", IdPObject(
        idp_id="idp_3",
        name="RapidBox SSO", 
        domain=None,
        raw_data={"external_ref": "rapidbox.net"}
    ), "idp"),
    
    ("CMDBConfigItem with domain", CMDBConfigItem(
        ci_id="cmdb_1",
        name="RapidBox",
        domain="rapidbox.net"
    ), "cmdb"),
    
    ("CMDBConfigItem with domain=None, raw_data has external_ref", CMDBConfigItem(
        ci_id="cmdb_2",
        name="RapidBox",
        domain=None,
        raw_data={"external_ref": "rapidbox.net"}
    ), "cmdb"),
]

print(f"Testing {len(evidence_variations)} data shapes against Admission Logic...")

for i, (desc, record, plane) in enumerate(evidence_variations):
    print(f"\n--- TEST CASE {i+1}: {desc} ---")
    print(f"Record Type: {type(record).__name__}")
    if hasattr(record, '__dict__'):
        print(f"Domain attr: {getattr(record, 'domain', 'N/A')}")
        raw_data = getattr(record, 'raw_data', None)
        print(f"raw_data: {raw_data}")
    else:
        print(f"Record: {record}")
    
    if plane == "idp":
        correlation = CorrelationResult(
            entity=dummy_entity,
            idp=PlaneMatch(
                status=MatchStatus.MATCHED,
                match_key="rapidbox",
                matched_records=[record]
            )
        )
    else:
        correlation = CorrelationResult(
            entity=dummy_entity,
            cmdb=PlaneMatch(
                status=MatchStatus.MATCHED,
                match_key="rapidbox",
                matched_records=[record]
            )
        )
    
    try:
        result = _extract_domain_from_correlation(correlation)
        
        if result == "rapidbox.net":
            print(f"SUCCESS: Domain extracted = '{result}'")
        else:
            print(f"FAILED: Returned '{result}' (Expected 'rapidbox.net')")
            
    except Exception as e:
        print(f"CRASH: {e}")
        import traceback
        traceback.print_exc()

print("\n--- DIAGNOSTIC COMPLETE ---")
