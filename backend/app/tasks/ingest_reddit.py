"""Ingest public Reddit posts into local Post records."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.classifier import classify_text
from app.analytics.cve import cve_ids_to_json, extract_cve_ids
from app.collectors.reddit import RedditEntry, fetch_reddit_entries, resolve_subreddits
from app.core.config import settings
from app.db.models import Organization, Post
from app.db.session import SessionLocal, init_db
from app.tasks.ingest_rss import compute_severity_score, infer_organizations_and_sectors


def _post_id(external_id: str) -> str:
    digest = hashlib.sha256(f"reddit|{external_id}".encode("utf-8")).hexdigest()[:20]
    return f"reddit-{digest}"


def upsert_reddit_entry(
    db: Session,
    entry: RedditEntry,
    watchlist: list[Organization],
) -> str:
    """Insert or update a Post from one Reddit entry."""
    text = f"{entry.title}\n{entry.content}"
    classification = classify_text(text)
    entities = infer_organizations_and_sectors(text, watchlist)
    cve_ids = extract_cve_ids(text)
    now = datetime.now(timezone.utc)

    narrative_type = (
        classification.label if classification.label != "Unclassified" else None
    )
    if cve_ids and narrative_type in (None, "Unclassified"):
        narrative_type = "Zero-day / critical vulnerability"
    elif cve_ids and classification.score < 0.45:
        narrative_type = "Zero-day / critical vulnerability"

    severity_score = compute_severity_score(
        classification.label if narrative_type else "Unclassified",
        classification.score,
        len(entities.organizations),
        cve_count=len(cve_ids),
    )

    existing = db.scalar(
        select(Post)
        .where(Post.source == "reddit", Post.external_id == entry.external_id)
        .limit(1)
    )
    payload = {
        "title": entry.title,
        "content": entry.content or f"Discussion in r/{entry.subreddit}",
        "url": entry.url,
        "published_at": entry.published_at,
        "organization_mentions": json.dumps(list(entities.organizations)),
        "narrative_type": narrative_type,
        "severity_score": severity_score,
        "cve_ids": cve_ids_to_json(cve_ids),
    }

    if existing is not None:
        for key, value in payload.items():
            setattr(existing, key, value)
        if existing.created_at is None:
            existing.created_at = now
        return "updated"

    db.add(
        Post(
            id=_post_id(entry.external_id),
            source="reddit",
            external_id=entry.external_id,
            created_at=now,
            **payload,
        )
    )
    return "inserted"


def ingest_reddit(
    *,
    subreddits: tuple[str, ...] | None = None,
    limit_per_subreddit: int = 15,
) -> dict[str, int]:
    """Pull recent Reddit posts from cyber communities into local Posts."""
    init_db()
    db = SessionLocal()
    stats = {
        "subreddits": 0,
        "fetched": 0,
        "inserted": 0,
        "updated": 0,
        "skipped_errors": 0,
    }
    targets = subreddits if subreddits is not None else resolve_subreddits()
    stats["subreddits"] = len(targets)

    try:
        watchlist = list(db.scalars(select(Organization)).all())
        entries = fetch_reddit_entries(
            subreddits=targets,
            limit_per_subreddit=limit_per_subreddit,
        )
        stats["fetched"] = len(entries)
        for entry in entries:
            try:
                action = upsert_reddit_entry(db, entry, watchlist)
                if action in stats:
                    stats[action] += 1
            except Exception as exc:  # noqa: BLE001
                print(f"[reddit] upsert failed for {entry.external_id}: {exc}")
                stats["skipped_errors"] += 1
        db.commit()
        print(
            "[reddit] done — "
            f"subs={stats['subreddits']} fetched={stats['fetched']} "
            f"inserted={stats['inserted']} updated={stats['updated']} "
            f"errors={stats['skipped_errors']}"
        )
        return stats
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def reddit_ingest_enabled() -> bool:
    return bool(settings.reddit_enabled)


if __name__ == "__main__":
    ingest_reddit()
