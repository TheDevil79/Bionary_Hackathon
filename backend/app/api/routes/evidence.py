"""GET /evidence/{id} — retrieve a single evidence item by ID."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.core.database import get_db
from app.models.evidence import EvidenceChunk, Source
from app.schemas.claim import EvidenceDetailResponse

router = APIRouter(tags=["evidence"])


@router.get(
    "/evidence/{evidence_id}",
    response_model=EvidenceDetailResponse,
    summary="Get evidence item",
    description="Retrieve the full detail of a single evidence chunk by its UUID.",
)
async def get_evidence(
    evidence_id: uuid.UUID,
    db: AsyncSession | None = Depends(get_db),
) -> EvidenceDetailResponse:

    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is unavailable.",
        )

    result = await db.execute(
        select(EvidenceChunk, Source)
        .join(Source, EvidenceChunk.source_id == Source.id)
        .where(EvidenceChunk.id == evidence_id)
    )
    row = result.first()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence item '{evidence_id}' not found.",
        )

    chunk, source = row
    return EvidenceDetailResponse(
        id=chunk.id,
        title=source.title,
        publisher=source.publisher,
        published_at=source.published_at.date() if source.published_at else None,
        url=source.url,
        excerpt=chunk.text,
        source_type=source.source_type,
        language=source.language,
    )
