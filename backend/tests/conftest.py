"""
Test fixtures for EvidenceLens backend.

Uses httpx.AsyncClient with the FastAPI app directly (no real server needed).
Database is NOT connected during unit tests — services use their mock implementations.
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Set a dummy DATABASE_URL so Settings doesn't raise on import
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("GEMINI_API_KEY", "test-key")

from app.main import app


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """Async test client wired directly to the FastAPI app."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac
