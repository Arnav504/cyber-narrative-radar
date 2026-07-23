"""Server-Sent Events stream for lightweight dashboard notifications."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.events import (
    EVENT_ALERTS_UPDATED,
    EVENT_NARRATIVES_UPDATED,
    EVENT_NEW_POST,
    event_bus,
)

router = APIRouter(prefix="/events", tags=["events"])

HEARTBEAT_SECONDS = 20

ALLOWED_EVENTS = frozenset(
    {
        EVENT_NEW_POST,
        EVENT_ALERTS_UPDATED,
        EVENT_NARRATIVES_UPDATED,
    }
)


class NotifyRequest(BaseModel):
    """Out-of-process task notification (e.g. CLI ingest → running API)."""

    event: str = Field(description="new_post | alerts_updated | narratives_updated")
    data: dict = Field(default_factory=dict)


@router.get("/stream")
async def stream_events(request: Request) -> StreamingResponse:
    """
    SSE notification channel.

    Emits ``new_post``, ``alerts_updated``, and ``narratives_updated`` so the
    frontend can refetch existing JSON APIs. Does not push full domain payloads.
    """

    async def event_generator():
        queue = event_bus.subscribe()
        try:
            yield (
                "event: connected\n"
                'data: {"service":"cyber-narrative-radar"}\n\n'
            )
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(
                        queue.get(),
                        timeout=HEARTBEAT_SECONDS,
                    )
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
                    continue

                if message is None:
                    break
                yield message.to_sse()
        finally:
            event_bus.unsubscribe(queue)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers=headers,
    )


@router.post("/notify")
def notify_event(body: NotifyRequest) -> dict[str, str | bool]:
    """
    Accept a notification from a CLI task in another process.

    Local ``publish_*`` calls cover in-process emits; this endpoint bridges
    separate ingest/score processes to the API's SSE subscribers.
    """
    if body.event not in ALLOWED_EVENTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported event '{body.event}'. Allowed: {sorted(ALLOWED_EVENTS)}",
        )
    event_bus.publish(body.event, **body.data)
    return {"ok": True, "event": body.event}


@router.get("/types")
def list_event_types() -> dict[str, list[str]]:
    """Document the notification event names (no payload schema)."""
    return {"events": sorted(ALLOWED_EVENTS)}
