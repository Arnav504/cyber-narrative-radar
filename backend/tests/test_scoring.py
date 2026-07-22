"""Tests for deterministic time-aware anomaly scoring (0-100)."""

from datetime import datetime, timedelta, timezone

from app.analytics.scoring import (
    build_hourly_counts,
    build_pattern_counts,
    build_temporal_org_counts,
    score_org_recency,
    score_post_anomaly,
    score_time_burst,
    severity_from_score,
)


def test_severity_thresholds() -> None:
    assert severity_from_score(90) == "critical"
    assert severity_from_score(72) == "high"
    assert severity_from_score(50) == "medium"
    assert severity_from_score(20) == "low"


def test_score_stays_within_0_to_100() -> None:
    now = datetime(2026, 7, 20, 15, 0, tzinfo=timezone.utc)
    records = [("Ransomware", ("Acme Logistics",))] * 8
    counts = build_pattern_counts(records)
    timestamps = [now] * 6 + [now - timedelta(hours=i) for i in range(1, 9)]
    hourly = build_hourly_counts(timestamps)
    temporal = build_temporal_org_counts(
        [(("Acme Logistics",), ts) for ts in timestamps],
        now=now,
    )

    result = score_post_anomaly(
        narrative_type="Ransomware",
        organizations=("Acme Logistics",),
        counts=counts,
        prior_severity_score=100,
        published_at=now,
        hourly_counts=hourly,
        temporal_org_counts=temporal,
    )
    assert 0 <= result.score <= 100


def test_repeated_category_and_org_raises_score() -> None:
    records = [
        ("Ransomware", ("Acme Logistics",)),
        ("Ransomware", ("Acme Logistics",)),
        ("Ransomware", ("Acme Logistics",)),
        ("Phishing / social engineering", ("Nova Bank",)),
    ]
    counts = build_pattern_counts(records)

    burst = score_post_anomaly(
        narrative_type="Ransomware",
        organizations=("Acme Logistics",),
        counts=counts,
    )
    rare = score_post_anomaly(
        narrative_type="Phishing / social engineering",
        organizations=("Nova Bank",),
        counts=counts,
    )

    assert burst.score > rare.score
    assert burst.category_count == 3
    assert any("Ransomware" in reason for reason in burst.reasons)


def test_time_burst_boosts_busy_hour() -> None:
    now = datetime(2026, 7, 20, 15, 0, tzinfo=timezone.utc)
    timestamps = [now - timedelta(hours=offset) for offset in range(1, 9)]
    timestamps.extend([now] * 5)
    hourly = build_hourly_counts(timestamps)

    boost, reasons, recent, baseline = score_time_burst(
        published_at=now,
        hourly_counts=hourly,
        lookback_hours=8,
    )
    assert recent == 5
    assert baseline == 1.0
    assert boost > 0
    assert any("baseline" in reason for reason in reasons)


def test_recent_and_very_recent_org_windows() -> None:
    now = datetime(2026, 7, 20, 18, 0, tzinfo=timezone.utc)
    records = [
        (("Acme Logistics",), now - timedelta(hours=1)),
        (("Acme Logistics",), now - timedelta(hours=2)),
        (("Acme Logistics",), now - timedelta(hours=3)),
        (("Acme Logistics",), now - timedelta(hours=12)),
        (("Nova Bank",), now - timedelta(hours=30)),
    ]
    temporal = build_temporal_org_counts(records, now=now)

    assert temporal.very_recent["Acme Logistics"] == 3
    assert temporal.recent["Acme Logistics"] == 4
    assert "Nova Bank" not in temporal.recent

    boost, reasons, recent_count, very_recent_count = score_org_recency(
        organizations=("Acme Logistics",),
        temporal=temporal,
    )
    assert recent_count == 4
    assert very_recent_count == 3
    assert boost > 0
    assert any("6h" in reason for reason in reasons)
    assert any("24h" in reason for reason in reasons)


def test_multiple_recent_posts_raise_score_vs_single() -> None:
    now = datetime(2026, 7, 20, 18, 0, tzinfo=timezone.utc)
    counts = build_pattern_counts(
        [
            ("Ransomware", ("Acme Logistics",)),
            ("Ransomware", ("Acme Logistics",)),
        ]
    )

    multi_temporal = build_temporal_org_counts(
        [
            (("Acme Logistics",), now - timedelta(hours=1)),
            (("Acme Logistics",), now - timedelta(hours=2)),
            (("Acme Logistics",), now - timedelta(hours=3)),
        ],
        now=now,
    )
    single_temporal = build_temporal_org_counts(
        [(("Acme Logistics",), now - timedelta(hours=1))],
        now=now,
    )

    multi = score_post_anomaly(
        narrative_type="Ransomware",
        organizations=("Acme Logistics",),
        counts=counts,
        published_at=now,
        temporal_org_counts=multi_temporal,
    )
    single = score_post_anomaly(
        narrative_type="Ransomware",
        organizations=("Acme Logistics",),
        counts=counts,
        published_at=now,
        temporal_org_counts=single_temporal,
    )

    assert multi.score > single.score
    assert multi.very_recent_org_count >= 2
    assert any("last 6h" in reason for reason in multi.reasons)


def test_time_aware_score_is_deterministic() -> None:
    now = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
    records = [("Data breach", ("Helix Cloud",)), ("Data breach", ("Helix Cloud",))]
    counts = build_pattern_counts(records)
    hourly = build_hourly_counts([now, now, now - timedelta(hours=1)])
    temporal = build_temporal_org_counts(
        [
            (("Helix Cloud",), now),
            (("Helix Cloud",), now - timedelta(hours=1)),
        ],
        now=now,
    )

    first = score_post_anomaly(
        narrative_type="Data breach",
        organizations=["Helix Cloud"],
        counts=counts,
        published_at=now,
        hourly_counts=hourly,
        temporal_org_counts=temporal,
    )
    second = score_post_anomaly(
        narrative_type="Data breach",
        organizations=["Helix Cloud"],
        counts=counts,
        published_at=now,
        hourly_counts=hourly,
        temporal_org_counts=temporal,
    )
    assert first == second
    assert 0 <= first.score <= 100
