"""Ingest public RSS entries into local Post records."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.classifier import classify_text
from app.analytics.cve import cve_ids_to_json, extract_cve_ids
from app.collectors.rss import RssEntry, fetch_rss_entries
from app.core.config import settings
from app.db.models import Organization, Post
from app.db.session import SessionLocal, init_db
from app.services.event_notify import notify_api
from app.services.events import (
    EVENT_NARRATIVES_UPDATED,
    EVENT_NEW_POST,
    publish_narratives_updated,
    publish_new_post,
)
from app.services.rss_sources import DEFAULT_RSS_SOURCES, RssSource

# Lightweight alias map for common entities seen in public cyber news.
# Values are (canonical_name, sector).
ORG_ALIASES: dict[str, tuple[str, str]] = {
    "microsoft": ("Microsoft", "Technology"),
    "google": ("Google", "Technology"),
    "amazon": ("Amazon", "Technology"),
    "aws": ("Amazon Web Services", "Technology"),
    "apple": ("Apple", "Technology"),
    "meta": ("Meta", "Technology"),
    "facebook": ("Meta", "Technology"),
    "cisco": ("Cisco", "Technology"),
    "crowdstrike": ("CrowdStrike", "Technology"),
    "palo alto": ("Palo Alto Networks", "Technology"),
    "okta": ("Okta", "Technology"),
    "cloudflare": ("Cloudflare", "Technology"),
    "ibm": ("IBM", "Technology"),
    "oracle": ("Oracle", "Technology"),
    "samsung": ("Samsung", "Technology"),
    "tesla": ("Tesla", "Automotive"),
    "jpmorgan": ("JPMorgan", "Financial Services"),
    "jp morgan": ("JPMorgan", "Financial Services"),
    "bank of america": ("Bank of America", "Financial Services"),
    "cisa": ("CISA", "Government"),
    "acme logistics": ("Acme Logistics", "Transportation"),
    "nova bank": ("Nova Bank", "Financial Services"),
    "helix cloud": ("Helix Cloud", "Technology"),
}

SECTOR_HINTS: tuple[tuple[str, str], ...] = (
    ("bank", "Financial Services"),
    ("payment", "Financial Services"),
    ("hospital", "Healthcare"),
    ("health", "Healthcare"),
    ("airline", "Transportation"),
    ("logistics", "Transportation"),
    ("shipping", "Transportation"),
    ("utility", "Energy"),
    ("energy", "Energy"),
    ("government", "Government"),
    ("cloud", "Technology"),
    ("software", "Technology"),
)


@dataclass(frozen=True)
class InferredEntities:
    """Heuristic organization/sector tags for an RSS entry."""

    organizations: tuple[str, ...]
    sectors: tuple[str, ...]


def _post_id(source_name: str, external_id: str) -> str:
    digest = hashlib.sha256(f"{source_name}|{external_id}".encode("utf-8")).hexdigest()[:20]
    return f"rss-{digest}"


def _combined_text(entry: RssEntry) -> str:
    return f"{entry.title}\n{entry.content}"


def infer_organizations_and_sectors(
    text: str,
    watchlist: list[Organization],
) -> InferredEntities:
    """
    Infer organization mentions and sectors with simple substring heuristics.

    Prefer watchlist names from the local DB, then fall back to ORG_ALIASES.
    """
    lowered = text.lower()
    found_orgs: list[str] = []
    found_sectors: list[str] = []

    for org in watchlist:
        name = org.name.strip()
        if len(name) < 3:
            continue
        if re.search(rf"(?<!\w){re.escape(name.lower())}(?!\w)", lowered):
            found_orgs.append(name)
            if org.sector and org.sector not in found_sectors:
                found_sectors.append(org.sector)

    for alias, (canonical, sector) in ORG_ALIASES.items():
        if alias in lowered and canonical not in found_orgs:
            found_orgs.append(canonical)
            if sector not in found_sectors:
                found_sectors.append(sector)

    if not found_sectors:
        for hint, sector in SECTOR_HINTS:
            if hint in lowered and sector not in found_sectors:
                found_sectors.append(sector)

    return InferredEntities(
        organizations=tuple(found_orgs),
        sectors=tuple(found_sectors),
    )


def _existing_post(db: Session, source: str, external_id: str) -> Post | None:
    return db.scalar(
        select(Post).where(Post.source == source, Post.external_id == external_id).limit(1)
    )


def compute_severity_score(
    classification_label: str,
    classifier_score: float,
    organization_count: int,
    *,
    cve_count: int = 0,
) -> float:
    """
    Build a simple deterministic 0-1 severity score for a post.

    Uses classifier confidence, whether a narrative category matched,
    organizations inferred, and CVE mentions.
    """
    if classification_label == "Unclassified":
        score = 0.12
    else:
        score = 0.35 + (0.5 * max(0.0, min(1.0, classifier_score)))

    if organization_count > 0:
        score += min(0.15, 0.05 * organization_count)
    if cve_count > 0:
        score += min(0.2, 0.08 * cve_count)

    return round(min(1.0, score), 4)


def upsert_rss_entry(db: Session, entry: RssEntry, watchlist: list[Organization]) -> str:
    """Insert or update a Post from one normalized RSS entry. Returns action label."""
    text = _combined_text(entry)
    classification = classify_text(text)
    entities = infer_organizations_and_sectors(text, watchlist)
    cve_ids = extract_cve_ids(text)
    now = datetime.now(timezone.utc)
    published_at = entry.published_at or now

    narrative_type = (
        classification.label if classification.label != "Unclassified" else None
    )
    # CVE mentions are strong evidence for vulnerability narratives.
    if cve_ids and narrative_type in (None, "Unclassified"):
        narrative_type = "Zero-day / critical vulnerability"
    elif cve_ids and narrative_type != "Zero-day / critical vulnerability":
        # Keep phishing/ransomware if the classifier already matched; otherwise prefer CVE.
        if classification.score < 0.45:
            narrative_type = "Zero-day / critical vulnerability"

    organization_mentions = json.dumps(list(entities.organizations))
    severity_score = compute_severity_score(
        classification.label if narrative_type else "Unclassified",
        classification.score,
        len(entities.organizations),
        cve_count=len(cve_ids),
    )
    cve_json = cve_ids_to_json(cve_ids)

    existing = _existing_post(db, "rss", entry.external_id)
    if existing is not None:
        existing.title = entry.title
        existing.content = entry.content
        existing.url = entry.url
        existing.published_at = published_at
        existing.organization_mentions = organization_mentions
        existing.narrative_type = narrative_type
        existing.severity_score = severity_score
        existing.cve_ids = cve_json
        # Keep original created_at on updates; only fill if missing.
        if existing.created_at is None:
            existing.created_at = now
        return "updated"

    db.add(
        Post(
            id=_post_id(entry.source_name, entry.external_id),
            source="rss",
            external_id=entry.external_id,
            title=entry.title,
            content=entry.content,
            url=entry.url,
            published_at=published_at,
            organization_mentions=organization_mentions,
            narrative_type=narrative_type,
            severity_score=severity_score,
            cve_ids=cve_json,
            created_at=now,
        )
    )
    return "inserted"


def ingest_rss(
    sources: tuple[RssSource, ...] = DEFAULT_RSS_SOURCES,
    *,
    max_entries_per_feed: int | None = None,
    include_cisa_kev: bool = True,
    include_nvd: bool = True,
    include_reddit: bool | None = None,
) -> dict[str, int]:
    """Pull RSS (+ optional CISA KEV / NVD / Reddit) into local Post records."""
    init_db()
    stats = {
        "feeds": 0,
        "fetched": 0,
        "inserted": 0,
        "updated": 0,
        "skipped_errors": 0,
        "cisa_kev_inserted": 0,
        "nvd_inserted": 0,
        "reddit_inserted": 0,
    }

    db = SessionLocal()
    try:
        watchlist = list(db.scalars(select(Organization)).all())

        for source in sources:
            stats["feeds"] += 1
            try:
                entries = fetch_rss_entries(source, max_entries=max_entries_per_feed)
            except Exception as exc:  # noqa: BLE001 - keep ingest resilient per feed
                print(f"[rss] failed to fetch {source.name}: {exc}")
                stats["skipped_errors"] += 1
                continue

            print(f"[rss] {source.name}: {len(entries)} entries")
            for entry in entries:
                stats["fetched"] += 1
                try:
                    action = upsert_rss_entry(db, entry, watchlist)
                    stats[action] += 1
                except Exception as exc:  # noqa: BLE001
                    print(f"[rss] failed to upsert '{entry.title[:80]}': {exc}")
                    stats["skipped_errors"] += 1

            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    # Advisory JSON/API sources (Week 2) — separate sessions, best-effort.
    if include_cisa_kev:
        try:
            from app.collectors.cisa_kev import ingest_cisa_kev

            kev = ingest_cisa_kev(max_items=15)
            stats["cisa_kev_inserted"] = int(kev.get("inserted", 0))
            stats["inserted"] += int(kev.get("inserted", 0))
            stats["updated"] += int(kev.get("updated", 0))
            stats["fetched"] += int(kev.get("fetched", 0))
        except Exception as exc:  # noqa: BLE001
            print(f"[rss] CISA KEV ingest skipped: {exc}")
            stats["skipped_errors"] += 1

    if include_nvd:
        try:
            from app.collectors.nvd import ingest_nvd_recent

            nvd = ingest_nvd_recent(results_per_page=10, lookback_days=7)
            stats["nvd_inserted"] = int(nvd.get("inserted", 0))
            stats["inserted"] += int(nvd.get("inserted", 0))
            stats["updated"] += int(nvd.get("updated", 0))
            stats["fetched"] += int(nvd.get("fetched", 0))
        except Exception as exc:  # noqa: BLE001
            print(f"[rss] NVD ingest skipped: {exc}")
            stats["skipped_errors"] += 1

    run_reddit = settings.reddit_enabled if include_reddit is None else include_reddit
    if run_reddit:
        try:
            from app.tasks.ingest_reddit import ingest_reddit

            reddit = ingest_reddit(limit_per_subreddit=12)
            stats["reddit_inserted"] = int(reddit.get("inserted", 0))
            stats["inserted"] += int(reddit.get("inserted", 0))
            stats["updated"] += int(reddit.get("updated", 0))
            stats["fetched"] += int(reddit.get("fetched", 0))
        except Exception as exc:  # noqa: BLE001
            print(f"[rss] Reddit ingest skipped: {exc}")
            stats["skipped_errors"] += 1

    changed = stats["inserted"] + stats["updated"]
    if changed > 0:
        publish_new_post(inserted=stats["inserted"], updated=stats["updated"])
        publish_narratives_updated(reason="rss_ingest")
        notify_api(
            EVENT_NEW_POST,
            inserted=stats["inserted"],
            updated=stats["updated"],
        )
        notify_api(EVENT_NARRATIVES_UPDATED, reason="rss_ingest")

    print(
        "[rss] done — "
        f"feeds={stats['feeds']} fetched={stats['fetched']} "
        f"inserted={stats['inserted']} updated={stats['updated']} "
        f"cisa_kev_inserted={stats['cisa_kev_inserted']} "
        f"nvd_inserted={stats['nvd_inserted']} "
        f"reddit_inserted={stats['reddit_inserted']} "
        f"errors={stats['skipped_errors']}"
    )
    return stats


if __name__ == "__main__":
    ingest_rss()
