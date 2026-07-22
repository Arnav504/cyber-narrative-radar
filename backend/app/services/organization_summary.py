"""Deterministic, rule-based organization activity summaries."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Protocol


class PostLike(Protocol):
    """Minimal post fields needed for organization summaries."""

    source: str
    narrative_type: str | None


@dataclass(frozen=True)
class OrganizationSummary:
    """Readable, explainable summary of an organization's related posts."""

    top_category: str | None
    top_source: str | None
    summary: str
    post_count: int = 0


def _top_value(counts: Counter[str]) -> str | None:
    """Pick the mode; ties break alphabetically for stable output."""
    if not counts:
        return None
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0].casefold()))
    return ranked[0][0]


def _build_summary_text(
    org_name: str,
    *,
    post_count: int,
    top_category: str | None,
    top_source: str | None,
) -> str:
    if post_count <= 0:
        return f"No related public posts found for {org_name}."

    post_label = "post" if post_count == 1 else "posts"
    parts = [f"{org_name} has {post_count} related {post_label}."]

    if top_category:
        parts.append(f"Top category: {top_category}.")
    else:
        parts.append("Top category: unclassified.")

    if top_source:
        parts.append(f"Top source: {top_source}.")
    else:
        parts.append("Top source: unknown.")

    return " ".join(parts)


def build_organization_summary(
    org_name: str,
    posts: list[PostLike],
) -> OrganizationSummary:
    """
    Build a simple rule-based summary from an organization's related posts.

    Uses mode counts only (no LLM). Empty corpora produce an explicit empty-state
    sentence so the dashboard can render the field without special cases.
    """
    category_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()

    for post in posts:
        category = (post.narrative_type or "").strip()
        if category:
            category_counts[category] += 1

        source = (post.source or "").strip()
        if source:
            source_counts[source] += 1

    top_category = _top_value(category_counts)
    top_source = _top_value(source_counts)
    post_count = len(posts)

    return OrganizationSummary(
        top_category=top_category,
        top_source=top_source,
        summary=_build_summary_text(
            org_name,
            post_count=post_count,
            top_category=top_category,
            top_source=top_source,
        ),
        post_count=post_count,
    )
