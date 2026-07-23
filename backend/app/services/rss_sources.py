"""Public RSS feed definitions for local MVP ingestion."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RssSource:
    """A public RSS feed used by the collector."""

    name: str
    url: str
    max_entries: int = 8


# Industry / news RSS (general cyber chatter).
NEWS_RSS_SOURCES: tuple[RssSource, ...] = (
    RssSource(
        name="Krebs on Security",
        url="https://krebsonsecurity.com/feed/",
        max_entries=8,
    ),
    RssSource(
        name="The Hacker News",
        url="https://feeds.feedburner.com/TheHackersNews",
        max_entries=8,
    ),
    RssSource(
        name="BleepingComputer",
        url="https://www.bleepingcomputer.com/feed/",
        max_entries=8,
    ),
    RssSource(
        name="Cisco Talos Blog",
        url="https://blog.talosintelligence.com/rss/",
        max_entries=8,
    ),
)

# Official government / vulnerability advisory feeds (Week 2).
ADVISORY_RSS_SOURCES: tuple[RssSource, ...] = (
    RssSource(
        name="CISA Cybersecurity Advisories",
        url="https://www.cisa.gov/cybersecurity-advisories/all.xml",
        max_entries=10,
    ),
    RssSource(
        name="CISA Alerts",
        url="https://www.cisa.gov/uscert/ncas/alerts.xml",
        max_entries=8,
    ),
    RssSource(
        name="CISA Current Activity",
        url="https://www.cisa.gov/uscert/ncas/current-activity.xml",
        max_entries=8,
    ),
)

# Combined default set used by scheduled + CLI ingest.
DEFAULT_RSS_SOURCES: tuple[RssSource, ...] = NEWS_RSS_SOURCES + ADVISORY_RSS_SOURCES
