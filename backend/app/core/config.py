"""
EvidenceLens — Application configuration.

All settings are loaded from environment variables.
Never hard-code secrets here.

Usage:
    from app.core.config import settings
    settings.database_url
"""

from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────────────────
    app_env: str = "development"
    app_title: str = "EvidenceLens API"
    app_version: str = "0.1.0"

    # ── Database ───────────────────────────────────────────────────────────────
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/evidencelens"
    )
    """
    Full async SQLAlchemy connection string.
    Example (local):    postgresql+asyncpg://user:pass@localhost:5432/evidencelens
    Example (Supabase): postgresql+asyncpg://postgres:[PASSWORD]@db.[REF].supabase.co:5432/postgres
    """

    # ── AI Services ────────────────────────────────────────────────────────────
    gemini_api_key: str = ""

    # ── CORS ───────────────────────────────────────────────────────────────────
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Accept either a comma-separated string or a list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # ── Upload limits ──────────────────────────────────────────────────────────
    max_upload_bytes: int = 20 * 1024 * 1024  # 20 MB

    # ── Derived helpers ────────────────────────────────────────────────────────
    @property
    def is_development(self) -> bool:
        return self.app_env.lower() == "development"

    @property
    def database_url_sync(self) -> str:
        """Synchronous version of the DB URL (used by Alembic migrations)."""
        return self.database_url.replace("+asyncpg", "")


# Singleton instance — import this everywhere.
settings = Settings()
