"""Tests for the in-process live event bus (SSE notification layer)."""

import asyncio

from app.services.events import EVENT_NEW_POST, LiveEventBus, event_bus


def test_publish_fanout_to_subscriber() -> None:
    async def _run() -> None:
        bus = LiveEventBus()
        bus.bind_loop(asyncio.get_running_loop())
        queue = bus.subscribe()
        bus.publish(EVENT_NEW_POST, inserted=2)
        message = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert message is not None
        assert message.event == EVENT_NEW_POST
        assert message.data["inserted"] == 2
        assert "event: new_post" in message.to_sse()
        bus.unsubscribe(queue)

    asyncio.run(_run())


def test_process_singleton_exports_helpers() -> None:
    assert event_bus is not None
