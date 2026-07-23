"""Environment-based application settings for local and deployed runs."""

from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    app_name: str = "Cyber Narrative Radar API"
    app_version: str = "0.1.0"
    api_prefix: str = "/api"
    environment: str = Field(default="local", description="local | production")

    # Local default is SQLite; set DATABASE_URL for Postgres (or other) in deployment.
    database_url: str = Field(
        default="sqlite:///./cyber_narrative_radar.db",
        description="SQLAlchemy database URL (env: DATABASE_URL)",
    )

    # Primary frontend origin used for CORS (env: FRONTEND_URL).
    frontend_url: str = Field(
        default="http://localhost:5173",
        description="Deployed or local frontend origin (env: FRONTEND_URL)",
    )

    # Optional comma-separated extra origins, e.g. "https://a.com,https://b.com"
    cors_origins: str = Field(
        default="",
        description="Extra CORS origins as a comma-separated string (env: CORS_ORIGINS)",
    )

    # Optional near-real-time RSS loop inside the API process (env: LIVE_INGEST=1).
    live_ingest_enabled: bool = Field(
        default=False,
        description="When true, schedule RSS ingest + scoring in the API lifespan",
        validation_alias=AliasChoices("LIVE_INGEST", "live_ingest_enabled"),
    )
    live_ingest_interval_seconds: int = Field(
        default=180,
        ge=30,
        description="Seconds between scheduled RSS ingest runs (default 3 minutes)",
        validation_alias=AliasChoices(
            "LIVE_INGEST_INTERVAL_SECONDS",
            "live_ingest_interval_seconds",
        ),
    )
    # Auto-alerts from scoring: create/update alerts when post score >= threshold.
    auto_alert_min_score: float = Field(
        default=45.0,
        ge=0.0,
        le=100.0,
        description="Minimum 0-100 anomaly score to upsert an auto-generated alert",
        validation_alias=AliasChoices("AUTO_ALERT_MIN_SCORE", "auto_alert_min_score"),
    )

    # Reddit collector (public JSON by default; optional app-only OAuth).
    reddit_enabled: bool = Field(
        default=True,
        description="Include Reddit in ingest_rss / live ingest when true",
        validation_alias=AliasChoices("REDDIT_ENABLED", "reddit_enabled"),
    )
    reddit_subreddits: str = Field(
        default="netsec,cybersecurity,blueteamsec",
        description="Comma-separated subreddit names",
        validation_alias=AliasChoices("REDDIT_SUBREDDITS", "reddit_subreddits"),
    )
    reddit_client_id: str = Field(
        default="",
        description="Optional Reddit app client id for OAuth",
        validation_alias=AliasChoices("REDDIT_CLIENT_ID", "reddit_client_id"),
    )
    reddit_client_secret: str = Field(
        default="",
        description="Optional Reddit app client secret for OAuth",
        validation_alias=AliasChoices("REDDIT_CLIENT_SECRET", "reddit_client_secret"),
    )

    @field_validator("frontend_url")
    @classmethod
    def _strip_frontend_url(cls, value: str) -> str:
        return (value or "").strip()

    @field_validator("live_ingest_enabled", "reddit_enabled", mode="before")
    @classmethod
    def _parse_bool_flag(cls, value: object) -> bool:
        """Accept 1/true/yes/on style env flags."""
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        """Strip and normalize provider URLs (postgres:// → postgresql://)."""
        cleaned = (value or "").strip()
        if cleaned.startswith("postgres://"):
            return "postgresql://" + cleaned[len("postgres://") :]
        return cleaned

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    def resolved_cors_origins(self) -> list[str]:
        """Build the CORS allowlist from FRONTEND_URL plus optional extras."""
        origins: list[str] = []

        def add(origin: str) -> None:
            cleaned = origin.strip().rstrip("/")
            if cleaned and cleaned not in origins:
                origins.append(cleaned)

        add(self.frontend_url)
        # Local Vite defaults so local demos keep working without extra env.
        add("http://localhost:5173")
        add("http://127.0.0.1:5173")

        if self.cors_origins:
            for part in self.cors_origins.split(","):
                add(part)

        return origins


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()
