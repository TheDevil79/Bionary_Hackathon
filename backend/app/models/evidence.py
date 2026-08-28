"""
EvidenceLens — ORM models.

Tables:
  sources          — original documents/articles in the evidence corpus
  evidence_chunks  — text chunks with pgvector embeddings
  claims           — submitted claims from /analyze requests
  claim_evidence   — many-to-many join with relationship labels
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship as sa_relationship
from sqlalchemy.sql import func

from app.core.database import Base


# ── Sources ───────────────────────────────────────────────────────────────────

class Source(Base):
    """
    An original document that serves as an evidence source.
    E.g. a news article, fact-check report, or academic paper.
    """
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    publisher: Mapped[str | None] = mapped_column(String(256))
    url: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_type: Mapped[str | None] = mapped_column(
        String(64)
    )  # "news" | "fact-check" | "academic" | "social"
    license: Mapped[str | None] = mapped_column(String(128))
    language: Mapped[str | None] = mapped_column(String(16))
    content_hash: Mapped[str | None] = mapped_column(
        String(64), unique=True, index=True
    )  # SHA-256 of the raw content to prevent duplicates
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    chunks: Mapped[list[EvidenceChunk]] = sa_relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


# ── Evidence chunks ───────────────────────────────────────────────────────────

class EvidenceChunk(Base):
    """
    A text chunk from a Source document, with a pgvector embedding
    for semantic similarity search.
    """
    __tablename__ = "evidence_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(768)
    )  # 768-dim for all-mpnet-base-v2; adjust if using a different model
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    source: Mapped[Source] = sa_relationship(back_populates="chunks")
    claim_links: Mapped[list[ClaimEvidence]] = sa_relationship(
        back_populates="evidence", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # IVFFlat index for approximate nearest-neighbour search
        # Tune lists= based on corpus size (rule of thumb: rows / 1000)
        Index(
            "ix_evidence_chunks_embedding",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


# ── Claims ────────────────────────────────────────────────────────────────────

class Claim(Base):
    """
    A submitted claim (from a /analyze request).
    One request may decompose into several atomic sub-claims.
    """
    __tablename__ = "claims"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("claims.id", ondelete="SET NULL"), nullable=True
    )  # NULL = top-level claim; non-NULL = atomic sub-claim
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    evidence_links: Mapped[list[ClaimEvidence]] = sa_relationship(
        back_populates="claim", cascade="all, delete-orphan"
    )


# ── Claim ↔ Evidence relationship ─────────────────────────────────────────────

class ClaimEvidence(Base):
    """
    Many-to-many join between a Claim and an EvidenceChunk.
    Stores the relationship type and relevance score.
    """
    __tablename__ = "claim_evidence"

    claim_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("claims.id", ondelete="CASCADE"), primary_key=True
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence_chunks.id", ondelete="CASCADE"), primary_key=True
    )
    relationship: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # "SUPPORTS" | "CONTRADICTS" | "CONTEXT_MISMATCH"
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)

    claim: Mapped[Claim] = sa_relationship(back_populates="evidence_links")
    evidence: Mapped[EvidenceChunk] = sa_relationship(back_populates="claim_links")

    __table_args__ = (
        UniqueConstraint("claim_id", "evidence_id", name="uq_claim_evidence"),
    )
