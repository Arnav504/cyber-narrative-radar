"""Public RSS feed definitions for local MVP ingestion."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RssSource:
    """A public RSS feed used by the collector."""

    name: str
    url: str
    max_entries: int = 8


# Small set of reputable, publicly available cybersecurity feeds.
DEFAULT_RSS_SOURCES: tuple[RssSource, ...] = (
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
