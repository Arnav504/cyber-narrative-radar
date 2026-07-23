"""Deterministic CVE ID extraction for public advisory text."""

from __future__ import annotations

import json
import re

# Official CVE ID pattern (MITRE): CVE-YYYY-N+ with at least 4 digits in the sequence.
CVE_ID_PATTERN = re.compile(r"\bCVE-(\d{4})-(\d{4,7})\b", re.IGNORECASE)


def normalize_cve_id(year: str, seq: str) -> str:
    """Return canonical ``CVE-YYYY-NNNN…`` form."""
    return f"CVE-{year}-{seq}"


def extract_cve_ids(text: str) -> tuple[str, ...]:
    """
    Extract unique CVE IDs from free text in stable sorted order.

    Duplicate mentions collapse; ordering is chronological by year then sequence.
    """
    if not text or not text.strip():
        return ()

    found: set[str] = set()
    for match in CVE_ID_PATTERN.finditer(text):
        found.add(normalize_cve_id(match.group(1), match.group(2)))

    return tuple(sorted(found, key=lambda cve: (int(cve[4:8]), int(cve.split("-")[2]))))


def cve_ids_to_json(cve_ids: tuple[str, ...] | list[str]) -> str:
    """Serialize CVE IDs for the Post.cve_ids JSON text column."""
    return json.dumps(list(cve_ids))


def parse_cve_ids_json(raw: str | None) -> tuple[str, ...]:
    """Parse a Post.cve_ids JSON list."""
    if not raw:
        return ()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return ()
    if not isinstance(value, list):
        return ()
    cleaned: list[str] = []
    for item in value:
        text = str(item).strip().upper()
        match = CVE_ID_PATTERN.fullmatch(text)
        if match:
            cleaned.append(normalize_cve_id(match.group(1), match.group(2)))
    # Preserve order while deduping.
    return tuple(dict.fromkeys(cleaned))
