"""Organization routes with list, slug drilldown, and timeseries."""

from __future__ import annotations

import json
import re
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import models
from app.db.session import get_db
from app.services.organization_summary import build_organization_summary

router = APIRouter(prefix="/organizations", tags=["organizations"])


class Organization(BaseModel):
    """Watchlist organization with narrative activity summary."""

    id: str
    slug: str
    name: str
    sector: str
    tickers: list[str] = Field(default_factory=list)
    alert_count: int
    top_narrative_types: list[str]
    risk_score: float
    post_count: int = 0
    max_score: float = 0.0


class RelatedPost(BaseModel):
    """Post linked to an organization drilldown."""

    id: str
    title: str
    source: str
    url: str | None = None
    narrative_type: str | None = None
    severity_score: float = 0.0
    published_at: str | None = None


class RelatedAlert(BaseModel):
    """Alert linked to an organization drilldown."""

    id: str
    title: str
    narrative_type: str
    severity: str
    score: float
    summary: str


class OrganizationActivitySummary(BaseModel):
    """Deterministic summary derived from related posts."""

    top_category: str | None = None
    top_source: str | None = None
    summary: str
    post_count: int = Field(ge=0, default=0)


class OrganizationDetail(BaseModel):
    """Organization drilldown with related posts, alerts, and summary."""

    organization: Organization
    related_posts: list[RelatedPost]
    related_alerts: list[RelatedAlert]
    summary: OrganizationActivitySummary


class TimeseriesPoint(BaseModel):
    """Daily activity bucket for one organization."""

    date: str
    count: int = Field(ge=0)
    max_score: float = 0.0


class OrganizationTimeseries(BaseModel):
    """Simple daily timeseries for organization drilldown charts."""

    organization_slug: str
    organization_name: str
    total_posts: int
    points: list[TimeseriesPoint]


def _parse_string_list(raw: str) -> list[str]:
    try:
        value = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def _format_datetime(value) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


def _slugify(name: str) -> str:
    """Derive a stable URL slug from an organization name."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower())
    return slug.strip("-") or "unknown"


def _post_mentions_org(post: models.Post, org_name: str) -> bool:
    mentions = _parse_string_list(post.organization_mentions)
    if org_name in mentions:
        return True
    return org_name.lower() in (post.title or "").lower()


def _day_key(value) -> str | None:
    if value is None:
        return None
    return value.date().isoformat()


def _related_posts_for_org(
    posts: list[models.Post],
    org_name: str,
    *,
    limit: int | None = None,
) -> list[models.Post]:
    matched = [post for post in posts if _post_mentions_org(post, org_name)]
    matched.sort(
        key=lambda post: (
            _format_datetime(post.published_at or post.created_at) or "",
            post.id,
        ),
        reverse=True,
    )
    if limit is not None:
        return matched[:limit]
    return matched


def _to_organization(
    row: models.Organization,
    *,
    post_count: int = 0,
    max_score: float = 0.0,
) -> Organization:
    return Organization(
        id=row.id,
        slug=_slugify(row.name),
        name=row.name,
        sector=row.sector,
        tickers=_parse_string_list(row.tickers),
        alert_count=row.alert_count,
        top_narrative_types=_parse_string_list(row.top_narrative_types),
        risk_score=float(row.risk_score or 0.0),
        post_count=post_count,
        max_score=round(float(max_score or 0.0), 2),
    )


def _resolve_organization(db: Session, organization_slug: str) -> models.Organization:
    """Resolve by derived name slug, falling back to primary key id."""
    rows = list(db.scalars(select(models.Organization)).all())
    for row in rows:
        if _slugify(row.name) == organization_slug:
            return row
    row = db.get(models.Organization, organization_slug)
    if row is not None:
        return row
    raise HTTPException(
        status_code=404,
        detail=f"Organization '{organization_slug}' not found",
    )


def _org_activity(
    row: models.Organization,
    posts: list[models.Post],
) -> tuple[int, float, list[models.Post]]:
    related = _related_posts_for_org(posts, row.name)
    max_score = max((float(post.severity_score or 0.0) for post in related), default=0.0)
    return len(related), max_score, related


def _contains(haystack: str | None, needle: str) -> bool:
    """Case-insensitive substring match for simple query filters."""
    if not haystack:
        return False
    return needle.casefold() in haystack.casefold()


def _filter_organizations(
    organizations: list[Organization],
    *,
    search: str | None = None,
    sector: str | None = None,
) -> list[Organization]:
    """Apply optional name search and sector filters in Python."""
    results = organizations

    if search and search.strip():
        needle = search.strip()
        results = [org for org in results if _contains(org.name, needle)]

    if sector and sector.strip():
        needle = sector.strip()
        results = [org for org in results if _contains(org.sector, needle)]

    return results


@router.get("", response_model=list[Organization])
def list_organizations(
    db: Session = Depends(get_db),
    search: str | None = Query(
        default=None,
        description="Search by organization name (substring, case-insensitive)",
    ),
    sector: str | None = Query(
        default=None,
        description="Filter by sector (substring, case-insensitive)",
    ),
) -> list[Organization]:
    """Return watchlist organizations with optional name search and sector filter."""
    rows = list(db.scalars(select(models.Organization)).all())
    posts = list(db.scalars(select(models.Post)).all())

    organizations: list[Organization] = []
    for row in rows:
        post_count, max_score, _ = _org_activity(row, posts)
        organizations.append(
            _to_organization(row, post_count=post_count, max_score=max_score)
        )

    organizations.sort(key=lambda item: (item.max_score, item.post_count), reverse=True)
    return _filter_organizations(organizations, search=search, sector=sector)


@router.get("/{organization_slug}", response_model=OrganizationDetail)
def get_organization(
    organization_slug: str,
    db: Session = Depends(get_db),
) -> OrganizationDetail:
    """Return organization drilldown detail by slug (id also accepted)."""
    row = _resolve_organization(db, organization_slug)
    posts = list(db.scalars(select(models.Post)).all())
    post_count, max_score, related = _org_activity(row, posts)
    org = _to_organization(row, post_count=post_count, max_score=max_score)

    related_posts = [
        RelatedPost(
            id=post.id,
            title=post.title,
            source=post.source,
            url=post.url,
            narrative_type=post.narrative_type,
            severity_score=float(post.severity_score or 0.0),
            published_at=_format_datetime(post.published_at),
        )
        for post in related[:12]
    ]

    alerts = (
        db.scalars(
            select(models.Alert)
            .options(selectinload(models.Alert.evidence))
            .where(
                (models.Alert.organization_id == row.id)
                | (models.Alert.organization_name == row.name)
            )
            .order_by(models.Alert.score.desc())
        )
        .unique()
        .all()
    )
    related_alerts = [
        RelatedAlert(
            id=alert.id,
            title=alert.title,
            narrative_type=alert.narrative_type,
            severity=alert.severity,
            score=float(alert.score or 0.0),
            summary=alert.summary,
        )
        for alert in alerts
    ]

    activity = build_organization_summary(row.name, related)

    return OrganizationDetail(
        organization=org,
        related_posts=related_posts,
        related_alerts=related_alerts,
        summary=OrganizationActivitySummary(
            top_category=activity.top_category,
            top_source=activity.top_source,
            summary=activity.summary,
            post_count=activity.post_count,
        ),
    )


@router.get("/{organization_slug}/timeseries", response_model=OrganizationTimeseries)
def get_organization_timeseries(
    organization_slug: str,
    db: Session = Depends(get_db),
    days: int = Query(default=14, ge=1, le=90),
) -> OrganizationTimeseries:
    """Return daily post counts and max scores for one organization."""
    row = _resolve_organization(db, organization_slug)
    posts = list(db.scalars(select(models.Post)).all())
    related = _related_posts_for_org(posts, row.name)

    by_day_count: dict[str, int] = defaultdict(int)
    by_day_max: dict[str, float] = defaultdict(float)
    for post in related:
        day = _day_key(post.published_at or post.created_at)
        if day is None:
            continue
        by_day_count[day] += 1
        score = float(post.severity_score or 0.0)
        if score > by_day_max[day]:
            by_day_max[day] = score

    sorted_days = sorted(by_day_count.keys())[-days:]
    points = [
        TimeseriesPoint(
            date=day,
            count=by_day_count[day],
            max_score=round(by_day_max[day], 2),
        )
        for day in sorted_days
    ]

    return OrganizationTimeseries(
        organization_slug=_slugify(row.name),
        organization_name=row.name,
        total_posts=len(related),
        points=points,
    )


# Backward-compatible alias used by the current frontend drilldown client.
@router.get("/{organization_slug}/drilldown", response_model=OrganizationDetail)
def get_organization_drilldown(
    organization_slug: str,
    db: Session = Depends(get_db),
) -> OrganizationDetail:
    """Alias for GET /organizations/{organization_slug}."""
    return get_organization(organization_slug, db)
