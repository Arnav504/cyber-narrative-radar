"""In-process live event bus for Server-Sent Events (notification layer only).

Business tasks call ``publish_*`` helpers. The SSE route subscribes and streams
event names to the dashboard; payloads stay small — clients refetch normal APIs.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


# Canonical SSE event names for the dashboard notification layer.
EVENT_NEW_POST = "new_post"
EVENT_ALERTS_UPDATED = "alerts_updated"
EVENT_NARRATIVES_UPDATED = "narratives_updated"


@dataclass(frozen=True)
class LiveEvent:
    """Lightweight notification pushed over SSE."""

    event: str
    data: dict[str, Any]
    ts: str

    def to_sse(self) -> str:
        payload = json.dumps({"ts": self.ts, **self.data}, separators=(",", ":"))
        return f"event: {self.event}\ndata: {payload}\n\n"


class LiveEventBus:
    """Fan-out bus shared by API workers and background tasks in one process."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[LiveEvent | None]] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Remember the API event loop so sync tasks can publish safely."""
        self._loop = loop

    def subscribe(self) -> asyncio.Queue[LiveEvent | None]:
        queue: asyncio.Queue[LiveEvent | None] = asyncio.Queue(maxsize=64)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[LiveEvent | None]) -> None:
        self._subscribers.discard(queue)

    def publish(self, event: str, **data: Any) -> None:
        """Publish from async or sync code (ingest/score tasks)."""
        message = LiveEvent(
            event=event,
            data=dict(data),
            ts=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None

        if running is not None:
            self._fanout(message)
            return

        loop = self._loop
        if loop is None or not loop.is_running():
            return
        loop.call_soon_threadsafe(self._fanout, message)

    def _fanout(self, message: LiveEvent) -> None:
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                # Drop oldest overflow for slow clients; keep stream alive.
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    queue.put_nowait(message)
                except asyncio.QueueFull:
                    pass


# Process-wide singleton — one API process / one local demo.
event_bus = LiveEventBus()


def publish_new_post(**data: Any) -> None:
    event_bus.publish(EVENT_NEW_POST, **data)


def publish_alerts_updated(**data: Any) -> None:
    event_bus.publish(EVENT_ALERTS_UPDATED, **data)


def publish_narratives_updated(**data: Any) -> None:
    event_bus.publish(EVENT_NARRATIVES_UPDATED, **data)
