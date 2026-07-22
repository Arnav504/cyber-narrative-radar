"""Lightweight metrics endpoints for local charting."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Post
from app.db.session import get_db

router = APIRouter(prefix="/metrics", tags=["metrics"])


class CategoryCount(BaseModel):
    """Post count for one narrative category."""

    category: str = Field(description="Narrative type label, or Unclassified")
    count: int = Field(ge=0)


class CategoryMetricsResponse(BaseModel):
    """Simple category distribution for charts."""

    total_posts: int
    categories: list[CategoryCount]


@router.get("/categories", response_model=CategoryMetricsResponse)
def get_category_metrics(db: Session = Depends(get_db)) -> CategoryMetricsResponse:
    """Return narrative category counts from the local Post table."""
    rows = db.execute(
        select(Post.narrative_type, func.count())
        .group_by(Post.narrative_type)
        .order_by(func.count().desc())
    ).all()

    categories: list[CategoryCount] = []
    total_posts = 0
    for narrative_type, count in rows:
        label = narrative_type if narrative_type else "Unclassified"
        value = int(count)
        total_posts += value
        categories.append(CategoryCount(category=label, count=value))

    return CategoryMetricsResponse(total_posts=total_posts, categories=categories)


class VolumePoint(BaseModel):
    """Post volume for one UTC day bucket."""

    date: str
    count: int = Field(ge=0)


class VolumeMetricsResponse(BaseModel):
    """Daily post volume series for charting."""

    total_posts: int
    points: list[VolumePoint]


@router.get("/volume", response_model=VolumeMetricsResponse)
def get_volume_metrics(
    db: Session = Depends(get_db),
    days: int = 14,
) -> VolumeMetricsResponse:
    """Return daily post counts for a simple timeline chart."""
    window_days = max(1, min(days, 90))
    posts = db.scalars(select(Post)).all()

    by_day: dict[str, int] = {}
    total_posts = 0
    for post in posts:
        ts = post.published_at or post.created_at
        if ts is None:
            continue
        if ts.tzinfo is None:
            day = ts.date().isoformat()
        else:
            day = ts.date().isoformat()
        by_day[day] = by_day.get(day, 0) + 1
        total_posts += 1

    # Keep the most recent window_days buckets that have data, sorted ascending.
    sorted_days = sorted(by_day.keys())[-window_days:]
    points = [VolumePoint(date=day, count=by_day[day]) for day in sorted_days]
    return VolumeMetricsResponse(total_posts=total_posts, points=points)
