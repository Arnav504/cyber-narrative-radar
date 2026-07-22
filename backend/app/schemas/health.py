"""Health-check response schemas."""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Liveness payload returned by the health endpoint."""

    status: str = Field(description="Service health status")
    service: str = Field(description="Service identifier")
    version: str = Field(description="API version")
