"""Deterministic, explainable anomaly scoring (patterns + time windows)."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


# Score range is always 0-100.
RECENT_WINDOW_HOURS = 24
VERY_RECENT_WINDOW_HOURS = 6


@dataclass(frozen=True)
class PatternCounts:
    """Corpus-level frequency tables used for explainable scoring."""

    by_category: dict[str, int]
    by_organization: dict[str, int]
    by_category_org: dict[tuple[str, str], int]
    total_posts: int


@dataclass(frozen=True)
class TemporalOrgCounts:
    """Per-organization post counts inside recent time windows."""

    recent: dict[str, int]
    very_recent: dict[str, int]
    recent_hours: int = RECENT_WINDOW_HOURS
    very_recent_hours: int = VERY_RECENT_WINDOW_HOURS


@dataclass(frozen=True)
class AnomalyScore:
    """Explainable anomaly score for a single post."""

    score: float
    severity: str
    reasons: tuple[str, ...]
    category_count: int
    max_org_count: int
    max_category_org_count: int
    recent_hour_count: int = 0
    baseline_hourly_mean: float = 0.0
    recent_org_count: int = 0
    very_recent_org_count: int = 0


def severity_from_score(score: float) -> str:
    """Map a 0-100 score to a discrete severity label."""
    if score >= 85:
        return "critical"
    if score >= 70:
        return "high"
    if score >= 45:
        return "medium"
    return "low"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _hour_bucket(value: datetime) -> datetime:
    value = _as_utc(value)
    return value.replace(minute=0, second=0, microsecond=0)


def build_hourly_counts(timestamps: list[datetime | None]) -> dict[datetime, int]:
    """Count posts per UTC hour bucket."""
    counts: Counter[datetime] = Counter()
    for ts in timestamps:
        if ts is None:
            continue
        counts[_hour_bucket(ts)] += 1
    return dict(counts)


def build_pattern_counts(
    records: list[tuple[str | None, tuple[str, ...]]],
) -> PatternCounts:
    """
    Build frequency tables from (narrative_type, organizations) records.

    ``narrative_type`` may be None/empty for unclassified posts.
    """
    by_category: Counter[str] = Counter()
    by_organization: Counter[str] = Counter()
    by_category_org: Counter[tuple[str, str]] = Counter()

    for narrative_type, organizations in records:
        category = (narrative_type or "").strip()
        orgs = tuple(sorted({org.strip() for org in organizations if org and org.strip()}))

        if category:
            by_category[category] += 1
        for org in orgs:
            by_organization[org] += 1
            if category:
                by_category_org[(category, org)] += 1

    return PatternCounts(
        by_category=dict(by_category),
        by_organization=dict(by_organization),
        by_category_org=dict(by_category_org),
        total_posts=len(records),
    )


def build_temporal_org_counts(
    records: list[tuple[tuple[str, ...], datetime | None]],
    *,
    now: datetime,
    recent_hours: int = RECENT_WINDOW_HOURS,
    very_recent_hours: int = VERY_RECENT_WINDOW_HOURS,
) -> TemporalOrgCounts:
    """
    Count organization mentions inside recent and very-recent windows.

    ``records`` are (organizations, timestamp) pairs. Missing timestamps are skipped.
    """
    now = _as_utc(now)
    recent_cutoff = now - timedelta(hours=recent_hours)
    very_recent_cutoff = now - timedelta(hours=very_recent_hours)

    recent: Counter[str] = Counter()
    very_recent: Counter[str] = Counter()

    for organizations, timestamp in records:
        if timestamp is None:
            continue
        ts = _as_utc(timestamp)
        orgs = {org.strip() for org in organizations if org and org.strip()}
        if not orgs:
            continue

        if ts >= recent_cutoff:
            for org in orgs:
                recent[org] += 1
        if ts >= very_recent_cutoff:
            for org in orgs:
                very_recent[org] += 1

    return TemporalOrgCounts(
        recent=dict(recent),
        very_recent=dict(very_recent),
        recent_hours=recent_hours,
        very_recent_hours=very_recent_hours,
    )


def score_time_burst(
    *,
    published_at: datetime | None,
    hourly_counts: dict[datetime, int],
    lookback_hours: int = 24,
) -> tuple[float, tuple[str, ...], int, float]:
    """
    Score a volume spike versus the mean of prior hours (0-20 points).

    Compares the post's hour count to the mean of the previous ``lookback_hours``.
    """
    if published_at is None or not hourly_counts:
        return 0.0, ("No usable timestamp for time-based scoring",), 0, 0.0

    bucket = _hour_bucket(published_at)
    recent_count = hourly_counts.get(bucket, 0)

    baseline_values: list[int] = []
    for offset in range(1, lookback_hours + 1):
        prior = bucket - timedelta(hours=offset)
        if prior in hourly_counts:
            baseline_values.append(hourly_counts[prior])

    if not baseline_values:
        if recent_count >= 3:
            boost = min(12.0, 3.0 * (recent_count - 2))
            return (
                round(boost, 2),
                (f"Hourly volume {recent_count} with no prior baseline (+{boost:.1f})",),
                recent_count,
                0.0,
            )
        return 0.0, ("Insufficient baseline hours for time-based scoring",), recent_count, 0.0

    baseline_mean = sum(baseline_values) / len(baseline_values)
    if baseline_mean <= 0:
        return 0.0, ("Baseline hourly mean is zero",), recent_count, 0.0

    ratio = recent_count / baseline_mean
    if ratio < 1.5:
        return (
            0.0,
            (
                f"Hourly volume {recent_count} near baseline mean "
                f"{baseline_mean:.2f} (ratio {ratio:.2f})",
            ),
            recent_count,
            round(baseline_mean, 4),
        )

    # Map 1.5x-4x into roughly 5-20 points.
    boost = min(20.0, 5.0 + 5.0 * (ratio - 1.5))
    return (
        round(boost, 2),
        (
            f"Hourly volume {recent_count} is {ratio:.2f}x the "
            f"{lookback_hours}h baseline mean {baseline_mean:.2f} (+{boost:.1f})",
        ),
        recent_count,
        round(baseline_mean, 4),
    )


def score_org_recency(
    *,
    organizations: tuple[str, ...] | list[str],
    temporal: TemporalOrgCounts,
) -> tuple[float, tuple[str, ...], int, int]:
    """
    Reward organizations with multiple posts in recent windows (0-25 points).

    - Very recent window (default 6h): stronger signal
    - Recent window (default 24h): supporting signal
    """
    orgs = tuple(sorted({org.strip() for org in organizations if org and org.strip()}))
    if not orgs:
        return 0.0, ("No organizations available for recency scoring",), 0, 0

    top_recent_org = max(orgs, key=lambda org: temporal.recent.get(org, 0))
    top_very_recent_org = max(orgs, key=lambda org: temporal.very_recent.get(org, 0))
    recent_count = temporal.recent.get(top_recent_org, 0)
    very_recent_count = temporal.very_recent.get(top_very_recent_org, 0)

    boost = 0.0
    reasons: list[str] = []

    if very_recent_count >= 2:
        very_recent_boost = min(15.0, 5.0 * (very_recent_count - 1))
        boost += very_recent_boost
        reasons.append(
            f"Organization '{top_very_recent_org}' appears in {very_recent_count} posts "
            f"in the last {temporal.very_recent_hours}h (+{very_recent_boost:.1f})"
        )
    elif orgs:
        reasons.append(
            f"No multi-post burst for tagged orgs in the last {temporal.very_recent_hours}h"
        )

    if recent_count >= 2:
        recent_boost = min(10.0, 3.0 * (recent_count - 1))
        boost += recent_boost
        reasons.append(
            f"Organization '{top_recent_org}' appears in {recent_count} posts "
            f"in the last {temporal.recent_hours}h (+{recent_boost:.1f})"
        )
    elif orgs and very_recent_count < 2:
        reasons.append(
            f"No multi-post activity for tagged orgs in the last {temporal.recent_hours}h"
        )

    return round(boost, 2), tuple(reasons), recent_count, very_recent_count


def score_post_anomaly(
    *,
    narrative_type: str | None,
    organizations: tuple[str, ...] | list[str],
    counts: PatternCounts,
    prior_severity_score: float = 0.0,
    published_at: datetime | None = None,
    hourly_counts: dict[datetime, int] | None = None,
    lookback_hours: int = 24,
    temporal_org_counts: TemporalOrgCounts | None = None,
) -> AnomalyScore:
    """
    Score a post on a 0-100 scale from patterns, hourly burst, and org recency.

    Components (approximate caps):
    - prior seed contribution: 0-10
    - repeated category / org / combo patterns: 0-60
    - hourly volume burst: 0-20
    - org recent + very-recent activity: 0-25
    """
    category = (narrative_type or "").strip()
    orgs = tuple(sorted({org.strip() for org in organizations if org and org.strip()}))

    category_count = counts.by_category.get(category, 0) if category else 0
    org_counts = [counts.by_organization.get(org, 0) for org in orgs]
    max_org_count = max(org_counts) if org_counts else 0
    category_org_counts = [
        counts.by_category_org.get((category, org), 0) for org in orgs if category
    ]
    max_category_org_count = max(category_org_counts) if category_org_counts else 0

    # Accept legacy 0-1 priors or new 0-100 priors.
    prior = max(0.0, float(prior_severity_score))
    if prior <= 1.0:
        prior *= 100.0
    score = min(10.0, prior * 0.10)
    reasons: list[str] = []

    if category and category_count >= 2:
        category_boost = min(25.0, 6.0 * (category_count - 1))
        score += category_boost
        reasons.append(
            f"Category '{category}' appears in {category_count} posts "
            f"(+{category_boost:.1f})"
        )
    elif category:
        reasons.append(f"Category '{category}' appears only once in the corpus")

    if max_org_count >= 2:
        org_boost = min(20.0, 7.0 * (max_org_count - 1))
        score += org_boost
        top_org = max(orgs, key=lambda org: counts.by_organization.get(org, 0))
        reasons.append(
            f"Organization '{top_org}' appears in {max_org_count} posts "
            f"(+{org_boost:.1f})"
        )
    elif orgs:
        reasons.append(f"Organization mention(s) are rare in the corpus: {', '.join(orgs)}")

    if max_category_org_count >= 2:
        combo_boost = min(15.0, 8.0 * (max_category_org_count - 1))
        score += combo_boost
        top_pair_org = max(
            orgs,
            key=lambda org: counts.by_category_org.get((category, org), 0),
        )
        reasons.append(
            f"Repeated '{category}' + '{top_pair_org}' pattern in "
            f"{max_category_org_count} posts (+{combo_boost:.1f})"
        )

    recent_hour_count = 0
    baseline_hourly_mean = 0.0
    if hourly_counts is not None:
        time_boost, time_reasons, recent_hour_count, baseline_hourly_mean = score_time_burst(
            published_at=published_at,
            hourly_counts=hourly_counts,
            lookback_hours=lookback_hours,
        )
        score += time_boost
        reasons.extend(time_reasons)

    recent_org_count = 0
    very_recent_org_count = 0
    if temporal_org_counts is not None:
        recency_boost, recency_reasons, recent_org_count, very_recent_org_count = (
            score_org_recency(
                organizations=orgs,
                temporal=temporal_org_counts,
            )
        )
        score += recency_boost
        reasons.extend(recency_reasons)

    if not reasons:
        reasons.append("No repeated category/organization pattern detected")

    final_score = round(min(100.0, max(0.0, score)), 2)
    return AnomalyScore(
        score=final_score,
        severity=severity_from_score(final_score),
        reasons=tuple(reasons),
        category_count=category_count,
        max_org_count=max_org_count,
        max_category_org_count=max_category_org_count,
        recent_hour_count=recent_hour_count,
        baseline_hourly_mean=baseline_hourly_mean,
        recent_org_count=recent_org_count,
        very_recent_org_count=very_recent_org_count,
    )
