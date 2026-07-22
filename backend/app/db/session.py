"""Database engine and session helpers.

Supports SQLite locally and PostgreSQL in deployment via DATABASE_URL.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base


def normalize_database_url(url: str) -> str:
    """
    Normalize provider URLs for SQLAlchemy.

    Many hosts (Railway, Heroku, etc.) emit ``postgres://``; SQLAlchemy expects
    ``postgresql://`` (psycopg2) or an explicit dialect like ``postgresql+psycopg://``.
    """
    cleaned = (url or "").strip()
    if cleaned.startswith("postgres://"):
        return "postgresql://" + cleaned[len("postgres://") :]
    return cleaned


database_url = normalize_database_url(settings.database_url)
is_sqlite = database_url.startswith("sqlite")

if is_sqlite:
    # SQLite does not use a connection pool the same way as Postgres.
    _engine_kwargs: dict = {
        "connect_args": {"check_same_thread": False, "timeout": 30},
    }
else:
    _engine_kwargs = {
        "pool_pre_ping": True,
        "pool_size": 5,
        "max_overflow": 10,
    }

engine = create_engine(database_url, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db() -> None:
    """Create all tables if they do not already exist."""
    # Import models so metadata is registered before create_all.
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Yield a request-scoped database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
