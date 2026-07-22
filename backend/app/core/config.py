"""Environment-based application settings for local and deployed runs."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
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

    @field_validator("frontend_url", "database_url")
    @classmethod
    def _strip_value(cls, value: str) -> str:
        return (value or "").strip()

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
