"""Tests for auto-alert upserts from scored posts."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.analytics.scoring import AnomalyScore
from app.db.base import Base
from app.db.models import Alert, AlertEvidence, Organization, Post
from app.services.auto_alerts import auto_alert_id, upsert_alerts_from_scored_posts


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _score(value: float, severity: str = "medium") -> AnomalyScore:
    return AnomalyScore(
        score=value,
        severity=severity,
        reasons=(f"Score {value}",),
        category_count=2,
        max_org_count=2,
        max_category_org_count=2,
    )


def test_auto_alert_id_is_stable() -> None:
    assert auto_alert_id("Acme Logistics", "Ransomware") == auto_alert_id(
        "acme logistics", "ransomware"
    )


def test_upsert_creates_alert_with_evidence() -> None:
    db = _session()
    now = datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)
    db.add(
        Organization(
            id="org-acme",
            name="Acme Logistics",
            sector="Transportation",
            tickers="[]",
        )
    )
    post = Post(
        id="post-r1",
        source="rss",
        title="Acme Logistics ransomware chatter",
        content="ransomware lockbit",
        published_at=now,
        organization_mentions=json.dumps(["Acme Logistics"]),
        narrative_type="Ransomware",
        severity_score=72.0,
        created_at=now,
    )
    db.add(post)
    db.commit()

    stats = upsert_alerts_from_scored_posts(
        db,
        [post],
        {"post-r1": _score(72.0, "high")},
        min_score=45.0,
    )
    db.commit()

    assert stats["alerts_upserted"] == 1
    assert stats["evidence_links"] == 1

    alert_id = auto_alert_id("Acme Logistics", "Ransomware")
    alert = db.get(Alert, alert_id)
    assert alert is not None
    assert alert.organization_name == "Acme Logistics"
    assert alert.severity == "high"
    assert alert.score == 72.0
    evidence = list(db.scalars(select(AlertEvidence).where(AlertEvidence.alert_id == alert_id)))
    assert len(evidence) == 1
    assert evidence[0].post_id == "post-r1"


def test_upsert_skips_below_threshold() -> None:
    db = _session()
    now = datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)
    post = Post(
        id="post-low",
        source="rss",
        title="Quiet mention",
        content="note",
        published_at=now,
        organization_mentions=json.dumps(["Acme Logistics"]),
        narrative_type="Ransomware",
        severity_score=10.0,
        created_at=now,
    )
    db.add(post)
    db.commit()

    stats = upsert_alerts_from_scored_posts(
        db,
        [post],
        {"post-low": _score(10.0, "low")},
        min_score=45.0,
    )
    assert stats["alerts_upserted"] == 0
    assert db.scalar(select(Alert.id).limit(1)) is None


def test_upsert_refreshes_same_alert() -> None:
    db = _session()
    now = datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)
    p1 = Post(
        id="post-a",
        source="rss",
        title="First",
        content="ransomware",
        published_at=now,
        organization_mentions=json.dumps(["Nova Bank"]),
        narrative_type="Ransomware",
        severity_score=50.0,
        created_at=now,
    )
    p2 = Post(
        id="post-b",
        source="rss",
        title="Second",
        content="ransomware stronger",
        published_at=now,
        organization_mentions=json.dumps(["Nova Bank"]),
        narrative_type="Ransomware",
        severity_score=80.0,
        created_at=now,
    )
    db.add_all([p1, p2])
    db.commit()

    upsert_alerts_from_scored_posts(
        db, [p1], {"post-a": _score(50.0)}, min_score=45.0
    )
    db.commit()
    alert_id = auto_alert_id("Nova Bank", "Ransomware")
    assert db.get(Alert, alert_id) is not None

    upsert_alerts_from_scored_posts(
        db,
        [p1, p2],
        {"post-a": _score(50.0), "post-b": _score(80.0, "high")},
        min_score=45.0,
    )
    db.commit()

    alert = db.get(Alert, alert_id)
    assert alert is not None
    assert alert.score == 80.0
    evidence = list(db.scalars(select(AlertEvidence).where(AlertEvidence.alert_id == alert_id)))
    assert len(evidence) == 2
