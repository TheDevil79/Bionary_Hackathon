"""GET /health — liveness and readiness check."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from sqlalchemy import text

from app.core.database import get_session_factory
from app.schemas.claim import HealthResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description=(
        "Returns HTTP 200 when the API server is running. "
        "Optionally reports database connectivity."
    ),
)
async def health() -> HealthResponse:
    db_status = await _check_database()
    return HealthResponse(status="ok", database=db_status)


async def _check_database() -> str:
    """
    Attempt a lightweight query to verify the database is reachable.
    Returns 'ok' or 'unavailable' — never raises or crashes.
    """
    factory = get_session_factory()
    if factory is None:
        return "unavailable"

    try:
        async with factory() as session:
            await session.execute(text("SELECT 1"))
        return "ok"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Database health check ping failed: %s", exc)
        return "unavailable"
