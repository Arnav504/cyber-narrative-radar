"""Optional env-gated RSS ingest scheduler (API process background loop)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.services.ingest_status import ingest_status
from app.tasks.ingest_rss import ingest_rss
from app.tasks.score_posts import score_posts

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def run_ingest_cycle(*, score: bool = True) -> dict[str, object]:
    """
    Run one RSS ingest (+ optional scoring) off the event loop.

    Updates ``ingest_status`` for the status API.
    """
    ingest_status.begin_run()
    try:
        stats = await asyncio.to_thread(ingest_rss)
        score_stats: dict[str, object] = {}
        if score:
            score_stats = await asyncio.to_thread(score_posts)
        ingest_status.finish_run(ok=True, stats=stats, score_stats=score_stats)
        return {"ok": True, "stats": stats, "score_stats": score_stats}
    except Exception as exc:  # noqa: BLE001 - surface in status API
        logger.exception("Live ingest cycle failed")
        ingest_status.finish_run(ok=False, error=str(exc))
        return {"ok": False, "error": str(exc)}


async def live_ingest_loop(stop_event: asyncio.Event) -> None:
    """
    Periodically ingest RSS and re-score while ``LIVE_INGEST`` is enabled.

    First run starts after a short warm-up so API startup stays responsive.
    """
    interval = max(30, int(settings.live_ingest_interval_seconds))
    ingest_status.configure(enabled=True, interval_seconds=interval)
    logger.info("Live RSS ingest enabled — interval=%ss", interval)

    # Brief warm-up so /health and SSE bind first.
    warmup = min(5, interval)
    next_at = _utc_now() + timedelta(seconds=warmup)
    ingest_status.mark_next_run(next_at)

    try:
        while not stop_event.is_set():
            remaining = (next_at - _utc_now()).total_seconds()
            if remaining > 0:
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=remaining)
                    break
                except asyncio.TimeoutError:
                    pass

            if stop_event.is_set():
                break

            result = await run_ingest_cycle(score=True)
            if result.get("ok"):
                logger.info("Live ingest ok — %s", result.get("stats"))
            else:
                logger.warning("Live ingest failed — %s", result.get("error"))

            next_at = _utc_now() + timedelta(seconds=interval)
            ingest_status.mark_next_run(next_at)
    finally:
        ingest_status.configure(enabled=False, interval_seconds=interval)
        ingest_status.mark_next_run(None)
        logger.info("Live RSS ingest loop stopped")
