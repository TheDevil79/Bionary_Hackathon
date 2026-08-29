"""
EvidenceLens — Application configuration.

All settings are loaded from environment variables.
Never hard-code secrets here.

Usage:
    from app.core.config import settings
    settings.async_database_url
"""

from __future__ import annotations

import json
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
    database_url: str = ""
    """
    PostgreSQL connection string.
    Supports standard postgresql://, postgres://, or postgresql+asyncpg://
    Example (local):    postgresql://user:pass@localhost:5432/evidencelens
    Example (Supabase): postgresql://postgres:[PASSWORD]@db.[REF].supabase.co:5432/postgres
    """

    # ── AI Services ────────────────────────────────────────────────────────────
    gemini_api_key: str = ""

    # ── Local LLM (Ollama) — fallback when Gemini is rate-limited ─────────────
    ollama_model: str = "gemma3:12b"
    ollama_base_url: str = "http://localhost:11434"


    # ── CORS ───────────────────────────────────────────────────────────────────
    # Typed as str | list[str] so Pydantic Settings accepts raw comma-separated env strings without failing JSON decode
    cors_origins: str | list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    @field_validator("cors_origins", mode="after")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Ensure cors_origins is always returned as a list of strings."""
        if isinstance(v, str):
            trimmed = v.strip()
            if trimmed.startswith("[") and trimmed.endswith("]"):
                try:
                    parsed = json.loads(trimmed)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except Exception:
                    pass
            return [origin.strip() for origin in trimmed.split(",") if origin.strip()]
        return [origin.strip() for origin in v if origin.strip()]

    # ── Upload limits ──────────────────────────────────────────────────────────
    max_upload_bytes: int = 20 * 1024 * 1024  # 20 MB

    # ── Web Evidence & Source Reliability ──────────────────────────────────────
    web_search_enabled: bool = True
    web_search_model: str = "gemini-3.6-flash"

    trusted_domains_tier_1: list[str] = [
        "who.int",
        "un.org",
        "unesco.org",
        "worldbank.org",
        "imf.org",
        "wmo.int",
        "nasa.gov",
        "nih.gov",
        "cdc.gov",
        "nature.com",
        "science.org",
        "nejm.org",
        "thelancet.com",
        "ncbi.nlm.nih.gov",
        "reuters.com",
        "apnews.com",
        "bbc.com",
        "bbc.co.uk",
        "weather.gov",
        "mausam.imd.gov.in",
        "imd.gov.in",
    ]

    trusted_domains_tier_2: list[str] = [
        "wikipedia.org",
        "britannica.com",
        "theguardian.com",
        "nytimes.com",
        "washingtonpost.com",
        "wsj.com",
        "bloomberg.com",
        "afp.com",
        "aljazeera.com",
        "sciencedirect.com",
        "cell.com",
        "pnas.org",
        "factcheck.org",
        "snopes.com",
        "politifact.com",
        "fullfact.org",
        "thehindu.com",
        "indianexpress.com",
        "ndtv.com",
    ]

    blocked_domains: list[str] = [
        # Social media & video platforms
        "instagram.com",
        "facebook.com",
        "tiktok.com",
        "threads.net",
        "pinterest.com",
        "youtube.com",
        "youtu.be",
        "twitter.com",
        "x.com",
        "vimeo.com",
        "dailymotion.com",
        "reddit.com",
        # Stock photo & creative asset marketplaces (contain fictional stock titles)
        "shutterstock.com",
        "gettyimages.com",
        "istockphoto.com",
        "stock.adobe.com",
        "adobestock.com",
        "alamy.com",
        "dreamstime.com",
        "freepik.com",
        "123rf.com",
        "vectorstock.com",
        "pixabay.com",
        "pexels.com",
        "unsplash.com",
        "deviantart.com",
        "artstation.com",
        "wallpapercave.com",
        "wallpaperflare.com",
        "zedge.net",
        # E-commerce & merchandise
        "amazon.com",
        "ebay.com",
        "aliexpress.com",
        "etsy.com",
        "redbubble.com",
        # Known clickbait & spam
        "clickbait.example",
        "spam-archive.xyz",
        "fakenews-daily.co",
    ]



    # ── Derived helpers ────────────────────────────────────────────────────────
    @property
    def is_development(self) -> bool:
        return self.app_env.lower() == "development"

    @property
    def async_database_url(self) -> str:
        """
        Normalize database_url to use the asyncpg dialect.
        Handles postgres:// and postgresql:// prefixes automatically.
        """
        url = self.database_url.strip()
        if not url:
            return ""
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://") :]
        if url.startswith("postgresql://") and not url.startswith(
            "postgresql+asyncpg://"
        ):
            url = "postgresql+asyncpg://" + url[len("postgresql://") :]
        return url

    @property
    def database_url_sync(self) -> str:
        """
        Synchronous version of the DB URL for Alembic migrations.
        Strips async driver modifiers.
        """
        url = self.database_url.strip()
        if not url:
            return ""
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://") :]
        if url.startswith("postgresql+asyncpg://"):
            url = "postgresql://" + url[len("postgresql+asyncpg://") :]
        return url


# Singleton instance — import this everywhere.
settings = Settings()
