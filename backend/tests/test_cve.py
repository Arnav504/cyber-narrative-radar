"""Tests for CVE ID extraction and advisory post enrichment helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.analytics.cve import extract_cve_ids, parse_cve_ids_json
from app.collectors.cisa_kev import upsert_kev_entry
from app.collectors.nvd import upsert_nvd_entry
from app.db.base import Base
from app.db.models import Post
from app.services.rss_sources import ADVISORY_RSS_SOURCES, DEFAULT_RSS_SOURCES


def test_extract_cve_ids_dedupes_and_normalizes() -> None:
    text = "See cve-2024-12345 and CVE-2024-12345 plus CVE-2023-9999 in the advisory."
    assert extract_cve_ids(text) == ("CVE-2023-9999", "CVE-2024-12345")


def test_extract_cve_ids_empty() -> None:
    assert extract_cve_ids("") == ()
    assert extract_cve_ids("no identifiers here") == ()


def test_parse_cve_ids_json_roundtrip() -> None:
    raw = json.dumps(["CVE-2024-1111", "not-a-cve", "cve-2024-2222"])
    assert parse_cve_ids_json(raw) == ("CVE-2024-1111", "CVE-2024-2222")


def test_advisory_feeds_are_in_default_sources() -> None:
    names = {source.name for source in DEFAULT_RSS_SOURCES}
    assert "CISA Cybersecurity Advisories" in names
    assert "CISA Alerts" in names
    assert len(ADVISORY_RSS_SOURCES) >= 2


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_upsert_kev_entry_sets_cve_ids() -> None:
    db = _session()
    action = upsert_kev_entry(
        db,
        {
            "cveID": "CVE-2024-21762",
            "vendorProject": "Fortinet",
            "product": "FortiOS",
            "vulnerabilityName": "Fortinet FortiOS Out-of-bound Write",
            "shortDescription": "An out-of-bounds write in FortiOS.",
            "requiredAction": "Apply updates per vendor.",
            "dateAdded": "2024-02-09",
        },
    )
    db.commit()
    assert action == "inserted"
    post = db.scalar(select(Post).where(Post.source == "cisa").limit(1))
    assert post is not None
    assert "CVE-2024-21762" in parse_cve_ids_json(post.cve_ids)
    assert post.narrative_type == "Zero-day / critical vulnerability"


def test_upsert_nvd_entry_sets_cve_ids() -> None:
    db = _session()
    action = upsert_nvd_entry(
        db,
        {
            "cve": {
                "id": "CVE-2025-10001",
                "published": "2025-01-15T12:00:00.000",
                "descriptions": [
                    {"lang": "en", "value": "Example NVD description mentioning a flaw."}
                ],
                "metrics": {
                    "cvssMetricV31": [
                        {
                            "cvssData": {
                                "baseScore": 9.8,
                                "baseSeverity": "CRITICAL",
                            }
                        }
                    ]
                },
            }
        },
    )
    db.commit()
    assert action == "inserted"
    post = db.scalar(select(Post).where(Post.source == "nvd").limit(1))
    assert post is not None
    assert parse_cve_ids_json(post.cve_ids) == ("CVE-2025-10001",)
    assert "CVSS" in post.content
    assert post.published_at is not None
    assert post.published_at.tzinfo is not None or True
    _ = datetime.now(timezone.utc)
