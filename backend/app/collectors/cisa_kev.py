"""CISA Known Exploited Vulnerabilities (KEV) public JSON ingest."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.classifier import classify_text
from app.analytics.cve import cve_ids_to_json, extract_cve_ids
from app.db.models import Post

CISA_KEV_URL = (
    "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
)
USER_AGENT = "CyberNarrativeRadar/0.1 (+https://github.com/local; portfolio MVP)"


def _post_id(cve_id: str) -> str:
    digest = hashlib.sha256(f"cisa-kev|{cve_id}".encode("utf-8")).hexdigest()[:20]
    return f"cisa-{digest}"


def _parse_date(raw: str | None) -> datetime:
    if not raw:
        return datetime.now(timezone.utc)
    try:
        # KEV dates are typically YYYY-MM-DD
        return datetime.strptime(raw.strip()[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


def fetch_kev_vulnerabilities(*, max_items: int = 15) -> list[dict]:
    """
    Download the public CISA KEV catalog and return the newest ``max_items`` rows.

    Sorted by ``dateAdded`` descending when present.
    """
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    with httpx.Client(timeout=30.0, follow_redirects=True, headers=headers) as client:
        response = client.get(CISA_KEV_URL)
        response.raise_for_status()
        payload = response.json()

    rows = payload.get("vulnerabilities") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return []

    def sort_key(item: dict) -> str:
        return str(item.get("dateAdded") or "")

    ordered = sorted(
        [row for row in rows if isinstance(row, dict)],
        key=sort_key,
        reverse=True,
    )
    return ordered[: max(0, max_items)]


def upsert_kev_entry(db: Session, row: dict) -> str:
    """Insert or update one KEV vulnerability as a Post. Returns action label."""
    cve_id = str(row.get("cveID") or "").strip().upper()
    if not cve_id:
        return "skipped"

    extracted = extract_cve_ids(cve_id) or extract_cve_ids(json.dumps(row))
    if not extracted:
        extracted = (cve_id,) if cve_id.startswith("CVE-") else ()

    vendor = str(row.get("vendorProject") or "").strip()
    product = str(row.get("product") or "").strip()
    name = str(row.get("vulnerabilityName") or "Known exploited vulnerability").strip()
    summary = str(row.get("shortDescription") or "").strip()
    required = str(row.get("requiredAction") or "").strip()
    date_added = _parse_date(str(row.get("dateAdded") or "") or None)

    title = f"{cve_id}: {name}"[:512]
    content_parts = [
        summary,
        f"Vendor/project: {vendor}." if vendor else "",
        f"Product: {product}." if product else "",
        f"CISA required action: {required}." if required else "",
        "Source: CISA Known Exploited Vulnerabilities catalog.",
    ]
    content = " ".join(part for part in content_parts if part)

    classification = classify_text(f"{title}\n{content}")
    narrative_type = (
        classification.label
        if classification.label != "Unclassified"
        else "Zero-day / critical vulnerability"
    )
    # KEV entries are always vulnerability-centric.
    if extracted:
        narrative_type = "Zero-day / critical vulnerability"

    orgs: list[str] = []
    if vendor:
        orgs.append(vendor)
    organization_mentions = json.dumps(orgs)

    external_id = f"kev-{cve_id}"
    existing = db.scalar(
        select(Post).where(Post.source == "cisa", Post.external_id == external_id).limit(1)
    )
    now = datetime.now(timezone.utc)
    cve_json = cve_ids_to_json(extracted)
    url = f"https://nvd.nist.gov/vuln/detail/{cve_id}"

    if existing is not None:
        existing.title = title
        existing.content = content
        existing.url = url
        existing.published_at = date_added
        existing.organization_mentions = organization_mentions
        existing.narrative_type = narrative_type
        existing.cve_ids = cve_json
        if existing.created_at is None:
            existing.created_at = now
        return "updated"

    db.add(
        Post(
            id=_post_id(cve_id),
            source="cisa",
            external_id=external_id,
            title=title,
            content=content,
            url=url,
            published_at=date_added,
            organization_mentions=organization_mentions,
            narrative_type=narrative_type,
            severity_score=0.7,
            cve_ids=cve_json,
            created_at=now,
        )
    )
    return "inserted"


def ingest_cisa_kev(*, max_items: int = 15) -> dict[str, int]:
    """Ingest recent CISA KEV entries into local Post records."""
    from app.db.session import SessionLocal, init_db

    init_db()
    db = SessionLocal()
    stats = {"fetched": 0, "inserted": 0, "updated": 0, "skipped_errors": 0}
    try:
        rows = fetch_kev_vulnerabilities(max_items=max_items)
        stats["fetched"] = len(rows)
        for row in rows:
            try:
                action = upsert_kev_entry(db, row)
                if action in stats:
                    stats[action] += 1
            except Exception as exc:  # noqa: BLE001
                print(f"[cisa-kev] upsert failed: {exc}")
                stats["skipped_errors"] += 1
        db.commit()
        print(
            "[cisa-kev] done — "
            f"fetched={stats['fetched']} inserted={stats['inserted']} "
            f"updated={stats['updated']} errors={stats['skipped_errors']}"
        )
        return stats
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
