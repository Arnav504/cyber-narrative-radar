"""Narrative cluster routes powered by TF-IDF + KMeans."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.clustering import cluster_posts
from app.db import models
from app.db.session import get_db
from app.services.narrative_summary import build_narrative_summary

router = APIRouter(prefix="/narratives", tags=["narratives"])

TOP_POSTS_LIMIT = 5


class NarrativeTopPost(BaseModel):
    """Representative post inside a narrative cluster."""

    id: str
    title: str
    source: str
    url: str | None = None
    narrative_type: str | None = None
    severity_score: float = 0.0
    published_at: str | None = None


class NarrativeClusterSummary(BaseModel):
    """
    Optional narrative summary layer.

    ``provider`` is ``rule_based`` for now; a future LLM path can reuse this shape.
    """

    summary: str
    organizations: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    provider: str = "rule_based"
    post_count: int = Field(ge=0, default=0)


class NarrativeCluster(BaseModel):
    """Simple cluster summary for the narratives API."""

    id: str
    title: str
    count: int = Field(ge=0)
    top_posts: list[NarrativeTopPost]
    keywords: list[str] = Field(default_factory=list)
    summary: NarrativeClusterSummary | None = None


def _format_datetime(value) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


def _post_text(post: models.Post) -> str:
    title = (post.title or "").strip()
    content = (post.content or "").strip()
    if title and content:
        return f"{title}. {content}"
    return title or content


def _to_top_post(post: models.Post) -> NarrativeTopPost:
    return NarrativeTopPost(
        id=post.id,
        title=post.title or "(untitled)",
        source=post.source,
        url=post.url,
        narrative_type=post.narrative_type,
        severity_score=float(post.severity_score or 0.0),
        published_at=_format_datetime(post.published_at),
    )


def _build_clusters(
    db: Session,
    *,
    n_clusters: int | None = None,
) -> list[NarrativeCluster]:
    rows = list(db.scalars(select(models.Post)).all())
    by_id = {row.id: row for row in rows}

    cluster_input = [
        (row.id, _post_text(row))
        for row in rows
        if _post_text(row)
    ]
    clustered = cluster_posts(cluster_input, n_clusters=n_clusters)

    results: list[NarrativeCluster] = []
    for cluster in clustered:
        members = [by_id[post.id] for post in cluster.posts if post.id in by_id]
        members.sort(
            key=lambda post: (
                float(post.severity_score or 0.0),
                _format_datetime(post.published_at or post.created_at) or "",
            ),
            reverse=True,
        )
        top_posts = [_to_top_post(post) for post in members[:TOP_POSTS_LIMIT]]
        keywords = list(cluster.top_terms)
        activity = build_narrative_summary(
            title=cluster.label,
            posts=members,
            keywords=keywords,
        )
        results.append(
            NarrativeCluster(
                id=f"cluster-{cluster.cluster_id}",
                title=cluster.label,
                count=cluster.count,
                top_posts=top_posts,
                keywords=keywords,
                summary=NarrativeClusterSummary(
                    summary=activity.summary,
                    organizations=list(activity.organizations),
                    categories=list(activity.categories),
                    provider=activity.provider,
                    post_count=activity.post_count,
                ),
            )
        )
    return results


@router.get("", response_model=list[NarrativeCluster])
def list_narratives(
    db: Session = Depends(get_db),
    n_clusters: int | None = Query(default=None, ge=1, le=20),
) -> list[NarrativeCluster]:
    """Cluster local posts and return narrative summaries."""
    return _build_clusters(db, n_clusters=n_clusters)


@router.get("/{narrative_id}", response_model=NarrativeCluster)
def get_narrative(
    narrative_id: str,
    db: Session = Depends(get_db),
) -> NarrativeCluster:
    """Return a single narrative cluster by id."""
    for narrative in _build_clusters(db):
        if narrative.id == narrative_id:
            return narrative
    raise HTTPException(
        status_code=404,
        detail=f"Narrative '{narrative_id}' not found",
    )
