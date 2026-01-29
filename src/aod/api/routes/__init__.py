"""Aggregated API routes for AOD"""

from fastapi import APIRouter

from .health import router as health_router
from .farm import router as farm_router
from .fabric import router as fabric_router
from .runs import router as runs_router
from .catalog import router as catalog_router
from .findings import router as findings_router
from .triage import router as triage_router
from .debug import router as debug_router
from .policy import router as policy_router
from .handoff import router as handoff_router

router = APIRouter(prefix="/api")

router.include_router(health_router, tags=["health"])
router.include_router(farm_router, tags=["farm"])
router.include_router(fabric_router, tags=["fabric"])
router.include_router(runs_router, tags=["runs"])
router.include_router(catalog_router, tags=["catalog"])
router.include_router(findings_router, tags=["findings"])
router.include_router(triage_router, tags=["triage"])
router.include_router(debug_router, tags=["debug"])
router.include_router(handoff_router, tags=["handoff"])

router.include_router(policy_router, prefix="/v1", tags=["policy"])
