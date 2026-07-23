"""Tests for ingest status tracker and settings flags."""

from datetime import datetime, timezone

from app.core.config import Settings
from app.services.ingest_status import IngestStatusTracker


def test_live_ingest_env_flag_parsing() -> None:
    assert Settings(live_ingest_enabled="1").live_ingest_enabled is True
    assert Settings(live_ingest_enabled="true").live_ingest_enabled is True
    assert Settings(live_ingest_enabled="0").live_ingest_enabled is False
    assert Settings(live_ingest_enabled=False).live_ingest_enabled is False


def test_ingest_status_tracker_lifecycle() -> None:
    tracker = IngestStatusTracker()
    tracker.configure(enabled=True, interval_seconds=120)
    tracker.begin_run()
    snap = tracker.snapshot()
    assert snap["enabled"] is True
    assert snap["running"] is True
    assert snap["last_started_at"] is not None

    tracker.finish_run(
        ok=True,
        stats={"inserted": 2},
        score_stats={"posts_scored": 5, "alerts_upserted": 1},
        next_run_at=datetime(2026, 7, 23, 13, 0, tzinfo=timezone.utc),
    )
    snap = tracker.snapshot()
    assert snap["running"] is False
    assert snap["runs_completed"] == 1
    assert snap["last_stats"]["inserted"] == 2
    assert snap["last_score_stats"]["alerts_upserted"] == 1
    assert snap["last_error"] is None
    assert snap["next_run_at"] == "2026-07-23T13:00:00Z"


def test_ingest_status_records_errors() -> None:
    tracker = IngestStatusTracker()
    tracker.begin_run()
    tracker.finish_run(ok=False, error="feed timeout")
    snap = tracker.snapshot()
    assert snap["last_error"] == "feed timeout"
    assert snap["last_success_at"] is None
