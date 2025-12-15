"""
Zombie v0 - Isolated Zombie Recognition Lane

This module is completely walled-off from the main pipeline.
It does not affect main zombie/shadow logic, reconciliation, or existing routes.

For debugging purposes only.
"""

from .compute import compute_zombies_v0, ZombieV0Result

__all__ = ["compute_zombies_v0", "ZombieV0Result"]
