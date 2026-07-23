"""FastAPI entrypoint for Cyber Narrative Radar."""

from contextlib import asynccontextmanager

import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import alerts, events, health, ingest, metrics, narratives, organizations
from app.core.config import settings
from app.db.session import init_db
from app.services.events import event_bus
from app.services.ingest_status import ingest_status
from app.services.live_ingest import live_ingest_loop


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Create tables, bind the event bus, and optionally start live RSS ingest."""
    init_db()
    event_bus.bind_loop(asyncio.get_running_loop())
    ingest_status.configure(
        enabled=settings.live_ingest_enabled,
        interval_seconds=settings.live_ingest_interval_seconds,
    )

    stop_event: asyncio.Event | None = None
    ingest_task: asyncio.Task | None = None
    if settings.live_ingest_enabled:
        stop_event = asyncio.Event()
        ingest_task = asyncio.create_task(
            live_ingest_loop(stop_event),
            name="live-rss-ingest",
        )

    try:
        yield
    finally:
        if stop_event is not None and ingest_task is not None:
            stop_event.set()
            try:
                await asyncio.wait_for(ingest_task, timeout=15)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                ingest_task.cancel()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.resolved_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(alerts.router, prefix=settings.api_prefix)
app.include_router(organizations.router, prefix=settings.api_prefix)
app.include_router(narratives.router, prefix=settings.api_prefix)
app.include_router(metrics.router, prefix=settings.api_prefix)
app.include_router(events.router, prefix=settings.api_prefix)
app.include_router(ingest.router, prefix=settings.api_prefix)


@app.get("/")
def read_root() -> dict[str, str]:
    """Return a short service identity payload."""
    return {
        "message": "Cyber Narrative Radar API is running",
        "status": "ok",
        "version": settings.app_version,
        "environment": settings.environment,
        "docs": "/docs",
    }
