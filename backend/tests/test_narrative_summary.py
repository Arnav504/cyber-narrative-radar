"""Tests for deterministic narrative cluster summaries."""

from dataclasses import dataclass

from app.services.narrative_summary import build_narrative_summary


@dataclass(frozen=True)
class _Post:
    narrative_type: str | None
    organization_mentions: str


def test_build_narrative_summary_empty() -> None:
    result = build_narrative_summary(title="lockbit / ransomware", posts=[])
    assert result.post_count == 0
    assert result.organizations == ()
    assert result.categories == ()
    assert result.provider == "rule_based"
    assert result.summary == "No posts available for narrative cluster 'lockbit / ransomware'."


def test_build_narrative_summary_extracts_orgs_and_categories() -> None:
    posts = [
        _Post(
            narrative_type="Ransomware",
            organization_mentions='["Acme Logistics", "Helix Cloud"]',
        ),
        _Post(
            narrative_type="Ransomware",
            organization_mentions='["Acme Logistics"]',
        ),
        _Post(
            narrative_type="Supply chain compromise",
            organization_mentions='["Helix Cloud"]',
        ),
    ]
    result = build_narrative_summary(
        title="ransomware / lockbit",
        posts=posts,
        keywords=["ransomware", "lockbit"],
    )

    assert result.post_count == 3
    assert result.provider == "rule_based"
    assert result.categories == ("Ransomware", "Supply chain compromise")
    assert result.organizations == ("Acme Logistics", "Helix Cloud")
    assert "covers 3 posts" in result.summary
    assert "Categories: Ransomware, Supply chain compromise." in result.summary
    assert "Organizations: Acme Logistics, Helix Cloud." in result.summary
    assert "Keywords: ransomware, lockbit." in result.summary


def test_build_narrative_summary_tie_break_is_alphabetical() -> None:
    posts = [
        _Post(narrative_type="Zero-day / critical vulnerability", organization_mentions='["Nova Bank"]'),
        _Post(narrative_type="Ransomware", organization_mentions='["Acme Logistics"]'),
    ]
    result = build_narrative_summary(title="mixed", posts=posts)

    # Equal counts → alphabetical order for stable ranking.
    assert result.categories == ("Ransomware", "Zero-day / critical vulnerability")
    assert result.organizations == ("Acme Logistics", "Nova Bank")
