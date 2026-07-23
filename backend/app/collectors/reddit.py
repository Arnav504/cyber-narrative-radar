"""Official Reddit public JSON / optional OAuth collector.

Uses Reddit's documented HTTP JSON endpoints with a descriptive User-Agent.
Optional app-only OAuth (client credentials) when REDDIT_CLIENT_ID/SECRET are set.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import settings

USER_AGENT = "cyber-narrative-radar/0.1 (portfolio MVP; local-first)"
PUBLIC_BASE = "https://www.reddit.com"
OAUTH_BASE = "https://oauth.reddit.com"
TOKEN_URL = "https://www.reddit.com/api/v1/access_token"

DEFAULT_SUBREDDITS: tuple[str, ...] = (
    "netsec",
    "cybersecurity",
    "blueteamsec",
)


@dataclass(frozen=True)
class RedditEntry:
    """Normalized Reddit post ready for persistence."""

    subreddit: str
    external_id: str
    title: str
    content: str
    url: str | None
    published_at: datetime
    permalink: str | None


def _parse_created_utc(raw: Any) -> datetime:
    try:
        ts = float(raw)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def _normalize_listing_children(payload: dict[str, Any], subreddit: str) -> list[RedditEntry]:
    data = payload.get("data") if isinstance(payload, dict) else None
    children = data.get("children") if isinstance(data, dict) else None
    if not isinstance(children, list):
        return []

    entries: list[RedditEntry] = []
    for child in children:
        if not isinstance(child, dict) or child.get("kind") != "t3":
            continue
        post = child.get("data")
        if not isinstance(post, dict):
            continue
        post_id = str(post.get("id") or "").strip()
        title = str(post.get("title") or "").strip() or "Untitled"
        if not post_id:
            continue
        selftext = str(post.get("selftext") or "").strip()
        link = str(post.get("url") or "").strip() or None
        permalink = str(post.get("permalink") or "").strip()
        permalink_url = f"https://www.reddit.com{permalink}" if permalink else link
        entries.append(
            RedditEntry(
                subreddit=subreddit,
                external_id=f"t3_{post_id}",
                title=title[:512],
                content=selftext,
                url=(permalink_url or link)[:1024] if (permalink_url or link) else None,
                published_at=_parse_created_utc(post.get("created_utc")),
                permalink=permalink_url,
            )
        )
    return entries


class RedditClient:
    """Thin Reddit HTTP client with optional app-only OAuth."""

    def __init__(
        self,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
        user_agent: str = USER_AGENT,
        request_pause_seconds: float = 1.25,
    ) -> None:
        self.client_id = (client_id or "").strip()
        self.client_secret = (client_secret or "").strip()
        self.user_agent = user_agent
        self.request_pause_seconds = max(0.0, request_pause_seconds)
        self._token: str | None = None

    @property
    def uses_oauth(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def _headers(self, *, bearer: str | None = None) -> dict[str, str]:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"
        return headers

    def _fetch_token(self, client: httpx.Client) -> str:
        if self._token:
            return self._token
        response = client.post(
            TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(self.client_id, self.client_secret),
            headers={"User-Agent": self.user_agent},
        )
        response.raise_for_status()
        payload = response.json()
        token = str(payload.get("access_token") or "").strip()
        if not token:
            raise RuntimeError("Reddit OAuth response missing access_token")
        self._token = token
        return token

    def fetch_subreddit_new(
        self,
        subreddit: str,
        *,
        limit: int = 15,
    ) -> list[RedditEntry]:
        """Fetch newest posts from one public subreddit."""
        name = subreddit.strip().lstrip("r/").strip()
        if not name:
            return []
        limit = max(1, min(int(limit), 50))

        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            if self.uses_oauth:
                token = self._fetch_token(client)
                url = f"{OAUTH_BASE}/r/{name}/new"
                response = client.get(
                    url,
                    params={"limit": limit, "raw_json": 1},
                    headers=self._headers(bearer=token),
                )
            else:
                url = f"{PUBLIC_BASE}/r/{name}/new.json"
                response = client.get(
                    url,
                    params={"limit": limit, "raw_json": 1},
                    headers=self._headers(),
                )
            response.raise_for_status()
            payload = response.json()

        if self.request_pause_seconds:
            time.sleep(self.request_pause_seconds)
        return _normalize_listing_children(payload, name)


def resolve_subreddits(raw: str | None = None) -> tuple[str, ...]:
    """Parse comma-separated subreddit list from env or use defaults."""
    text = (raw if raw is not None else settings.reddit_subreddits).strip()
    if not text:
        return DEFAULT_SUBREDDITS
    parts = []
    for part in text.split(","):
        name = part.strip().lstrip("r/").strip()
        if name and name not in parts:
            parts.append(name)
    return tuple(parts) if parts else DEFAULT_SUBREDDITS


def fetch_reddit_entries(
    *,
    subreddits: tuple[str, ...] | None = None,
    limit_per_subreddit: int = 15,
) -> list[RedditEntry]:
    """Fetch newest posts across configured cyber subreddits."""
    client = RedditClient(
        client_id=settings.reddit_client_id,
        client_secret=settings.reddit_client_secret,
    )
    targets = subreddits if subreddits is not None else resolve_subreddits()
    collected: list[RedditEntry] = []
    for name in targets:
        try:
            collected.extend(
                client.fetch_subreddit_new(name, limit=limit_per_subreddit)
            )
        except Exception as exc:  # noqa: BLE001 - keep multi-sub ingest resilient
            print(f"[reddit] failed to fetch r/{name}: {exc}")
    return collected
