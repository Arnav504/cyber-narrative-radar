"""Score local posts from patterns, hourly bursts, and org recency windows."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.analytics.scoring import (
    AnomalyScore,
    build_hourly_counts,
    build_pattern_counts,
    build_temporal_org_counts,
    score_post_anomaly,
)
from app.db.models import Alert, Post
from app.db.session import SessionLocal, init_db


def _parse_organizations(raw: str) -> tuple[str, ...]:
    try:
        value = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return ()
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value if str(item).strip())


def _alert_score_from_posts(post_scores: list[AnomalyScore]) -> AnomalyScore | None:
    if not post_scores:
        return None
    return max(post_scores, key=lambda item: item.score)


def score_posts(*, lookback_hours: int = 24) -> dict[str, int]:
    """
    Recompute post severity scores (0-100) and sync linked alert score/severity.

    Combines repeated category/org patterns, hourly volume bursts, and
    recent / very-recent organization activity windows.
    """
    init_db()
    db = SessionLocal()
    stats = {"posts_scored": 0, "alerts_updated": 0}
    now = datetime.now(timezone.utc)

    try:
        posts = list(db.scalars(select(Post)).all())
        records = [
            (post.narrative_type, _parse_organizations(post.organization_mentions))
            for post in posts
        ]
        counts = build_pattern_counts(records)
        timestamps = [post.published_at or post.created_at for post in posts]
        hourly_counts = build_hourly_counts(timestamps)
        temporal_org_counts = build_temporal_org_counts(
            [
                (_parse_organizations(post.organization_mentions), ts)
                for post, ts in zip(posts, timestamps, strict=True)
            ],
            now=now,
        )

        scored_by_id: dict[str, AnomalyScore] = {}
        for post in posts:
            result = score_post_anomaly(
                narrative_type=post.narrative_type,
                organizations=_parse_organizations(post.organization_mentions),
                counts=counts,
                prior_severity_score=0.0,
                published_at=post.published_at or post.created_at,
                hourly_counts=hourly_counts,
                lookback_hours=lookback_hours,
                temporal_org_counts=temporal_org_counts,
            )
            post.severity_score = result.score
            scored_by_id[post.id] = result
            stats["posts_scored"] += 1

        alerts = list(
            db.scalars(
                select(Alert).options(
                    selectinload(Alert.evidence),
                )
            )
            .unique()
            .all()
        )

        for alert in alerts:
            evidence_scores = [
                scored_by_id[item.post_id]
                for item in alert.evidence
                if item.post_id and item.post_id in scored_by_id
            ]
            best = _alert_score_from_posts(evidence_scores)
            if best is None:
                continue

            alert.score = best.score
            alert.severity = best.severity

            existing_reasons: list[str] = []
            try:
                parsed = json.loads(alert.why_flagged or "[]")
                if isinstance(parsed, list):
                    existing_reasons = [str(item) for item in parsed]
            except json.JSONDecodeError:
                existing_reasons = []

            merged = list(existing_reasons)
            for reason in best.reasons:
                if reason not in merged:
                    merged.append(reason)
            alert.why_flagged = json.dumps(merged)
            stats["alerts_updated"] += 1

        db.commit()
        print(
            "[score] done — "
            f"posts_scored={stats['posts_scored']} "
            f"alerts_updated={stats['alerts_updated']} "
            f"lookback_hours={lookback_hours}"
        )
        return stats
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    score_posts()
