"""Zombie v0 types - completely isolated from main AOD logic."""

from typing import Optional
from pydantic import BaseModel


class ZombieV0Result(BaseModel):
    """Single asset zombie classification result."""
    asset_id: str
    exists_in_sor: bool
    activity_in_window: bool
    zombie: bool
    last_activity_observed_at: Optional[str]
    reason: str


class ZombieV0Response(BaseModel):
    """Response for the Zombie v0 endpoint."""
    run_id: str
    window_days: int
    results: list[ZombieV0Result]
