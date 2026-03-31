"""Stage 6: Artifact Handling - Identify and record artifacts (non-system objects)"""

import re
from typing import Optional

from ..models.output_contracts import Artifact, ArtifactType
from .normalize_observations import CandidateEntity
from .deterministic_ids import deterministic_uuid

ARTIFACT_PATTERNS = [
    (r"\bdashboard\b", ArtifactType.DASHBOARD),
    (r"\breport\b", ArtifactType.REPORT),
    (r"\bcalculator\b", ArtifactType.CALCULATOR),
    (r"\bworksheet\b", ArtifactType.WORKSHEET),
    (r"\bspreadsheet\b", ArtifactType.WORKSHEET),
    (r"\bview\b", ArtifactType.VIEW),
    (r"\bsaved\s+quer(?:y|ies)\b", ArtifactType.SAVED_QUERY),
    (r"\bfile\b", ArtifactType.FILE),
    (r"\.xlsx?$", ArtifactType.FILE),
    (r"\.csv$", ArtifactType.FILE),
    (r"\.pdf$", ArtifactType.FILE),
    (r"\.docx?$", ArtifactType.FILE),
]


def detect_artifact_type(name: str) -> Optional[ArtifactType]:
    """
    Detect if a name indicates an artifact type.
    
    Returns the artifact type if detected, None otherwise.
    """
    name_lower = name.lower()
    
    for pattern, artifact_type in ARTIFACT_PATTERNS:
        if re.search(pattern, name_lower):
            return artifact_type
    
    return None


def is_artifact(entity: CandidateEntity) -> tuple[bool, Optional[ArtifactType]]:
    """
    Check if an entity is an artifact (non-system object).
    
    Global negative list includes:
    - dashboards
    - reports  
    - calculators
    - worksheets
    - views
    - saved queries
    - files
    
    Artifacts must never be assets.
    
    Args:
        entity: Candidate entity to check
        
    Returns:
        Tuple of (is_artifact, artifact_type)
    """
    artifact_type = detect_artifact_type(entity.original_name)
    if artifact_type:
        return True, artifact_type
    
    artifact_type = detect_artifact_type(entity.canonical_name)
    if artifact_type:
        return True, artifact_type
    
    return False, None


def handle_artifacts(
    entities: list[CandidateEntity],
    tenant_id: str,
    run_id: str,
    snapshot_id: str
) -> tuple[list[CandidateEntity], list[Artifact]]:
    """
    Filter out artifacts from candidate entities.
    
    Artifacts are optionally persisted with:
    - artifact_id
    - parent_asset_id (nullable)
    - name
    - artifact_type
    - source
    - evidence_ref
    
    Args:
        entities: List of candidate entities
        tenant_id: Tenant ID
        run_id: Run ID
        
    Returns:
        Tuple of (filtered_entities, artifacts)
    """
    filtered_entities = []
    artifacts = []
    
    for entity in sorted(entities, key=lambda e: e.entity_id):
        is_art, artifact_type = is_artifact(entity)
        
        if is_art and artifact_type:
            artifact = Artifact(
                artifact_id=deterministic_uuid(snapshot_id, run_id, "artifact", entity.original_name),
                tenant_id=tenant_id,
                aod_discovery_id=run_id,
                parent_asset_id=None,
                name=entity.original_name,
                artifact_type=artifact_type,
                source=entity.source,
                evidence_ref=entity.observation_ids[0] if entity.observation_ids else entity.entity_id
            )
            artifacts.append(artifact)
        else:
            filtered_entities.append(entity)
    
    return filtered_entities, artifacts
