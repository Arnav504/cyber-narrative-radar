"""Health-check routes."""

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Return API liveness status."""
    return HealthResponse(
        status="healthy",
        service="cyber-narrative-radar",
        version=settings.app_version,
    )
