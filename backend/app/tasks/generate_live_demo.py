"""Optional demo-mode live synthetic post generator.

Inserts ``source=synthetic`` posts on a 20–30s cadence, re-runs scoring, and
notifies the SSE bus so the dashboard visibly updates during demos.

Start:
  python -m app.tasks.generate_live_demo

Stop:
  Ctrl+C

Disable for normal usage: simply do not start this process (demo-only).
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import time
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.db.models import Post
from app.db.session import SessionLocal, init_db
from app.services.event_notify import notify_api
from app.services.events import (
    EVENT_NARRATIVES_UPDATED,
    EVENT_NEW_POST,
    publish_narratives_updated,
    publish_new_post,
)
from app.services.synthetic_posts import (
    build_synthetic_post,
    interval_seconds_for_tick,
)
from app.tasks.score_posts import score_posts

# Cooperative stop flag for Ctrl+C / SIGTERM.
_stop_requested = False


def _request_stop(_signum: int | None = None, _frame: object | None = None) -> None:
    global _stop_requested
    _stop_requested = True
    print("\n[demo-live] stop requested — finishing current tick…")


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _next_tick(db) -> int:
    """Continue from the highest existing synthetic-* external_id suffix."""
    rows = db.scalars(
        select(Post.external_id).where(Post.source == "synthetic")
    ).all()
    max_tick = -1
    for external_id in rows:
        if not external_id or not external_id.startswith("synthetic-"):
            continue
        suffix = external_id.removeprefix("synthetic-")
        try:
            max_tick = max(max_tick, int(suffix))
        except ValueError:
            continue
    return max_tick + 1


def insert_synthetic_batch(*, tick_start: int, batch_size: int = 1) -> dict[str, int]:
    """
    Insert ``batch_size`` synthetic posts starting at ``tick_start``.

    Returns counts including the next tick to use.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be >= 1")

    init_db()
    db = SessionLocal()
    inserted = 0
    skipped = 0
    now = datetime.now(timezone.utc)

    try:
        for offset in range(batch_size):
            tick = tick_start + offset
            draft = build_synthetic_post(tick, now=now)

            exists = db.scalar(select(Post.id).where(Post.id == draft.id).limit(1))
            if exists is not None:
                skipped += 1
                continue

            # Also skip if the sequential external_id was already written.
            by_ext = db.scalar(
                select(Post.id).where(Post.external_id == draft.external_id).limit(1)
            )
            if by_ext is not None:
                skipped += 1
                continue

            db.add(
                Post(
                    id=draft.id,
                    source="synthetic",
                    external_id=draft.external_id,
                    title=draft.title,
                    content=draft.content,
                    url=draft.url,
                    published_at=draft.published_at,
                    organization_mentions=json.dumps([draft.organization]),
                    narrative_type=draft.narrative_type,
                    severity_score=0.0,
                    created_at=now,
                )
            )
            inserted += 1

        db.commit()

        if inserted > 0:
            publish_new_post(source="synthetic", inserted=inserted)
            publish_narratives_updated(reason="generate_live_demo")
            notify_api(EVENT_NEW_POST, source="synthetic", inserted=inserted)
            notify_api(EVENT_NARRATIVES_UPDATED, reason="generate_live_demo")

        return {
            "inserted": inserted,
            "skipped": skipped,
            "next_tick": tick_start + batch_size,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def run_live_demo(
    *,
    min_interval: int = 20,
    max_interval: int = 30,
    batch_size: int = 1,
    max_ticks: int | None = None,
    score_after_insert: bool = True,
) -> None:
    """
    Loop: insert synthetic posts → score → sleep 20–30s → repeat.

    Stops on Ctrl+C / SIGTERM, or after ``max_ticks`` iterations (tests).
    """
    global _stop_requested
    _stop_requested = False

    signal.signal(signal.SIGINT, _request_stop)
    signal.signal(signal.SIGTERM, _request_stop)

    init_db()
    db = SessionLocal()
    try:
        tick = _next_tick(db)
        total = db.scalar(
            select(func.count()).select_from(Post).where(Post.source == "synthetic")
        )
    finally:
        db.close()

    print(
        "[demo-live] starting — "
        f"tick={tick} existing_synthetic={total or 0} "
        f"interval={min_interval}-{max_interval}s batch={batch_size}"
    )
    print("[demo-live] press Ctrl+C to stop")

    iterations = 0
    while not _stop_requested:
        if max_ticks is not None and iterations >= max_ticks:
            break

        stats = insert_synthetic_batch(tick_start=tick, batch_size=batch_size)
        tick = stats["next_tick"]
        iterations += 1

        print(
            f"[demo-live] tick_batch inserted={stats['inserted']} "
            f"skipped={stats['skipped']} next_tick={tick}"
        )

        if score_after_insert and stats["inserted"] > 0:
            score_stats = score_posts()
            print(
                "[demo-live] scored — "
                f"posts={score_stats['posts_scored']} "
                f"alerts={score_stats['alerts_updated']}"
            )

        if _stop_requested:
            break
        if max_ticks is not None and iterations >= max_ticks:
            break

        sleep_for = interval_seconds_for_tick(
            tick - 1,
            min_seconds=min_interval,
            max_seconds=max_interval,
        )
        print(f"[demo-live] sleeping {sleep_for}s…")
        # Interruptible sleep so Ctrl+C feels responsive.
        deadline = time.monotonic() + sleep_for
        while not _stop_requested and time.monotonic() < deadline:
            time.sleep(min(0.5, deadline - time.monotonic()))

    print("[demo-live] stopped")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Optional demo-mode synthetic live post generator",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Insert one batch, score, and exit (no loop)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=_env_int("DEMO_LIVE_BATCH_SIZE", 1),
        help="Posts per tick (default 1; env DEMO_LIVE_BATCH_SIZE)",
    )
    parser.add_argument(
        "--min-interval",
        type=int,
        default=_env_int("DEMO_LIVE_INTERVAL_MIN", 20),
        help="Minimum seconds between ticks (default 20)",
    )
    parser.add_argument(
        "--max-interval",
        type=int,
        default=_env_int("DEMO_LIVE_INTERVAL_MAX", 30),
        help="Maximum seconds between ticks (default 30)",
    )
    parser.add_argument(
        "--no-score",
        action="store_true",
        help="Skip score_posts after insert (debug only)",
    )
    args = parser.parse_args(argv)

    if args.once:
        init_db()
        db = SessionLocal()
        try:
            tick = _next_tick(db)
        finally:
            db.close()
        stats = insert_synthetic_batch(tick_start=tick, batch_size=max(1, args.batch_size))
        print(f"[demo-live] once — {stats}")
        if not args.no_score and stats["inserted"] > 0:
            score_posts()
        return

    run_live_demo(
        min_interval=max(1, args.min_interval),
        max_interval=max(1, args.max_interval),
        batch_size=max(1, args.batch_size),
        score_after_insert=not args.no_score,
    )


if __name__ == "__main__":
    main()
