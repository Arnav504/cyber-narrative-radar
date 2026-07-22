"""Alert routes backed by seeded SQLite demo data."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.analytics.scoring import severity_from_score
from app.db import models
from app.db.session import get_db

router = APIRouter(prefix="/alerts", tags=["alerts"])


class EvidencePost(BaseModel):
    """A supporting post cited by an alert."""

    id: str
    source: str
    title: str
    url: str | None = None
    published_at: str
    severity_score: float = 0.0
    narrative_type: str | None = None


class Alert(BaseModel):
    """Explainable cyber-narrative alert."""

    id: str
    title: str
    narrative_type: str
    organization: str
    sector: str
    severity: str = Field(description="low | medium | high | critical")
    score: float
    summary: str
    why_flagged: list[str]
    evidence: list[EvidencePost]


def _parse_string_list(raw: str) -> list[str]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def _format_datetime(value) -> str:
    if value is None:
        return ""
    return value.isoformat().replace("+00:00", "Z")


def _contains(haystack: str | None, needle: str) -> bool:
    """Case-insensitive substring match for simple query filters."""
    if not haystack:
        return False
    return needle.casefold() in haystack.casefold()


def _to_alert_response(row: models.Alert) -> Alert:
    evidence: list[EvidencePost] = []
    evidence_scores: list[float] = []

    for item in row.evidence:
        post = item.post
        post_score = float(post.severity_score) if post is not None else 0.0
        evidence_scores.append(post_score)
        evidence.append(
            EvidencePost(
                id=post.id if post is not None else item.id,
                source=post.source if post is not None else item.source,
                title=post.title if post is not None else item.title,
                url=post.url if post is not None else item.url,
                published_at=_format_datetime(
                    post.published_at if post is not None else item.published_at
                ),
                severity_score=round(post_score, 4),
                narrative_type=post.narrative_type if post is not None else None,
            )
        )

    # Prefer persisted alert score; fall back to strongest evidence post score.
    score = float(row.score or 0.0)
    if evidence_scores:
        score = max(score, max(evidence_scores))
    severity = row.severity or severity_from_score(score)
    # Keep severity aligned with the effective exposed score.
    if severity_from_score(score) != severity and evidence_scores:
        severity = severity_from_score(score)

    return Alert(
        id=row.id,
        title=row.title,
        narrative_type=row.narrative_type,
        organization=row.organization_name,
        sector=row.sector,
        severity=severity,
        score=round(score, 4),
        summary=row.summary,
        why_flagged=_parse_string_list(row.why_flagged),
        evidence=evidence,
    )


def _alert_query():
    return (
        select(models.Alert)
        .options(selectinload(models.Alert.evidence).selectinload(models.AlertEvidence.post))
        .order_by(models.Alert.score.desc())
    )


def _alert_matches_search(alert: Alert, query: str) -> bool:
    """
    Case-insensitive substring search across title, text, organization,
    category, and evidence source fields.
    """
    needle = query.strip()
    if not needle:
        return True

    text_blobs = [
        alert.summary,
        " ".join(alert.why_flagged),
        *(item.title for item in alert.evidence),
    ]

    if _contains(alert.title, needle):
        return True
    if any(_contains(blob, needle) for blob in text_blobs):
        return True
    if _contains(alert.organization, needle):
        return True
    if _contains(alert.narrative_type, needle):
        return True
    if any(_contains(item.source, needle) for item in alert.evidence):
        return True
    return False


def _filter_alerts(
    alerts: list[Alert],
    *,
    category: str | None = None,
    organization: str | None = None,
    source: str | None = None,
    search: str | None = None,
) -> list[Alert]:
    """Apply optional category / organization / source / search filters in Python."""
    results = alerts

    if category:
        results = [a for a in results if _contains(a.narrative_type, category)]

    if organization:
        results = [a for a in results if _contains(a.organization, organization)]

    if source:
        needle = source.strip()
        results = [
            a
            for a in results
            if any(_contains(item.source, needle) for item in a.evidence)
        ]

    if search and search.strip():
        results = [a for a in results if _alert_matches_search(a, search)]

    return results


@router.get("", response_model=list[Alert])
def list_alerts(
    db: Session = Depends(get_db),
    category: str | None = Query(
        default=None,
        description="Filter by narrative category / type (substring, case-insensitive)",
    ),
    organization: str | None = Query(
        default=None,
        description="Filter by organization name (substring, case-insensitive)",
    ),
    source: str | None = Query(
        default=None,
        description="Filter by evidence post source, e.g. rss | reddit | synthetic",
    ),
    search: str | None = Query(
        default=None,
        description=(
            "Free-text search across title, summary/evidence text, organization, "
            "category, and source (substring, case-insensitive)"
        ),
    ),
) -> list[Alert]:
    """Return explainable alerts with optional filters and free-text search."""
    rows = db.scalars(_alert_query()).unique().all()
    alerts = [_to_alert_response(row) for row in rows]
    return _filter_alerts(
        alerts,
        category=category,
        organization=organization,
        source=source,
        search=search,
    )


@router.get("/{alert_id}", response_model=Alert)
def get_alert(alert_id: str, db: Session = Depends(get_db)) -> Alert:
    """Return a single alert by id with score and severity."""
    row = db.scalars(_alert_query().where(models.Alert.id == alert_id)).unique().first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")
    return _to_alert_response(row)
