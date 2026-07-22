"""Tests for the keyword-based narrative classifier."""

from app.analytics.classifier import (
    NARRATIVE_CATEGORIES,
    classify_text,
    score_text,
)


def test_classifies_ransomware_with_matched_keywords() -> None:
    result = classify_text(
        "Acme Logistics faces LockBit ransomware and a payment demand after encryption."
    )
    assert result.label == "Ransomware"
    assert result.score > 0
    assert "ransomware" in result.matched_keywords
    assert "lockbit" in result.matched_keywords


def test_classifies_phishing() -> None:
    result = classify_text(
        "Customers report phishing emails with a fake login and MFA reset lure."
    )
    assert result.label == "Phishing / social engineering"
    assert "phishing" in result.matched_keywords


def test_classifies_data_breach() -> None:
    result = classify_text("A data breach exposed customer data and leaked records online.")
    assert result.label == "Data breach"


def test_classifies_zero_day() -> None:
    result = classify_text(
        "Researchers disclose a zero-day CVE enabling remote code execution."
    )
    assert result.label == "Zero-day / critical vulnerability"


def test_classifies_supply_chain() -> None:
    result = classify_text(
        "A software supply chain attack used a poisoned package from a third-party vendor."
    )
    assert result.label == "Supply chain compromise"


def test_classifies_deepfake_disinformation() -> None:
    result = classify_text(
        "An influence operation used deepfake synthetic media to spread disinformation."
    )
    assert result.label == "Deepfake / disinformation cyber influence"


def test_unclassified_when_no_keywords() -> None:
    result = classify_text("Quarterly earnings improved and the weather was mild.")
    assert result.label == "Unclassified"
    assert result.score == 0.0
    assert result.matched_keywords == ()


def test_empty_text_is_unclassified() -> None:
    result = classify_text("   ")
    assert result.label == "Unclassified"
    assert all(score == 0.0 for score in result.category_scores.values())


def test_score_text_is_deterministic() -> None:
    text = "Phishing and ransomware mentions in the same post."
    first = score_text(text)
    second = score_text(text)
    assert first == second
    assert set(first) == set(NARRATIVE_CATEGORIES)


def test_specific_phrase_can_outrank_generic_token() -> None:
    # "supply chain" (2-word weight) should beat a lone weak hit elsewhere.
    result = classify_text(
        "Investigators describe a supply chain compromise involving a vendor breach."
    )
    assert result.label == "Supply chain compromise"
