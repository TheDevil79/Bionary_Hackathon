"""
EvidenceLens — Evidence Retriever Service.

Responsibility: given a claim or query string, generate a 768-dim query embedding
and perform a pgvector cosine similarity search against evidence_chunks joined with sources.

Returns ranked EvidenceItem objects with full provenance (source title, publisher,
publication date, URL, chunk excerpt, and normalized similarity score).
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session_factory
from app.ingestion.embedder import get_embedder
from app.models.evidence import EvidenceChunk, Source
from app.schemas.claim import AtomicClaim, EvidenceItem, Relationship

logger = logging.getLogger(__name__)


# ─── Public Interface ─────────────────────────────────────────────────────────

async def search(
    claim: AtomicClaim | str,
    top_k: int = 5,
    session: AsyncSession | None = None,
) -> list[EvidenceItem]:
    """
    Retrieve evidence items relevant to the given atomic claim or query string.

    Args:
        claim: AtomicClaim instance or raw query string.
        top_k: Maximum number of evidence items to return.
        session: Optional external AsyncSession. If None, acquires from factory.

    Returns:
        List of EvidenceItem objects ordered by relevance score descending.
    """
    query_text = claim.text if isinstance(claim, AtomicClaim) else str(claim)
    query_text = query_text.strip()

    if not query_text:
        logger.warning("Empty query provided to EvidenceRetriever.search()")
        return []

    logger.info("Executing pgvector semantic search for query: '%s' (top_k=%d)", query_text[:80], top_k)

    # 1. Generate query embedding (768-dim normalized vector)
    embedder = get_embedder()
    query_vector = embedder.embed_query(query_text)

    # 2. Database search
    own_session = False
    if session is None:
        factory = get_session_factory()
        if factory is None:
            logger.warning("Database unavailable, falling back to mock evidence.")
            return _mock_search(query_text, top_k)
        session = factory()
        own_session = True

    try:
        # Distance metric: Cosine distance (via pgvector vector_cosine_ops <=>)
        # For unit-normalized vectors: cosine_distance = 1 - cosine_similarity
        distance_col = EvidenceChunk.embedding.cosine_distance(query_vector).label("distance")

        # Set ivfflat.probes for high recall across all clusters on demo/small corpora
        try:
            from sqlalchemy import text
            await session.execute(text("SET ivfflat.probes = 10;"))
        except Exception:
            pass

        stmt = (
            select(EvidenceChunk, Source, distance_col)
            .join(Source, EvidenceChunk.source_id == Source.id)
            .order_by(distance_col.asc())
            .limit(top_k)
        )

        import asyncio
        result = await asyncio.wait_for(session.execute(stmt), timeout=4.0)
        rows = result.all()

        if not rows:
            logger.info("No evidence chunks found in database.")
            return []

        evidence_items: list[EvidenceItem] = []
        for chunk, source, dist in rows:
            # Convert cosine distance to normalized similarity score [0.0, 1.0]
            # dist can be between 0.0 (identical) and 2.0 (opposite)
            raw_sim = 1.0 - float(dist) if dist is not None else 0.0
            relevance_score = round(max(0.0, min(1.0, raw_sim)), 4)

            # Heuristic default relationship placeholder (VerdictEngine updates this later)
            rel = Relationship.SUPPORTS if relevance_score >= 0.5 else Relationship.CONTEXT_MISMATCH

            published_date = source.published_at.date() if source.published_at else None

            item = EvidenceItem(
                id=chunk.id,
                title=source.title,
                publisher=source.publisher,
                published_at=published_date,
                url=source.url,
                excerpt=chunk.text,
                relationship=rel,
                relevance_score=relevance_score,
            )
            evidence_items.append(item)

        return evidence_items

    except Exception as exc:
        logger.error("Vector search query failed: %s", exc)
        # In case of DB error during development, fallback gracefully
        return _mock_search(query_text, top_k)
    finally:
        if own_session:
            await session.close()


# ─── Mock Fallback ────────────────────────────────────────────────────────────

_MOCK_EVIDENCE: list[dict] = [
    {
        "id": UUID("00000000-0000-0000-0000-000000000001"),
        "title": "[DEMO] IMD Weather Bulletin: Heavy Rain in Chennai",
        "publisher": "National Meteorological Centre",
        "published_at": None,
        "url": "https://example.com/imd-bulletin-chennai",
        "excerpt": "Severe rainfall triggered localized waterlogging and flash floods across Chennai districts on Thursday.",
        "relationship": Relationship.SUPPORTS,
        "relevance_score": 0.94,
    },
    {
        "id": UUID("00000000-0000-0000-0000-000000000002"),
        "title": "[DEMO] Fact Check: 2015 Marina Beach Car Submersion Clip",
        "publisher": "National FactCheck Council",
        "published_at": None,
        "url": "https://example.com/factcheck-marina-cars",
        "excerpt": "Visuals being circulated showing submerged cars at Marina Beach are recycled archival clips from 2015.",
        "relationship": Relationship.CONTRADICTS,
        "relevance_score": 0.88,
    },
]


def _mock_search(query_text: str, top_k: int) -> list[EvidenceItem]:
    """Fallback when database is not connected."""
    return [EvidenceItem(**item) for item in _MOCK_EVIDENCE[:top_k]]
