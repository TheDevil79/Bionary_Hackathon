"""
EvidenceLens — Evidence Retriever Service.

Responsibility: given an atomic claim, search the evidence corpus and return
the most relevant EvidenceItems.

Current state: DEVELOPMENT MOCK
  Returns deterministic demo evidence so the pipeline can be tested
  without a live database or embedding model.

TODO (Phase 2):
  - Embed the claim text using sentence-transformers.
  - Run a pgvector cosine similarity search against evidence_chunks.
  - Join with sources to build EvidenceItem objects.
  - Support hybrid keyword + semantic search.
"""

from __future__ import annotations

import logging
from uuid import UUID

from app.schemas.claim import AtomicClaim, EvidenceItem, Relationship

logger = logging.getLogger(__name__)

# ─── Public interface ─────────────────────────────────────────────────────────

async def search(claim: AtomicClaim, top_k: int = 5) -> list[EvidenceItem]:
    """
    Retrieve evidence items relevant to the given atomic claim.

    Args:
        claim:  The atomic claim to search evidence for.
        top_k:  Maximum number of evidence items to return.

    Returns:
        A list of EvidenceItem objects ordered by relevance score (desc).

    Raises:
        RuntimeError: If the database or embedding service is unavailable.
    """
    logger.info("Searching evidence for claim '%s'", claim.id)

    # TODO: implement real pgvector search in Phase 2
    return _mock_search(claim, top_k)


# ─── Mock (development only) ──────────────────────────────────────────────────

_MOCK_EVIDENCE: list[dict] = [
    {
        "id": UUID("00000000-0000-0000-0000-000000000001"),
        "title": "[DEMO] Example Supporting Article",
        "publisher": "Demo News Network",
        "published_at": None,
        "url": "https://example.com/demo-article-1",
        "excerpt": "⚠️ DEMO DATA — This evidence item is synthetic and does not represent real reporting.",
        "relationship": Relationship.SUPPORTS,
        "relevance_score": 0.91,
    },
    {
        "id": UUID("00000000-0000-0000-0000-000000000002"),
        "title": "[DEMO] Example Contradicting Source",
        "publisher": "Demo Fact-Check",
        "published_at": None,
        "url": "https://example.com/demo-article-2",
        "excerpt": "⚠️ DEMO DATA — This evidence item is synthetic and does not represent real reporting.",
        "relationship": Relationship.CONTRADICTS,
        "relevance_score": 0.74,
    },
]


def _mock_search(claim: AtomicClaim, top_k: int) -> list[EvidenceItem]:
    """
    ⚠️  DEVELOPMENT MOCK — not real retrieval output.
    Returns static demo evidence items.
    Replace with pgvector similarity search in Phase 2.
    """
    return [EvidenceItem(**item) for item in _MOCK_EVIDENCE[:top_k]]
