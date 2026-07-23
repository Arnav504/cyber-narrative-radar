"""Lightweight RSS collector using feedparser (+ httpx User-Agent)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from time import struct_time
from typing import Any

import feedparser
import httpx

from app.services.rss_sources import RssSource

USER_AGENT = "CyberNarrativeRadar/0.1 (+https://github.com/local; portfolio MVP)"


@dataclass(frozen=True)
class RssEntry:
    """Normalized RSS entry ready for persistence."""

    source_name: str
    external_id: str
    title: str
    content: str
    url: str | None
    published_at: datetime


def utc_now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc)


def _struct_time_to_datetime(value: struct_time | None) -> datetime | None:
    if value is None:
        return None
    return datetime(
        value.tm_year,
        value.tm_mon,
        value.tm_mday,
        value.tm_hour,
        value.tm_min,
        value.tm_sec,
        tzinfo=timezone.utc,
    )


def parse_published_at(entry: dict[str, Any], *, fallback: datetime | None = None) -> datetime:
    """
    Parse an RSS published/updated timestamp.

    Falls back to ``fallback`` or current UTC when the feed omits a usable date.
    """
    parsed = _struct_time_to_datetime(entry.get("published_parsed"))
    if parsed is not None:
        return parsed

    parsed = _struct_time_to_datetime(entry.get("updated_parsed"))
    if parsed is not None:
        return parsed

    raw = entry.get("published") or entry.get("updated")
    if isinstance(raw, str) and raw.strip():
        try:
            dt = parsedate_to_datetime(raw)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except (TypeError, ValueError, IndexError, OverflowError):
            pass

    return fallback if fallback is not None else utc_now()


def _entry_external_id(entry: dict[str, Any], fallback_title: str) -> str:
    for key in ("id", "guid", "link"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:255]
    return fallback_title[:255]


def _entry_content(entry: dict[str, Any]) -> str:
    summary = entry.get("summary")
    if isinstance(summary, str) and summary.strip():
        return summary.strip()

    content = entry.get("content")
    if isinstance(content, list) and content:
        first = content[0]
        if isinstance(first, dict):
            value = first.get("value")
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _download_feed(url: str) -> str:
    """Fetch feed XML with an explicit User-Agent (CISA requires this)."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
    }
    with httpx.Client(timeout=30.0, follow_redirects=True, headers=headers) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text


def fetch_rss_entries(source: RssSource, *, max_entries: int | None = None) -> list[RssEntry]:
    """
    Fetch and normalize recent entries from one RSS feed.

    Each entry always has a UTC ``published_at`` (feed date or current UTC fallback).
    """
    limit = max_entries if max_entries is not None else source.max_entries
    raw_xml = _download_feed(source.url)
    parsed = feedparser.parse(raw_xml)
    fetched_at = utc_now()

    raw_entries = list(parsed.entries or [])[: max(0, limit)]
    normalized: list[RssEntry] = []

    for entry in raw_entries:
        title = str(entry.get("title") or "Untitled").strip() or "Untitled"
        link = entry.get("link")
        url = link.strip() if isinstance(link, str) and link.strip() else None
        external_id = _entry_external_id(entry, fallback_title=title)
        normalized.append(
            RssEntry(
                source_name=source.name,
                external_id=external_id,
                title=title[:512],
                content=_entry_content(entry),
                url=url[:1024] if url else None,
                published_at=parse_published_at(entry, fallback=fetched_at),
            )
        )

    return normalized
