"""Tests for deterministic organization activity summaries."""

from dataclasses import dataclass

from app.services.organization_summary import build_organization_summary


@dataclass(frozen=True)
class _Post:
    source: str
    narrative_type: str | None


def test_build_organization_summary_empty() -> None:
    result = build_organization_summary("Acme Logistics", [])
    assert result.post_count == 0
    assert result.top_category is None
    assert result.top_source is None
    assert result.summary == "No related public posts found for Acme Logistics."


def test_build_organization_summary_modes_and_text() -> None:
    posts = [
        _Post(source="rss", narrative_type="Ransomware"),
        _Post(source="rss", narrative_type="Ransomware"),
        _Post(source="reddit", narrative_type="Phishing / social engineering"),
        _Post(source="synthetic", narrative_type=None),
    ]
    result = build_organization_summary("Acme Logistics", posts)

    assert result.post_count == 4
    assert result.top_category == "Ransomware"
    assert result.top_source == "rss"
    assert result.summary == (
        "Acme Logistics has 4 related posts. "
        "Top category: Ransomware. "
        "Top source: rss."
    )


def test_build_organization_summary_tie_break_is_alphabetical() -> None:
    posts = [
        _Post(source="reddit", narrative_type="Zero-day / critical vulnerability"),
        _Post(source="rss", narrative_type="Ransomware"),
    ]
    result = build_organization_summary("Nova Bank", posts)

    # Equal counts → alphabetical winner for stable, explainable output.
    assert result.top_category == "Ransomware"
    assert result.top_source == "reddit"
