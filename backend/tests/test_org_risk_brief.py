"""Tests for deterministic organization risk briefs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.org_risk_brief import build_organization_risk_brief


class _Post:
    def __init__(
        self,
        *,
        post_id: str,
        title: str,
        source: str,
        narrative_type: str | None,
        score: float,
        hours_ago: float,
        cve_ids: str = "[]",
        url: str | None = "https://example.com/p",
    ) -> None:
        now = datetime(2026, 7, 23, 15, 0, tzinfo=timezone.utc)
        self.id = post_id
        self.title = title
        self.source = source
        self.url = url
        self.narrative_type = narrative_type
        self.severity_score = score
        self.published_at = now - timedelta(hours=hours_ago)
        self.created_at = self.published_at
        self.cve_ids = cve_ids


class _Alert:
    def __init__(self, severity: str = "high", score: float = 72.0) -> None:
        self.id = "a1"
        self.title = "Test alert"
        self.narrative_type = "Ransomware"
        self.severity = severity
        self.score = score
        self.summary = "test"


def test_risk_brief_elevates_on_volume_and_score() -> None:
    now = datetime(2026, 7, 23, 15, 0, tzinfo=timezone.utc)
    posts = [
        _Post(
            post_id="p1",
            title="Acme ransomware",
            source="rss",
            narrative_type="Ransomware",
            score=80,
            hours_ago=1,
            cve_ids='["CVE-2024-1111"]',
        ),
        _Post(
            post_id="p2",
            title="Acme follow-up",
            source="reddit",
            narrative_type="Ransomware",
            score=70,
            hours_ago=2,
        ),
        _Post(
            post_id="p3",
            title="Older baseline",
            source="rss",
            narrative_type="Phishing / social engineering",
            score=20,
            hours_ago=48,
        ),
    ]
    brief = build_organization_risk_brief(
        organization_name="Acme Logistics",
        organization_slug="acme-logistics",
        sector="Transportation",
        posts=posts,
        alerts=[_Alert()],
        now=now,
    )
    assert brief.volume_24h == 2
    assert brief.baseline_7d_daily_avg >= 1.0
    assert brief.volume_ratio >= 1.0
    assert brief.risk_level in {"medium", "high", "critical"}
    assert brief.cve_ids == ("CVE-2024-1111",)
    assert brief.open_alert_count == 1
    assert len(brief.evidence) >= 1
    assert "Acme Logistics" in brief.executive_summary
    assert brief.caveats


def test_risk_brief_empty_org() -> None:
    now = datetime(2026, 7, 23, 15, 0, tzinfo=timezone.utc)
    brief = build_organization_risk_brief(
        organization_name="Empty Co",
        organization_slug="empty-co",
        sector="Technology",
        posts=[],
        alerts=[],
        now=now,
    )
    assert brief.risk_level == "low"
    assert brief.volume_24h == 0
    assert brief.volume_ratio == 0.0
    assert brief.evidence == ()
