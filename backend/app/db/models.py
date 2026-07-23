"""ORM models for the local-first SQLite MVP."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Organization(Base):
    """Watchlist organization tracked for cyber narrative activity."""

    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    sector: Mapped[str] = mapped_column(String(128), index=True)
    tickers: Mapped[str] = mapped_column(Text, default="[]")  # JSON list as text
    alert_count: Mapped[int] = mapped_column(Integer, default=0)
    top_narrative_types: Mapped[str] = mapped_column(Text, default="[]")  # JSON list
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    alerts: Mapped[list["Alert"]] = relationship(back_populates="organization")


class Post(Base):
    """Normalized public or synthetic discourse record."""

    __tablename__ = "posts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[str] = mapped_column(String(64), index=True)  # rss | reddit | synthetic
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(512), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True, index=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    organization_mentions: Mapped[str] = mapped_column(Text, default="[]")  # JSON list
    # Extracted CVE IDs (JSON list), e.g. ["CVE-2024-1234"].
    cve_ids: Mapped[str] = mapped_column(Text, default="[]")
    narrative_type: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    # Deterministic 0-1 score for ranking / future anomaly workflows.
    severity_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )

    evidence_links: Mapped[list["AlertEvidence"]] = relationship(back_populates="post")


class Narrative(Base):
    """Clustered cyber narrative with volume and shift signals."""

    __tablename__ = "narratives"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(512))
    narrative_type: Mapped[str] = mapped_column(String(128), index=True)
    organizations: Mapped[str] = mapped_column(Text, default="[]")  # JSON list of org names
    volume_24h: Mapped[int] = mapped_column(Integer, default=0)
    baseline_7d: Mapped[float] = mapped_column(Float, default=0.0)
    shift_score: Mapped[float] = mapped_column(Float, default=0.0)
    summary: Mapped[str] = mapped_column(Text, default="")
    keywords: Mapped[str] = mapped_column(Text, default="[]")  # JSON list
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Alert(Base):
    """Explainable alert raised from narrative/activity signals."""

    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(512))
    narrative_type: Mapped[str] = mapped_column(String(128), index=True)
    organization_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("organizations.id"),
        nullable=True,
        index=True,
    )
    organization_name: Mapped[str] = mapped_column(String(255), index=True)
    sector: Mapped[str] = mapped_column(String(128), default="")
    severity: Mapped[str] = mapped_column(String(32), default="medium", index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    summary: Mapped[str] = mapped_column(Text, default="")
    why_flagged: Mapped[str] = mapped_column(Text, default="[]")  # JSON list
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organization: Mapped[Organization | None] = relationship(back_populates="alerts")
    evidence: Mapped[list["AlertEvidence"]] = relationship(
        back_populates="alert",
        cascade="all, delete-orphan",
    )


class AlertEvidence(Base):
    """Evidence post linked to an alert for explainability."""

    __tablename__ = "alert_evidence"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    alert_id: Mapped[str] = mapped_column(String(64), ForeignKey("alerts.id"), index=True)
    post_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("posts.id"),
        nullable=True,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(512))
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    alert: Mapped[Alert] = relationship(back_populates="evidence")
    post: Mapped[Post | None] = relationship(back_populates="evidence_links")
