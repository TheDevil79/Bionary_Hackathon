"""
EvidenceLens — Pydantic request/response schemas.

This file is the authoritative Python representation of the API contract
documented in docs/API_CONTRACT.md.

If you change a schema here, update API_CONTRACT.md accordingly and
notify the frontend developer.
"""

from __future__ import annotations

import datetime as dt
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


# ─── Enumerations ─────────────────────────────────────────────────────────────

class Verdict(str, Enum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    MIXED = "MIXED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class Relationship(str, Enum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    CONTEXT_MISMATCH = "CONTEXT_MISMATCH"


# ─── Sub-schemas ──────────────────────────────────────────────────────────────

class AtomicClaim(BaseModel):
    """A single atomic sub-claim extracted from the user input."""
    id: str = Field(..., description="Short identifier e.g. 'C1', 'C2'")
    text: str
    verdict: Verdict
    confidence: float = Field(..., ge=0.0, le=1.0)


class PreviousOccurrence(BaseModel):
    """Prior occurrence of an image/video found in the corpus."""
    date: dt.date | None = None
    source: str | None = None
    url: str | None = None


class MediaAnalysis(BaseModel):
    """Result of perceptual hash / CLIP analysis on uploaded media."""
    analyzed: bool
    matched: bool = False
    similarity: float | None = Field(None, ge=0.0, le=1.0)
    context_mismatch: bool = False
    previous_occurrence: PreviousOccurrence | None = None


class EvidenceItem(BaseModel):
    """A piece of evidence linked to a claim."""
    id: UUID
    title: str
    publisher: str | None = None
    published_at: dt.date | None = None
    url: str | None = None
    excerpt: str
    relationship: Relationship
    relevance_score: float = Field(..., ge=0.0, le=1.0)


# ─── Request ──────────────────────────────────────────────────────────────────
# /analyze accepts multipart/form-data — the FastAPI route declares
# text: str = Form(...) and media: UploadFile | None = File(None)
# directly in the route function (no Pydantic model for requests).


# ─── Response ─────────────────────────────────────────────────────────────────

class AnalyzeResponse(BaseModel):
    """Full verification result returned by POST /analyze."""
    claim_id: UUID
    atomic_claims: list[AtomicClaim]
    verdict: Verdict
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: list[EvidenceItem]
    media_analysis: MediaAnalysis | None = None
    uncertainty: list[str] = Field(default_factory=list)
    analyst_notes: str | None = None


class EvidenceDetailResponse(BaseModel):
    """Full detail for a single evidence item — GET /evidence/{id}."""
    id: UUID
    title: str
    publisher: str | None = None
    published_at: dt.date | None = None
    url: str | None = None
    excerpt: str
    source_type: str | None = None
    language: str | None = None


# ─── Health ───────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    database: str | None = None  # "connected" | "unavailable"


# ─── Error ────────────────────────────────────────────────────────────────────

class ErrorDetail(BaseModel):
    """Standard error body returned on 4xx/5xx."""
    error: str
    detail: str | None = None
