"""Deterministic keyword-based cyber narrative classifier."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Canonical narrative labels from AGENTS.md
NARRATIVE_CATEGORIES: tuple[str, ...] = (
    "Data breach",
    "Ransomware",
    "Phishing / social engineering",
    "Zero-day / critical vulnerability",
    "Supply chain compromise",
    "Deepfake / disinformation cyber influence",
)

# Keyword lists are intentionally small and human-readable for explainability.
CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Data breach": (
        "data breach",
        "breach",
        "leaked data",
        "exposed records",
        "stolen data",
        "credential dump",
        "customer data",
    ),
    "Ransomware": (
        "ransomware",
        "ransom",
        "lockbit",
        "encrypt",
        "encryption attack",
        "payment demand",
        "double extortion",
    ),
    "Phishing / social engineering": (
        "phishing",
        "spear phishing",
        "social engineering",
        "credential harvesting",
        "fake login",
        "mfa reset",
        "smishing",
        "business email compromise",
        "bec",
    ),
    "Zero-day / critical vulnerability": (
        "zero-day",
        "zero day",
        "0-day",
        "critical vulnerability",
        "cve",
        "remote code execution",
        "rce",
        "exploit",
        "unpatched",
    ),
    "Supply chain compromise": (
        "supply chain",
        "third-party vendor",
        "software supply chain",
        "dependency compromise",
        "poisoned package",
        "vendor breach",
        "upstream compromise",
    ),
    "Deepfake / disinformation cyber influence": (
        "deepfake",
        "disinformation",
        "synthetic media",
        "ai-generated video",
        "influence operation",
        "fake audio",
        "coordinated inauthentic",
    ),
}


@dataclass(frozen=True)
class ClassificationResult:
    """Explainable output from the keyword classifier."""

    label: str
    score: float
    matched_keywords: tuple[str, ...]
    category_scores: dict[str, float]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _keyword_pattern(keyword: str) -> re.Pattern[str]:
    """Build a word-boundary-aware pattern for multi-word keywords."""
    parts = [re.escape(part) for part in keyword.lower().split()]
    body = r"\s+".join(parts)
    return re.compile(rf"(?<!\w){body}(?!\w)")


def score_text(text: str) -> dict[str, float]:
    """
    Score each narrative category by keyword hits.

    Longer keyword matches count slightly more so specific phrases beat
    single generic tokens when both appear.
    """
    normalized = _normalize(text)
    if not normalized:
        return {category: 0.0 for category in NARRATIVE_CATEGORIES}

    scores: dict[str, float] = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        total = 0.0
        for keyword in keywords:
            matches = _keyword_pattern(keyword).findall(normalized)
            if matches:
                # Weight by phrase length (word count) for specificity.
                weight = max(1.0, float(len(keyword.split())))
                total += len(matches) * weight
        scores[category] = total
    return scores


def classify_text(text: str, *, min_score: float = 1.0) -> ClassificationResult:
    """
    Classify text into a cyber narrative category using keyword rules.

    Returns label \"Unclassified\" when no category reaches ``min_score``.
    """
    category_scores = score_text(text)
    best_label = max(category_scores, key=category_scores.get)
    best_score = category_scores[best_label]

    if best_score < min_score:
        return ClassificationResult(
            label="Unclassified",
            score=0.0,
            matched_keywords=(),
            category_scores=category_scores,
        )

    normalized = _normalize(text)
    matched = tuple(
        keyword
        for keyword in CATEGORY_KEYWORDS[best_label]
        if _keyword_pattern(keyword).search(normalized)
    )

    # Confidence is share of total keyword weight captured by the winner.
    total_weight = sum(category_scores.values())
    confidence = best_score / total_weight if total_weight > 0 else 0.0

    return ClassificationResult(
        label=best_label,
        score=round(confidence, 4),
        matched_keywords=matched,
        category_scores=category_scores,
    )
