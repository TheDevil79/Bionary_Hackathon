"""
EvidenceLens — Async database engine and session factory.

Uses SQLAlchemy 2.x async engine backed by asyncpg.
The pgvector extension must be enabled in PostgreSQL before running migrations:
    CREATE EXTENSION IF NOT EXISTS vector;

Usage (as a FastAPI dependency):
    from app.core.database import get_db
    async def my_route(db: AsyncSession = Depends(get_db)): ...
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

logger = logging.getLogger(__name__)


# ── Declarative base ──────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    """All ORM models inherit from this base."""
    pass


# ── Engine & Session Helpers ──────────────────────────────────────────────────

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine | None:
    """Lazily construct and cache the async engine."""
    global _engine
    if _engine is None:
        db_url = settings.async_database_url
        if not db_url:
            logger.info("DATABASE_URL is not set in environment.")
            return None

        connect_args: dict = {}
        if "supabase.com" in db_url or ":6543" in db_url or ":5432" in db_url:
            connect_args["ssl"] = "require"
            connect_args["statement_cache_size"] = 0
            connect_args["prepared_statement_cache_size"] = 0

        try:
            _engine = create_async_engine(
                db_url,
                echo=False,
                future=True,
                pool_pre_ping=True,
                connect_args=connect_args,
            )
        except Exception as exc:
            logger.warning("Could not initialize database engine: %s", exc)
            return None
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession] | None:
    """Lazily construct and cache the async session factory."""
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        if engine is not None:
            _session_factory = async_sessionmaker(
                bind=engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            )
    return _session_factory


# ── Dependency ────────────────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession | None, None]:
    """FastAPI dependency that yields an async database session."""
    factory = get_session_factory()
    if factory is None:
        yield None
        return

    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
