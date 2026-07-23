"""Tests for Reddit collector helpers and source-mix metrics."""

from __future__ import annotations

from app.api.metrics import get_source_metrics
from app.collectors.reddit import (
    DEFAULT_SUBREDDITS,
    RedditClient,
    _normalize_listing_children,
    resolve_subreddits,
)
from app.db.base import Base
from app.db.models import Post
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def test_normalize_listing_children() -> None:
    payload = {
        "data": {
            "children": [
                {
                    "kind": "t3",
                    "data": {
                        "id": "abc123",
                        "title": "CVE-2024-1234 discussion",
                        "selftext": "Details about an exploit",
                        "url": "https://example.com",
                        "permalink": "/r/netsec/comments/abc123/cve/",
                        "created_utc": 1_720_000_000,
                    },
                },
                {"kind": "t1", "data": {"id": "comment"}},
            ]
        }
    }
    entries = _normalize_listing_children(payload, "netsec")
    assert len(entries) == 1
    assert entries[0].external_id == "t3_abc123"
    assert entries[0].subreddit == "netsec"
    assert "CVE-2024-1234" in entries[0].title
    assert entries[0].url and "reddit.com" in entries[0].url


def test_resolve_subreddits_defaults_and_parsing() -> None:
    assert "netsec" in DEFAULT_SUBREDDITS
    assert resolve_subreddits("netsec, r/cybersecurity ,") == ("netsec", "cybersecurity")


def test_reddit_client_oauth_flag() -> None:
    assert RedditClient().uses_oauth is False
    assert (
        RedditClient(client_id="id", client_secret="secret").uses_oauth is True
    )


def test_source_metrics_share() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db: Session = SessionLocal()
    db.add_all(
        [
            Post(id="1", source="rss", title="a", content="", cve_ids="[]"),
            Post(id="2", source="rss", title="b", content="", cve_ids="[]"),
            Post(id="3", source="reddit", title="c", content="", cve_ids="[]"),
        ]
    )
    db.commit()

    result = get_source_metrics(db)
    assert result.total_posts == 3
    by_source = {row.source: row for row in result.sources}
    assert by_source["rss"].count == 2
    assert by_source["rss"].share == 0.6667
    assert by_source["reddit"].count == 1
    assert by_source["reddit"].share == 0.3333
    db.close()
