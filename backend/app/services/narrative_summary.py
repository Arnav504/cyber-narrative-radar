"""Deterministic narrative-cluster summaries (LLM-ready shape, no LLM yet)."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from typing import Protocol


class NarrativePostLike(Protocol):
    """Minimal post fields needed for narrative cluster summaries."""

    narrative_type: str | None
    organization_mentions: str  # JSON list as text


@dataclass(frozen=True)
class NarrativeSummary:
    """
    Explainable cluster summary.

    ``provider`` is ``rule_based`` today; a future LLM path can return the same
    shape with ``provider="llm"`` without changing API consumers.
    """

    summary: str
    organizations: tuple[str, ...] = field(default_factory=tuple)
    categories: tuple[str, ...] = field(default_factory=tuple)
    provider: str = "rule_based"
    post_count: int = 0


def _parse_org_mentions(raw: str | None) -> list[str]:
    try:
        value = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _ranked_keys(counts: Counter[str], *, limit: int = 5) -> tuple[str, ...]:
    """Sort by count desc, then name asc for stable output."""
    if not counts:
        return ()
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0].casefold()))
    return tuple(name for name, _ in ranked[:limit])


def _build_summary_text(
    title: str,
    *,
    post_count: int,
    organizations: tuple[str, ...],
    categories: tuple[str, ...],
    keywords: tuple[str, ...],
) -> str:
    if post_count <= 0:
        return f"No posts available for narrative cluster '{title}'."

    post_label = "post" if post_count == 1 else "posts"
    parts = [f"Narrative cluster '{title}' covers {post_count} {post_label}."]

    if categories:
        parts.append(f"Categories: {', '.join(categories)}.")
    else:
        parts.append("Categories: unclassified.")

    if organizations:
        parts.append(f"Organizations: {', '.join(organizations)}.")
    else:
        parts.append("Organizations: none extracted.")

    if keywords:
        parts.append(f"Keywords: {', '.join(keywords)}.")

    return " ".join(parts)


def build_narrative_summary(
    *,
    title: str,
    posts: list[NarrativePostLike],
    keywords: list[str] | tuple[str, ...] = (),
) -> NarrativeSummary:
    """
    Build a deterministic summary from clustered narrative posts.

    Uses frequency counts only (no LLM). Output shape is stable so an optional
    LLM provider can replace the text later without changing field names.
    """
    category_counts: Counter[str] = Counter()
    organization_counts: Counter[str] = Counter()

    for post in posts:
        category = (post.narrative_type or "").strip()
        if category:
            category_counts[category] += 1
        for org in _parse_org_mentions(getattr(post, "organization_mentions", None)):
            organization_counts[org] += 1

    categories = _ranked_keys(category_counts)
    organizations = _ranked_keys(organization_counts)
    keyword_tuple = tuple(k.strip() for k in keywords if k and k.strip())
    post_count = len(posts)

    return NarrativeSummary(
        summary=_build_summary_text(
            title,
            post_count=post_count,
            organizations=organizations,
            categories=categories,
            keywords=keyword_tuple,
        ),
        organizations=organizations,
        categories=categories,
        provider="rule_based",
        post_count=post_count,
    )
