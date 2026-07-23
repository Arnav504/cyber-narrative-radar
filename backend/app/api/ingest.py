"""Ingest status and optional manual run routes."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.ingest_status import ingest_status
from app.services.live_ingest import run_ingest_cycle

router = APIRouter(prefix="/ingest", tags=["ingest"])


class IngestStatusResponse(BaseModel):
    """Operator-facing snapshot of the optional live RSS ingest loop."""

    enabled: bool
    interval_seconds: int
    running: bool
    runs_completed: int
    last_started_at: str | None = None
    last_finished_at: str | None = None
    last_success_at: str | None = None
    next_run_at: str | None = None
    last_error: str | None = None
    last_stats: dict = Field(default_factory=dict)
    last_score_stats: dict = Field(default_factory=dict)
    auto_alert_min_score: float
    live_ingest_configured: bool = Field(
        description="True when LIVE_INGEST env enables the background scheduler",
    )


class IngestRunAccepted(BaseModel):
    """Manual run accepted into a background task."""

    accepted: bool = True
    message: str


@router.get("/status", response_model=IngestStatusResponse)
def get_ingest_status() -> IngestStatusResponse:
    """Return the latest scheduled/manual ingest status."""
    snap = ingest_status.snapshot()
    return IngestStatusResponse(
        enabled=bool(snap.get("enabled")),
        interval_seconds=int(snap.get("interval_seconds") or settings.live_ingest_interval_seconds),
        running=bool(snap.get("running")),
        runs_completed=int(snap.get("runs_completed") or 0),
        last_started_at=snap.get("last_started_at"),
        last_finished_at=snap.get("last_finished_at"),
        last_success_at=snap.get("last_success_at"),
        next_run_at=snap.get("next_run_at"),
        last_error=snap.get("last_error"),
        last_stats=dict(snap.get("last_stats") or {}),
        last_score_stats=dict(snap.get("last_score_stats") or {}),
        auto_alert_min_score=settings.auto_alert_min_score,
        live_ingest_configured=settings.live_ingest_enabled,
    )


@router.post("/run", response_model=IngestRunAccepted)
async def trigger_ingest_run(background_tasks: BackgroundTasks) -> IngestRunAccepted:
    """
    Trigger one RSS ingest + score cycle in the background.

    Available even when LIVE_INGEST is off (handy for demos).
    """
    snap = ingest_status.snapshot()
    if snap.get("running"):
        raise HTTPException(status_code=409, detail="Ingest cycle already running")

    async def _job() -> None:
        await run_ingest_cycle(score=True)

    background_tasks.add_task(_job)
    return IngestRunAccepted(
        message="Ingest + score cycle started in the background",
    )
