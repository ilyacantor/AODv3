"""AOD Pipeline - Deterministic discovery pipeline stages"""

from .validate_snapshot import validate_snapshot
from .normalize_observations import normalize_observations, CandidateEntity
from .build_plane_indexes import build_plane_indexes, PlaneIndexes
from .correlate_entities import correlate_entities_to_planes, CorrelationResult
from .admission import apply_admission_criteria, AdmissionResult
from .artifact_handler import handle_artifacts, is_artifact
from .findings_engine import generate_findings
from .pipeline_executor import execute_pipeline, PipelineResult

__all__ = [
    "validate_snapshot",
    "normalize_observations",
    "CandidateEntity",
    "build_plane_indexes",
    "PlaneIndexes",
    "correlate_entities_to_planes",
    "CorrelationResult",
    "apply_admission_criteria",
    "AdmissionResult",
    "handle_artifacts",
    "is_artifact",
    "generate_findings",
    "execute_pipeline",
    "PipelineResult",
]
