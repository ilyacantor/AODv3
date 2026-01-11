"""Debug admission decisions for problem domains."""
import sys
sys.path.insert(0, 'src')

import json
from aod.models.input_contracts import Snapshot
from aod.pipeline.normalize_observations import normalize_observations
from aod.pipeline.build_plane_indexes import build_plane_indexes
from aod.pipeline.resolve_entities import resolve_entities
from aod.pipeline.correlate import correlate_all
from aod.pipeline.admission import apply_admission

# Load snapshot
with open('tests/fixtures/real_farm_snapshot.json') as f:
    raw_json = json.load(f)

print("Loading snapshot...")
snapshot = Snapshot(**raw_json)

print("Normalizing observations...")
normalized = normalize_observations(snapshot.planes.discovery)

print("Building plane indexes...")
indexes = build_plane_indexes(snapshot.planes)

print("Resolving entities...")
entities = resolve_entities(normalized)

print("Correlating...")
correlations = correlate_all(entities, indexes)

print("\nChecking admission for problem domains...")
problem_domains = ['googleapis.com', 'office.com', 'tiktok.com', 'awsstatic.com', 'workers.dev']

for entity in entities:
    entity_domain = None
    for domain in entity.identifiers.domains:
        if domain.lower() in problem_domains:
            entity_domain = domain.lower()
            break

    if not entity_domain:
        continue

    correlation = correlations.get(entity.canonical_key)
    if not correlation:
        print(f"\n❌ {entity_domain}: No correlation found")
        continue

    # Get discovery observations
    observations = [obs for obs in normalized if
                   any(d.lower() == entity_domain for d in (obs.domains or []))]

    print(f"\n=== {entity_domain} ===")
    print(f"Discovery observations: {len(observations)}")

    # Show sources
    sources = [obs.source for obs in observations if obs.source]
    print(f"Sources: {sources}")
    print(f"Unique sources: {set(sources)}")

    # Check admission
    result = apply_admission(
        entity=entity,
        correlation=correlation,
        observations=observations,
        idp_activity_map={}
    )

    print(f"Admitted: {result.admitted}")
    print(f"Reason: {result.admission_reason or result.rejection_reason}")
    print(f"Status: {result.provisioning_status}")
