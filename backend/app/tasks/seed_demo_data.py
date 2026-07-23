"""Seed local SQLite with demo organizations, posts, narratives, and alerts."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.models import Alert, AlertEvidence, Narrative, Organization, Post
from app.db.session import SessionLocal, init_db
from app.services.event_notify import notify_api
from app.services.events import (
    EVENT_ALERTS_UPDATED,
    EVENT_NARRATIVES_UPDATED,
    EVENT_NEW_POST,
    publish_alerts_updated,
    publish_narratives_updated,
    publish_new_post,
)


def _hours_ago(hours: float, *, minutes: int = 0) -> datetime:
    """Return a UTC timestamp ``hours`` ago (plus optional minutes)."""
    return datetime.now(timezone.utc) - timedelta(hours=hours, minutes=minutes)


def seed_demo_data(*, reset: bool = True) -> None:
    """Insert a small, deterministic demo dataset for local demos."""
    init_db()
    db = SessionLocal()

    try:
        if reset:
            db.query(AlertEvidence).delete()
            db.query(Alert).delete()
            db.query(Narrative).delete()
            db.query(Post).delete()
            db.query(Organization).delete()
            db.commit()

        existing = db.scalar(select(Organization.id).limit(1))
        if existing is not None:
            print("Demo data already present; skipping seed.")
            return

        # Spread posts across recent hours so volume charts and time-based
        # scoring have a quiet baseline and a busier current window.
        t0 = _hours_ago(0, minutes=10)
        t1 = _hours_ago(0, minutes=25)
        t2 = _hours_ago(0, minutes=40)
        t3 = _hours_ago(1, minutes=5)
        t4 = _hours_ago(2, minutes=20)
        t5 = _hours_ago(5, minutes=15)
        t6 = _hours_ago(12, minutes=30)
        t7 = _hours_ago(26, minutes=10)
        t8 = _hours_ago(48, minutes=45)

        organizations = [
            Organization(
                id="org-acme",
                name="Acme Logistics",
                sector="Transportation",
                tickers=json.dumps(["ACME"]),
                alert_count=1,
                top_narrative_types=json.dumps(["Ransomware", "Supply chain compromise"]),
                risk_score=0.82,
            ),
            Organization(
                id="org-nova",
                name="Nova Bank",
                sector="Financial Services",
                tickers=json.dumps(["NOVA"]),
                alert_count=1,
                top_narrative_types=json.dumps(["Phishing / social engineering"]),
                risk_score=0.64,
            ),
            Organization(
                id="org-helix",
                name="Helix Cloud",
                sector="Technology",
                tickers=json.dumps(["HLX"]),
                alert_count=0,
                top_narrative_types=json.dumps(["Zero-day / critical vulnerability"]),
                risk_score=0.41,
            ),
        ]

        posts = [
            Post(
                id="post-101",
                source="rss",
                external_id="rss-acme-1",
                title="Security researchers note uptick in Acme Logistics mentions",
                content=(
                    "Public reporting mentions Acme Logistics alongside ransomware "
                    "keywords and possible operational disruption."
                ),
                url="https://example.com/rss/acme-ransomware",
                published_at=t0,
                organization_mentions=json.dumps(["Acme Logistics"]),
                narrative_type="Ransomware",
                severity_score=0.86,
                created_at=t0 + timedelta(minutes=1),
            ),
            Post(
                id="post-102",
                source="reddit",
                external_id="reddit-acme-1",
                title="Thread discussing possible Acme Logistics ransomware disruption",
                content=(
                    "Users are discussing LockBit-style ransomware chatter tied to "
                    "Acme Logistics shipping delays."
                ),
                url="https://reddit.com/r/netsec/comments/example",
                published_at=t1,
                organization_mentions=json.dumps(["Acme Logistics"]),
                narrative_type="Ransomware",
                severity_score=0.81,
                created_at=t1 + timedelta(minutes=1),
            ),
            Post(
                id="post-103",
                source="rss",
                external_id="rss-acme-2",
                title="Follow-up: Acme Logistics ransomware payment demand chatter",
                content=(
                    "Additional posts reference a payment demand and encryption attack "
                    "linked to Acme Logistics."
                ),
                url="https://example.com/rss/acme-ransom-followup",
                published_at=t2,
                organization_mentions=json.dumps(["Acme Logistics"]),
                narrative_type="Ransomware",
                severity_score=0.84,
                created_at=t2 + timedelta(minutes=1),
            ),
            Post(
                id="post-201",
                source="synthetic",
                external_id="synthetic-nova-1",
                title="Demo post: fake Nova Bank MFA reset campaign",
                content=(
                    "Synthetic chatter describing phishing messages that impersonate "
                    "Nova Bank MFA reset notices."
                ),
                url=None,
                published_at=t3,
                organization_mentions=json.dumps(["Nova Bank"]),
                narrative_type="Phishing / social engineering",
                severity_score=0.71,
                created_at=t3 + timedelta(minutes=1),
            ),
            Post(
                id="post-202",
                source="rss",
                external_id="rss-nova-1",
                title="Nova Bank customers report phishing lure emails",
                content=(
                    "Reports describe spear phishing and fake login pages targeting "
                    "Nova Bank account holders."
                ),
                url="https://example.com/rss/nova-phishing",
                published_at=t4,
                organization_mentions=json.dumps(["Nova Bank"]),
                narrative_type="Phishing / social engineering",
                severity_score=0.68,
                created_at=t4 + timedelta(minutes=1),
            ),
            Post(
                id="post-301",
                source="rss",
                external_id="rss-helix-1",
                title="Low-confidence chatter around Helix Cloud tooling CVE",
                content=(
                    "Sparse discussion of a possible critical vulnerability in Helix "
                    "Cloud management tooling involving CVE-2024-31337."
                ),
                url="https://example.com/rss/helix-cve",
                published_at=t5,
                organization_mentions=json.dumps(["Helix Cloud"]),
                cve_ids=json.dumps(["CVE-2024-31337"]),
                narrative_type="Zero-day / critical vulnerability",
                severity_score=0.45,
                created_at=t5 + timedelta(minutes=1),
            ),
            Post(
                id="post-302",
                source="rss",
                external_id="rss-helix-2",
                title="Helix Cloud dependency note in security advisory roundup",
                content=(
                    "A brief advisory mentions Helix Cloud in the context of an "
                    "unpatched exploit path related to CVE-2024-31337."
                ),
                url="https://example.com/rss/helix-advisory",
                published_at=t6,
                organization_mentions=json.dumps(["Helix Cloud"]),
                cve_ids=json.dumps(["CVE-2024-31337"]),
                narrative_type="Zero-day / critical vulnerability",
                severity_score=0.42,
                created_at=t6 + timedelta(minutes=1),
            ),
            Post(
                id="post-401",
                source="synthetic",
                external_id="synthetic-general-1",
                title="Quiet baseline: general cyber hygiene reminder",
                content="Routine reminder about patching and MFA with no org-specific spike.",
                url=None,
                published_at=t7,
                organization_mentions=json.dumps([]),
                narrative_type=None,
                severity_score=0.12,
                created_at=t7 + timedelta(minutes=1),
            ),
            Post(
                id="post-402",
                source="rss",
                external_id="rss-general-1",
                title="Quiet baseline: weekly threat briefing digest",
                content="A low-volume briefing digest with no concentrated narrative burst.",
                url="https://example.com/rss/weekly-digest",
                published_at=t8,
                organization_mentions=json.dumps([]),
                narrative_type=None,
                severity_score=0.10,
                created_at=t8 + timedelta(minutes=1),
            ),
        ]

        narratives = [
            Narrative(
                id="nar-001",
                title="Ransomware pressure on logistics operators",
                narrative_type="Ransomware",
                organizations=json.dumps(["Acme Logistics"]),
                volume_24h=48,
                baseline_7d=15.0,
                shift_score=0.88,
                summary=(
                    "Discussion is concentrating on ransomware disruption risks for "
                    "logistics and shipping operators."
                ),
                keywords=json.dumps(["ransomware", "lockbit", "logistics", "disruption"]),
            ),
            Narrative(
                id="nar-002",
                title="Credential phishing aimed at retail banking users",
                narrative_type="Phishing / social engineering",
                organizations=json.dumps(["Nova Bank"]),
                volume_24h=31,
                baseline_7d=18.5,
                shift_score=0.67,
                summary=(
                    "A phishing narrative is forming around fake account-security "
                    "messages targeting bank customers."
                ),
                keywords=json.dumps(["phishing", "mfa", "credentials", "bank"]),
            ),
            Narrative(
                id="nar-003",
                title="Critical vulnerability chatter in cloud tooling",
                narrative_type="Zero-day / critical vulnerability",
                organizations=json.dumps(["Helix Cloud"]),
                volume_24h=12,
                baseline_7d=9.0,
                shift_score=0.39,
                summary=(
                    "Low-confidence chatter around a possible critical vulnerability "
                    "in cloud management tooling."
                ),
                keywords=json.dumps(["zero-day", "cve", "cloud", "exploit"]),
            ),
        ]

        alerts = [
            Alert(
                id="alert-001",
                title="Elevated ransomware chatter around Acme Logistics",
                narrative_type="Ransomware",
                organization_id="org-acme",
                organization_name="Acme Logistics",
                sector="Transportation",
                severity="high",
                score=0.86,
                summary=(
                    "Public discussion volume mentioning Acme Logistics and ransomware "
                    "keywords rose sharply in the last 24 hours."
                ),
                why_flagged=json.dumps(
                    [
                        "3.2x volume spike vs 7-day baseline",
                        "Keyword cluster: ransomware, lockbit, payment demand",
                        "Multiple independent sources in short window",
                    ]
                ),
            ),
            Alert(
                id="alert-002",
                title="Phishing narrative forming around Nova Bank customers",
                narrative_type="Phishing / social engineering",
                organization_id="org-nova",
                organization_name="Nova Bank",
                sector="Financial Services",
                severity="medium",
                score=0.71,
                summary=(
                    "Synthetic and public chatter suggests a coordinated phishing theme "
                    "targeting Nova Bank account holders."
                ),
                why_flagged=json.dumps(
                    [
                        "Rising share of phishing-related keywords",
                        "Organization entity density above threshold",
                        "Narrative type classifier confidence 0.71",
                    ]
                ),
            ),
        ]

        evidence = [
            AlertEvidence(
                id="ev-101",
                alert_id="alert-001",
                post_id="post-101",
                source="rss",
                title="Security researchers note uptick in Acme Logistics mentions",
                url="https://example.com/rss/acme-ransomware",
                published_at=t0,
            ),
            AlertEvidence(
                id="ev-102",
                alert_id="alert-001",
                post_id="post-102",
                source="reddit",
                title="Thread discussing possible Acme Logistics ransomware disruption",
                url="https://reddit.com/r/netsec/comments/example",
                published_at=t1,
            ),
            AlertEvidence(
                id="ev-103",
                alert_id="alert-001",
                post_id="post-103",
                source="rss",
                title="Follow-up: Acme Logistics ransomware payment demand chatter",
                url="https://example.com/rss/acme-ransom-followup",
                published_at=t2,
            ),
            AlertEvidence(
                id="ev-201",
                alert_id="alert-002",
                post_id="post-201",
                source="synthetic",
                title="Demo post: fake Nova Bank MFA reset campaign",
                url=None,
                published_at=t3,
            ),
        ]

        db.add_all(organizations)
        db.add_all(posts)
        db.add_all(narratives)
        db.add_all(alerts)
        db.add_all(evidence)
        db.commit()

        publish_new_post(source="seed_demo_data", count=len(posts))
        publish_alerts_updated(source="seed_demo_data", count=len(alerts))
        publish_narratives_updated(source="seed_demo_data", count=len(narratives))
        notify_api(EVENT_NEW_POST, source="seed_demo_data", count=len(posts))
        notify_api(EVENT_ALERTS_UPDATED, source="seed_demo_data", count=len(alerts))
        notify_api(
            EVENT_NARRATIVES_UPDATED,
            source="seed_demo_data",
            count=len(narratives),
        )

        print(
            "Seeded demo data: "
            f"{len(organizations)} orgs, {len(posts)} posts, "
            f"{len(narratives)} narratives, {len(alerts)} alerts "
            "(posts spread across recent hours)."
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_data()
