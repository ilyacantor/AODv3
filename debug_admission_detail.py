"""Deep debug of admission logic for cloudflareinsights.com and tiktok.com"""
import sys
sys.path.insert(0, 'src')

import json
from aod.models.input_contracts import Snapshot
from aod.pipeline.normalize_observations import normalize_observations
from aod.pipeline.build_plane_indexes import build_plane_indexes
from aod.pipeline.correlate_entities import correlate_entities_to_planes
from aod.pipeline.admission import build_discovery_footprint, check_discovery_admission

# Load snapshot
with open('tests/fixtures/real_farm_snapshot.json') as f:
    snapshot_dict = json.load(f)

snapshot = Snapshot(**snapshot_dict)

# Run pipeline
candidates, obs_by_key = normalize_observations(snapshot.planes.discovery.observations)
indexes = build_plane_indexes(snapshot.planes)
correlations = correlate_entities_to_planes(candidates, indexes)

# Check specific domains
check_domains = ['cloudflareinsights.com', 'tiktok.com']

for c in correlations:
    entity = c.entity
    if not entity.domain or entity.domain not in check_domains:
        continue

    print(f"\n{'='*80}")
    print(f"{entity.domain}")
    print(f"{'='*80}")

    # Get observations
    observations = obs_by_key.get(entity.canonical_key, [])
    print(f"\nObservations for entity (key={entity.canonical_key}): {len(observations)}")
    for obs in observations:
        print(f"  {obs.source}: {obs.observed_at}")

    # Build discovery footprint
    footprint = build_discovery_footprint(observations, canonical_key=entity.domain)
    print(f"\nDiscovery Footprint:")
    print(f"  discovery_sources: {footprint.discovery_sources} (count={len(footprint.discovery_sources)})")
    print(f"  planes_present: {footprint.planes_present}")
    print(f"  recent_activity: {footprint.recent_activity}")
    print(f"  latest_activity_at: {footprint.latest_activity_at}")
    print(f"  reason_codes: {footprint.reason_codes}")

    # Check discovery admission
    admitted, reason = check_discovery_admission(observations, canonical_key=entity.domain)
    print(f"\nDiscovery Admission Check:")
    print(f"  admitted: {admitted}")
    print(f"  reason: {reason}")
