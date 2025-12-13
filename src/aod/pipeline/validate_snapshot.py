"""Stage 1: ValidateSnapshot - Schema validation and banned field rejection"""

from typing import Any

from ..models.input_contracts import Snapshot, check_banned_fields


class ValidationError(Exception):
    """Validation error for snapshot"""
    def __init__(self, message: str, violations: list[str] | None = None):
        super().__init__(message)
        self.violations = violations or []


def validate_snapshot(data: dict[str, Any]) -> Snapshot:
    """
    Validate snapshot JSON data.
    
    1. Check for banned ground-truth fields anywhere in payload
    2. Parse and validate against Pydantic schema
    
    Args:
        data: Raw snapshot JSON data
        
    Returns:
        Validated Snapshot object
        
    Raises:
        ValidationError: If validation fails
    """
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
