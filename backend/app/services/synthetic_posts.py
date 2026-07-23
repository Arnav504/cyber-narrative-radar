"""Deterministic synthetic cyber post templates for local demo mode.

Used by the live generator task. No network I/O — portfolio-safe chatter only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha1


# Fixed watchlist + narrative mix so demos cycle predictably.
SYNTHETIC_SCENARIOS: tuple[dict[str, str], ...] = (
    {
        "organization": "Acme Logistics",
        "sector": "Transportation",
        "narrative_type": "Ransomware",
        "title": "Forum chatter cites ransomware pressure on Acme Logistics ops",
        "content": (
            "Synthetic demo chatter: operators mention ransomware encryption "
            "and payment demand language tied to Acme Logistics."
        ),
    },
    {
        "organization": "Nova Bank",
        "sector": "Financial Services",
        "narrative_type": "Phishing / social engineering",
        "title": "Phishing wave reportedly targets Nova Bank customers",
        "content": (
            "Synthetic demo chatter: credential harvesting and fake login pages "
            "are discussed in connection with Nova Bank."
        ),
    },
    {
        "organization": "Helix Cloud",
        "sector": "Technology",
        "narrative_type": "Zero-day / critical vulnerability",
        "title": "Critical vulnerability chatter rises around Helix Cloud stack",
        "content": (
            "Synthetic demo chatter: zero-day and remote code execution keywords "
            "appear alongside Helix Cloud product names."
        ),
    },
    {
        "organization": "Acme Logistics",
        "sector": "Transportation",
        "narrative_type": "Supply chain compromise",
        "title": "Supply chain risk notes mention Acme Logistics vendors",
        "content": (
            "Synthetic demo chatter: third-party vendor and upstream compromise "
            "themes are linked to Acme Logistics partners."
        ),
    },
    {
        "organization": "Nova Bank",
        "sector": "Financial Services",
        "narrative_type": "Data breach",
        "title": "Data breach rumors circulate about Nova Bank records",
        "content": (
            "Synthetic demo chatter: exposed records and leaked data language "
            "appear in posts naming Nova Bank."
        ),
    },
    {
        "organization": "Helix Cloud",
        "sector": "Technology",
        "narrative_type": "Deepfake / disinformation cyber influence",
        "title": "Deepfake influence chatter references Helix Cloud executives",
        "content": (
            "Synthetic demo chatter: deepfake and disinformation keywords are "
            "paired with Helix Cloud leadership names."
        ),
    },
    {
        "organization": "Acme Logistics",
        "sector": "Transportation",
        "narrative_type": "Phishing / social engineering",
        "title": "Business email compromise chatter hits Acme Logistics",
        "content": (
            "Synthetic demo chatter: BEC and social engineering tactics are "
            "discussed with Acme Logistics as the named target."
        ),
    },
    {
        "organization": "Nova Bank",
        "sector": "Financial Services",
        "narrative_type": "Ransomware",
        "title": "Ransomware group name-drops Nova Bank in public post",
        "content": (
            "Synthetic demo chatter: LockBit-style ransomware and double "
            "extortion language mentions Nova Bank."
        ),
    },
)


@dataclass(frozen=True)
class SyntheticPostDraft:
    """Ready-to-insert synthetic post fields (source is always synthetic)."""

    id: str
    external_id: str
    title: str
    content: str
    organization: str
    narrative_type: str
    published_at: datetime
    url: str


def interval_seconds_for_tick(tick: int, *, min_seconds: int = 20, max_seconds: int = 30) -> int:
    """
    Deterministic sleep in [min_seconds, max_seconds] for tick ``n``.

    Keeps demo pacing varied without true randomness.
    """
    if max_seconds < min_seconds:
        min_seconds, max_seconds = max_seconds, min_seconds
    span = max_seconds - min_seconds
    if span == 0:
        return min_seconds
    return min_seconds + (tick % (span + 1))


def build_synthetic_post(
    tick: int,
    *,
    now: datetime | None = None,
) -> SyntheticPostDraft:
    """
    Build one synthetic post for generator tick ``tick``.

    Same tick always yields the same org/category/title pattern; ``published_at``
    is anchored to ``now`` with a small deterministic offset so charts move.
    """
    if tick < 0:
        raise ValueError("tick must be >= 0")

    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)

    scenario = SYNTHETIC_SCENARIOS[tick % len(SYNTHETIC_SCENARIOS)]
    org = scenario["organization"]
    narrative = scenario["narrative_type"]
    # Slight time jitter so volume buckets and freshness stamps update.
    minutes_ago = tick % 7
    published_at = clock - timedelta(minutes=minutes_ago, seconds=(tick % 17))

    digest = sha1(f"synthetic:{tick}:{org}:{narrative}".encode("utf-8")).hexdigest()[:12]
    external_id = f"synthetic-{tick:06d}"
    post_id = f"syn-{digest}"
    wave = (tick // len(SYNTHETIC_SCENARIOS)) + 1
    title = f"{scenario['title']} (demo wave {wave})"

    return SyntheticPostDraft(
        id=post_id,
        external_id=external_id,
        title=title,
        content=scenario["content"],
        organization=org,
        narrative_type=narrative,
        published_at=published_at,
        url=f"https://example.local/synthetic/{external_id}",
    )
