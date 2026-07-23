"""Deterministic organization risk brief for analyst / portfolio demos."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from app.analytics.cve import parse_cve_ids_json
from app.analytics.scoring import severity_from_score


class PostLike(Protocol):
    id: str
    title: str
    source: str
    url: str | None
    narrative_type: str | None
    severity_score: float
    published_at: datetime | None
    created_at: datetime | None
    cve_ids: str


class AlertLike(Protocol):
    id: str
    title: str
    narrative_type: str
    severity: str
    score: float
    summary: str


@dataclass(frozen=True)
class EvidenceLink:
    id: str
    title: str
    source: str
    url: str | None
    published_at: str | None
    severity_score: float
    cve_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class NarrativeShare:
    narrative_type: str
    count: int
    share: float


@dataclass(frozen=True)
class OrganizationRiskBrief:
    """One-page, explainable risk brief for a watchlist organization."""

    organization_name: str
    organization_slug: str
    sector: str
    risk_level: str
    risk_score_0_100: float
    executive_summary: str
    volume_24h: int
    baseline_7d_daily_avg: float
    volume_ratio: float
    top_narratives: tuple[NarrativeShare, ...]
    open_alert_count: int
    highest_alert_severity: str | None
    cve_ids: tuple[str, ...]
    evidence: tuple[EvidenceLink, ...]
    caveats: tuple[str, ...]
    generated_at: str


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


def _post_ts(post: PostLike) -> datetime | None:
    return _as_utc(post.published_at or post.created_at)


def build_organization_risk_brief(
    *,
    organization_name: str,
    organization_slug: str,
    sector: str,
    posts: list[PostLike],
    alerts: list[AlertLike],
    now: datetime | None = None,
    evidence_limit: int = 5,
) -> OrganizationRiskBrief:
    """
    Build an explainable org risk brief from related posts and alerts.

    Volume ratio compares last-24h post count to the mean daily count over the
    prior 7 days (excluding the current day). Risk combines volume pressure and
    max post/alert scores — no LLM.
    """
    clock = _as_utc(now) or datetime.now(timezone.utc)
    window_24h = clock - timedelta(hours=24)
    window_7d = clock - timedelta(days=7)

    volume_24h = 0
    prior_day_counts: Counter[str] = Counter()
    narrative_counts: Counter[str] = Counter()
    cve_set: set[str] = set()
    max_post_score = 0.0

    for post in posts:
        ts = _post_ts(post)
        score = float(getattr(post, "severity_score", 0.0) or 0.0)
        max_post_score = max(max_post_score, score)
        narrative = (post.narrative_type or "").strip()
        if narrative:
            narrative_counts[narrative] += 1
        for cve in parse_cve_ids_json(getattr(post, "cve_ids", None)):
            cve_set.add(cve)
        if ts is None:
            continue
        if ts >= window_24h:
            volume_24h += 1
        if window_7d <= ts < window_24h:
            prior_day_counts[ts.date().isoformat()] += 1

    if prior_day_counts:
        baseline = sum(prior_day_counts.values()) / max(len(prior_day_counts), 1)
    else:
        baseline = 0.0

    if baseline > 0:
        volume_ratio = round(volume_24h / baseline, 2)
    elif volume_24h > 0:
        volume_ratio = float(volume_24h)
    else:
        volume_ratio = 0.0

    total_posts = len(posts)
    top_narratives: list[NarrativeShare] = []
    for label, count in sorted(
        narrative_counts.items(),
        key=lambda item: (-item[1], item[0].casefold()),
    )[:4]:
        share = (count / total_posts) if total_posts else 0.0
        top_narratives.append(
            NarrativeShare(narrative_type=label, count=count, share=round(share, 4))
        )

    max_alert_score = max((float(a.score or 0.0) for a in alerts), default=0.0)
    # Alerts may still be on 0-1 in seed data — normalize lightly.
    if max_alert_score <= 1.0 and max_alert_score > 0:
        max_alert_score *= 100.0

    combined = max(max_post_score, max_alert_score)
    # Volume pressure: modest boost when chatter is elevated vs baseline.
    if volume_ratio >= 3:
        combined = min(100.0, combined + 12)
    elif volume_ratio >= 2:
        combined = min(100.0, combined + 8)
    elif volume_ratio >= 1.5:
        combined = min(100.0, combined + 4)

    risk_level = severity_from_score(combined)
    highest_alert_severity = None
    if alerts:
        order = {"critical": 3, "high": 2, "medium": 1, "low": 0}
        best = max(alerts, key=lambda a: order.get((a.severity or "").lower(), -1))
        highest_alert_severity = best.severity

    ranked_posts = sorted(
        posts,
        key=lambda p: (
            float(getattr(p, "severity_score", 0.0) or 0.0),
            _iso(_post_ts(p)) or "",
        ),
        reverse=True,
    )
    evidence = tuple(
        EvidenceLink(
            id=post.id,
            title=post.title,
            source=post.source,
            url=post.url,
            published_at=_iso(_post_ts(post)),
            severity_score=round(float(post.severity_score or 0.0), 2),
            cve_ids=parse_cve_ids_json(getattr(post, "cve_ids", None)),
        )
        for post in ranked_posts[:evidence_limit]
    )

    caveats: list[str] = [
        "Brief uses public/synthetic posts only — not confirmed incident status.",
        "Scores are deterministic pattern/time signals, not CVSS exploitability.",
    ]
    if volume_24h == 0:
        caveats.append("No posts in the last 24 hours for this organization.")
    if baseline <= 0 and volume_24h > 0:
        caveats.append("Baseline is thin; volume ratio may overstate novelty.")

    top_label = top_narratives[0].narrative_type if top_narratives else "unclassified chatter"
    exec_bits = [
        f"{organization_name} ({sector or 'Unknown sector'}) is assessed "
        f"{risk_level} risk ({combined:.0f}/100).",
        f"Last 24h volume: {volume_24h} vs ~{baseline:.1f}/day baseline "
        f"(ratio {volume_ratio:.2f}x).",
        f"Dominant narrative: {top_label}.",
    ]
    if alerts:
        exec_bits.append(f"{len(alerts)} linked alert(s) on the watchlist.")
    if cve_set:
        exec_bits.append(f"CVE mentions: {', '.join(sorted(cve_set)[:5])}.")

    return OrganizationRiskBrief(
        organization_name=organization_name,
        organization_slug=organization_slug,
        sector=sector,
        risk_level=risk_level,
        risk_score_0_100=round(combined, 2),
        executive_summary=" ".join(exec_bits),
        volume_24h=volume_24h,
        baseline_7d_daily_avg=round(baseline, 2),
        volume_ratio=volume_ratio,
        top_narratives=tuple(top_narratives),
        open_alert_count=len(alerts),
        highest_alert_severity=highest_alert_severity,
        cve_ids=tuple(sorted(cve_set)),
        evidence=evidence,
        caveats=tuple(caveats),
        generated_at=_iso(clock) or "",
    )


def risk_brief_to_dict(brief: OrganizationRiskBrief) -> dict[str, Any]:
    """Serialize a brief for API responses."""
    return {
        "organization_name": brief.organization_name,
        "organization_slug": brief.organization_slug,
        "sector": brief.sector,
        "risk_level": brief.risk_level,
        "risk_score_0_100": brief.risk_score_0_100,
        "executive_summary": brief.executive_summary,
        "volume_24h": brief.volume_24h,
        "baseline_7d_daily_avg": brief.baseline_7d_daily_avg,
        "volume_ratio": brief.volume_ratio,
        "top_narratives": [
            {
                "narrative_type": item.narrative_type,
                "count": item.count,
                "share": item.share,
            }
            for item in brief.top_narratives
        ],
        "open_alert_count": brief.open_alert_count,
        "highest_alert_severity": brief.highest_alert_severity,
        "cve_ids": list(brief.cve_ids),
        "evidence": [
            {
                "id": item.id,
                "title": item.title,
                "source": item.source,
                "url": item.url,
                "published_at": item.published_at,
                "severity_score": item.severity_score,
                "cve_ids": list(item.cve_ids),
            }
            for item in brief.evidence
        ],
        "caveats": list(brief.caveats),
        "generated_at": brief.generated_at,
    }
