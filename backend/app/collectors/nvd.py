"""NVD CVE 2.0 API ingest (public, recent vulnerabilities)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.cve import cve_ids_to_json, extract_cve_ids
from app.db.models import Post

NVD_CVE_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"
USER_AGENT = "CyberNarrativeRadar/0.1 (+https://github.com/local; portfolio MVP)"


def _post_id(cve_id: str) -> str:
    digest = hashlib.sha256(f"nvd|{cve_id}".encode("utf-8")).hexdigest()[:20]
    return f"nvd-{digest}"


def _parse_iso(raw: str | None) -> datetime:
    if not raw:
        return datetime.now(timezone.utc)
    text = raw.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _english_description(cve_item: dict) -> str:
    descriptions = (
        cve_item.get("cve", {}).get("descriptions")
        if isinstance(cve_item.get("cve"), dict)
        else None
    )
    if not isinstance(descriptions, list):
        return ""
    for item in descriptions:
        if isinstance(item, dict) and item.get("lang") == "en":
            return str(item.get("value") or "").strip()
    for item in descriptions:
        if isinstance(item, dict):
            value = str(item.get("value") or "").strip()
            if value:
                return value
    return ""


def _cvss_hint(cve_item: dict) -> str:
    metrics = (
        cve_item.get("cve", {}).get("metrics")
        if isinstance(cve_item.get("cve"), dict)
        else None
    )
    if not isinstance(metrics, dict):
        return ""
    for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        rows = metrics.get(key)
        if not isinstance(rows, list) or not rows:
            continue
        first = rows[0]
        if not isinstance(first, dict):
            continue
        data = first.get("cvssData") if isinstance(first.get("cvssData"), dict) else {}
        score = data.get("baseScore")
        severity = data.get("baseSeverity") or first.get("baseSeverity")
        if score is not None:
            return f"CVSS base score {score}" + (f" ({severity})" if severity else "") + "."
    return ""


def fetch_recent_nvd_cves(
    *,
    results_per_page: int = 10,
    lookback_days: int = 7,
) -> list[dict]:
    """
    Fetch recently published CVEs from the public NVD 2.0 API.

    No API key required for low-volume portfolio demos; respect rate limits.
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=max(1, lookback_days))
    # NVD expects ISO-8601 with milliseconds and timezone offset.
    fmt = "%Y-%m-%dT%H:%M:%S.000"
    params = {
        "resultsPerPage": max(1, min(results_per_page, 50)),
        "pubStartDate": start.strftime(fmt) + "%2B00:00",
        "pubEndDate": end.strftime(fmt) + "%2B00:00",
    }
    # httpx encodes +; NVD wants literal +00:00 — pass prebuilt query via URL.
    query = (
        f"{NVD_CVE_API}?resultsPerPage={params['resultsPerPage']}"
        f"&pubStartDate={start.strftime(fmt)}%2B00:00"
        f"&pubEndDate={end.strftime(fmt)}%2B00:00"
    )
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    with httpx.Client(timeout=45.0, follow_redirects=True, headers=headers) as client:
        response = client.get(query)
        response.raise_for_status()
        payload = response.json()

    items = payload.get("vulnerabilities") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def upsert_nvd_entry(db: Session, item: dict) -> str:
    """Insert or update one NVD CVE as a Post."""
    cve_obj = item.get("cve") if isinstance(item.get("cve"), dict) else {}
    cve_id = str(cve_obj.get("id") or "").strip().upper()
    if not cve_id:
        return "skipped"

    description = _english_description(item)
    cvss = _cvss_hint(item)
    published = _parse_iso(str(cve_obj.get("published") or "") or None)
    title = f"{cve_id}: NVD vulnerability record"[:512]
    content = " ".join(
        part
        for part in (
            description,
            cvss,
            "Source: NIST National Vulnerability Database (NVD) API 2.0.",
        )
        if part
    )
    extracted = extract_cve_ids(f"{cve_id} {description}") or (cve_id,)
    external_id = f"nvd-{cve_id}"
    now = datetime.now(timezone.utc)
    url = f"https://nvd.nist.gov/vuln/detail/{cve_id}"

    existing = db.scalar(
        select(Post).where(Post.source == "nvd", Post.external_id == external_id).limit(1)
    )
    payload = {
        "title": title,
        "content": content,
        "url": url,
        "published_at": published,
        "organization_mentions": json.dumps([]),
        "narrative_type": "Zero-day / critical vulnerability",
        "cve_ids": cve_ids_to_json(extracted),
        "severity_score": 0.65,
    }

    if existing is not None:
        for key, value in payload.items():
            setattr(existing, key, value)
        if existing.created_at is None:
            existing.created_at = now
        return "updated"

    db.add(
        Post(
            id=_post_id(cve_id),
            source="nvd",
            external_id=external_id,
            created_at=now,
            **payload,
        )
    )
    return "inserted"


def ingest_nvd_recent(
    *,
    results_per_page: int = 10,
    lookback_days: int = 7,
) -> dict[str, int]:
    """Ingest recent NVD CVE records into local Post rows."""
    from app.db.session import SessionLocal, init_db

    init_db()
    db = SessionLocal()
    stats = {"fetched": 0, "inserted": 0, "updated": 0, "skipped_errors": 0}
    try:
        items = fetch_recent_nvd_cves(
            results_per_page=results_per_page,
            lookback_days=lookback_days,
        )
        stats["fetched"] = len(items)
        for item in items:
            try:
                action = upsert_nvd_entry(db, item)
                if action in stats:
                    stats[action] += 1
            except Exception as exc:  # noqa: BLE001
                print(f"[nvd] upsert failed: {exc}")
                stats["skipped_errors"] += 1
        db.commit()
        print(
            "[nvd] done — "
            f"fetched={stats['fetched']} inserted={stats['inserted']} "
            f"updated={stats['updated']} errors={stats['skipped_errors']}"
        )
        return stats
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
