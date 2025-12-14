"""Stage 1: ValidateSnapshot - Schema validation and banned field rejection"""

from typing import Any

from ..models.input_contracts import Snapshot, check_banned_fields
from .farm_adapter import normalize_farm_snapshot, NormalizationError


class ValidationError(Exception):
    """Validation error for snapshot"""
    def __init__(self, message: str, violations: list[str] | None = None):
        super().__init__(message)
        self.violations = violations or []


def validate_snapshot(
    data: dict[str, Any],
    normalize: bool = False,
    fallback_tenant_id: str | None = None,
    snapshot_id: str | None = None
) -> Snapshot:
    """
    Validate snapshot JSON data.
    
    Flow:
    1. Optionally normalize raw Farm data to canonical format
    2. Check for banned ground-truth fields anywhere in payload
    3. Parse and validate against Pydantic schema
    
    Args:
        data: Raw snapshot JSON data
        normalize: If True, normalize Farm data before validation
        fallback_tenant_id: Tenant ID from request (for normalization)
        snapshot_id: Snapshot ID (for normalization)
        
    Returns:
        Validated Snapshot object
        
    Raises:
        ValidationError: If validation fails
    """
    if normalize:
        try:
            data = normalize_farm_snapshot(
                data,
                fallback_tenant_id=fallback_tenant_id,
                snapshot_id=snapshot_id
            )
        except NormalizationError as e:
            raise ValidationError(
                f"INVALID_SNAPSHOT: {e.message}",
                violations=e.missing_fields
            )
    
    violations = check_banned_fields(data)
    if violations:
        raise ValidationError(
            f"INVALID_INPUT_CONTRACT: Banned ground-truth fields detected: {violations}. "
            "AOD does not accept pre-adjudicated data.",
            violations=violations
        )
    
    try:
        snapshot = Snapshot.model_validate(data)
        return snapshot
    except Exception as e:
        raise ValidationError(f"Schema validation failed: {str(e)}")
