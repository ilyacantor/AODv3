"""Health check route module"""

from fastapi import APIRouter

from ..schemas import HealthResponse

router = APIRouter(prefix="")


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        version="1.0.0"
    )
