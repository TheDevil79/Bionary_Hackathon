"""
POST /analyze — Main claim verification endpoint.

Accepts multipart/form-data with:
  text  (required) — the claim or social-media post text
  media (optional) — an image or video file

Pipeline:
  1. Validate input
  2. ClaimExtractor  → extract atomic claims
  3. EvidenceRetriever → search evidence corpus per claim
  4. MediaAnalyzer  → analyze uploaded media (if any)
  5. VerdictEngine  → synthesize final verdict
  6. Return AnalyzeResponse
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status

from app.core.config import settings
from app.schemas.claim import AnalyzeResponse, EvidenceItem
from app.services import (
    claim_extractor,
    evidence_retriever,
    media_analyzer,
    verdict_engine,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["claims"])

# Allowed media content types
_ALLOWED_MEDIA_TYPES = media_analyzer.SUPPORTED_MEDIA_TYPES


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify a claim",
    description=(
        "Submit a text claim and an optional media file. "
        "Returns atomic claims, supporting/contradicting evidence, "
        "media provenance analysis, and an overall verdict."
    ),
)
async def analyze(
    request: Request,
    text: str = Form(..., description="The claim or social-media post to verify."),
    media: UploadFile | None = File(
        None, description="Optional image or video file (max 20 MB)."
    ),
) -> AnalyzeResponse:

    # ── 1. Input validation ───────────────────────────────────────────────────
    text = text.strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="'text' must not be empty.",
        )

    if media is not None:
        # Check content type
        content_type = media.content_type or ""
        if content_type not in _ALLOWED_MEDIA_TYPES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=(
                    f"Unsupported media type '{content_type}'. "
                    f"Allowed: {', '.join(sorted(_ALLOWED_MEDIA_TYPES))}"
                ),
            )

        # Check file size
        contents = await media.read()
        if len(contents) > settings.max_upload_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=(
                    f"File exceeds the maximum allowed size of "
                    f"{settings.max_upload_bytes // (1024 * 1024)} MB."
                ),
            )
        # Rewind so the analyzer can read it
        await media.seek(0)

    # ── 2. Claim extraction ───────────────────────────────────────────────────
    try:
        claims = await claim_extractor.extract_claims(text)
    except Exception as exc:
        logger.exception("ClaimExtractor failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Claim extraction service is unavailable. Please try again later.",
        ) from exc

    # ── 3. Evidence retrieval (per claim, deduplicated) ───────────────────────
    # Build per-claim evidence map so the verdict engine can assess each claim
    # against exactly the evidence retrieved for it.
    evidence_per_claim: dict[str, list[EvidenceItem]] = {}
    all_evidence_map: dict[str, EvidenceItem] = {}
    try:
        for claim in claims:
            items = await evidence_retriever.search(claim)
            evidence_per_claim[claim.id] = items
            for item in items:
                all_evidence_map[str(item.id)] = item
    except Exception as exc:
        logger.exception("EvidenceRetriever failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Evidence retrieval service is unavailable. Please try again later.",
        ) from exc

    all_evidence = list(all_evidence_map.values())

    # ── 4. Media analysis ─────────────────────────────────────────────────────
    try:
        media_result = await media_analyzer.analyze(media, claim_text=text)
    except ValueError as exc:
        # Raised for unsupported type (belt-and-suspenders; already checked above)
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("MediaAnalyzer failed — continuing without media analysis")
        media_result = None  # degrade gracefully

    # ── 5. Verdict synthesis ──────────────────────────────────────────────────
    try:
        result = await verdict_engine.verify(
            claims, evidence_per_claim, all_evidence, media_result
        )
    except Exception as exc:
        logger.exception("VerdictEngine failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Verdict engine is unavailable. Please try again later.",
        ) from exc

    return result
