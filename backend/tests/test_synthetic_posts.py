"""Tests for deterministic synthetic demo post generation."""

from datetime import datetime, timezone

from app.services.synthetic_posts import (
    SYNTHETIC_SCENARIOS,
    build_synthetic_post,
    interval_seconds_for_tick,
)


def test_build_synthetic_post_is_deterministic() -> None:
    now = datetime(2026, 7, 22, 15, 0, 0, tzinfo=timezone.utc)
    a = build_synthetic_post(3, now=now)
    b = build_synthetic_post(3, now=now)
    assert a == b
    assert a.external_id == "synthetic-000003"
    assert a.id.startswith("syn-")
    assert a.url.endswith(a.external_id)
    assert a.organization
    assert a.narrative_type


def test_build_synthetic_post_cycles_scenarios() -> None:
    now = datetime(2026, 7, 22, 15, 0, 0, tzinfo=timezone.utc)
    first = build_synthetic_post(0, now=now)
    wrapped = build_synthetic_post(len(SYNTHETIC_SCENARIOS), now=now)
    assert first.organization == wrapped.organization
    assert first.narrative_type == wrapped.narrative_type
    assert "demo wave 1" in first.title
    assert "demo wave 2" in wrapped.title


def test_interval_seconds_stay_in_range() -> None:
    for tick in range(40):
        value = interval_seconds_for_tick(tick, min_seconds=20, max_seconds=30)
        assert 20 <= value <= 30


def test_synthetic_posts_use_known_watchlist_orgs() -> None:
    orgs = {item["organization"] for item in SYNTHETIC_SCENARIOS}
    assert orgs == {"Acme Logistics", "Nova Bank", "Helix Cloud"}
