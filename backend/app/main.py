"""FastAPI entrypoint for Cyber Narrative Radar."""

from contextlib import asynccontextmanager

import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import alerts, events, health, metrics, narratives, organizations
from app.core.config import settings
from app.db.session import init_db
from app.services.events import event_bus


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Create tables on startup and bind the live event bus to this loop."""
    init_db()
    event_bus.bind_loop(asyncio.get_running_loop())
    yield


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
