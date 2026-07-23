"""Upsert explainable alerts from scored posts (auto-alert path)."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.scoring import AnomalyScore
from app.analytics.cve import parse_cve_ids_json
from app.db.models import Alert, AlertEvidence, Organization, Post


def _parse_organizations(raw: str) -> tuple[str, ...]:
    try:
        value = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return ()
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value if str(item).strip())


def auto_alert_id(organization: str, narrative_type: str) -> str:
    """Stable id so re-scoring updates the same alert instead of duplicating."""
    digest = hashlib.sha256(
        f"{organization.strip().lower()}|{narrative_type.strip().lower()}".encode("utf-8")
    ).hexdigest()[:16]
    return f"alert-auto-{digest}"


def _evidence_id(alert_id: str, post_id: str) -> str:
    digest = hashlib.sha256(f"{alert_id}|{post_id}".encode("utf-8")).hexdigest()[:12]
    return f"ev-auto-{digest}"


def upsert_alerts_from_scored_posts(
    db: Session,
    posts: list[Post],
    scored_by_id: dict[str, AnomalyScore],
    *,
    min_score: float = 45.0,
    max_evidence: int = 5,
) -> dict[str, int]:
    """
    Create or refresh auto-alerts for (organization, narrative_type) groups.

    Only posts with a narrative type, at least one org mention, and score
    ``>= min_score`` contribute. Seed alerts (non ``alert-auto-*``) are left alone.
    """
    stats = {"alerts_upserted": 0, "evidence_links": 0, "groups_considered": 0}

    # Group eligible posts by org + category.
    grouped: dict[tuple[str, str], list[tuple[Post, AnomalyScore]]] = defaultdict(list)
    for post in posts:
        scored = scored_by_id.get(post.id)
        if scored is None or scored.score < min_score:
            continue
        narrative = (post.narrative_type or "").strip()
        if not narrative:
            continue
        for org in _parse_organizations(post.organization_mentions):
            grouped[(org, narrative)].append((post, scored))

    if not grouped:
        return stats

    org_rows = {
        row.name: row
        for row in db.scalars(select(Organization)).all()
    }

    for (organization, narrative_type), members in grouped.items():
        stats["groups_considered"] += 1
        members_sorted = sorted(members, key=lambda item: item[1].score, reverse=True)
        top = members_sorted[:max_evidence]
        best_score = top[0][1]
        org_row = org_rows.get(organization)
        sector = org_row.sector if org_row is not None else ""
        alert_id = auto_alert_id(organization, narrative_type)

        reasons: list[str] = []
        for _, scored in top:
            for reason in scored.reasons:
                if reason not in reasons:
                    reasons.append(reason)

        cve_mentions: list[str] = []
        for post, _scored in top:
            for cve in parse_cve_ids_json(getattr(post, "cve_ids", None)):
                if cve not in cve_mentions:
                    cve_mentions.append(cve)
        if cve_mentions:
            reasons.append(f"CVE IDs: {', '.join(cve_mentions[:8])}")

        if not reasons:
            reasons.append(
                f"Anomaly score {best_score.score:.1f} for {narrative_type} / {organization}"
            )

        cve_clause = (
            f" Linked CVEs: {', '.join(cve_mentions[:5])}."
            if cve_mentions
            else ""
        )
        summary = (
            f"Automated alert: {len(members_sorted)} scored post(s) mention "
            f"{organization} under '{narrative_type}' "
            f"(top score {best_score.score:.1f}/100).{cve_clause}"
        )
        title = f"{narrative_type} activity around {organization}"

        existing = db.get(Alert, alert_id)
        if existing is None:
            db.add(
                Alert(
                    id=alert_id,
                    title=title,
                    narrative_type=narrative_type,
                    organization_id=org_row.id if org_row is not None else None,
                    organization_name=organization,
                    sector=sector,
                    severity=best_score.severity,
                    score=best_score.score,
                    summary=summary,
                    why_flagged=json.dumps(reasons),
                )
            )
            db.flush()
        else:
            existing.title = title
            existing.narrative_type = narrative_type
            existing.organization_id = org_row.id if org_row is not None else None
            existing.organization_name = organization
            existing.sector = sector or existing.sector
            existing.severity = best_score.severity
            existing.score = best_score.score
            existing.summary = summary
            existing.why_flagged = json.dumps(reasons)
            for old in list(existing.evidence):
                db.delete(old)
            db.flush()

        for post, _scored in top:
            db.add(
                AlertEvidence(
                    id=_evidence_id(alert_id, post.id),
                    alert_id=alert_id,
                    post_id=post.id,
                    source=post.source,
                    title=post.title,
                    url=post.url,
                    published_at=post.published_at or post.created_at,
                )
            )
            stats["evidence_links"] += 1

        stats["alerts_upserted"] += 1

    return stats
