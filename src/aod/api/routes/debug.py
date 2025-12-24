"""Debug and reconcile API routes for AOD

This module aggregates all debug endpoints from specialized sub-modules:
- zombie.py: Zombie classification debugging
- reconcile.py: Farm/AOD reconciliation
- trace.py: Asset tracing and decision debugging
- coverage.py: Timestamp coverage analysis
- test.py: Test execution

All sub-routers are included without prefixes since they define their own paths.
"""

from fastapi import APIRouter

from . import zombie
from . import reconcile
from . import trace
from . import coverage
from . import test


router = APIRouter(prefix="")

# Include all sub-routers
router.include_router(zombie.router, tags=["debug-zombie"])
router.include_router(reconcile.router, tags=["debug-reconcile"])
router.include_router(trace.router, tags=["debug-trace"])
router.include_router(coverage.router, tags=["debug-coverage"])
router.include_router(test.router, tags=["debug-test"])
